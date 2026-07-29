"""Investor aggregates service for Etapa 3 — "que se venda".

Returns read-only aggregated data without PII.
Investor sees only totals, no individual debtor data.
"""

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import Date, func, select
from sqlalchemy.orm import Session

from src.models import Credito, Jornada, MovimientoCaja, Pago, Renovacion, Ruta, Usuario


def get_inversionista_summary(
    db: Session,
    negocio_id: UUID,
    today: date | None = None,
) -> dict:
    """Get investor summary for a negocio — no PII.

    Returns aggregated portfolio data, today's collection status,
    and active staff counts.
    """
    if today is None:
        today = date.today()

    # Active credits
    result = db.execute(
        select(
            func.count(Credito.id).filter(
                Credito.negocio_id == negocio_id,
                Credito.estado == "ACTIVO",
            )
        )
    )
    total_creditos_activos = result.scalar() or 0

    # Net portfolio (sum of remaining balances)
    result = db.execute(
        select(func.sum(Credito.monto)).filter(
            Credito.negocio_id == negocio_id,
            Credito.estado == "ACTIVO",
        )
    )
    cartera_neta = result.scalar() or 0

    # Today's collection
    result = db.execute(
        select(func.sum(Pago.monto)).filter(
            Pago.negocio_id == negocio_id,
            Pago.tipo == "PAYMENT",
            func.cast(Pago.recibido_el_servidor, Date) == today,
        )
    )
    recaudo_hoy = result.scalar() or 0

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
