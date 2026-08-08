"""Payment service — complete business logic for payments, reversals, and queries.

Architecture: routes → services → models

The router receives schemas, gets RequestContext, calls the service, and converts
domain errors to HTTP responses. No financial rules live in the router.
"""

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.models import Credito, CuotaProgramada, Jornada, Negocio, Pago
from src.services.hoja_viva_service import today_bogota

BOGOTA_TZ = timezone(timedelta(hours=-5))


class PaymentError(Exception):
    """Domain error raised by payment service."""


class PaymentNotFoundError(PaymentError):
    pass


class PaymentRouteError(PaymentError):
    """Payment belongs to a different route than the cobrador's."""


class PaymentIdempotencyError(PaymentError):
    """Conflict: same idempotency key with different payload."""


class PaymentReversalError(PaymentError):
    """Cannot reverse a reversal or already reversed."""


def _uuid_eq(column, val):
    if isinstance(val, str):
        return column == UUID(val)
    return column == val


def get_net_paid(db: Session, credito_id: UUID) -> int:
    """Net paid = SUM(PAYMENT) - SUM(REVERSAL) for a credit."""
    pagos = (
        db.query(Pago)
        .filter(
            _uuid_eq(Pago.credito_id, credito_id),
            Pago.tipo.in_(["PAYMENT", "REVERSAL"]),
        )
        .all()
    )
    paid = sum(p.monto for p in pagos if p.tipo == "PAYMENT")
    reversed_ = sum(p.monto for p in pagos if p.tipo == "REVERSAL")
    return paid - reversed_


def _validate_credito_access(
    db: Session,
    credito: Credito,
    ctx: RequestContext,
) -> None:
    """Validate that the cobrador can access this credit."""
    if ctx.is_cobrador() and credito.ruta_id != ctx.route_id:
        raise PaymentRouteError("El crédito no pertenece a tu ruta")


def _validate_negocio(db: Session, negocio_id: UUID) -> Negocio:
    """Validate negocio exists."""
    negocio = db.query(Negocio).filter(_uuid_eq(Negocio.id, negocio_id)).first()
    if not negocio:
        raise PaymentError("Negocio no encontrado")
    return negocio


def _check_idempotency(
    db: Session,
    negocio_id: UUID,
    clave_idempotencia: str,
    credito_id: UUID,
    monto: int,
) -> Pago | None:
    """Check idempotency: same key with different payload -> 409."""
    existing = db.query(Pago).filter(
        _uuid_eq(Pago.negocio_id, negocio_id),
        Pago.clave_idempotencia == clave_idempotencia,
    ).first()
    if existing:
        if (
            str(existing.credito_id) != str(credito_id)
            or existing.monto != monto
        ):
            raise PaymentIdempotencyError(
                "Misma clave de idempotencia con payload diferente"
            )
        return existing
    return None


def _normalize_uuid(val) -> UUID:
    """Convert string or UUID to UUID."""
    if isinstance(val, UUID):
        return val
    return UUID(val)


