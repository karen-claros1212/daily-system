"""M3 tests — Etapa 3: Suscripcion, dispositivo autorizado, inversionista aggregates."""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from src.models import Dispositivo, Negocio
from src.schemas import DispositivoCreate


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

    def test_registrar_dispositivo_crea_entry(self, client, db_session, negocio_con_suscripcion):
        """Registrar dispositivo crea entry en BD."""
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

    def test_registrar_duplicado_reutiliza(self, client, db_session, negocio_con_suscripcion):
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

    def test_registrar_revocado_se_reactiva(self, client, db_session, negocio_con_suscripcion):
        """Dispositivo revocado se reactiva al registrar de nuevo."""
        huella = "revocable_device"

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
        assert resp2.json()["revocado_el"] is not None

        # Re-register
        resp3 = client.post(
            f"/api/dispositivos?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
            json={"huella": huella},
        )
        assert resp3.status_code == 201
        assert resp3.json()["revocado_el"] is None
        assert resp3.json()["activo"] == 1

    def test_validar_dispositivo_actualiza_timestamp(
        self, client, db_session, negocio_con_suscripcion
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
            f"/api/dispositivos/{dev_id}/validar?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
        )
        assert resp2.status_code == 200
        assert resp2.json()["ultima_validacion_servidor"] is not None

    def test_validar_dispositivo_no_autorizado_404(
        self, client, db_session, negocio_con_suscripcion
    ):
        """Validar dispositivo no autorizado retorna 404."""
        fake_id = uuid.uuid4()
        resp = client.post(
            f"/api/dispositivos/{fake_id}/validar?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
        )
        assert resp.status_code == 404

    def test_revocar_dispositivo(self, client, db_session, negocio_con_suscripcion):
        """Revocar dispositivo marca revocado_el."""
        huella = "revocable_device"
        resp = client.post(
            f"/api/dispositivos?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
            json={"huella": huella},
        )
        assert resp.status_code == 201
        dev_id = resp.json()["id"]

        resp2 = client.post(
            f"/api/dispositivos/{dev_id}/revocar?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
        )
        assert resp2.status_code == 200
        assert resp2.json()["revocado_el"] is not None
        assert resp2.json()["activo"] == 0

    def test_listar_dispositivos(self, client, db_session, negocio_con_suscripcion):
        """Listar dispositivos muestra todos los del negocio."""
        # Register 3 devices
        for i in range(3):
            client.post(
                f"/api/dispositivos?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
                json={"huella": f"device_{i}"},
            )

        resp = client.get(
            f"/api/dispositivos?negocio_id={negocio_con_suscripcion.id}&role=ADMINISTRADOR",
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 3

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

    def test_suscripcion_activa_permite(self, client, db_session, negocio_con_suscripcion):
        """Negocio con suscripcion activa permite operaciones."""
        resp = client.get(
            f"/api/inversionista/suscripcion?negocio_id={negocio_con_suscripcion.id}&role=INVERSIONISTA",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["estado_suscripcion"] == "al_dia"
        assert data["activa"] is True

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

    def test_resumen_inversionista_negocio_vacio(self, client, db_session, negocio_con_suscripcion):
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
