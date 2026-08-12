"""Conflict detection and resolution — S5 server-authoritative sync.

Unifica la deteccion de conflictos en todas las entidades sincronizadas:
- Pago: idempotency key con full-payload comparison
- Movimiento: idempotency key con full-payload comparison
- Jornada: snapshot hash + estado terminal
- Ruta: version_asignacion + ruta activa unica

Cada operacion push debe verificar antes de escribir:
1. Recurso existe? → si, verificar version/hash/payload
2. Payload coincide? → si, idempotente success
3. Payload distinto? → 409 conflict
4. Estado terminal? → no permitir rollback

Resolucion server-authoritative:
- Servidor conserva su estado canónico
- Movil conoce conflicto y reconcilia con pull
- No write parcial antes de detectar conflicto
- Rollback/transaccion impide efectos secundarios
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ConflictInfo:
    """Informacion de conflicto detectado."""

    entidad: str  # pago, movimiento, jornada, ruta
    clave: str  # idempotency_key, snapshot_hash, etc.
    esperado: str  # valor esperado
    actual: str  # valor actual en servidor
    mensaje: str  # mensaje para el cliente


class ConflictError(Exception):
    """Error de conflicto: payload esperado no coincide con servidor."""

    def __init__(
        self,
        entidad: str,
        clave: str,
        esperado: str,
        actual: str,
        mensaje: str | None = None,
    ):
        self.entidad = entidad
        self.clave = clave
        self.esperado = esperado
        self.actual = actual
        self.mensaje = mensaje or f"{entidad}: {clave} esperado={esperado} actual={actual}"
        super().__init__(self.mensaje)


def verificar_conflicto_pago(
    existing: dict,
    payload: dict,
) -> ConflictInfo | None:
    """Verificar conflicto en pago: misma clave_idempotencia + payload distinto.

    Args:
        existing: pago existente en servidor
        payload: payload del push

    Returns:
        ConflictInfo si hay conflicto, None si coincide (idempotente)
    """
    if existing["tipo"] != "PAYMENT":
        return ConflictError(
            "pago",
            "clave_idempotencia",
            "PAYMENT",
            existing["tipo"],
            "Misma clave con tipo diferente",
        )

    if str(existing.get("credito_id")) != str(payload.get("credito_id")):
        return ConflictError(
            "pago",
            "credito_id",
            str(payload.get("credito_id")),
            str(existing.get("credito_id")),
            "Misma clave con credito diferente",
        )

    if existing.get("monto") != payload.get("monto"):
        return ConflictError(
            "pago",
            "monto",
            str(payload.get("monto")),
            str(existing.get("monto")),
            "Misma clave con monto diferente",
        )

    if str(existing.get("jornada_id") or "") != str(payload.get("jornada_id") or ""):
        return ConflictError(
            "pago",
            "jornada_id",
            str(payload.get("jornada_id")),
            str(existing.get("jornada_id")),
            "Misma clave con jornada diferente",
        )

    return None


def verificar_conflicto_movimiento(
    existing: dict,
    payload: dict,
) -> ConflictInfo | None:
    """Verificar conflicto en movimiento: misma clave_idempotencia + full-payload.

    Compara los 8 campos que movimiento_service.validate compara:
    jornada_id, tipo, naturaleza, monto, nota, credito_id, renovacion_id,
    ajuste_de_movimiento_id.

    Coincide con movimiento_service.py:266-284.
    """
    if str(existing.get("jornada_id")) != str(payload.get("jornada_id")):
        return ConflictError(
            "movimiento",
            "jornada_id",
            str(payload.get("jornada_id")),
            str(existing.get("jornada_id")),
            "Misma clave con jornada diferente",
        )

    if existing.get("tipo") != payload.get("tipo"):
        return ConflictError(
            "movimiento",
            "tipo",
            payload.get("tipo"),
            existing.get("tipo"),
            "Misma clave con tipo diferente",
        )

    if existing.get("naturaleza") != payload.get("naturaleza"):
        return ConflictError(
            "movimiento",
            "naturaleza",
            str(payload.get("naturaleza")),
            str(existing.get("naturaleza")),
            "Misma clave con naturaleza diferente",
        )

    if existing.get("monto") != payload.get("monto"):
        return ConflictError(
            "movimiento",
            "monto",
            str(payload.get("monto")),
            str(existing.get("monto")),
            "Misma clave con monto diferente",
        )

    if (existing.get("nota") or "") != (payload.get("nota") or ""):
        return ConflictError(
            "movimiento",
            "nota",
            str(payload.get("nota")),
            str(existing.get("nota")),
            "Misma clave con nota diferente",
        )

    if str(existing.get("credito_id") or "") != str(payload.get("credito_id") or ""):
        return ConflictError(
            "movimiento",
            "credito_id",
            str(payload.get("credito_id")),
            str(existing.get("credito_id")),
            "Misma clave con credito diferente",
        )

    if str(existing.get("renovacion_id") or "") != str(payload.get("renovacion_id") or ""):
        return ConflictError(
            "movimiento",
            "renovacion_id",
            str(payload.get("renovacion_id")),
            str(existing.get("renovacion_id")),
            "Misma clave con renovacion diferente",
        )

    if str(existing.get("ajuste_de_movimiento_id") or "") != str(payload.get("ajuste_de_movimiento_id") or ""):
        return ConflictError(
            "movimiento",
            "ajuste_de_movimiento_id",
            str(payload.get("ajuste_de_movimiento_id")),
            str(existing.get("ajuste_de_movimiento_id")),
            "Misma clave con ajuste diferente",
        )

    return None


def verificar_conflicto_jornada(
    stored_hash: str,
    received_hash: str,
    stored_snapshot: dict,
    received_snapshot: dict,
) -> ConflictInfo | None:
    """Verificar conflicto en jornada: snapshot hash no coincide.

    Compara:
    - Hash canónico
    - IDs financieros: pagos_ids, reversales_ids, movimientos_ids, renovaciones_ids
    - Valores financieros: efectivo_esperado, diferencia, efectivo_contado
    - Server-caja: si server_caja_efectivo_esperado existe, valida consistency

    Coincide con jornada_service.sincronizar_cierre() + cerrar_jornada().
    """
    if not stored_hash:
        return None  # Primera sincronizacion

    if received_hash != stored_hash:
        return ConflictError(
            "jornada",
            "snapshot_hash",
            stored_hash[:16] + "...",
            received_hash[:16] + "...",
            "Snapshot hash no coincide — datos modificados en servidor",
        )

    # Verificar IDs financieros inmutables (incluye renovaciones_ids)
    stored_ids = {
        "pagos": sorted(stored_snapshot.get("pagos_ids", [])),
        "reversales": sorted(stored_snapshot.get("reversales_ids", [])),
        "movimientos": sorted(stored_snapshot.get("movimientos_ids", [])),
        "renovaciones": sorted(stored_snapshot.get("renovaciones_ids", [])),
    }
    received_ids = {
        "pagos": sorted(received_snapshot.get("pagos_ids", [])),
        "reversales": sorted(received_snapshot.get("reversales_ids", [])),
        "movimientos": sorted(received_snapshot.get("movimientos_ids", [])),
        "renovaciones": sorted(received_snapshot.get("renovaciones_ids", [])),
    }

    for campo in stored_ids:
        if stored_ids[campo] != received_ids[campo]:
            return ConflictError(
                "jornada",
                f"{campo}_ids",
                str(stored_ids[campo]),
                str(received_ids[campo]),
                f"{campo} modificados en servidor",
            )

    # Verificar campos financieros inmutables
    if stored_snapshot.get("efectivo_esperado") != received_snapshot.get("efectivo_esperado"):
        return ConflictError(
            "jornada",
            "efectivo_esperado",
            str(stored_snapshot.get("efectivo_esperado")),
            str(received_snapshot.get("efectivo_esperado")),
            "Efectivo esperado modificado en servidor",
        )

    if stored_snapshot.get("diferencia") != received_snapshot.get("diferencia"):
        return ConflictError(
            "jornada",
            "diferencia",
            str(stored_snapshot.get("diferencia")),
            str(received_snapshot.get("diferencia")),
            "Diferencia de caja modificada en servidor",
        )

    if stored_snapshot.get("efectivo_contado") != received_snapshot.get("efectivo_contado"):
        return ConflictError(
            "jornada",
            "efectivo_contado",
            str(stored_snapshot.get("efectivo_contado")),
            str(received_snapshot.get("efectivo_contado")),
            "Efectivo contado modificado en servidor",
        )

    # Validar server-caja: client_esperado == server_esperado
    server_esperado = stored_snapshot.get("server_caja_efectivo_esperado")
    client_esperado = received_snapshot.get("efectivo_esperado")
    if server_esperado is not None and client_esperado is not None:
        if client_esperado != server_esperado:
            return ConflictError(
                "jornada",
                "server_caja_efectivo_esperado",
                str(server_esperado),
                str(client_esperado),
                "Snapshot efectivo_esperado no coincide con server-caja",
            )

    # Validar consistency: contado == esperado + diferencia
    client_esperado = received_snapshot.get("efectivo_esperado", 0)
    client_diferencia = received_snapshot.get("diferencia", 0)
    client_contado = received_snapshot.get("efectivo_contado", 0)
    expected_contado = client_esperado + client_diferencia
    if client_contado != expected_contado:
        return ConflictError(
            "jornada",
            "caja_consistency",
            str(expected_contado),
            str(client_contado),
            f"caja inconsistente: esperado({client_esperado}) + diferencia({client_diferencia}) != contado({client_contado})",
        )

    return None


def verificar_conflicto_reversal(
    existing_pago: dict,
    reversal_payload: dict,
) -> ConflictInfo | None:
    """Verificar conflicto en reversal: payment original modificado.

    Compara:
    - Tipo del pago original (debe ser PAYMENT, no REVERSAL)
    - reversal_of_payment_id (no debe tener reversal previo)
    - Monto (debe coincidir con el pago original)

    Coincide con payment_service.reverse_payment() :303-328.
    """
    payment_id = reversal_payload.get("reversal_of_payment_id")
    if not payment_id:
        return None

    # Verificar que el payment original existe y no fue revertido
    if existing_pago.get("tipo") == "REVERSAL":
        return ConflictError(
            "reversal",
            "payment_original",
            "PAYMENT",
            "REVERSAL",
            "Payment original ya revertido",
        )

    if str(existing_pago.get("reversal_of_payment_id") or "") != "":
        # Payment ya tiene reversal
        return ConflictError(
            "reversal",
            "payment_original",
            "sin reversal",
            "con reversal",
            "Payment original ya tiene reversal",
        )

    # Validar monto: reversal debe tener mismo monto que el pago original
    original_monto = existing_pago.get("monto")
    reversal_monto = reversal_payload.get("monto")
    if original_monto is not None and reversal_monto is not None:
        if original_monto != reversal_monto:
            return ConflictError(
                "reversal",
                "monto",
                str(original_monto),
                str(reversal_monto),
                "Mismo clave con monto diferente",
            )

    return None


def verificar_conflicto_jornada_abrir(
    existing: dict,
    payload: dict,
) -> ConflictInfo | None:
    """Verificar conflicto en apertura de jornada.

    Compara:
    - ruta_id
    - opening_base
    - fecha
    - cobrador_id

    Usa apertura_idempotency_key (columna separada de cierre_idempotency_key).

    Coincide con jornada_service.open_jornada() :134-154.
    """
    if existing.get("ruta_id") != payload.get("ruta_id"):
        return ConflictError(
            "jornada_abrir",
            "ruta_id",
            str(payload.get("ruta_id")),
            str(existing.get("ruta_id")),
            "Misma clave con ruta diferente",
        )

    if existing.get("opening_base") != payload.get("opening_base"):
        return ConflictError(
            "jornada_abrir",
            "opening_base",
            str(payload.get("opening_base")),
            str(existing.get("opening_base")),
            "Misma clave con opening_base diferente",
        )

    if existing.get("fecha") != payload.get("fecha"):
        return ConflictError(
            "jornada_abrir",
            "fecha",
            str(payload.get("fecha")),
            str(existing.get("fecha")),
            "Misma clave con fecha diferente",
        )

    existing_cobrador = str(existing.get("cobrador_id") or "")
    payload_cobrador = str(payload.get("cobrador_id") or "")
    if existing_cobrador and payload_cobrador and existing_cobrador != payload_cobrador:
        return ConflictError(
            "jornada_abrir",
            "cobrador_id",
            payload_cobrador,
            existing_cobrador,
            "Misma clave con cobrador diferente",
        )

    return None


def verificar_conflicto_ruta(
    ruta_id: str,
    ruta_origen: str,
    ruta_actual: str,
    ruta_asignaciones: list[dict] | None = None,
) -> ConflictInfo | None:
    """Verificar conflicto R1→R2: ruta_id_origen != ruta actual del cobrador.

    Regla S4: un evento nacido en R1 nunca se envia bajo R2 aunque
    el cobrador sea el mismo. No se desactiva R1 al reasignar.

    Args:
        ruta_id: ruta de la entidad (jornada, pago, movimiento)
        ruta_origen: ruta_id_origen de la fila sync_queue
        ruta_actual: ruta operativa actual del cobrador
        ruta_asignaciones: lista de asignaciones de ruta (opcional)

    Returns:
        ConflictInfo si hay mismatch, None si coincide.
    """
    if ruta_origen and ruta_origen != ruta_actual:
        return ConflictError(
            "ruta",
            "ruta_id_origen",
            ruta_origen,
            ruta_actual,
            f"R1->R2 mismatch: ruta_origen={ruta_origen} != actual={ruta_actual}",
        )

    # Verificar que la ruta de la entidad coincide con la ruta actual
    if ruta_id and ruta_id != ruta_actual:
        return ConflictError(
            "ruta",
            "entidad_ruta",
            ruta_id,
            ruta_actual,
            f"Entidad en ruta {ruta_id} no coincide con ruta actual {ruta_actual}",
        )

    return None


def clasificar_conflicto(
    entidad: str,
    codigo_http: int,
    detail: str,
) -> str:
    """Clasificar resultado de operacion en categoria determinista.

    Returns:
        'success' | 'idempotent_success' | 'conflict' | 'validation_error' | 'not_found' | 'unauthorized'
    """
    if codigo_http == 200 or codigo_http == 201:
        if "idempotente" in detail.lower() or "ya existe" in detail.lower():
            return "idempotent_success"
        return "success"

    if codigo_http == 409:
        return "conflict"

    if codigo_http == 400 or codigo_http == 422:
        return "validation_error"

    if codigo_http == 404:
        return "not_found"

    if codigo_http == 401:
        return "unauthorized"

    return "conflict"  # default para otros errores