def register_payment(
    db: Session,
    data: dict,
    ctx: RequestContext,
) -> Pago:
    """Register a PAYMENT with full validation.

    Args:
        db: SQLAlchemy session
        data: dict with credito_id, jornada_id, monto, clave_idempotencia, nota
        ctx: RequestContext from auth

    Returns:
        Pago object

    Raises:
        PaymentError: negocio not found
        PaymentRouteError: cobrador cannot access credit's route
        PaymentIdempotencyError: duplicate key with different payload
    """
    negocio_id = ctx.negocio_id
    credito_id = _normalize_uuid(data["credito_id"])
    monto = data["monto"]
    clave_idempotencia = data["clave_idempotencia"]

    # Validate negocio
    _validate_negocio(db, negocio_id)

    # Validate credit exists and belongs to negocio
    credito = db.query(Credito).filter(
        _uuid_eq(Credito.id, credito_id),
        _uuid_eq(Credito.negocio_id, negocio_id),
    ).first()
    if not credito:
        raise PaymentError("Crédito no encontrado")

    # Validate cobrador route access
    _validate_credito_access(db, credito, ctx)

    # Validate jornada belongs to negocio and same route as the credit
    jornada_id = data.get("jornada_id")
    if jornada_id:
        jornada = db.query(Jornada).filter(
            _uuid_eq(Jornada.id, jornada_id),
            _uuid_eq(Jornada.negocio_id, negocio_id),
        ).first()
        if not jornada:
            raise PaymentError("Jornada no encontrada")
        if jornada.ruta_id != credito.ruta_id:
            raise PaymentRouteError("El crédito y la jornada no pertenecen a la misma ruta")
        if ctx.is_cobrador() and not ctx.has_route(jornada.ruta_id):
            raise PaymentRouteError("La jornada no pertenece a tu ruta")

    # Check idempotency
    existing = _check_idempotency(
        db, negocio_id, clave_idempotencia, credito_id, monto
    )
    if existing:
        return existing

    # Create PAYMENT
    pago = Pago(
        id=__import__("uuid").uuid4(),
        negocio_id=negocio_id,
        credito_id=credito_id,
        jornada_id=jornada_id,
        tipo="PAYMENT",
        monto=monto,
        cobrador_id=ctx.user_id,
        dispositivo_id=ctx.device_id,
        registrado_el_dispositivo=datetime.now(BOGOTA_TZ),
        clave_idempotencia=clave_idempotencia,
        nota=data.get("nota"),
    )
    db.add(pago)
    db.flush()
    return pago


def get_payment(
    db: Session,
    pago_id: UUID,
    ctx: RequestContext,
) -> Pago:
    """Get a payment by ID with route isolation for cobrador.

    Args:
        db: SQLAlchemy session
        pago_id: UUID of the payment
        ctx: RequestContext from auth

    Returns:
        Pago object

    Raises:
        PaymentError: payment not found or cobrador cannot access route
    """
    query = db.query(Pago).filter(
        _uuid_eq(Pago.id, pago_id),
        _uuid_eq(Pago.negocio_id, ctx.negocio_id),
    )

    if ctx.is_cobrador():
        # Cobrador can only see payments from their route
        query = query.join(
            Credito, _uuid_eq(Pago.credito_id, Credito.id)
        ).filter(_uuid_eq(Credito.ruta_id, ctx.route_id))

    pago = query.first()
    if not pago:
        raise PaymentNotFoundError("Pago no encontrado")
    return pago


def list_payments(
    db: Session,
    ctx: RequestContext,
) -> list[Pago]:
    """List payments with route isolation for cobrador.

    Args:
        db: SQLAlchemy session
        ctx: RequestContext from auth

    Returns:
        List of Pago objects
    """
    query = db.query(Pago).filter(
        _uuid_eq(Pago.negocio_id, ctx.negocio_id)
    )

    if ctx.is_cobrador():
        # Cobrador only sees payments from their route
        query = query.join(
            Credito, _uuid_eq(Pago.credito_id, Credito.id)
        ).filter(_uuid_eq(Credito.ruta_id, ctx.route_id))

    return query.all()


