"""M3 tests — Etapa 3: Suscripcion, dispositivo autorizado, inversionista aggregates."""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from src.models import Dispositivo, Negocio

# === Fixtures ===


@pytest.fixture
def negocio_con_suscripcion(db_session):
    """Negocio con suscripcion activa."""
    n = Negocio(
        id=uuid.uuid4(),
        nombre="Negocio M3 Test",
        nit="900123456",
        estado_suscripcion="al_dia",
        paid_through_at=datetime.now(timezone.utc) + timedelta(days=365),
    )
    db_session.add(n)
    db_session.flush()
    return n


@pytest.fixture
def route_id(db_session, negocio_con_suscripcion):
    """Create a test route."""
    from src.models import Ruta
    r = Ruta(
        id=uuid.uuid4(),
        negocio_id=negocio_con_suscripcion.id,
        nombre="Ruta Test M3",
    )
    db_session.add(r)
    db_session.flush()
    return r.id


@pytest.fixture
def negocio_vencido(db_session):
    """Negocio con suscripcion vencida."""
    n = Negocio(
        id=uuid.uuid4(),
        nombre="Negocio Vencido",
        nit="900987654",
        estado_suscripcion="vencida",
        paid_through_at=datetime.now(timezone.utc) - timedelta(days=30),
    )
    db_session.add(n)
    db_session.flush()
    return n


# === Dispositivo tests ===


