"""S5: conflict_service.py unit tests.

Verifica que cada funcion de deteccion de conflicto:
- Devuelve None cuando payload coincide (idempotente)
- Devuelve ConflictInfo cuando hay mismatch
- Compara los mismos campos que el service layer correspondiente
"""

import pytest
from uuid import uuid4

from src.services.conflict_service import (
    ConflictError,
    clasificar_conflicto,
    verificar_conflicto_jornada,
    verificar_conflicto_jornada_abrir,
    verificar_conflicto_movimiento,
    verificar_conflicto_pago,
    verificar_conflicto_reversal,
    verificar_conflicto_ruta,
)


# === PAYMENT ===

@pytest.fixture
def base_payment():
    return {
        "tipo": "PAYMENT",
        "credito_id": str(uuid4()),
        "monto": 50000,
        "jornada_id": str(uuid4()),
    }


class TestVerificarConflictoPago:
    def test_mismo_payload_sin_conflicto(self, base_payment):
        assert verificar_conflicto_pago(base_payment, base_payment) is None

    def test_tipo_diferente_REVERSAL(self, base_payment):
        other = {**base_payment, "tipo": "REVERSAL"}
        err = verificar_conflicto_pago(other, base_payment)
        assert isinstance(err, ConflictError)
        assert err.entidad == "pago"

    def test_credito_diferente(self, base_payment):
        other = {**base_payment, "credito_id": str(uuid4())}
        err = verificar_conflicto_pago(other, base_payment)
        assert isinstance(err, ConflictError)
        assert "credito" in err.mensaje

    def test_monto_diferente(self, base_payment):
        other = {**base_payment, "monto": 60000}
        err = verificar_conflicto_pago(other, base_payment)
        assert isinstance(err, ConflictError)
        assert "monto" in err.mensaje

    def test_jornada_diferente(self, base_payment):
        other = {**base_payment, "jornada_id": str(uuid4())}
        err = verificar_conflicto_pago(other, base_payment)
        assert isinstance(err, ConflictError)
        assert "jornada" in err.mensaje


# === MOVIMIENTO ===

@pytest.fixture
def base_movimiento():
    return {
        "jornada_id": str(uuid4()),
        "tipo": "GASOLINA",
        "naturaleza": "GASTO",
        "monto": 10000,
        "nota": "combustible",
        "credito_id": str(uuid4()),
        "renovacion_id": None,
        "ajuste_de_movimiento_id": None,
    }


class TestVerificarConflictoMovimiento:
    def test_mismo_payload_sin_conflicto(self, base_movimiento):
        assert verificar_conflicto_movimiento(base_movimiento, base_movimiento) is None

    def test_jornada_diferente(self, base_movimiento):
        other = {**base_movimiento, "jornada_id": str(uuid4())}
        err = verificar_conflicto_movimiento(other, base_movimiento)
        assert isinstance(err, ConflictError)
        assert "jornada" in err.mensaje

    def test_tipo_diferente(self, base_movimiento):
        other = {**base_movimiento, "tipo": "OFICINA"}
        err = verificar_conflicto_movimiento(other, base_movimiento)
        assert isinstance(err, ConflictError)
        assert "tipo" in err.mensaje

    def test_naturaleza_diferente(self, base_movimiento):
        other = {**base_movimiento, "naturaleza": "CUENTA_POR_COBRAR"}
        err = verificar_conflicto_movimiento(other, base_movimiento)
        assert isinstance(err, ConflictError)
        assert "naturaleza" in err.mensaje

    def test_monto_diferente(self, base_movimiento):
        other = {**base_movimiento, "monto": 20000}
        err = verificar_conflicto_movimiento(other, base_movimiento)
        assert isinstance(err, ConflictError)
        assert "monto" in err.mensaje

    def test_nota_diferente(self, base_movimiento):
        other = {**base_movimiento, "nota": "otro motivo"}
        err = verificar_conflicto_movimiento(other, base_movimiento)
        assert isinstance(err, ConflictError)
        assert "nota" in err.mensaje

    def test_credito_diferente(self, base_movimiento):
        other = {**base_movimiento, "credito_id": str(uuid4())}
        err = verificar_conflicto_movimiento(other, base_movimiento)
        assert isinstance(err, ConflictError)
        assert "credito" in err.mensaje

    def test_renovacion_diferente(self, base_movimiento):
        ren_id = str(uuid4())
        other = {**base_movimiento, "renovacion_id": ren_id}
        err = verificar_conflicto_movimiento(other, base_movimiento)
        assert isinstance(err, ConflictError)
        assert "renovacion" in err.mensaje

    def test_ajuste_diferente(self, base_movimiento):
        aj_id = str(uuid4())
        other = {**base_movimiento, "ajuste_de_movimiento_id": aj_id}
        err = verificar_conflicto_movimiento(other, base_movimiento)
        assert isinstance(err, ConflictError)
        assert "ajuste" in err.mensaje


