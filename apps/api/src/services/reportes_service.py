"""Reportes Premium service — read-models financieros con periodo.

Reutiliza:
- hoja_viva_service: resumen_creditos, today_bogota, BOGOTA_TZ
- cobranza_service: _calc_aging, aging_bucket, AGING_BUCKETS
- Pago: recaudo (PAYMENT - REVERSAL)
- MovimientoCaja: gastos

NO duplica lógica financiera. Backend es única autoridad.
"""

from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models import Credito, CuotaProgramada, MovimientoCaja, Pago, Ruta
from src.services.cobranza_service import AGING_BUCKETS, _calc_aging, aging_bucket
from src.services.hoja_viva_service import BOGOTA_TZ, resumen_creditos, today_bogota

PERIODOS_VALIDOS = frozenset({"hoy", "7d", "30d", "custom"})


def _parse_periodo(
    periodo: str,
    fecha_inicio: str | None,
    fecha_fin: str | None,
    report_date: date | None = None,
) -> tuple[date, date]:
    """Resuelve el periodo a un rango [inicio, fin) en Colombia."""
    report_date = report_date or today_bogota()

    if periodo == "hoy":
        return report_date, report_date + timedelta(days=1)
    elif periodo == "7d":
        return report_date - timedelta(days=6), report_date + timedelta(days=1)
    elif periodo == "30d":
        return report_date - timedelta(days=29), report_date + timedelta(days=1)
    elif periodo == "custom":
        if not fecha_inicio or not fecha_fin:
            raise HTTPException(status_code=422, detail="custom requiere fecha_inicio y fecha_fin")
        try:
            ini = date.fromisoformat(fecha_inicio)
            fin = date.fromisoformat(fecha_fin)
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="fecha_inicio/fecha_fin deben ser ISO (YYYY-MM-DD)")
        if ini > fin:
            raise HTTPException(status_code=422, detail="fecha_inicio no puede ser mayor que fecha_fin")
        return ini, fin + timedelta(days=1)
    else:
        raise HTTPException(status_code=422, detail=f"periodo inválido: {periodo} (permitidos: hoy, 7d, 30d, custom)")


def _date_to_utc_range(d: date) -> tuple[datetime, datetime]:
    """Convierte una fecha Colombia a rango UTC [00:00, 24:00) para consultas."""
    inicio = datetime.combine(d, time.min, tzinfo=BOGOTA_TZ).astimezone(timezone.utc)
    fin = inicio + timedelta(days=1)
    return inicio, fin


def _recaudo_en_periodo(
    db: Session,
    negocio_id: UUID,
    inicio: date,
    fin: date,
) -> int:
    """Recaudo neto (PAYMENT - REVERSAL) en el periodo [inicio, fin)."""
    utc_inicio = datetime.combine(inicio, time.min, tzinfo=BOGOTA_TZ).astimezone(timezone.utc)
    utc_fin = datetime.combine(fin, time.min, tzinfo=BOGOTA_TZ).astimezone(timezone.utc)

    payments = db.query(func.coalesce(func.sum(Pago.monto), 0)).filter(
        Pago.negocio_id == negocio_id,
        Pago.tipo == "PAYMENT",
        Pago.recibido_el_servidor >= utc_inicio,
        Pago.recibido_el_servidor < utc_fin,
    ).scalar() or 0

    reversals = db.query(func.coalesce(func.sum(Pago.monto), 0)).filter(
        Pago.negocio_id == negocio_id,
        Pago.tipo == "REVERSAL",
        Pago.recibido_el_servidor >= utc_inicio,
        Pago.recibido_el_servidor < utc_fin,
    ).scalar() or 0

    return int(payments) - int(reversals)


def _gastos_en_periodo(
    db: Session,
    negocio_id: UUID,
    inicio: date,
    fin: date,
) -> int:
    """Gastos totales en el periodo [inicio, fin)."""
    utc_inicio = datetime.combine(inicio, time.min, tzinfo=BOGOTA_TZ).astimezone(timezone.utc)
    utc_fin = datetime.combine(fin, time.min, tzinfo=BOGOTA_TZ).astimezone(timezone.utc)

    total = db.query(func.coalesce(func.sum(MovimientoCaja.monto), 0)).filter(
        MovimientoCaja.negocio_id == negocio_id,
        MovimientoCaja.naturaleza == "GASTO",
        MovimientoCaja.creado_el >= utc_inicio,
        MovimientoCaja.creado_el < utc_fin,
    ).scalar() or 0

    return int(total)