class TestDispositivo:
    """Device authorization tests."""

    def test_registrar_dispositivo_requiere_admin(
        self, client, db_session, negocio_con_suscripcion, route_id
    ):
        """Registrar dispositivo es SOLO ADMINISTRADOR (gate del contrato).

        Contrato seccion 9: la creacion de dispositivo NO exige admin para
        dispositivos nuevos es un riesgo cerrado — un COBRADOR nunca registra.
        """
        huella = "admin_required_test"
        # First register as admin
        resp1 = client.post(
            f"/api/dispositivos?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
            json={"huella": huella},
        )
        assert resp1.status_code == 201
        dev_id = resp1.json()["id"]

        # Revoke as admin
        client.post(
            f"/api/dispositivos/{dev_id}/revocar?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
        )

        # Try register as COBRADOR — should fail with 403 (admin-only gate)
        resp2 = client.post(
            f"/api/dispositivos?negocio_id={negocio_con_suscripcion.id}&role=COBRADOR&route_id={route_id}",
            json={"huella": huella},
        )
        assert resp2.status_code == 403
        assert "ADMINISTRADOR" in resp2.json()["detail"]

    def test_registrar_dispositivo_crea_entry(
        self, client, db_session, negocio_con_suscripcion
    ):
        """Registrar dispositivo con ADMIN crea entry en BD."""
        huella = "abc123fingerprint"
        resp = client.post(
            f"/api/dispositivos?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
            json={"huella": huella, "modelo": "Samsung Galaxy S24", "plataforma": "android"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["huella"] == huella
        assert data["modelo"] == "Samsung Galaxy S24"
        assert data["plataforma"] == "android"
        assert data["activo"] == 1
        assert data["autorizado_el"] is not None

    def test_registrar_duplicado_reutiliza(
        self, client, db_session, negocio_con_suscripcion
    ):
        """Dispositivo con misma huella reutiliza entry existente."""
        huella = "unique_fingerprint"
        # First registration
        resp1 = client.post(
            f"/api/dispositivos?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
            json={"huella": huella, "modelo": "Modelo Original"},
        )
        assert resp1.status_code == 201
        id1 = resp1.json()["id"]

        # Second registration with same huella
        resp2 = client.post(
            f"/api/dispositivos?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
            json={"huella": huella, "modelo": "Modelo Actualizado"},
        )
        assert resp2.status_code == 201
        id2 = resp2.json()["id"]
        assert id1 == id2  # Same device

    def test_registrar_revocado_no_se_reactiva_sin_admin(
        self, client, db_session, negocio_con_suscripcion, route_id
    ):
        """Dispositivo revocado NO se reactiva con role=COBRADOR."""
        huella = "revocable_device"

        # Register as admin
        resp1 = client.post(
            f"/api/dispositivos?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
            json={"huella": huella},
        )
        assert resp1.status_code == 201
        dev_id = resp1.json()["id"]

        # Revoke as admin
        resp2 = client.post(
            f"/api/dispositivos/{dev_id}/revocar?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
        )
        assert resp2.status_code == 200
        assert resp2.json()["revocado_el"] is not None

        # Try to register again as COBRADOR — admin-only gate, 403
        resp3 = client.post(
            f"/api/dispositivos?negocio_id={negocio_con_suscripcion.id}&role=COBRADOR&route_id={route_id}",
            json={"huella": huella},
        )
        assert resp3.status_code == 403
        assert "ADMINISTRADOR" in resp3.json()["detail"]

    def test_registrar_revocado_se_reactiva_con_admin(
        self, client, db_session, negocio_con_suscripcion
    ):
        """Dispositivo revocado se reactiva con role=ADMINISTRADOR."""
        huella = "revocable_device_admin"

        # Register as admin
        resp1 = client.post(
            f"/api/dispositivos?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
            json={"huella": huella},
        )
        assert resp1.status_code == 201
        dev_id = resp1.json()["id"]

        # Revoke as admin
        resp2 = client.post(
            f"/api/dispositivos/{dev_id}/revocar?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
        )
        assert resp2.status_code == 200

        # Register again as ADMIN — reactivates
        resp3 = client.post(
            f"/api/dispositivos?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
            json={"huella": huella},
        )
        assert resp3.status_code == 201
        assert resp3.json()["revocado_el"] is None
        assert resp3.json()["activo"] == 1

    def test_dispositivo_id_es_uuid4_no_hash(
        self, db_session, negocio_con_suscripcion
    ):
        """Defecto corregido: id ya NO se deriva de hash(huella+negocio).

        Antes: UUID(int=hash(huella+negocio_id) % 2**128) — hash() es aleatorio
        por proceso, no criptografico ni determinista, y podia producir hex
        solo digitos que SQLite convertia a REAL y rompia el roundtrip.
        Ahora: uuid4() (v4). Este test guarda ademas el roundtrip SQLite
        del id tras reload (regresion del fix A original).
        """
        import uuid as _uuid

        from src.services import dispositivo_service

        huella = "hex_solo_digitos"
        dev = dispositivo_service.registrar_dispositivo(
            db_session,
            negocio_id=negocio_con_suscripcion.id,
            huella=huella,
            is_admin=True,
        )

        assert dev.id.version == 4
        assert dev.id != _uuid.UUID(
            int=hash(huella + str(negocio_con_suscripcion.id)) % (2**128)
        )

        db_session.expire_all()
        reloaded = (
            db_session.query(Dispositivo)
            .filter(Dispositivo.id == dev.id)
            .first()
        )
        assert isinstance(reloaded.id, uuid.UUID)
        assert reloaded.id == dev.id

    def test_reactivar_endpoint_explicito(
        self, client, db_session, negocio_con_suscripcion
    ):
        """Endpoint /reactivar requiere ADMIN."""
        huella = "reactivar_explicit"

        # Register
        resp1 = client.post(
            f"/api/dispositivos?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
            json={"huella": huella},
        )
        assert resp1.status_code == 201
        dev_id = resp1.json()["id"]

        # Revoke
        resp2 = client.post(
            f"/api/dispositivos/{dev_id}/revocar?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
        )
        assert resp2.status_code == 200

        # Reactivate via explicit endpoint as admin
        resp3 = client.post(
            f"/api/dispositivos/{dev_id}/reactivar?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
        )
        assert resp3.status_code == 200
        assert resp3.json()["revocado_el"] is None
        assert resp3.json()["activo"] == 1

    def test_reactivar_sin_admin_403(
        self, client, db_session, negocio_con_suscripcion, route_id
    ):
        """Reactivar dispositivo requiere ADMIN."""
        huella = "reactivar_sin_admin"

        resp1 = client.post(
            f"/api/dispositivos?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
            json={"huella": huella},
        )
        assert resp1.status_code == 201
        dev_id = resp1.json()["id"]

        # Revoke
        client.post(
            f"/api/dispositivos/{dev_id}/revocar?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
        )

        # Try reactivar as COBRADOR
        resp2 = client.post(
            f"/api/dispositivos/{dev_id}/reactivar?negocio_id={negocio_con_suscripcion.id}&role=COBRADOR&route_id={route_id}",
        )
        assert resp2.status_code == 403

    def test_revocar_requiere_admin(
        self, client, db_session, negocio_con_suscripcion, route_id
    ):
        """Revocar dispositivo requiere ADMIN."""
        huella = "revocar_admin_only"
        resp1 = client.post(
            f"/api/dispositivos?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
            json={"huella": huella},
        )
        assert resp1.status_code == 201
        dev_id = resp1.json()["id"]

        resp2 = client.post(
            f"/api/dispositivos/{dev_id}/revocar?negocio_id={negocio_con_suscripcion.id}&role=COBRADOR&route_id={route_id}",
        )
        assert resp2.status_code == 403

    def test_validar_dispositivo_actualiza_timestamp(
        self, client, db_session, negocio_con_suscripcion, route_id
    ):
        """Validar dispositivo actualiza ultima_validacion_servidor."""
        huella = "validable_device"
        resp = client.post(
            f"/api/dispositivos?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
            json={"huella": huella},
        )
        assert resp.status_code == 201
        dev_id = resp.json()["id"]

        resp2 = client.post(
            f"/api/dispositivos/{dev_id}/validar?negocio_id={negocio_con_suscripcion.id}&role=COBRADOR&route_id={route_id}",
        )
        assert resp2.status_code == 200
        assert resp2.json()["ultima_validacion_servidor"] is not None

    def test_validar_dispositivo_no_autorizado_404(
        self, client, db_session, negocio_con_suscripcion, route_id
    ):
        """Validar dispositivo no autorizado retorna 404."""
        fake_id = uuid.uuid4()
        resp = client.post(
            f"/api/dispositivos/{fake_id}/validar?negocio_id={negocio_con_suscripcion.id}&role=COBRADOR&route_id={route_id}",
        )
        assert resp.status_code == 404

    def test_listar_dispositivos_cualquier_role(
        self, client, db_session, negocio_con_suscripcion, route_id
    ):
        """Listar dispositivos funciona con cualquier rol."""
        # Register as admin
        client.post(
            f"/api/dispositivos?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
            json={"huella": "device_admin"},
        )

        # List as COBRADOR — should work
        resp = client.get(
            f"/api/dispositivos?negocio_id={negocio_con_suscripcion.id}&role=COBRADOR&route_id={route_id}",
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_dispositivo_huella_unica_por_negocio(
        self, client, db_session, negocio_con_suscripcion
    ):
        """Huella es unica por negocio."""
        huella = "unique_huella"
        # First registration succeeds
        resp1 = client.post(
            f"/api/dispositivos?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
            json={"huella": huella},
        )
        assert resp1.status_code == 201

        # Second registration with same huella updates (no 409 on same huella)
        resp2 = client.post(
            f"/api/dispositivos?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
            json={"huella": huella},
        )
        # Should return existing device (201 or 200 depending on implementation)
        assert resp2.status_code in (200, 201)


# === Suscripcion tests ===


class TestSuscripcion:
    """Subscription check tests."""

    def test_suscripcion_activa_permite(
        self, client, db_session, negocio_con_suscripcion
    ):
        """Negocio con suscripcion activa permite operaciones."""
        resp = client.get(
            f"/api/inversionista/suscripcion?negocio_id={negocio_con_suscripcion.id}&role=INVERSIONISTA",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["estado_suscripcion"] == "al_dia"
        assert data["activa"] is True

    def test_suscripcion_requiere_inversionista_o_admin(
        self, client, db_session, negocio_con_suscripcion, route_id
    ):
        """Suscripcion requiere INVERSIONISTA o ADMINISTRADOR."""
        resp = client.get(
            f"/api/inversionista/suscripcion?negocio_id={negocio_con_suscripcion.id}&role=COBRADOR&route_id={route_id}",
        )
        assert resp.status_code == 403

    def test_suscripcion_vencida(self, client, db_session, negocio_vencido):
        """Negocio con suscripcion vencida retorna estado correcto."""
        resp = client.get(
            f"/api/inversionista/suscripcion?negocio_id={negocio_vencido.id}&role=INVERSIONISTA",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["estado_suscripcion"] == "vencida"
        assert data["activa"] is False

    def test_suscripcion_nunca_vence(self, client, db_session):
        """Negocio sin paid_through_at se considera activo."""
        n = Negocio(
            id=uuid.uuid4(),
            nombre="Sin Tope",
            nit="900000000",
            estado_suscripcion="al_dia",
            paid_through_at=None,
        )
        db_session.add(n)
        db_session.flush()

        resp = client.get(
            f"/api/inversionista/suscripcion?negocio_id={n.id}&role=INVERSIONISTA",
        )
        assert resp.status_code == 200
        assert resp.json()["activa"] is True


# === Inversionista aggregates tests ===


class TestInversionista:
    """Investor aggregates tests — no PII."""

    def test_resumen_requiere_inversionista_o_admin(
        self, client, db_session, negocio_con_suscripcion, route_id
    ):
        """Resumen requiere INVERSIONISTA o ADMINISTRADOR."""
        resp = client.get(
            f"/api/inversionista/resumen?negocio_id={negocio_con_suscripcion.id}&role=COBRADOR&route_id={route_id}",
        )
        assert resp.status_code == 403

    def test_resumen_inversionista_sin_datos_personales(
        self, client, db_session, negocio_con_suscripcion
    ):
        """Resumen inversionista no contiene PII."""
        resp = client.get(
            f"/api/inversionista/resumen?negocio_id={negocio_con_suscripcion.id}&role=INVERSIONISTA",
        )
        assert resp.status_code == 200
        data = resp.json()
        portfolio = data["portfolio"]

        # Verify expected fields exist
        assert "total_creditos_activos" in portfolio
        assert "cartera_neta" in portfolio
        assert "recaudo_hoy" in portfolio
        assert "jornada_cerrada_hoy" in portfolio
        assert "cobradores_activos" in portfolio
        assert "rutas_activas" in portfolio

        # Verify no PII fields
        assert "cliente_nombre" not in str(data)
        assert "documento" not in str(data)
        assert "direccion" not in str(data)

    def test_resumen_inversionista_negocio_vacio(
        self, client, db_session, negocio_con_suscripcion
    ):
        """Resumen con negocio sin datos retorna ceros."""
        resp = client.get(
            f"/api/inversionista/resumen?negocio_id={negocio_con_suscripcion.id}&role=INVERSIONISTA",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["portfolio"]["total_creditos_activos"] == 0
        assert data["portfolio"]["cartera_neta"] == 0
        assert data["portfolio"]["recaudo_hoy"] == 0

    def test_resumen_inversionista_negocio_no_encontrado(self, client, db_session):
        """Resumen para negocio inexistente retorna 404."""
        fake_id = uuid.uuid4()
        resp = client.get(
            f"/api/inversionista/resumen?negocio_id={fake_id}&role=INVERSIONISTA",
        )
        assert resp.status_code == 404

    def test_resumen_inversionista_suscripcion_vencida(
        self, client, db_session, negocio_vencido
    ):
        """Resumen para negocio con suscripcion vencida retorna 403."""
        resp = client.get(
            f"/api/inversionista/resumen?negocio_id={negocio_vencido.id}&role=INVERSIONISTA",
        )
        assert resp.status_code == 403

    def test_resumen_incluye_datos_negocio(
        self, client, db_session, negocio_con_suscripcion
    ):
        """Resumen incluye nombre, plan, moneda, zona_horaria del negocio."""
        resp = client.get(
            f"/api/inversionista/resumen?negocio_id={negocio_con_suscripcion.id}&role=INVERSIONISTA",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["negocio_nombre"] == "Negocio M3 Test"
        assert data["plan"] == "basic"
        assert data["moneda"] == "COP"
        assert data["zona_horaria"] == "America/Bogota"


# === Dispositivo model tests ===


class TestDispositivoModel:
    """Direct model-level tests."""

    def test_dispositivo_creacion(self, db_session):
        """Crear Dispositivo directamente en BD."""
        n = Negocio(
            id=uuid.uuid4(),
            nombre="Model Test",
            estado_suscripcion="al_dia",
        )
        db_session.add(n)
        db_session.flush()

        dev = Dispositivo(
            id=uuid.uuid4(),
            negocio_id=n.id,
            huella="test_fingerprint",
            modelo="Test Phone",
            plataforma="android",
            activo=1,
        )
        db_session.add(dev)
        db_session.flush()

        assert dev.id is not None
        assert dev.huella == "test_fingerprint"
        assert dev.activo == 1

    def test_dispositivo_revocado(self, db_session):
        """Dispositivo revocado tiene revocado_el."""
        n = Negocio(
            id=uuid.uuid4(),
            nombre="Model Test",
            estado_suscripcion="al_dia",
        )
        db_session.add(n)
        db_session.flush()

        dev = Dispositivo(
            id=uuid.uuid4(),
            negocio_id=n.id,
            huella="revoked_fingerprint",
            modelo="Test Phone",
            plataforma="android",
            activo=0,
            revocado_el=datetime.now(timezone.utc),
        )
        db_session.add(dev)
        db_session.flush()

        assert dev.revocado_el is not None
        assert dev.activo == 0

    def test_dispositivo_plataforma_check(self, db_session):
        """Plataforma valida solo valores permitidos."""
        n = Negocio(
            id=uuid.uuid4(),
            nombre="Model Test",
            estado_suscripcion="al_dia",
        )
        db_session.add(n)
        db_session.flush()

        for plat in ["android", "ios", "web", "linux", "windows", "macos", "other"]:
            dev = Dispositivo(
                id=uuid.uuid4(),
                negocio_id=n.id,
                huella=f"platform_{plat}",
                plataforma=plat,
            )
            db_session.add(dev)

        db_session.flush()  # Should not raise


# === Aggregates correctness tests ===


class TestAggregatesCorrectness:
    """Test that financial aggregates are calculated correctly."""

    def test_cartera_neta_resta_pagos(self, client, db_session, negocio_con_suscripcion):
        """cartera_neta = monto - pagos + reversales, no solo monto."""
        from src.models import Credito, Pago

        # Create a credit with monto=100000
        credito = Credito(
            id=uuid.uuid4(),
            negocio_id=negocio_con_suscripcion.id,
            cliente_id=uuid.uuid4(),
            ruta_id=uuid.uuid4(),
            cuota=10000,
            n_cuotas=10,
            monto=100000,
            total=100000,
            estado="ACTIVO",
            fecha_inicio=date.today(),
        )
        db_session.add(credito)

        # Register a payment of 30000
        pago = Pago(
            id=uuid.uuid4(),
            negocio_id=negocio_con_suscripcion.id,
            credito_id=credito.id,
            tipo="PAYMENT",
            monto=30000,
            clave_idempotencia="test-payment-001",
            recibido_el_servidor=datetime.now(timezone.utc),
        )
        db_session.add(pago)
        db_session.flush()

        resp = client.get(
            f"/api/inversionista/resumen?negocio_id={negocio_con_suscripcion.id}&role=INVERSIONISTA",
        )
        assert resp.status_code == 200
        data = resp.json()
        # cartera_neta should be 100000 - 30000 = 70000, not 100000
        assert data["portfolio"]["cartera_neta"] == 70000

    def test_recaudo_hoy_resta_reversales(
        self, client, db_session, negocio_con_suscripcion
    ):
        """recaudo_hoy = pagos - reversales de hoy."""
        from src.models import Pago

        today_dt = datetime(2026, 7, 29, 12, 0, 0, tzinfo=timezone.utc)

        # Payment of 50000
        pago = Pago(
            id=uuid.uuid4(),
            negocio_id=negocio_con_suscripcion.id,
            credito_id=uuid.uuid4(),
            tipo="PAYMENT",
            monto=50000,
            clave_idempotencia="test-recaudo-001",
            recibido_el_servidor=today_dt,
        )
        db_session.add(pago)

        # Reversal of 10000
        reversal = Pago(
            id=uuid.uuid4(),
            negocio_id=negocio_con_suscripcion.id,
            credito_id=uuid.uuid4(),
            tipo="REVERSAL",
            monto=10000,
            clave_idempotencia="test-reversal-001",
            recibido_el_servidor=today_dt,
        )
        db_session.add(reversal)
        db_session.flush()

        # Pass today explicitly since the test date may differ from date.today()
        resp = client.get(
            f"/api/inversionista/resumen?negocio_id={negocio_con_suscripcion.id}&role=INVERSIONISTA&today=2026-07-29",
        )
        assert resp.status_code == 200
        data = resp.json()
        # recaudo_hoy should be 50000 - 10000 = 40000, not 50000
        assert data["portfolio"]["recaudo_hoy"] == 40000