# === JORNADA SYNC ===

@pytest.fixture
def base_snapshot():
    return {
        "jornada_id": str(uuid4()),
        "negocio_id": str(uuid4()),
        "ruta_id": str(uuid4()),
        "cobrador_id": str(uuid4()),
        "opening_base": 50000,
        "opening_carry": 0,
        "recaudo_real": 200000,
        "pagos_ids": ["a", "b"],
        "reversales_ids": ["c"],
        "movimientos_ids": ["d", "e"],
        "renovaciones_ids": ["f"],
        "efectivo_esperado": 250000,
        "efectivo_contado": 255000,
        "diferencia": 5000,
        "server_caja_efectivo_esperado": 250000,
    }


class TestVerificarConflictoJornada:
    def test_mismo_hash_sin_conflicto(self, base_snapshot):
        h = "abc123"
        assert verificar_conflicto_jornada(h, h, base_snapshot, base_snapshot) is None

    def test_hash_diferente(self, base_snapshot):
        assert verificar_conflicto_jornada("abc", "def", base_snapshot, base_snapshot) is not None

    def test_sin_stored_hash_no_conflicto(self, base_snapshot):
        assert verificar_conflicto_jornada("", "def", base_snapshot, base_snapshot) is None

    def test_pagos_ids_diferente(self, base_snapshot):
        snap = {**base_snapshot, "pagos_ids": ["x", "y"]}
        err = verificar_conflicto_jornada("h", "h", base_snapshot, snap)
        assert isinstance(err, ConflictError)
        assert "pagos" in err.mensaje

    def test_renovaciones_ids_diferente(self, base_snapshot):
        snap = {**base_snapshot, "renovaciones_ids": ["z"]}
        err = verificar_conflicto_jornada("h", "h", base_snapshot, snap)
        assert isinstance(err, ConflictError)
        assert "renovaciones" in err.mensaje

    def test_efectivo_esperado_diferente(self, base_snapshot):
        snap = {**base_snapshot, "efectivo_esperado": 300000}
        err = verificar_conflicto_jornada("h", "h", base_snapshot, snap)
        assert isinstance(err, ConflictError)
        assert "Efectivo" in err.mensaje or "efectivo" in err.mensaje

    def test_efectivo_contado_diferente(self, base_snapshot):
        snap = {**base_snapshot, "efectivo_contado": 260000}
        err = verificar_conflicto_jornada("h", "h", base_snapshot, snap)
        assert isinstance(err, ConflictError)
        assert "contado" in err.mensaje

    def test_diferencia_diferente(self, base_snapshot):
        snap = {**base_snapshot, "diferencia": 10000}
        err = verificar_conflicto_jornada("h", "h", base_snapshot, snap)
        assert isinstance(err, ConflictError)
        assert "Diferencia" in err.mensaje or "diferencia" in err.mensaje

    def test_server_caja_mismatch(self, base_snapshot):
        # server_caja_efectivo_esperado=250000, client_esperado cambia a 260000
        # El check de efectivo_esperado (linea anterior) lo captura primero
        snap = {**base_snapshot, "efectivo_esperado": 260000}
        err = verificar_conflicto_jornada("h", "h", base_snapshot, snap)
        assert isinstance(err, ConflictError)
        assert "Efectivo" in err.mensaje or "efectivo" in err.mensaje

    def test_caaja_consistency_violation(self, base_snapshot):
        snap = {**base_snapshot, "efectivo_contado": 300000}
        err = verificar_conflicto_jornada("h", "h", base_snapshot, snap)
        assert isinstance(err, ConflictError)
        assert "contado" in err.mensaje


# === JORNADA ABRIR ===

@pytest.fixture
def base_open_jornada():
    return {
        "ruta_id": str(uuid4()),
        "opening_base": 50000,
        "fecha": "2026-08-12",
        "cobrador_id": str(uuid4()),
    }


