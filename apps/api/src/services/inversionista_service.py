"""Investor aggregates service for Etapa 3 — "que se venda".

Returns read-only aggregated data without PII.
Investor sees only totals, no individual debtor data.
"""

from datetime import date
from uuid import UUID

from sqlalchemy import case as sa_case
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models import Credito, Jornada, Pago, Ruta, Usuario


def get_inversionista_summary(
    db: Session,
    negocio_id: UUID,
    today: date | None = None,
) -> dict:
    """Get investor summary for a negocio — no PII.

    Returns aggregated portfolio data, today's collection status,
    and active staff counts.

    cartera_neta = sum of (monto - pagos + reversales) for active credits
    recaudo_hoy = sum(PAYMENT) - sum(REVERSAL) for today
    """
    if today is None:
        today = date.today()

    # Active credits count
    result = db.execute(
        select(
            func.count(Credito.id).filter(
                Credito.negocio_id == negocio_id,
                Credito.estado == "ACTIVO",
            )
        )
    )
    total_creditos_activos = result.scalar() or 0

   # Net portfolio = sum of (monto - net_payments) for active credits
    # net_payments = sum(PAYMENT) - sum(REVERSAL) per credito
    # We compute: sum(credito.monto) - sum(all payment net amounts)
    # Subquery: net payment per credito
    net_payment_subq = (
        select(
            Pago.credito_id.label("credito_id"),
            func.coalesce(
                func.sum(
                    sa_case(
                        (Pago.tipo == "REVERSAL", -Pago.monto),
                        (Pago.tipo == "PAYMENT", Pago.monto),
                        else_=0,
                    )
                ),
                0,
            ).label("net_amount"),
        )
        .filter(
            Pago.negocio_id == negocio_id,
        )
        .group_by(Pago.credito_id)
        .subquery()
    )

 # Portfolio = sum(credito.monto) - sum(net_payments for active credits)
    # net_payments per credito = sum(PAYMENT) - sum(REVERSAL)
    result = db.execute(
        select(
            func.sum(Credito.monto)
            - func.coalesce(net_payment_subq.c.net_amount, 0)
        )
        .select_from(Credito)
        .join(
            net_payment_subq,
            net_payment_subq.c.credito_id == Credito.id,
            isouter=True,
        )
        .filter(
            Credito.negocio_id == negocio_id,
            Credito.estado == "ACTIVO",
        )
    )
    cartera_neta_raw = result.scalar()
    cartera_neta = cartera_neta_raw if cartera_neta_raw is not None else 0

# Today's collection = sum(PAYMENT) - sum(REVERSAL) for today
    result_payments = db.execute(
        select(func.coalesce(func.sum(Pago.monto), 0))
        .select_from(Pago)
        .filter(
            Pago.negocio_id == negocio_id,
            Pago.tipo == 'PAYMENT',
            func.strftime('%Y-%m-%d', Pago.recibido_el_servidor) == today.isoformat(),
        )
    )
    total_payments = result_payments.scalar() or 0

    result_reversals = db.execute(
        select(func.coalesce(func.sum(Pago.monto), 0))
        .select_from(Pago)
        .filter(
            Pago.negocio_id == negocio_id,
            Pago.tipo == 'REVERSAL',
            func.strftime('%Y-%m-%d', Pago.recibido_el_servidor) == today.isoformat(),
        )
    )
    total_reversals = result_reversals.scalar() or 0
    recaudo_hoy = total_payments - total_reversals

    # Today's jornada status
    result = db.execute(
        select(func.count(Jornada.id)).filter(
            Jornada.negocio_id == negocio_id,
            Jornada.fecha == today,
            Jornada.estado.in_(["CLOSED_LOCAL_PENDING_SYNC", "CLOSED_SYNCED"]),
        )
    )
    jornadas_cerradas = result.scalar() or 0

    # Active cobradores
    result = db.execute(
        select(func.count(Usuario.id)).filter(
            Usuario.negocio_id == negocio_id,
            Usuario.rol == "COBRADOR",
            Usuario.activo == 1,
        )
    )
    cobradores_activos = result.scalar() or 0

    # Active routes
    result = db.execute(
        select(func.count(Ruta.id)).filter(
            Ruta.negocio_id == negocio_id,
            Ruta.activa == 1,
        )
    )
    rutas_activas = result.scalar() or 0

    return {
        "portfolio": {
            "total_creditos_activos": total_creditos_activos,
            "cartera_neta": cartera_neta,
            "recaudo_hoy": recaudo_hoy,
            "jornada_cerrada_hoy": jornadas_cerradas > 0,
            "cobradores_activos": cobradores_activos,
            "rutas_activas": rutas_activas,
        },
        "negocio_nombre": "negocio",  # filled by route
        "plan": "basic",  # filled by route
        "moneda": "COP",  # filled by route
        "zona_horaria": "America/Bogota",  # filled by route
    }
