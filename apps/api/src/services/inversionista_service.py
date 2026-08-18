"""Inversionista aggregates service — read-model financiero read-only (W9).

Autoridad UNICA de los montos: composición server-side de las autoridades
canónicas W6/W7 (NO duplica fórmulas):

- cobranza_service.resumen_cobranza: cartera viva, vencido, pct, mora,
  promesas, aging_distribution (autoridad W6).
- reportes_service._recaudo_en_periodo / _gastos_en_periodo: flujo del día
  (autoridad W7).
- reportes_service.recaudo_diario: tendencia 7d (autoridad W7).
- reportes_service.rutas_reporte: exposición por ruta (autoridad W7).
- Conteos operativos directos (Credito ACTIVO, Usuario COBRADOR activo,
  Ruta activa, Jornada cerrada hoy) — NO son cálculo financiero.

Business Date: America/Bogota (today_bogota), nunca date.today() ni UTC.

W9 elimina la fórmula legacy que calculaba cartera_neta desde
Credito.monto - Pago y recaudo_hoy directo de Pago: ahora cartera y
recaudo salen de las mismas autoridades que W6/W7/W8 (una sola fuente de
verdad para cartera y recaudo en toda la web).
"""

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models import Credito, Jornada, Ruta, Usuario
from src.services.cobranza_service import resumen_cobranza
from src.services.hoja_viva_service import today_bogota
from src.services.reportes_service import (
    _gastos_en_periodo,
    _recaudo_en_periodo,
    recaudo_diario,
    rutas_reporte,
)

JORNADA_CERRADA_ESTADOS = ("CLOSED_LOCAL_PENDING_SYNC", "CLOSED_SYNCED")


def _conteos_operativos(db: Session, negocio_id: UUID, rd: date) -> dict:
    """Conteos operativos del negocio (no financiero)."""
    creditos_activos = (
        db.query(func.count(Credito.id))
        .filter(Credito.negocio_id == negocio_id, Credito.estado == "ACTIVO")
        .scalar()
        or 0
    )
    cobradores_activos = (
        db.query(func.count(Usuario.id))
        .filter(Usuario.negocio_id == negocio_id, Usuario.rol == "COBRADOR", Usuario.activo == 1)
        .scalar()
        or 0
    )
    rutas_activas = (
        db.query(func.count(Ruta.id))
        .filter(Ruta.negocio_id == negocio_id, Ruta.activa == 1)
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
        "total_creditos_activos": int(creditos_activos),
        "cobradores_activos": int(cobradores_activos),
        "rutas_activas": int(rutas_activas),
        "jornada_cerrada_hoy": jornadas_cerradas > 0,
    }


def _exposicion_rutas(db: Session, negocio_id: UUID, role: str) -> list[dict]:
    """Exposición por ruta (autoridad W7 rutas_reporte) — PII minimizada.

    Solo ruta_nombre + agregados financieros (sin ruta_id ni cobrador).
    """
    rutas = rutas_reporte(db, negocio_id, role, periodo="hoy")["rutas"]
    return [
        {
            "ruta_nombre": r["ruta_nombre"],
            "cartera": int(r["cartera"]),
            "vencido": int(r["vencido"]),
            "creditos": int(r["creditos"]),
        }
        for r in rutas
    ]


def get_inversionista_summary(
    db: Session,
    negocio_id: UUID,
    today: date | None = None,
    role: str = "INVERSIONISTA",
) -> dict:
    """Read-model financiero del inversionista — no PII, read-only.

    Composición de autoridades W6/W7 (una sola fuente de verdad para
    cartera y recaudo). Campos legacy del `portfolio` se conservan por
    compatibilidad y ahora salen de la misma autoridad canónica.
    """
    rd = today or today_bogota()
    fin = rd + timedelta(days=1)

    # Autoridad W6: cartera, vencido, pct, mora, promesas, aging.
    cobranza = resumen_cobranza(db, negocio_id, role, route_id=None, report_date=rd)
    cartera_viva = int(cobranza["total_cartera"])
    cartera_vencida = int(cobranza["total_vencido"])
    pct_vencido = float(cobranza["pct_vencido"])

    # Autoridad W7: flujo del día (recaudo neto + gastos).
    recaudo_hoy = _recaudo_en_periodo(db, negocio_id, rd, fin)
    gastos_hoy = _gastos_en_periodo(db, negocio_id, rd, fin)
    neto_hoy = recaudo_hoy - gastos_hoy

    # Autoridad W7: tendencia 7d.
    tendencia = recaudo_diario(db, negocio_id, role, periodo="7d", report_date=rd)

    # Autoridad W7: exposición por ruta (PII minimizada).
    rutas = _exposicion_rutas(db, negocio_id, role)

    # Conteos operativos (no financiero).
    operativo = _conteos_operativos(db, negocio_id, rd)

    return {
        "portfolio": {
            # Campos legacy (compatibilidad) — ahora de la autoridad canónica W6.
            "total_creditos_activos": operativo["total_creditos_activos"],
            "cartera_neta": cartera_viva,
            "recaudo_hoy": int(recaudo_hoy),
            "jornada_cerrada_hoy": operativo["jornada_cerrada_hoy"],
            "cobradores_activos": operativo["cobradores_activos"],
            "rutas_activas": operativo["rutas_activas"],
            # Campos W9 (aditivos).
            "cartera_viva": cartera_viva,
            "cartera_vencida": cartera_vencida,
            "pct_vencido": pct_vencido,
            "gastos_hoy": int(gastos_hoy),
            "neto_hoy": int(neto_hoy),
        },
        "riesgo": {
            "clientes_en_mora": int(cobranza["clientes_en_mora"]),
            "promesas_activas": int(cobranza["promesas_activas"]),
            "promesas_incumplidas": int(cobranza["promesas_incumplidas"]),
            "aging_distribution": cobranza["aging_distribution"],
        },
        "tendencia_7d": {
            "serie": tendencia["serie"],
            "total_recaudo": int(tendencia["total_recaudo"]),
            "total_reversal": int(tendencia["total_reversal"]),
            "total_neto": int(tendencia["total_neto"]),
        },
        "rutas": rutas,
        # Rellenados por la route (negocio).
        "negocio_nombre": "negocio",
        "plan": "basic",
        "moneda": "COP",
        "zona_horaria": "America/Bogota",
        "fecha": rd.isoformat(),
    }