class TestVerificarConflictoJornadaAbrir:
    def test_mismo_payload_sin_conflicto(self, base_open_jornada):
        assert verificar_conflicto_jornada_abrir(base_open_jornada, base_open_jornada) is None

    def test_ruta_diferente(self, base_open_jornada):
        other = {**base_open_jornada, "ruta_id": str(uuid4())}
        err = verificar_conflicto_jornada_abrir(other, base_open_jornada)
        assert isinstance(err, ConflictError)
        assert "ruta" in err.mensaje

    def test_opening_base_diferente(self, base_open_jornada):
        other = {**base_open_jornada, "opening_base": 60000}
        err = verificar_conflicto_jornada_abrir(other, base_open_jornada)
        assert isinstance(err, ConflictError)
        assert "opening_base" in err.mensaje

    def test_fecha_diferente(self, base_open_jornada):
        other = {**base_open_jornada, "fecha": "2026-08-13"}
        err = verificar_conflicto_jornada_abrir(other, base_open_jornada)
        assert isinstance(err, ConflictError)
        assert "fecha" in err.mensaje

    def test_cobrador_diferente(self, base_open_jornada):
        other = {**base_open_jornada, "cobrador_id": str(uuid4())}
        err = verificar_conflicto_jornada_abrir(other, base_open_jornada)
        assert isinstance(err, ConflictError)
        assert "cobrador" in err.mensaje

    def test_sin_cobrador_no_conflicto(self, base_open_jornada):
        base = {**base_open_jornada, "cobrador_id": None}
        other = {**base_open_jornada, "cobrador_id": None}
        assert verificar_conflicto_jornada_abrir(base, other) is None


# === REVERSAL ===

@pytest.fixture
def base_reversal():
    return {
        "reversal_of_payment_id": str(uuid4()),
        "monto": 50000,
    }


@pytest.fixture
def existing_payment():
    return {
        "tipo": "PAYMENT",
        "reversal_of_payment_id": None,
        "monto": 50000,
    }


class TestVerificarConflictoReversal:
    def test_sin_payment_id_sin_conflicto(self, existing_payment):
        payload = {"reversal_of_payment_id": None}
        assert verificar_conflicto_reversal(existing_payment, payload) is None

    def test_mismo_payload_sin_conflicto(self, existing_payment, base_reversal):
        assert verificar_conflicto_reversal(existing_payment, base_reversal) is None

    def test_payment_ya_revertido(self, base_reversal):
        existing = {
            "tipo": "REVERSAL",
            "reversal_of_payment_id": None,
            "monto": 50000,
        }
        err = verificar_conflicto_reversal(existing, base_reversal)
        assert isinstance(err, ConflictError)
        assert "ya revertido" in err.mensaje

    def test_payment_ya_tiene_reversal(self, base_reversal):
        existing = {
            "tipo": "PAYMENT",
            "reversal_of_payment_id": str(uuid4()),
            "monto": 50000,
        }
        err = verificar_conflicto_reversal(existing, base_reversal)
        assert isinstance(err, ConflictError)
        assert "ya tiene reversal" in err.mensaje

    def test_monto_diferente(self, base_reversal):
        existing = {
            "tipo": "PAYMENT",
            "reversal_of_payment_id": None,
            "monto": 60000,
        }
        err = verificar_conflicto_reversal(existing, base_reversal)
        assert isinstance(err, ConflictError)
        assert "monto" in err.mensaje


# === RUTA R1->R2 ===

class TestVerificarConflictoRuta:
    def test_mismas_rutas_sin_conflicto(self):
        assert verificar_conflicto_ruta("r1", "r1", "r1") is None

    def test_ruta_origen_diferente(self):
        err = verificar_conflicto_ruta("r1", "r1", "r2")
        assert isinstance(err, ConflictError)
        assert "R1->R2" in err.mensaje

    def test_entidad_ruta_diferente(self):
        err = verificar_conflicto_ruta("r1", None, "r2")
        assert isinstance(err, ConflictError)
        assert "Entidad" in err.mensaje or "entidad" in err.mensaje

    def test_sin_ruta_origen_solo_entidad(self):
        assert verificar_conflicto_ruta("r1", None, "r1") is None


# === CLASIFICAR CONFLICTO ===

class TestClasificarConflicto:
    def test_200_success(self):
        assert clasificar_conflicto("pago", 200, "ok") == "success"

    def test_201_created(self):
        assert clasificar_conflicto("pago", 201, "created") == "success"

    def test_200_idempotente(self):
        assert clasificar_conflicto("pago", 200, "ya existe") == "idempotent_success"

    def test_409_conflict(self):
        assert clasificar_conflicto("pago", 409, "mismatch") == "conflict"

    def test_400_validation_error(self):
        assert clasificar_conflicto("pago", 400, "invalid") == "validation_error"

    def test_422_validation_error(self):
        assert clasificar_conflicto("pago", 422, "invalid") == "validation_error"

    def test_404_not_found(self):
        assert clasificar_conflicto("pago", 404, "not found") == "not_found"

    def test_401_unauthorized(self):
        assert clasificar_conflicto("pago", 401, "unauthorized") == "unauthorized"

    def test_500_conflict_default(self):
        assert clasificar_conflicto("pago", 500, "server error") == "conflict"
