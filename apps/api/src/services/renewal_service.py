"""Renewal service — full renewal transaction with RequestContext, validation,
PAYMENT registration for pago_efectivo, idempotency, and Bogotá timezone.
"""

from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.models import Credito, Pago, Renovacion
from src.services.calculation_service import calcular_renovacion
from src.services.payment_service import _normalize_uuid, _uuid_eq
from src.services.schedule_service import generate_schedule

BOGOTA_TZ = timezone(timedelta(hours=-5))


class RenewalError(Exception):
    """Domain error raised by renewal service."""


class RenewalNotFoundError(RenewalError):
    pass


class RenewalRouteError(RenewalError):
    """Renewal credit belongs to a different route."""


def renew_credito(
    db: Session,
    credito_id: UUID,
    pago_efectivo: int,
    nueva_cuota: int,
    nuevas_n_cuotas: int,
    nuevo_monto: int,
    nueva_periodicidad: str = "DIARIO",
    fecha_inicio: date | None = None,
    recargo_pct: int = 20,
    ctx: RequestContext | None = None,
    idempotency_key: str | None = None,
) -> dict:
    """Full renewal transaction with validation, PAYMENT registration, and idempotency.

    Args:
        db: SQLAlchemy session
        credito_id: UUID of the credit to renew
        pago_efectivo: Cash payment at renewal time
        nueva_cuota: New installment amount
        nuevas_n_cuotas: Number of new installments
        nuevo_monto: New principal amount
        nueva_periodicidad: Periodicity for new credit
        fecha_inicio: Start date (defaults to today in Bogotá timezone)
        recargo_pct: Surcharge percentage
        ctx: RequestContext from auth (optional, used for cobrador validation)
        idempotency_key: Client-provided idempotency key (optional)

    Returns:
        dict with renewal details

    Raises:
        RenewalNotFoundError: credit not found
        RenewalRouteError: cobrador cannot access credit's route
    """
    credito_id = _normalize_uuid(credito_id)

    old = db.query(Credito).filter(_uuid_eq(Credito.id, credito_id)).first()
    if not old:
        raise RenewalNotFoundError("Crédito no encontrado")

    # Validate cobrador route access if ctx provided
    if ctx and ctx.is_cobrador() and old.ruta_id != ctx.route_id:
        raise RenewalRouteError("El crédito no pertenece a tu ruta")

    # Net saldo from payments
    pagos = (
        db.query(Pago)
        .filter(_uuid_eq(Pago.credito_id, old.id))
        .all()
    )
    total_pagado = sum(
        p.monto for p in pagos if p.tipo == "PAYMENT"
    ) - sum(
        p.monto for p in pagos if p.tipo == "REVERSAL"
    )
    saldo_anterior = old.total - total_pagado

    calc = calcular_renovacion(
        saldo_anterior=saldo_anterior,
        pago_efectivo=pago_efectivo,
        monto_nuevo=nuevo_monto,
        recargo_pct=recargo_pct,
    )

    nuevo_total = nueva_cuota * nuevas_n_cuotas

    # Use Bogotá timezone for fecha_inicio
    if fecha_inicio is None:
        fecha_inicio = datetime.now(BOGOTA_TZ).date()

    # Create new credito
    new = Credito(
        id=uuid4(),
        negocio_id=old.negocio_id,
        cliente_id=old.cliente_id,
        ruta_id=old.ruta_id,
        origination_type="RENEWAL",
        cuota=nueva_cuota,
        n_cuotas=nuevas_n_cuotas,
        monto=nuevo_monto,
        total=nuevo_total,
        periodicidad=nueva_periodicidad,
        fecha_inicio=fecha_inicio,
        estado="ACTIVO",
        credito_anterior_id=old.id,
    )
    db.add(new)
    db.flush()

    # Mark old as RENFINANCIADO
    old.estado = "REFINANCIADO"

    # Register PAYMENT when pago_efectivo > 0
    if pago_efectivo > 0:
        pay_key = idempotency_key or f"renew-pay-{old.id!s}"
        pago_efectivo_row = Pago(
            id=uuid4(),
            negocio_id=old.negocio_id,
            credito_id=old.id,
            tipo="PAYMENT",
            monto=pago_efectivo,
            cobrador_id=ctx.user_id if ctx else None,
            dispositivo_id=ctx.device_id if ctx else None,
            registrado_el_dispositivo=datetime.now(BOGOTA_TZ) if ctx else None,
            clave_idempotencia=pay_key,
            nota="Pago de renovación",
        )
        db.add(pago_efectivo_row)

    # Register renewal event
    ren = Renovacion(
        id=uuid4(),
        negocio_id=old.negocio_id,
        credito_viejo_id=old.id,
        credito_nuevo_id=new.id,
        saldo_anterior=calc["saldo_anterior"],
        pago_efectivo=calc["pago_efectivo"],
        saldo_refinanciado=calc["saldo_refinanciado"],
        monto_nuevo=calc["monto_nuevo"],
        dinero_nuevo_entregado=calc["dinero_nuevo_entregado"],
        creado_por=ctx.user_id if ctx else None,
    )
    db.add(ren)

    # Generate schedule for new credito
    cuotas = generate_schedule(db, new)

    db.flush()
    return {
        "credito_viejo_id": old.id,
        "credito_nuevo_id": new.id,
        "renovacion": calc,
        "cuotas_generadas": len(cuotas),
        "total_contractual": nuevo_total,
    }
