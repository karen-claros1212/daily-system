"""Tests for the API endpoints."""

import pytest


class TestHealthCheck:
    """Test the health check endpoint."""

    def test_health_ok(self, client):
        """Health check should return ok."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "daily-system-api"


class TestNegocioAPI:
    """Test negocio endpoints."""

    def test_create_negocio(self, client, db_session):
        """Create a new negocio."""
        response = client.post(
            "/api/negocios",
            json={"nombre": "Test Negocio", "nit": "900123456"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["nombre"] == "Test Negocio"
        assert data["nit"] == "900123456"
        assert data["pais"] == "CO"
        assert data["moneda"] == "COP"
        assert "id" in data

    def test_list_negocios(self, client, db_session):
        """List all negocios."""
        client.post(
            "/api/negocios",
            json={"nombre": "Negocio 1"},
        )
        client.post(
            "/api/negocios",
            json={"nombre": "Negocio 2"},
        )
        response = client.get("/api/negocios")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2


class TestRutaAPI:
    """Test ruta endpoints."""

    def test_create_ruta(self, client, db_session, negocio_id):
        """Create a new ruta."""
        response = client.post(
            f"/api/rutas?negocio_id={negocio_id}",
            json={"nombre": "Ruta 1"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["nombre"] == "Ruta 1"
        assert data["negocio_id"] == str(negocio_id)
        assert "id" in data

    def test_ruta_belongs_to_negocio(self, client, db_session, negocio_id):
        """Rutas are scoped to negocio."""
        client.post(
            f"/api/rutas?negocio_id={negocio_id}",
            json={"nombre": "Ruta A"},
        )
        response = client.get(f"/api/rutas?negocio_id={negocio_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        for r in data:
            assert r["negocio_id"] == str(negocio_id)


class TestClienteAPI:
    """Test cliente endpoints."""

    def test_create_cliente(self, client, db_session, negocio_id):
        """Create a new cliente."""
        response = client.post(
            f"/api/clientes?negocio_id={negocio_id}",
            json={
                "primer_apellido": "Perez",
                "nombres": "Juan",
                "tipo_documento": "CC",
                "documento_normalizado": "1234567890",
                "telefono_1": "3001234567",
                "ciudad": "Bogota",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["primer_apellido"] == "Perez"
        assert data["nombres"] == "Juan"
        assert data["identity_status"] == "PROVISIONAL"


class TestCreditoAPI:
    """Test credito endpoints."""

    def test_create_credito(self, client, db_session, negocio_id, ruta_id, cliente_id):
        """Create a new credito with total = cuota * n_cuotas."""
        response = client.post(
            f"/api/creditos?negocio_id={negocio_id}",
            json={
                "cliente_id": str(cliente_id),
                "ruta_id": str(ruta_id),
                "cuota": 30000,
                "n_cuotas": 40,
                "monto": 1000000,
                "fecha_inicio": "2026-07-28",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["cuota"] == 30000
        assert data["n_cuotas"] == 40
        assert data["total"] == 1200000  # 30000 * 40
        assert data["estado"] == "ACTIVO"
        assert data["periodicidad"] == "DIARIO"

    def test_credito_belongs_to_ruta(self, client, db_session, negocio_id, ruta_id, cliente_id):
        """Creditos are scoped to ruta."""
        response = client.post(
            f"/api/creditos?negocio_id={negocio_id}",
            json={
                "cliente_id": str(cliente_id),
                "ruta_id": str(ruta_id),
                "cuota": 30000,
                "n_cuotas": 40,
                "monto": 1000000,
                "fecha_inicio": "2026-07-28",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["ruta_id"] == str(ruta_id)

    def test_credito_total_constraint(self, client, db_session, negocio_id, ruta_id, cliente_id):
        """Total must equal cuota * n_cuotas (DB constraint)."""
        response = client.post(
            f"/api/creditos?negocio_id={negocio_id}",
            json={
                "cliente_id": str(cliente_id),
                "ruta_id": str(ruta_id),
                "cuota": 50000,
                "n_cuotas": 20,
                "monto": 500000,
                "fecha_inicio": "2026-07-28",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 1000000  # 50000 * 20


class TestPagoAPI:
    """Test pago endpoints."""

    def test_register_payment(self, client, db_session, negocio_id, ruta_id, cliente_id):
        """Register a payment with idempotency key."""
        # First create a credito
        credito_resp = client.post(
            f"/api/creditos?negocio_id={negocio_id}",
            json={
                "cliente_id": str(cliente_id),
                "ruta_id": str(ruta_id),
                "cuota": 30000,
                "n_cuotas": 40,
                "monto": 1000000,
                "fecha_inicio": "2026-07-28",
            },
        )
        credito_id = credito_resp.json()["id"]

        # Register payment
        response = client.post(
            f"/api/pagos?negocio_id={negocio_id}",
            json={
                "credito_id": credito_id,
                "jornada_id": None,
                "monto": 30000,
                "clave_idempotencia": "test-idempotency-key-001",
                "nota": "Primer abono",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["tipo"] == "PAYMENT"
        assert data["monto"] == 30000
        assert data["clave_idempotencia"] == "test-idempotency-key-001"

    def test_payment_idempotency(self, client, db_session, negocio_id, ruta_id, cliente_id):
        """Same idempotency key returns the same payment."""
        credito_resp = client.post(
            f"/api/creditos?negocio_id={negocio_id}",
            json={
                "cliente_id": str(cliente_id),
                "ruta_id": str(ruta_id),
                "cuota": 30000,
                "n_cuotas": 40,
                "monto": 1000000,
                "fecha_inicio": "2026-07-28",
            },
        )
        credito_id = credito_resp.json()["id"]

        # First payment
        resp1 = client.post(
            f"/api/pagos?negocio_id={negocio_id}",
            json={
                "credito_id": credito_id,
                "jornada_id": None,
                "monto": 30000,
                "clave_idempotencia": "idem-key-002",
            },
        )
        # Second payment with same key
        resp2 = client.post(
            f"/api/pagos?negocio_id={negocio_id}",
            json={
                "credito_id": credito_id,
                "jornada_id": None,
                "monto": 30000,
                "clave_idempotencia": "idem-key-002",
            },
        )

        assert resp1.status_code == 201
        assert resp2.status_code == 201
        assert resp1.json()["id"] == resp2.json()["id"]  # Same payment returned


class TestHojaViva:
    """Test the hoja viva endpoint."""

    def test_hoja_viva_empty(self, client, db_session, ruta_id):
        """Hoja viva with no creditos returns empty list."""
        response = client.get(f"/api/rutas/{ruta_id}/hoja-viva")
        assert response.status_code == 200
        data = response.json()
        assert data["ruta_id"] == str(ruta_id)
        assert data["clientes"] == []
        assert data["dc_legacy"] == 0

    def test_hoja_viva_with_creditos(self, client, db_session, negocio_id, ruta_id, cliente_id):
        """Hoja viva with creditos shows calculated values."""
        # Create two creditos for the same route
        client.post(
            f"/api/creditos?negocio_id={negocio_id}",
            json={
                "cliente_id": str(cliente_id),
                "ruta_id": str(ruta_id),
                "cuota": 30000,
                "n_cuotas": 40,
                "monto": 1000000,
                "fecha_inicio": "2026-07-28",
            },
        )

        response = client.get(f"/api/rutas/{ruta_id}/hoja-viva")
        assert response.status_code == 200
        data = response.json()
        assert len(data["clientes"]) >= 1
        assert data["dc_legacy"] > 0  # Sum of all cuotas
