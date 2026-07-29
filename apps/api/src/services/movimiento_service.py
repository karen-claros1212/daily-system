"""Movimiento service — append-only movements with catalog types/naturalezas and idempotency.

Movimientos financieros son append-only. No UPDATE ni DELETE ordinario.

AJUSTE es exclusivo del administrador y permite ajuste posterior al cierre.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.models import MovimientoCaja, Credito, Renovacion, Jornada
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

# === MAPEO TIPO → NATURALEZA (server-derived default) ===
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

# === TIPOS AJUSTE — exclusivos de administrador ===
AJUSTE_TIPOS = {"AJUSTE"}


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


class MovimientoMontoInvalido(MovimientoError):
    pass


class MovimientoAjusteError(MovimientoError):
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


def _derive_naturaleza(tipo: str, naturaleza_enviada: str | None) -> str | None:
    """Derive naturaleza from tipo. Client puede enviar override para OTRO."""
    default = TIPO_A_NATURALEZA.get(tipo)
    if default is None:
        # OTRO: usar la naturaleza enviada
        return naturaleza_enviada
    # Para otros tipos, usar el valor del servidor
    return default


def register_movimiento(
    db: Session,
    data: dict,
    ctx: RequestContext,
) -> MovimientoCaja:
    """Register an append-only movimiento de caja.

    Naturaleza se deriva en el servidor (no se confía en el cliente).
    OTRO exige naturaleza explícita + nota obligatoria.
    AJUSTE es exclusivo del administrador, permite ajuste en jornada cerrada.
    """
    jornada_id = data.get("jornada_id")
    tipo = data.get("tipo")
    naturaleza_enviada = data.get("naturaleza")
    monto = data.get("monto")
    nota = data.get("nota")
    clave_idempotencia = data.get("clave_idempotencia")
    motivo = data.get("motivo")
    credito_id = data.get("credito_id")
    renovacion_id = data.get("renovacion_id")
    ajuste_de_movimiento_id = data.get("ajuste_de_movimiento_id")

    # Validate tipo
    validate_tipo(tipo)

    # Validate monto > 0
    if not monto or monto <= 0:
        raise MovimientoMontoInvalido("monto debe ser > 0")

    # Derive naturaleza en el servidor
    naturaleza = _derive_naturaleza(tipo, naturaleza_enviada)

    # OTRO requiere naturaleza explícita + nota obligatoria
    if tipo == "OTRO":
        if not naturaleza_enviada or naturaleza_enviada not in MOVIMIENTO_NATURALEZAS:
            raise MovimientoNaturalezaInvalida(
                "Tipo OTRO exige naturaleza explícita válida"
            )
        if not nota or not nota.strip():
            raise MovimientoError("Tipo OTRO requiere nota obligatoria")
        naturaleza = naturaleza_enviada

    # AJUSTE exclusivo de administrador
    if tipo in AJUSTE_TIPOS:
        if not ctx.is_admin():
            raise MovimientoAjusteError("Solo el administrador puede registrar ajustes")
        # AJUSTE requiere motivo + referencia al movimiento corregido
        if not motivo or not motivo.strip():
            raise MovimientoAjusteError("AJUSTE requiere motivo")
        if not ajuste_de_movimiento_id:
            raise MovimientoAjusteError("AJUSTE requiere ajuste_de_movimiento_id")

    # Get or validate jornada
    if jornada_id:
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
            raise MovimientoJornadaError("Movimiento pertenece a otra ruta")

        # AJUSTE se permite en jornada cerrada (ajuste administrativo posterior)
        if tipo != "AJUSTE":
            if jornada.estado in {
                "CLOSED_LOCAL_PENDING_SYNC",
                "CLOSED_SYNCED",
            }:
                raise MovimientoJornadaError(
                    "No se pueden registrar movimientos en jornada cerrada"
                )

    # Validate referenced entities belong to negocio + ruta
    if credito_id:
        credito = db.query(Credito).filter(
            _uuid_eq(Credito.id, credito_id),
            _uuid_eq(Credito.negocio_id, ctx.negocio_id),
        ).first()
        if not credito:
            raise MovimientoJornadaError("Crédito no encontrado o no pertenece al negocio")
        if ctx.is_cobrador() and credito.ruta_id != ctx.route_id:
            raise MovimientoJornadaError("Crédito pertenece a otra ruta")

    if renovacion_id:
        renovacion = db.query(Renovacion).filter(
            _uuid_eq(Renovacion.id, renovacion_id),
            _uuid_eq(Renovacion.negocio_id, ctx.negocio_id),
        ).first()
        if not renovacion:
            raise MovimientoJornadaError("Renovación no encontrada o no pertenece al negocio")

    # Check idempotencia — compare full payload
    if clave_idempotencia:
        existing = db.query(MovimientoCaja).filter(
            _uuid_eq(MovimientoCaja.negocio_id, ctx.negocio_id),
            MovimientoCaja.clave_idempotencia == clave_idempotencia,
        ).first()
        if existing:
            # Compare ALL payload fields
            if (existing.tipo == tipo
                    and existing.naturaleza == naturaleza
                    and existing.monto == monto
                    and str(existing.jornada_id) == str(jornada_id)
                    and (existing.nota or "") == (nota or "")
                    and str(existing.credito_id or "") == str(credito_id or "")
                    and str(existing.renovacion_id or "") == str(renovacion_id or "")
                    and str(existing.ajuste_de_movimiento_id or "") == str(ajuste_de_movimiento_id or "")):
                return existing
            raise MovimientoIdempotencyError(
                "Misma clave de idempotencia con payload diferente"
            )

    # Create movimiento
    movimiento = MovimientoCaja(
        id=uuid4(),
        negocio_id=ctx.negocio_id,
        jornada_id=jornada_id,
        tipo=tipo,
        naturaleza=naturaleza,
        monto=monto,
        nota=nota,
        creado_por=ctx.user_id,
        dispositivo_id=ctx.device_id,
        registrado_el_dispositivo=datetime.now(BOGOTA_TZ),
        credito_id=credito_id,
        renovacion_id=renovacion_id,
        ajuste_de_movimiento_id=ajuste_de_movimiento_id,
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
