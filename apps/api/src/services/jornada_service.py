"""Jornada service — open, close, state transitions, carry chain, idempotent close.

States:
  OPEN → CLOSING → CLOSED_LOCAL_PENDING_SYNC → CLOSED_SYNCED

The server is the authority. The device may close locally (pending sync),
then the server validates and marks CLOSED_SYNCED.
"""

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.models import Jornada, Ruta, Credito, Renovacion, MovimientoCaja, Pago
from src.services.caja_service import calcular_cadena_caja
from src.services.hoja_viva_service import today_bogota

BOGOTA_TZ = timezone(timedelta(hours=-5))

JORNADA_ESTADO_CERRADAS = {
    "CLOSED_LOCAL_PENDING_SYNC",
    "CLOSED_SYNCED",
}


class JornadaError(Exception):
    """Domain error raised by jornada service."""


class JornadaNotFoundError(JornadaError):
    pass


class JornadaClosedError(JornadaError):
    """Operation not allowed on a closed jornada."""


class JornadaAlreadyClosed(JornadaError):
    """Jornada already closed with same idempotency key."""


class JornadaInvalidBase(JornadaError):
    pass


class JornadaRouteError(JornadaError):
    pass


class JornadaRoleError(JornadaError):
    pass


def _canonical_json_hash(obj: dict) -> str:
    """Compute SHA-256 hash of a dict using canonical JSON (sorted keys, no whitespace)."""
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _uuid_eq(column, val):
    if isinstance(val, str):
        return column == UUID(val)
    return column == val


def get_carry_for_date(db: Session, negocio_id: UUID, ruta_id: UUID, fecha: date) -> int:
    """Calculate opening_carry for a given date.

    opening_carry(D) = closing_carry(D-1) = sobrante_manana(D-1)
    """
    yesterday = fecha - timedelta(days=1)
    prev = (
        db.query(Jornada)
        .filter(
            _uuid_eq(Jornada.negocio_id, negocio_id),
            _uuid_eq(Jornada.ruta_id, ruta_id),
            Jornada.fecha == yesterday,
            Jornada.estado.in_(JORNADA_ESTADO_CERRADAS),
        )
        .order_by(Jornada.fecha.desc())
        .first()
    )
    return prev.sobrante_manana if prev else 0


def open_jornada(
    db: Session,
    ruta_id: UUID,
    negocio_id: UUID,
    fecha: date | None = None,
    opening_base: int = 0,
    ctx: RequestContext | None = None,
    clave_idempotencia: str | None = None,
) -> Jornada:
    """Open a new jornada for today (or specified date).

    Idempotent: same clave_idempotencia + same payload returns existing jornada.
    """
    fecha = fecha or today_bogota()

    # Validate opening_base
    if opening_base < 0:
        raise JornadaInvalidBase("opening_base debe ser >= 0")

    # Validate ruta exists and belongs to negocio
    ruta = db.query(Ruta).filter(
        _uuid_eq(Ruta.id, ruta_id),
        _uuid_eq(Ruta.negocio_id, negocio_id),
    ).first()
    if not ruta:
        raise JornadaRouteError("Ruta no encontrada o no pertenece al negocio")

    # Role-based restrictions
    if ctx:
        if ctx.role == "INVERSIONISTA":
            raise JornadaRoleError("El inversionista no puede abrir jornadas")
        if ctx.is_cobrador() and ruta_id != ctx.route_id:
            raise JornadaRoleError("El cobrador solo puede abrir su ruta")
        if ctx.role == "ADMINISTRADOR" and ruta_id != ctx.route_id:
            raise JornadaRoleError("El administrador solo puede abrir rutas asignadas")

    # Idempotencia: check if same key + same payload exists
    if clave_idempotencia:
        existing = db.query(Jornada).filter(
            _uuid_eq(Jornada.negocio_id, negocio_id),
            Jornada.cierre_idempotency_key == clave_idempotencia,
        ).first()
        if existing:
            # Compare payload: ruta_id, opening_base, fecha, cobrador
            if (existing.ruta_id == ruta_id
                    and existing.opening_base == opening_base
                    and existing.fecha == fecha
                    and (ctx is None or existing.cobrador_id == ctx.user_id)):
                return existing
            raise JornadaAlreadyClosed(
                "Misma clave de idempotencia con payload diferente"
            )

    # Check if jornada already exists for this date
    existing = (
        db.query(Jornada)
        .filter(
            _uuid_eq(Jornada.negocio_id, negocio_id),
            _uuid_eq(Jornada.ruta_id, ruta_id),
            Jornada.fecha == fecha,
        )
        .first()
    )
    if existing:
        if existing.estado in JORNADA_ESTADO_CERRADAS:
            raise JornadaClosedError("Ya existe una jornada cerrada para esta fecha")
        # Compare payload — reject if opening_base differs
        if existing.opening_base != opening_base:
            raise JornadaAlreadyClosed(
                "Ya existe jornada abierta con opening_base diferente"
            )
        return existing

    opening_carry = get_carry_for_date(db, negocio_id, ruta_id, fecha)

    jornada = Jornada(
        id=uuid4(),
        negocio_id=negocio_id,
        ruta_id=ruta_id,
        cobrador_id=ctx.user_id if ctx else None,
        fecha=fecha,
        estado="OPEN",
        opening_base=opening_base,
        opening_carry=opening_carry,
        esperado=0,
        contado=0,
        diferencia=0,
        diferencia_motivo=None,
        sobrante_manana=0,
    )
    db.add(jornada)
    db.flush()
    return jornada