def resumen_reporte(
    db: Session,
    negocio_id: UUID,
    role: str,
    periodo: str = "hoy",
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
    report_date: date | None = None,
) -> dict:
    """Resumen financiero del periodo."""
    rd = report_date or today_bogota()
    inicio, fin = _parse_periodo(periodo, fecha_inicio, fecha_fin, rd)

    creditos = db.query(Credito).filter(
        Credito.negocio_id == negocio_id,
        Credito.estado == "ACTIVO",
    ).all()

    if not creditos:
        return {
            "periodo": periodo,
            "fecha_inicio": inicio.isoformat(),
            "fecha_fin": (fin - timedelta(days=1)).isoformat(),
            "cartera_vigente": 0,
            "cartera_vencida": 0,
            "pct_vencido": 0,
            "recaudo_periodo": 0,
            "gastos_periodo": 0,
            "neto_periodo": 0,
        }

    resumen = resumen_creditos(db, creditos, rd)
    aging = _calc_aging(db, creditos, rd)

    cartera_vigente = sum(resumen[c.id]["saldo"] for c in creditos)
    cartera_vencida = sum(aging[c.id]["overdue_amount"] for c in creditos)
    pct_vencido = round((cartera_vencida / cartera_vigente * 100), 1) if cartera_vigente > 0 else 0

    recaudo = _recaudo_en_periodo(db, negocio_id, inicio, fin)
    gastos = _gastos_en_periodo(db, negocio_id, inicio, fin)
    neto = recaudo - gastos

    return {
        "periodo": periodo,
        "fecha_inicio": inicio.isoformat(),
        "fecha_fin": (fin - timedelta(days=1)).isoformat(),
        "cartera_vigente": cartera_vigente,
        "cartera_vencida": cartera_vencida,
        "pct_vencido": pct_vencido,
        "recaudo_periodo": recaudo,
        "gastos_periodo": gastos,
        "neto_periodo": neto,
    }


def recaudo_diario(
    db: Session,
    negocio_id: UUID,
    role: str,
    periodo: str = "7d",
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
    report_date: date | None = None,
) -> dict:
    """Serie diaria de recaudo (PAYMENT - REVERSAL) por día."""
    rd = report_date or today_bogota()
    inicio, fin = _parse_periodo(periodo, fecha_inicio, fecha_fin, rd)

    utc_inicio = datetime.combine(inicio, time.min, tzinfo=BOGOTA_TZ).astimezone(timezone.utc)
    utc_fin = datetime.combine(fin, time.min, tzinfo=BOGOTA_TZ).astimezone(timezone.utc)

    pagos = (
        db.query(
            func.date(Pago.recibido_el_servidor).label("dia"),
            Pago.tipo,
            func.sum(Pago.monto).label("total"),
        )
        .filter(
            Pago.negocio_id == negocio_id,
            Pago.tipo.in_(["PAYMENT", "REVERSAL"]),
            Pago.recibido_el_servidor >= utc_inicio,
            Pago.recibido_el_servidor < utc_fin,
        )
        .group_by(func.date(Pago.recibido_el_servidor), Pago.tipo)
        .all()
    )

    por_dia: dict[str, dict[str, int]] = {}
    for dia, tipo, total in pagos:
        d = str(dia)
        if d not in por_dia:
            por_dia[d] = {"PAYMENT": 0, "REVERSAL": 0}
        por_dia[d][tipo] = int(total or 0)

    serie = []
    d = inicio
    while d < fin:
        ds = d.isoformat()
        p = por_dia.get(ds, {"PAYMENT": 0, "REVERSAL": 0})
        serie.append({
            "fecha": ds,
            "recaudo": p["PAYMENT"],
            "reversal": p["REVERSAL"],
            "neto": p["PAYMENT"] - p["REVERSAL"],
        })
        d += timedelta(days=1)

    return {
        "periodo": periodo,
        "fecha_inicio": inicio.isoformat(),
        "fecha_fin": (fin - timedelta(days=1)).isoformat(),
        "serie": serie,
        "total_recaudo": sum(s["recaudo"] for s in serie),
        "total_reversal": sum(s["reversal"] for s in serie),
        "total_neto": sum(s["neto"] for s in serie),
    }


