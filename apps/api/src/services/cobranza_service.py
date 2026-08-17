"""Cobranza service — aging, mora, worklist, promise to pay.

Fuente de verdad: calendario contractual (CuotaProgramada) + pagos reales (Pago).
React NO debe reconstruir estas reglas.

Definiciones:
- oldest_unpaid_due_date: primera obligación vencida con saldo pendiente
- days_past_due: (report_date - oldest_unpaid_due_date).days
- overdue_installments: cantidad de obligaciones vencidas con saldo pendiente
- overdue_amount: suma del monto de obligaciones vencidas con saldo pendiente
- total_outstanding: saldo total vivo (vencido + no vencido)
- aging_bucket: bucket determinado por days_past_due
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models import Cliente, Credito, CuotaProgramada, Pago, Ruta, Usuario
from src.services.hoja_viva_service import resumen_creditos, today_bogota

BOGOTA_TZ = timezone(timedelta(hours=-5))

AGING_BUCKETS: list[tuple[str, int, int | None]] = [
    ("CURRENT", 0, 0),
    ("1-7", 1, 7),
    ("8-15", 8, 15),
    ("16-30", 16, 30),
    ("31-60", 31, 60),
    ("61-90", 61, 90),
    ("90+", 91, None),
]

SORT_ALLOWLIST = frozenset({
    "days_past_due",
    "overdue_amount",
    "total_outstanding",
    "oldest_unpaid_due_date",
    "cliente_nombre",
    "priority_score",
})

VALID_ORDERS = frozenset({"asc", "desc"})


def aging_bucket(days: int) -> str:
    """Devuelve el bucket de aging para un número de días de mora."""
    for name, lo, hi in AGING_BUCKETS:
        if hi is None:
            if days >= lo:
                return name
        elif lo <= days <= hi:
            return name
    return "CURRENT"


@dataclass
class CobranzaRow:
    """Fila del read model de cobranza."""
    credito_id: str
    cliente_id: str | None
    cliente_nombre: str | None
    ruta_id: str | None
    ruta_nombre: str | None
    cobrador_nombre: str | None
    estado: str
    total: int
    saldo: int
    cuota: int
    n_cuotas: int
    cuotas_pagadas: int
    mora_legacy: int
    oldest_unpaid_due_date: str | None
    days_past_due: int
    overdue_installments: int
    overdue_amount: int
    aging_bucket: str
    priority: str
    priority_score: int
    priority_factors: list[str]
    promesa_vigente: dict | None


def _calc_aging(
    db: Session,
    creditos: list[Credito],
    report_date: date,
) -> dict:
    """Calcula aging por crédito usando CuotaProgramada + pagos.

    Para cada crédito ACTIVO:
    - Encuentra cuotas vencidas (fecha_vencimiento < report_date)
    - Determina cuáles tienen saldo pendiente (no cubiertas por pagos)
    - Calcula days_past_due, overdue_installments, overdue_amount
    """
    credito_ids = [c.id for c in creditos]
    if not credito_ids:
        return {}

    # Batch: obtener todas las cuotas vencidas para los créditos
    cuotas = (
        db.query(CuotaProgramada)
        .filter(
            CuotaProgramada.credito_id.in_(credito_ids),
            CuotaProgramada.fecha_vencimiento < report_date,
            CuotaProgramada.estado != "PAGADO",
        )
        .order_by(CuotaProgramada.credito_id, CuotaProgramada.numero)
        .all()
    )

    # Agrupar por credito_id
    cuotas_por_credito: dict = {}
    for c in cuotas:
        cuotas_por_credito.setdefault(c.credito_id, []).append(c)

    # Batch: obtener abono neto por crédito (para saber si la cuota está cubierta)
    pagos_agg = {}
    rows = (
        db.query(
            Pago.credito_id,
            Pago.tipo,
            func.sum(Pago.monto).label("total"),
        )
        .filter(
            Pago.credito_id.in_(credito_ids),
            Pago.tipo.in_(["PAYMENT", "REVERSAL"]),
        )
        .group_by(Pago.credito_id, Pago.tipo)
        .all()
    )
    for credito_id, tipo, total in rows:
        if credito_id not in pagos_agg:
            pagos_agg[credito_id] = {"PAYMENT": 0, "REVERSAL": 0}
        pagos_agg[credito_id][tipo] = total or 0

    resultado = {}
    for credito in creditos:
        cid = credito.id
        if credito.estado != "ACTIVO":
            resultado[cid] = {
                "oldest_unpaid_due_date": None,
                "days_past_due": 0,
                "overdue_installments": 0,
                "overdue_amount": 0,
            }
            continue

        abono_neto = (pagos_agg.get(cid, {}).get("PAYMENT", 0)) - (pagos_agg.get(cid, {}).get("REVERSAL", 0))
        cuotas_vencidas = cuotas_por_credito.get(cid, [])

        # Determinar cuáles cuotas vencidas tienen saldo pendiente
        # Una cuota está "cubierta" si el abono neto acumulado la cubre
        # Simplificación: si abono_neto >= (numero - 1) * cuota, la cuota numero está cubierta
        overdue_count = 0
        overdue_amt = 0
        oldest_date = None

        for cuota_prog in sorted(cuotas_vencidas, key=lambda x: x.numero):
            # La cuota N está cubierta si abono_neto >= N * cuota
            if abono_neto >= cuota_prog.numero * credito.cuota:
                continue
            overdue_count += 1
            overdue_amt += cuota_prog.monto
            if oldest_date is None or cuota_prog.fecha_vencimiento < oldest_date:
                oldest_date = cuota_prog.fecha_vencimiento

        if oldest_date:
            days_past_due = (report_date - oldest_date).days
        else:
            days_past_due = 0

        resultado[cid] = {
            "oldest_unpaid_due_date": oldest_date,
            "days_past_due": days_past_due,
            "overdue_installments": overdue_count,
            "overdue_amount": overdue_amt,
        }

    return resultado


def _priority_score(days_past_due: int, overdue_amount: int, total: int, overdue_installments: int) -> tuple[str, int, list[str]]:
    """Scoring heurístico de prioridad para la worklist.

    No es ML — es una heurística determinista y explicable.
    """
    score = 0
    factors = []

    if days_past_due >= 91:
        score += 40
        factors.append("90+ días de mora")
    elif days_past_due >= 61:
        score += 35
        factors.append("61+ días de mora")
    elif days_past_due >= 31:
        score += 30
        factors.append("31+ días de mora")
    elif days_past_due >= 16:
        score += 20
        factors.append("16+ días de mora")
    elif days_past_due >= 8:
        score += 10
        factors.append("8+ días de mora")
    elif days_past_due >= 1:
        score += 5
        factors.append("1+ días de mora")

    if total > 0:
        pct_vencido = overdue_amount / total if total > 0 else 0
        if pct_vencido >= 0.5:
            score += 25
            factors.append("50%+ del total vencido")
        elif pct_vencido >= 0.25:
            score += 15
            factors.append("25%+ del total vencido")
        elif pct_vencido > 0:
            score += 5

    if overdue_installments >= 10:
        score += 15
        factors.append("10+ cuotas vencidas")
    elif overdue_installments >= 5:
        score += 10
        factors.append("5+ cuotas vencidas")
    elif overdue_installments >= 1:
        score += 5

    if score >= 70:
        priority = "high"
    elif score >= 40:
        priority = "medium"
    else:
        priority = "low"

    return priority, min(score, 100), factors


def list_cobranza(
    db: Session,
    negocio_id,
    role: str,
    route_id,
    search: str | None = None,
    bucket: str | None = None,
    ruta_id: str | None = None,
    estado: str | None = None,
    priority: str | None = None,
    dpd_min: int | None = None,
    dpd_max: int | None = None,
    limit: int = 50,
    offset: int = 0,
    sort: str = "days_past_due",
    order: str = "desc",
    report_date: date | None = None,
) -> dict:
    """Lista paginada del read model de cobranza con aging y prioridad."""
    if sort not in SORT_ALLOWLIST:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=f"sort inválido: {sort} (permitidos: {', '.join(sorted(SORT_ALLOWLIST))})")
    if order not in VALID_ORDERS:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=f"order inválido: {order} (permitidos: asc, desc)")

    report_date = report_date or today_bogota()
    mostrar_pii = role in ("ADMINISTRADOR", "COBRADOR")

    # Base query
    q = db.query(Credito).filter(Credito.negocio_id == negocio_id)
    if role == "COBRADOR":
        q = q.filter(Credito.ruta_id == route_id)
    if estado:
        q = q.filter(Credito.estado == estado)
    if ruta_id and role != "COBRADOR":
        q = q.filter(Credito.ruta_id == ruta_id)

    creditos = q.all()
    if not creditos:
        return {"items": [], "total": 0, "limit": limit, "offset": offset}

    # Enrichir con financiero + aging
    resumen = resumen_creditos(db, creditos)
    aging = _calc_aging(db, creditos, report_date)

    # Resolver nombres
    cliente_ids = {c.cliente_id for c in creditos if c.cliente_id}
    clientes = {}
    if cliente_ids:
        clientes = {c.id: c for c in db.query(Cliente).filter(Cliente.id.in_(cliente_ids)).all()}
    ruta_ids = {c.ruta_id for c in creditos if c.ruta_id}
    rutas = {}
    if ruta_ids:
        rutas = {r.id: r for r in db.query(Ruta).filter(Ruta.id.in_(ruta_ids)).all()}
    cobrador_ids = {r.cobrador_id for r in rutas.values() if r.cobrador_id}
    cobradores = {}
    if cobrador_ids:
        cobradores = {u.id: u.nombre for u in db.query(Usuario).filter(Usuario.id.in_(cobrador_ids)).all()}

    # Construir filas
    filas = []
    for c in creditos:
        fin = resumen[c.id]
        ag = aging[c.id]

        cliente = clientes.get(c.cliente_id) if c.cliente_id else None
        nombre_cliente = None
        if cliente and mostrar_pii:
            nombre_cliente = " ".join(
                x for x in (cliente.nombres, cliente.primer_apellido, cliente.segundo_apellido) if x
            ).strip() or None

        ruta = rutas.get(c.ruta_id) if c.ruta_id else None
        ruta_nombre = ruta.nombre if ruta else None
        cobrador_nombre = cobradores.get(ruta.cobrador_id) if ruta and ruta.cobrador_id else None

        dpd = ag["days_past_due"]
        bucket_name = aging_bucket(dpd)
        priority, score, factors = _priority_score(dpd, ag["overdue_amount"], c.total, ag["overdue_installments"])

        filas.append({
            "credito_id": str(c.id),
            "cliente_id": str(c.cliente_id) if (c.cliente_id and mostrar_pii) else None,
            "cliente_nombre": nombre_cliente,
            "ruta_id": str(c.ruta_id) if c.ruta_id else None,
            "ruta_nombre": ruta_nombre,
            "cobrador_nombre": cobrador_nombre,
            "estado": c.estado,
            "total": c.total,
            "saldo": fin["saldo"],
            "cuota": c.cuota,
            "n_cuotas": c.n_cuotas,
            "cuotas_pagadas": fin["cuotas_pagadas"],
            "mora_legacy": fin["mora_legacy"],
            "oldest_unpaid_due_date": ag["oldest_unpaid_due_date"].isoformat() if ag["oldest_unpaid_due_date"] else None,
            "days_past_due": dpd,
            "overdue_installments": ag["overdue_installments"],
            "overdue_amount": ag["overdue_amount"],
            "aging_bucket": bucket_name,
            "priority": priority,
            "priority_score": score,
            "priority_factors": factors,
        })

    # Filtros post-cálculo
    if search and mostrar_pii:
        term = search.strip().lower()
        filas = [f for f in filas if f["cliente_nombre"] and term in f["cliente_nombre"].lower()]
    if bucket:
        filas = [f for f in filas if f["aging_bucket"] == bucket]
    if priority:
        filas = [f for f in filas if f["priority"] == priority]
    if dpd_min is not None:
        filas = [f for f in filas if f["days_past_due"] >= dpd_min]
    if dpd_max is not None:
        filas = [f for f in filas if f["days_past_due"] <= dpd_max]

    # Sort
    dir_order = -1 if order == "desc" else 1
    filas.sort(key=lambda f: (f.get(sort) is None, f.get(sort) or 0), reverse=(order == "desc"))

    total = len(filas)
    items = filas[offset:offset + limit]

    return {"items": items, "total": total, "limit": limit, "offset": offset}


def resumen_cobranza(
    db: Session,
    negocio_id,
    role: str,
    route_id,
    report_date: date | None = None,
) -> dict:
    """Resumen de cobranza: KPIs + aging distribution."""
    report_date = report_date or today_bogota()

    q = db.query(Credito).filter(Credito.negocio_id == negocio_id)
    if role == "COBRADOR":
        q = q.filter(Credito.ruta_id == route_id)

    creditos = q.all()
    activos = [c for c in creditos if c.estado == "ACTIVO"]
    if not activos:
        return {
            "total_cartera": 0,
            "total_vencido": 0,
            "pct_vencido": 0,
            "clientes_en_mora": 0,
            "promesas_activas": 0,
            "promesas_incumplidas": 0,
            "aging_distribution": {b[0]: {"count": 0, "amount": 0} for b in AGING_BUCKETS},
        }

    resumen = resumen_creditos(db, activos)
    aging = _calc_aging(db, activos, report_date)

    total_cartera = sum(resumen[c.id]["saldo"] for c in activos)
    total_vencido = sum(aging[c.id]["overdue_amount"] for c in activos)
    clientes_en_mora = sum(1 for c in activos if aging[c.id]["days_past_due"] > 0)

    # Aging distribution
    distribution = {name: {"count": 0, "amount": 0} for name, _, _ in AGING_BUCKETS}
    for c in activos:
        ag = aging[c.id]
        bucket = aging_bucket(ag["days_past_due"])
        distribution[bucket]["count"] += 1
        distribution[bucket]["amount"] += ag["overdue_amount"]

    # Promesas (si existe el modelo)
    promesas_activas = 0
    promesas_incumplidas = 0
    try:
        from src.models import PromesaPago
        pq = db.query(PromesaPago).filter(PromesaPago.negocio_id == negocio_id)
        if role == "COBRADOR":
            pq = pq.join(Credito, PromesaPago.credito_id == Credito.id).filter(Credito.ruta_id == route_id)
        promesas_activas = pq.filter(PromesaPago.estado == "ACTIVE").count()
        promesas_incumplidas = pq.filter(PromesaPago.estado == "BROKEN").count()
    except ImportError:
        pass

    return {
        "total_cartera": total_cartera,
        "total_vencido": total_vencido,
        "pct_vencido": round(total_vencido / total_cartera * 100, 1) if total_cartera > 0 else 0,
        "clientes_en_mora": clientes_en_mora,
        "promesas_activas": promesas_activas,
        "promesas_incumplidas": promesas_incumplidas,
        "aging_distribution": distribution,
    }