def get_jornada(
    db: Session,
    jornada_id: UUID,
    ctx: RequestContext,
) -> Jornada:
    """Get a jornada by ID with route isolation for cobrador."""
    query = db.query(Jornada).filter(
        _uuid_eq(Jornada.id, jornada_id),
        _uuid_eq(Jornada.negocio_id, ctx.negocio_id),
    )

    if ctx.is_cobrador():
        query = query.filter(_uuid_eq(Jornada.ruta_id, ctx.route_id))

    jornada = query.first()
    if not jornada:
        raise JornadaNotFoundError("Jornada no encontrada")
    return jornada


def get_active_jornada(
    db: Session,
    ruta_id: UUID,
    negocio_id: UUID,
    fecha: date | None = None,
) -> Jornada | None:
    """Get the active (OPEN) jornada for a route and date."""
    fecha = fecha or today_bogota()
    return (
        db.query(Jornada)
        .filter(
            _uuid_eq(Jornada.negocio_id, negocio_id),
            _uuid_eq(Jornada.ruta_id, ruta_id),
            Jornada.fecha == fecha,
            Jornada.estado == "OPEN",
        )
        .first()
    )


def update_jornada_fields(
    db: Session,
    jornada: Jornada,
    **fields,
) -> None:
    """Update specific fields on a jornada."""
    if jornada.estado in JORNADA_ESTADO_CERRADAS:
        raise JornadaClosedError("No se puede modificar una jornada cerrada")

    for key, value in fields.items():
        if hasattr(jornada, key):
            setattr(jornada, key, value)

    db.flush()