def aging_reporte(
    db: Session,
    negocio_id: UUID,
    role: str,
    report_date: date | None = None,
) -> dict:
    """Distribución de aging por bucket."""
    rd = report_date or today_bogota()

    creditos = db.query(Credito).filter(
        Credito.negocio_id == negocio_id,
        Credito.estado == "ACTIVO",
    ).all()

    if not creditos:
        return {
            "fecha": rd.isoformat(),
            "buckets": {name: {"count": 0, "amount": 0} for name, _, _ in AGING_BUCKETS},
        }

    aging = _calc_aging(db, creditos, rd)
    buckets = {name: {"count": 0, "amount": 0} for name, _, _ in AGING_BUCKETS}

    for c in creditos:
        ag = aging[c.id]
        bucket = aging_bucket(ag["days_past_due"])
        buckets[bucket]["count"] += 1
        buckets[bucket]["amount"] += ag["overdue_amount"]

    return {
        "fecha": rd.isoformat(),
        "buckets": buckets,
    }


def rutas_reporte(
    db: Session,
    negocio_id: UUID,
    role: str,
    periodo: str = "hoy",
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
    report_date: date | None = None,
) -> dict:
    """Rendimiento agregado por ruta."""
    rd = report_date or today_bogota()
    inicio, fin = _parse_periodo(periodo, fecha_inicio, fecha_fin, rd)

    creditos = db.query(Credito).filter(
        Credito.negocio_id == negocio_id,
        Credito.estado == "ACTIVO",
    ).all()

    if not creditos:
        return {"periodo": periodo, "rutas": []}

    resumen = resumen_creditos(db, creditos, rd)
    aging = _calc_aging(db, creditos, rd)

    rutas = db.query(Ruta).filter(Ruta.negocio_id == negocio_id, Ruta.activa == 1).all()
    ruta_ids = {r.id for r in rutas}

    por_ruta: dict[str, dict] = {}
    for r in rutas:
        por_ruta[str(r.id)] = {
            "ruta_id": str(r.id),
            "ruta_nombre": r.nombre,
            "cartera": 0,
            "vencido": 0,
            "creditos": 0,
        }

    for c in creditos:
        rid = str(c.ruta_id) if c.ruta_id else None
        if rid not in por_ruta:
            continue
        por_ruta[rid]["cartera"] += resumen[c.id]["saldo"]
        por_ruta[rid]["vencido"] += aging[c.id]["overdue_amount"]
        por_ruta[rid]["creditos"] += 1

    return {
        "periodo": periodo,
        "rutas": list(por_ruta.values()),
    }


def movimientos_reporte(
    db: Session,
    negocio_id: UUID,
    role: str,
    periodo: str = "hoy",
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
    report_date: date | None = None,
) -> dict:
    """Breakdown de gastos/movimientos por tipo y naturaleza."""
    rd = report_date or today_bogota()
    inicio, fin = _parse_periodo(periodo, fecha_inicio, fecha_fin, rd)

    utc_inicio = datetime.combine(inicio, time.min, tzinfo=BOGOTA_TZ).astimezone(timezone.utc)
    utc_fin = datetime.combine(fin, time.min, tzinfo=BOGOTA_TZ).astimezone(timezone.utc)

    mostrar_pii = role in ("ADMINISTRADOR", "COBRADOR")

    rows = (
        db.query(
            MovimientoCaja.tipo,
            MovimientoCaja.naturaleza,
            func.count(MovimientoCaja.id),
            func.sum(MovimientoCaja.monto),
        )
        .filter(
            MovimientoCaja.negocio_id == negocio_id,
            MovimientoCaja.creado_el >= utc_inicio,
            MovimientoCaja.creado_el < utc_fin,
        )
        .group_by(MovimientoCaja.tipo, MovimientoCaja.naturaleza)
        .all()
    )

    por_tipo = {}
    total_gastos = 0
    total_recibido = 0
    for tipo, naturaleza, count, total in rows:
        if tipo not in por_tipo:
            por_tipo[tipo] = {"tipo": tipo, "total": 0, "count": 0, "naturalezas": {}}
        por_tipo[tipo]["total"] += int(total or 0)
        por_tipo[tipo]["count"] += int(count or 0)
        por_tipo[tipo]["naturalezas"][naturaleza] = int(total or 0)
        if naturaleza == "GASTO":
            total_gastos += int(total or 0)
        elif naturaleza == "CUENTA_POR_COBRAR":
            total_recibido += int(total or 0)

    return {
        "periodo": periodo,
        "fecha_inicio": inicio.isoformat(),
        "fecha_fin": (fin - timedelta(days=1)).isoformat(),
        "total_gastos": total_gastos,
        "total_recibido": total_recibido,
        "por_tipo": list(por_tipo.values()),
    }
