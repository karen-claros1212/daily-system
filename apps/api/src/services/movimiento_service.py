"""Movimiento service — append-only movements with catalog types/naturalezas and idempotency.

Movimientos financieros son append-only. No UPDATE ni DELETE ordinario.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.models import MovimientoCaja
from src.services.jornada_service import (
    _uuid_eq,
)

BOGOTA_TZ = timezone(timedelta(hours=-5))

# === CATÁLOGO CERRADO DE TIPOS ===
MOVIMIENTO_TIPOS = {
    "GASOLINA",
    "OFICINA",
    "AHORRO",
    "VALE",
    "ENTREGA",
    "RECIBIDO",
    "DESEMBOLSO",
    "AJUSTE",
    "OTRO",
}

# === CATÁLOGO CERRADO DE NATURALEZAS ===
MOVIMIENTO_NATURALEZAS = {
    "GASTO",
    "CUSTODIA",
    "CUENTA_POR_COBRAR",
    "TRASLADO_ENTRADA",
    "TRASLADO_SALIDA",
    "DESEMBOLSO",
    "AJUSTE",
}

# === MAPEO TIPO → NATURALEZA (default) ===
TIPO_A_NATURALEZA = {
    "GASOLINA": "GASTO",
    "OFICINA": "GASTO",
    "AHORRO": "CUSTODIA",
    "VALE": "CUENTA_POR_COBRAR",
    "ENTREGA": "TRASLADO_SALIDA",
    "RECIBIDO": "TRASLADO_ENTRADA",
    "DESEMBOLSO": "DESEMBOLSO",
    "AJUSTE": "AJUSTE",
    "OTRO": None,  # requiere naturaleza explícita + nota obligatoria
}


class MovimientoError(Exception):
    """Domain error raised by movimiento service."""


class MovimientoNotFoundError(MovimientoError):
    pass


class MovimientoIdempotencyError(MovimientoError):
    pass


class MovimientoTipoInvalido(MovimientoError):
    pass


class MovimientoNaturalezaInvalida(MovimientoError):
    pass


class MovimientoJornadaError(MovimientoError):
    pass


def validate_tipo(tipo: str) -> None:
    """Validate that tipo is in the closed catalog."""
    if tipo not in MOVIMIENTO_TIPOS:
        raise MovimientoTipoInvalido(
            f"Tipo '{tipo}' no válido. Tipos permitidos: {', '.join(sorted(MOVIMIENTO_TIPOS))}"
        )


def validate_naturaleza(naturaleza: str) -> None:
    """Validate that naturaleza is in the closed catalog."""
    if naturaleza not in MOVIMIENTO_NATURALEZAS:
        raise MovimientoNaturalezaInvalida(
            f"Naturaleza '{naturaleza}' no válida. Naturalezas permitidas: {', '.join(sorted(MOVIMIENTO_NATURALEZAS))}"
        )


def register_movimiento(
    db: Session,
    data: dict,
    ctx: RequestContext,
) -> MovimientoCaja:
    """Register an append-only movimiento de caja.

    Args:
        db: SQLAlchemy session
        data: dict with jornada_id, tipo, naturaleza, monto, nota, etc.
        ctx: RequestContext from auth

    Returns:
        MovimientoCaja object

    Raises:
        MovimientoJornadaError: jornada not found or closed
        MovimientoIdempotencyError: duplicate idempotency key
        MovimientoTipoInvalido: invalid tipo
        MovimientoNaturalezaInvalida: invalid naturaleza
    """
    jornada_id = data.get("jornada_id")
    tipo = data.get("tipo")
    naturaleza = data.get("naturaleza")
    monto = data.get("monto")
    clave_idempotencia = data.get("clave_idempotencia")

    # Validate tipo and naturaleza
    validate_tipo(tipo)
    validate_naturaleza(naturaleza)

    # OTRO requires explicit naturaleza and nota
    if tipo == "OTRO":
        if not naturaleza or naturaleza == "GASTO":
            raise MovimientoNaturalezaInvalida(
                "Tipo OTRO exige naturaleza explícita (no GASTO por defecto)"
            )
        if not monto:
            raise MovimientoError("Tipo OTRO requiere monto")

    # Get or validate jornada
    if jornada_id:
        from src.models import Jornada
        jornada = (
            db.query(Jornada)
            .filter(
                _uuid_eq(Jornada.id, jornada_id),
                _uuid_eq(Jornada.negocio_id, ctx.negocio_id),
            )
            .first()
        )
        if not jornada:
            raise MovimientoJornadaError("Jornada no encontrada")

        # Cobrador route isolation
        if ctx.is_cobrador() and jornada.ruta_id != ctx.route_id:
                raise MovimientoJornadaError(
                    "Movimiento pertenece a otra ruta"
                )

        # Check if jornada is closed (append-only: can still add to open jornadas)
        if jornada.estado in {
            "CLOSED_LOCAL_PENDING_SYNC",
            "CLOSED_SYNCED",
        }:
            raise MovimientoJornadaError(
                "No se pueden registrar movimientos en jornada cerrada"
            )

    # Check idempotency
    if clave_idempotencia:
        existing = db.query(MovimientoCaja).filter(
            _uuid_eq(MovimientoCaja.negocio_id, ctx.negocio_id),
            MovimientoCaja.clave_idempotencia == clave_idempotencia,
        ).first()
        if existing:
            # Idempotent return: same key + same monto = OK, different = conflict
            if existing.monto != monto:
                raise MovimientoIdempotencyError(
                    "Misma clave de idempotencia con monto diferente"
                )
            return existing

    # Create movimiento
    movimiento = MovimientoCaja(
        id=__import__("uuid").uuid4(),
        negocio_id=ctx.negocio_id,
        jornada_id=jornada_id,
        tipo=tipo,
        naturaleza=naturaleza,
        monto=monto,
        nota=data.get("nota"),
        creado_por=ctx.user_id,
        dispositivo_id=ctx.device_id,
        registrado_el_dispositivo=datetime.now(BOGOTA_TZ),
        credito_id=data.get("credito_id"),
        renovacion_id=data.get("renovacion_id"),
        ajuste_de_movimiento_id=data.get("ajuste_de_movimiento_id"),
        clave_idempotencia=clave_idempotencia,
    )
    db.add(movimiento)
    db.flush()
    return movimiento


def list_movimientos(
    db: Session,
    jornada_id: UUID,
    ctx: RequestContext,
) -> list[MovimientoCaja]:
    """List movements for a jornada with route isolation."""
    query = db.query(MovimientoCaja).filter(
        _uuid_eq(MovimientoCaja.negocio_id, ctx.negocio_id),
        _uuid_eq(MovimientoCaja.jornada_id, jornada_id),
    )

    if ctx.is_cobrador():
        # Only movements from cobrador's route
        query = query.join(
            __import__("src.models").models.Jornada,
            __import__("src.models").models.Jornada.id == MovimientoCaja.jornada_id,
        ).filter(
            _uuid_eq(__import__("src.models").models.Jornada.ruta_id, ctx.route_id)
        )

    return query.all()


def get_movimiento(
    db: Session,
    movimiento_id: UUID,
    ctx: RequestContext,
) -> MovimientoCaja:
    """Get a movement by ID with business isolation."""
    movimiento = db.query(MovimientoCaja).filter(
        _uuid_eq(MovimientoCaja.id, movimiento_id),
        _uuid_eq(MovimientoCaja.negocio_id, ctx.negocio_id),
    ).first()
    if not movimiento:
        raise MovimientoNotFoundError("Movimiento no encontrado")
    return movimiento