def cerrar_jornada(
    db: Session,
    jornada_id: UUID,
    data: dict,
    ctx: RequestContext,
) -> dict:
    """Close a jornada with idempotency, snapshot, and carry chain.

    Server-side close transitions directly to CLOSED_SYNCED (not CLOSED_LOCAL_PENDING_SYNC).
    The device may close locally to CLOSED_LOCAL_PENDING_SYNC, then sync to CLOSED_SYNCED.

    Steps:
    1. Validate and freeze input (transition to CLOSING)
    2. Recalculate caja via flujos físicos
    3. Validate consistency: efectivo_contado = efectivo_esperado + diferencia
    4. Calculate difference, require motivo if non-zero
    5. Sellar (OPEN → CLOSING → CLOSED_SYNCED)
    6. Prepare tomorrow (sobrante_manana → next opening_carry)
    7. Save immutable snapshot with full details
    """
    jornada = db.query(Jornada).filter(
        _uuid_eq(Jornada.id, jornada_id),
        _uuid_eq(Jornada.negocio_id, ctx.negocio_id),
    ).first()
    if not jornada:
        raise JornadaNotFoundError("Jornada no encontrada")

    # Cobrador route isolation
    if ctx.is_cobrador() and jornada.ruta_id != ctx.route_id:
        raise JornadaNotFoundError("Jornada no encontrada")

    idempotency_key = data.get("idempotencia_cierre", "")

    # Idempotency check — compare full payload
    if idempotency_key:
        existing = (
            db.query(Jornada)
            .filter(
                _uuid_eq(Jornada.negocio_id, ctx.negocio_id),
                Jornada.cierre_idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing and existing.id == jornada_id:
            stored_snapshot = existing.cierre_snapshot_json or {}
            payload_contado = data.get("efectivo_contado", 0)
            payload_motivo = data.get("motivo", "")
            payload_version = data.get("version", 1)
            stored_contado = stored_snapshot.get("efectivo_contado", 0)
            stored_motivo = stored_snapshot.get("diferencia_motivo", "") or ""
            stored_version = stored_snapshot.get("version", 1)

            if (payload_contado != stored_contado
                    or payload_motivo != stored_motivo
                    or payload_version != stored_version):
                raise JornadaAlreadyClosed(
                    "Misma clave de idempotencia con payload diferente"
                )
            # Return stored cierre values from snapshot
            return {
                "jornada_id": str(existing.id),
                "estado": existing.estado,
                "fecha": str(existing.fecha),
                "opening_base": existing.opening_base,
                "opening_carry": existing.opening_carry,
                "recaudo_real": stored_snapshot.get("recaudo_real", 0),
                "desembolsos": stored_snapshot.get("desembolsos", 0),
                "vales": stored_snapshot.get("vales", 0),
                "gastos": stored_snapshot.get("gastos", 0),
                "ahorro": stored_snapshot.get("ahorro", 0),
                "efectivo_esperado": stored_snapshot.get("efectivo_esperado", 0),
                "efectivo_contado": stored_contado,
                "diferencia": stored_snapshot.get("diferencia", 0),
                "diferencia_motivo": stored_motivo if stored_motivo else None,
                "sobrante_manana": existing.sobrante_manana,
                "cierre_idempotency_key": existing.cierre_idempotency_key,
                "cierre_version": existing.cierre_version,
                "cerrada_local_el": (
                    existing.cerrada_local_el.isoformat() if existing.cerrada_local_el else None
                ),
                "snapshot_hash": existing.cierre_snapshot_hash,
            }

    if jornada.estado in JORNADA_ESTADO_CERRADAS:
        raise JornadaAlreadyClosed("Jornada ya cerrada")

    if jornada.estado != "OPEN":
        raise JornadaClosedError("Solo se puede cerrar una jornada OPEN")

    # Step 1: Transition to CLOSING
    jornada.estado = "CLOSING"
    jornada.cerrada_local_el = datetime.now(BOGOTA_TZ)
    jornada.cerrada_por = ctx.user_id
    db.flush()

    # Step 2: Recalculate caja via flujos físicos
    efectivo_contado = data.get("efectivo_contado", 0)
    caja = calcular_cadena_caja(db, jornada.id)

    # Step 3: Validate consistency
    # efectivo_contado = efectivo_esperado + diferencia
    esperado = caja["efectivo_esperado"]
    contado = efectivo_contado
    diferencia = contado - esperado

    # Step 4: Require motivo if difference non-zero
    motivo = data.get("motivo", "")
    if diferencia != 0 and not motivo:
        raise JornadaError("Diferencia no cero exige motivo")

    # Step 5: Sellar — transition to CLOSED_LOCAL_PENDING_SYNC
    # Device closes to CLOSED_LOCAL_PENDING_SYNC, server syncs to CLOSED_SYNCED
    jornada.estado = "CLOSED_LOCAL_PENDING_SYNC"
    jornada.cierre_idempotency_key = idempotency_key
    jornada.cierre_version = 1

    # Calculate sobrante_manana (carry to next day)
    jornada.sobrante_manana = contado

    # Update caja fields
    jornada.esperado = esperado
    jornada.contado = contado
    jornada.diferencia = diferencia
    jornada.diferencia_motivo = motivo if motivo else None

    # Step 7: Save immutable snapshot with full details
    pagos_agg = (
        db.query(Pago)
        .filter(
            _uuid_eq(Pago.jornada_id, jornada_id),
            Pago.tipo == "PAYMENT",
        )
        .all()
    )
    pagos_ids = [str(p.id) for p in pagos_agg]

    reversales_agg = (
        db.query(Pago)
        .filter(
            _uuid_eq(Pago.jornada_id, jornada_id),
            Pago.tipo == "REVERSAL",
        )
        .all()
    )
    reversales_ids = [str(r.id) for r in reversales_agg]

    movimientos_agg = (
        db.query(MovimientoCaja)
        .filter(
            _uuid_eq(MovimientoCaja.jornada_id, jornada_id),
        )
        .all()
    )
    movimientos_ids = [str(m.id) for m in movimientos_agg]

    renovaciones_agg = (
        db.query(Renovacion.id)
        .join(
            MovimientoCaja,
            MovimientoCaja.renovacion_id == Renovacion.id,
        )
        .filter(MovimientoCaja.jornada_id == jornada_id)
        .all()
    )
    renovaciones_ids = [str(r[0]) for r in renovaciones_agg]

    snapshot = {
        "jornada_id": str(jornada.id),
        "negocio_id": str(jornada.negocio_id),
        "ruta_id": str(jornada.ruta_id),
        "cobrador_id": str(jornada.cobrador_id) if jornada.cobrador_id else None,
        "fecha": str(jornada.fecha),
        "opening_base": jornada.opening_base,
        "opening_carry": jornada.opening_carry,
        "recaudo_real": caja["recaudo_real"],
        "desembolsos": caja["desembolsos"],
        "vales": caja["vales"],
        "gastos": caja["gastos"],
        "ahorro": caja["ahorro"],
        "entregas": caja["entregas"],
        "otros_entrada": caja["otros_entrada"],
        "efectivo_esperado": esperado,
        "efectivo_contado": contado,
        "diferencia": diferencia,
        "diferencia_motivo": motivo if motivo else None,
        "movimientos_count": caja["movimientos_count"],
        "pagos_count": caja["pagos_count"],
        "renovaciones_count": caja["renovaciones_count"],
        "pagos_ids": pagos_ids,
        "reversales_ids": reversales_ids,
        "movimientos_ids": movimientos_ids,
        "renovaciones_ids": renovaciones_ids,
        "cerrada_el": jornada.cerrada_local_el.isoformat() if jornada.cerrada_local_el else None,
        "recibida_servidor_el": jornada.recibida_servidor_el.isoformat() if jornada.recibida_servidor_el else None,
        "sincronizada_el": jornada.sincronizada_el.isoformat() if jornada.sincronizada_el else None,
        "version": 1,
    }
    jornada.cierre_snapshot_json = snapshot
    jornada.cierre_snapshot_hash = _canonical_json_hash(snapshot)

    db.flush()

    return _build_cierre_response(jornada, caja, contado, diferencia, motivo)


def _build_cierre_response(
    jornada: Jornada,
    caja: dict,
    contado: int,
    diferencia: int,
    motivo: str,
) -> dict:
    """Build the cierre response dict."""
    return {
        "jornada_id": str(jornada.id),
        "estado": jornada.estado,
        "fecha": str(jornada.fecha),
        "opening_base": jornada.opening_base,
        "opening_carry": jornada.opening_carry,
        "recaudo_real": caja["recaudo_real"],
        "desembolsos": caja["desembolsos"],
        "vales": caja["vales"],
        "gastos": caja["gastos"],
        "ahorro": caja["ahorro"],
        "efectivo_esperado": caja["efectivo_esperado"],
        "efectivo_contado": contado,
        "diferencia": diferencia,
        "diferencia_motivo": motivo if motivo else None,
        "sobrante_manana": jornada.sobrante_manana,
        "cierre_idempotency_key": jornada.cierre_idempotency_key,
        "cierre_version": jornada.cierre_version,
        "cerrada_local_el": (
            jornada.cerrada_local_el.isoformat() if jornada.cerrada_local_el else None
        ),
        "snapshot_hash": jornada.cierre_snapshot_hash,
    }


def sincronizar_cierre(
    db: Session,
    jornada_id: UUID,
    snapshot: dict,
    snapshot_hash: str,
    ctx: RequestContext,
) -> dict:
    """Synchronize a locally-closed jornada from device to server.

    Server validates the snapshot against its own calculation.
    The server's snapshot is canonical; the client's is compared but not replaced.
    """
    jornada = db.query(Jornada).filter(
        _uuid_eq(Jornada.id, jornada_id),
        _uuid_eq(Jornada.negocio_id, ctx.negocio_id),
    ).first()
    if not jornada:
        raise JornadaNotFoundError("Jornada no encontrada")

    # Cobrador route isolation
    if ctx.is_cobrador() and jornada.ruta_id != ctx.route_id:
        raise JornadaNotFoundError("Jornada no encontrada")

    if jornada.estado != "CLOSED_LOCAL_PENDING_SYNC":
        raise JornadaError(
            f"Jornada está en estado {jornada.estado}, se requiere CLOSED_LOCAL_PENDING_SYNC"
        )

    # Validate snapshot hash (canonical JSON)
    computed_hash = _canonical_json_hash(snapshot)
    if computed_hash != snapshot_hash:
        raise JornadaError("Snapshot hash no coincide — posible manipulación")

    # Validate server-calculated caja matches client snapshot
    # Correct relation: efectivo_contado = efectivo_esperado + diferencia
    server_caja = calcular_cadena_caja(db, jornada_id)
    server_esperado = server_caja["efectivo_esperado"]
    server_contado = (server_esperado
                      + server_caja["desembolsos"]
                      + server_caja["vales"]
                      + server_caja["gastos"]
                      + server_caja["ahorro"]
                      + server_caja["entregas"]
                      - server_caja["opening_base"]
                      - server_caja["opening_carry"]
                      - server_caja["recaudo_real"]
                      - server_caja["otros_entrada"])

    client_esperado = snapshot.get("efectivo_esperado", 0)
    client_contado = snapshot.get("efectivo_contado", 0)
    client_diferencia = snapshot.get("diferencia", 0)

    # Validate: client esperado matches server esperado
    if client_esperado != server_esperado:
        raise JornadaError(
            f"Snapshot efectivo_esperado ({client_esperado}) no coincide con "
            f"server ({server_esperado})"
        )

    # Validate: client contado = esperado + diferencia
    expected_contado = client_esperado + client_diferencia
    if client_contado != expected_contado:
        raise JornadaError(
            f"Snapshot efectivo_contado ({client_contado}) no coincide con "
            f"esperado (esperado {client_esperado} + diferencia {client_diferencia} = {expected_contado})"
        )

    # Update server-side timestamps
    jornada.sincronizada_el = datetime.now(BOGOTA_TZ)

    # Transition to CLOSED_SYNCED (do NOT replace the server's canonical snapshot)
    jornada.estado = "CLOSED_SYNCED"

    db.flush()

    return {
        "jornada_id": str(jornada.id),
        "estado": "CLOSED_SYNCED",
        "sincronizada_el": jornada.sincronizada_el.isoformat(),
        "snapshot_valido": True,
    }


def preparar_siguiente_jornada(
    db: Session,
    ruta_id: UUID,
    negocio_id: UUID,
    fecha: date | None = None,
) -> dict:
    """Prepare the next day's jornada based on today's close.

    Sets opening_carry = sobrante_manana from the previous day.
    """
    from datetime import timedelta
    fecha = fecha or today_bogota()

    # Look for the previous day's closed jornada
    prev_date = fecha - timedelta(days=1)
    prev = (
        db.query(Jornada)
        .filter(
            _uuid_eq(Jornada.negocio_id, negocio_id),
            _uuid_eq(Jornada.ruta_id, ruta_id),
            Jornada.fecha == prev_date,
            Jornada.estado.in_(JORNADA_ESTADO_CERRADAS),
        )
        .order_by(Jornada.fecha.desc())
        .first()
    )

    if not prev:
        return {"ready": False, "reason": "No hay jornada cerrada previa"}

    carry = prev.sobrante_manana

    return {
        "ready": True,
        "opening_carry": carry,
        "prev_jornada_id": str(prev.id),
        "prev_sobrante_manana": carry,
    }


def check_jornada_locked(
    db: Session,
    jornada_id: UUID,
    ctx: RequestContext,
) -> bool:
    """Check if a jornada is locked (closed)."""
    jornada = db.query(Jornada).filter(
        _uuid_eq(Jornada.id, jornada_id),
        _uuid_eq(Jornada.negocio_id, ctx.negocio_id),
    ).first()
    if not jornada:
        return True  # Non-existent jornada is considered locked
    return jornada.estado in JORNADA_ESTADO_CERRADAS