def reverse_payment(
    db: Session,
    pago_id: UUID,
    data: dict,
    ctx: RequestContext,
) -> Pago:
    """Reverse a PAYMENT creating a REVERSAL row.

    Args:
        db: SQLAlchemy session
        pago_id: UUID of the original payment
        data: dict with motivo, clave_idempotencia (optional)
        ctx: RequestContext from auth

    Returns:
        Pago object (the REVERSAL)

    Raises:
        PaymentNotFoundError: original payment not found
        PaymentReversalError: not a PAYMENT type or already reversed
        PaymentIdempotencyError: duplicate reversal key
    """
    # Find original payment
    original = db.query(Pago).filter(
        _uuid_eq(Pago.id, pago_id),
        _uuid_eq(Pago.negocio_id, ctx.negocio_id),
    ).first()
    if not original:
        raise PaymentNotFoundError("Pago no encontrado")

    if original.tipo != "PAYMENT":
        raise PaymentReversalError("Solo se puede reversar un pago, no una reversión")

    # Validate cobrador route access on the credit
    credito = db.query(Credito).filter(
        _uuid_eq(Credito.id, original.credito_id),
    ).first()
    if credito:
        _validate_credito_access(db, credito, ctx)

    # Check for already reversed (idempotent return)
    already = db.query(Pago).filter(
        Pago.reversal_of_payment_id == pago_id,
    ).first()
    if already:
        return already

    # Generate idempotency key from client or internal
    idem_key = data.get("clave_idempotencia", f"rev-{pago_id!s}")

    # Check reversal idempotency
    existing = db.query(Pago).filter(
        _uuid_eq(Pago.negocio_id, ctx.negocio_id),
        Pago.clave_idempotencia == idem_key,
    ).first()
    if existing:
        if existing.monto != original.monto:
            raise PaymentIdempotencyError("Conflicto de idempotencia en reversión")
        return existing

    # Create REVERSAL
    reversal = Pago(
        id=__import__("uuid").uuid4(),
        negocio_id=ctx.negocio_id,
        credito_id=original.credito_id,
        jornada_id=original.jornada_id,
        tipo="REVERSAL",
        reversal_of_payment_id=pago_id,
        monto=original.monto,
        cobrador_id=ctx.user_id,
        dispositivo_id=ctx.device_id,
        registrado_el_dispositivo=datetime.now(BOGOTA_TZ),
        clave_idempotencia=idem_key,
        nota=data.get("motivo"),
    )
    db.add(reversal)
    db.flush()
    return reversal


def get_pico_amount(
    db: Session,
    credito_id: UUID,
) -> int:
    """Get the pico (remainder) for a credit.

    pico = abono_neto % cuota

    Returns 0 if no payments exist.
    """
    neto = get_net_paid(db, credito_id)
    credito = db.query(Credito).filter(_uuid_eq(Credito.id, credito_id)).first()
    if not credito or credito.cuota == 0:
        return 0
    return neto % credito.cuota


def get_cuotas_pagadas(
    db: Session,
    credito_id: UUID,
) -> int:
    """Get the number of paid cuotas for a credit.

    cuotas_pagadas = abono_neto // cuota
    """
    neto = get_net_paid(db, credito_id)
    credito = db.query(Credito).filter(_uuid_eq(Credito.id, credito_id)).first()
    if not credito or credito.cuota == 0:
        return 0
    return neto // credito.cuota


def get_saldo(
    db: Session,
    credito_id: UUID,
) -> int:
    """Get the remaining balance for a credit.

    saldo = total - abono_neto
    """
    neto = get_net_paid(db, credito_id)
    credito = db.query(Credito).filter(_uuid_eq(Credito.id, credito_id)).first()
    if not credito:
        raise PaymentError("Crédito no encontrado")
    return credito.total - neto


def get_vence_hoy_count(
    db: Session,
    credito_ids: list[UUID],
    report_date: date | None = None,
) -> tuple[int, int]:
    """Get count and total amount of cuotas that expire today.

    Returns (count, total_monto).
    """
    report_date = report_date or today_bogota()
    if not credito_ids:
        return (0, 0)

    result = (
        db.query(
            __import__("sqlalchemy").func.count(CuotaProgramada.id),
            __import__("sqlalchemy").func.sum(CuotaProgramada.monto),
        )
        .filter(
            CuotaProgramada.credito_id.in_(credito_ids),
            CuotaProgramada.fecha_vencimiento == report_date,
            CuotaProgramada.estado == "PENDIENTE",
        )
        .first()
    )
    if result:
        return (result[0] or 0, result[1] or 0)
    return (0, 0)
