"""Dashboard Ejecutivo service — read-model de decisión para ADMINISTRADOR (W8).

Composición server-side de autoridades existentes (NO duplica cálculos):
- cobranza_service.resumen_cobranza: cartera, vencido, pct, mora, promesas, aging
- reportes_service._recaudo_en_periodo / _gastos_en_periodo: flujo del día
- reportes_service.recaudo_diario: tendencia 7d
- reportes_service.rutas_reporte: concentración por ruta
- Conteos operativos directos (Ruta.activa, Usuario COBRADOR activo,
  Credito ACTIVO, Jornada cerrada hoy) — no son cálculo financiero.

Business Date: America/Bogota (today_bogota), nunca date.today() ni UTC.
"""

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models import Credito, Jornada, Negocio, Ruta, Usuario
from src.services.cobranza_service import resumen_cobranza
from src.services.hoja_viva_service import today_bogota
from src.services.reportes_service import (
    _gastos_en_periodo,
    _recaudo_en_periodo,
    recaudo_diario,
    rutas_reporte,
)

JORNADA_CERRADA_ESTADOS = ("CLOSED_LOCAL_PENDING_SYNC", "CLOSED_SYNCED")


def _contenidos_operativos(db: Session, negocio_id: UUID, rd: date) -> dict:
    """Conteos operativos del negocio (no financiero)."""
    rutas_activas = (
        db.query(func.count(Ruta.id))
        .filter(Ruta.negocio_id == negocio_id, Ruta.activa == 1)
        .scalar()
        or 0
    )
    cobradores_activos = (
        db.query(func.count(Usuario.id))
        .filter(Usuario.negocio_id == negocio_id, Usuario.rol == "COBRADOR", Usuario.activo == 1)
        .scalar()
        or 0
    )
    creditos_activos = (
        db.query(func.count(Credito.id))
        .filter(Credito.negocio_id == negocio_id, Credito.estado == "ACTIVO")
        .scalar()
        or 0
    )
    jornadas_cerradas = (
        db.query(func.count(Jornada.id))
        .filter(
            Jornada.negocio_id == negocio_id,
            Jornada.fecha == rd,
            Jornada.estado.in_(JORNADA_CERRADA_ESTADOS),
        )
        .scalar()
        or 0
    )
    return {
        "rutas_activas": int(rutas_activas),
        "cobradores_activos": int(cobradores_activos),
        "creditos_activos": int(creditos_activos),
        "jornada_cerrada_hoy": jornadas_cerradas > 0,
    }


def _derivar_alertas(hoy: dict, operativo: dict, riesgo: dict) -> list[dict]:
    """¿Qué requiere atención? Derivado server-side, sin PII."""
    alertas: list[dict] = []
    if not operativo["jornada_cerrada_hoy"]:
        alertas.append({
            "tipo": "JORNADA_ABIERTA",
            "mensaje": "Hay jornadas sin cerrar hoy",
            "severidad": "warning",
        })
    b90 = riesgo["aging_distribution"].get("90+", {"count": 0})
    if b90["count"] > 0:
        alertas.append({
            "tipo": "MORA_90+",
            "mensaje": f"{b90['count']} crédito(s) con más de 90 días de mora",
            "severidad": "critical",
        })
    if riesgo["promesas_incumplidas"] > 0:
        alertas.append({
            "tipo": "PROMESAS_INCUMPLIDAS",
            "mensaje": f"{riesgo['promesas_incumplidas']} promesa(s) incumplida(s)",
            "severidad": "warning",
        })
    if hoy["pct_vencido"] >= 20:
        alertas.append({
            "tipo": "PCT_VENCIDO_ALTO",
            "mensaje": f"{hoy['pct_vencido']}% de la cartera está vencida",
            "severidad": "critical",
        })
    if riesgo["clientes_en_mora"] > 0:
        alertas.append({
            "tipo": "CLIENTES_EN_MORA",
            "mensaje": f"{riesgo['clientes_en_mora']} cliente(s) en mora",
            "severidad": "info",
        })
    return alertas


def dashboard_ejecutivo(db: Session, negocio_id: UUID, role: str) -> dict:
    """Read-model ejecutivo: cómo está el negocio hoy + tendencia + riesgo."""
    rd = today_bogota()
    negocio = db.query(Negocio).filter(Negocio.id == negocio_id).first()

    cobranza = resumen_cobranza(db, negocio_id, role, route_id=None)

    inicio = rd
    fin = rd + timedelta(days=1)
    recaudo_hoy = _recaudo_en_periodo(db, negocio_id, inicio, fin)
    gastos_hoy = _gastos_en_periodo(db, negocio_id, inicio, fin)

    hoy = {
        "cartera_vigente": cobranza["total_cartera"],
        "cartera_vencida": cobranza["total_vencido"],
        "pct_vencido": cobranza["pct_vencido"],
        "recaudo_hoy": recaudo_hoy,
        "gastos_hoy": gastos_hoy,
        "neto_hoy": recaudo_hoy - gastos_hoy,
    }

    operativo = _contenidos_operativos(db, negocio_id, rd)
    riesgo = {
        "clientes_en_mora": cobranza["clientes_en_mora"],
        "promesas_activas": cobranza["promesas_activas"],
        "promesas_incumplidas": cobranza["promesas_incumplidas"],
        "aging_distribution": cobranza["aging_distribution"],
    }
    tendencia = recaudo_diario(db, negocio_id, role, periodo="7d")
    rutas = rutas_reporte(db, negocio_id, role, periodo="hoy")
    alertas = _derivar_alertas(hoy, operativo, riesgo)

    return {
        "fecha": rd.isoformat(),
        "negocio": {
            "nombre": negocio.nombre if negocio else "",
            "plan": negocio.plan if negocio else "basic",
            "moneda": negocio.moneda if negocio else "COP",
        },
        "hoy": hoy,
        "operativo": operativo,
        "riesgo": riesgo,
        "tendencia_7d": {
            "serie": tendencia["serie"],
            "total_recaudo": tendencia["total_recaudo"],
            "total_reversal": tendencia["total_reversal"],
            "total_neto": tendencia["total_neto"],
        },
        "rutas": rutas["rutas"],
        "alertas": alertas,
    }
