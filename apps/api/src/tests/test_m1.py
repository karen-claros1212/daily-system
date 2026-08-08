"""M1 tests: route isolation, calendar, reversals, hoja viva."""

from datetime import date
from uuid import uuid4

import pytest

from src.models import Cliente, Credito, Jornada, Negocio, Pago, Ruta
from src.services.calculation_service import calcular_mora_legacy, calcular_renovacion


class TestCalcularMoraLegacy:
    """Mora legacy with cuotas_pagadas subtraction."""

    def test_mora_legacy_basic(self):
        mora = calcular_mora_legacy(
            fecha_reporte=date(2026, 7, 6),
            inicia=date(2026, 5, 1),
            cuotas_pagadas=30,
        )
        assert mora >= 0

    def test_mora_legacy_zero_when_al_dia(self):
        mora = calcular_mora_legacy(
            fecha_reporte=date(2026, 7, 10),
            inicia=date(2026, 7, 9),
            cuotas_pagadas=5,
        )
        assert mora == 0


class TestCalcularRenovacion:
    """Renovación with recargo_pct used."""

    def test_recargo_used(self):
        result = calcular_renovacion(
            saldo_anterior=2740,
            pago_efectivo=0,
            monto_nuevo=3000,
            recargo_pct=20,
        )
        assert result["monto_final_con_recargo"] == 3600
        assert result["dinero_nuevo_entregado"] == 260

    def test_recargo_zero(self):
        result = calcular_renovacion(
            saldo_anterior=1000,
            pago_efectivo=200,
            monto_nuevo=800,
            recargo_pct=0,
        )
        assert result["monto_final_con_recargo"] == 800
        assert result["saldo_refinanciado"] == 800


class TestRouteIsolation:
    """Route isolation: R1 cannot touch R2."""

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.nid = uuid4()
        self.r1 = uuid4()
        self.r2 = uuid4()
        self.cid = uuid4()
        self.cr1 = uuid4()
        self.cr2 = uuid4()

        db_session.add(Negocio(id=self.nid, nombre="Negocio", nit="123"))
        db_session.add(Ruta(id=self.r1, negocio_id=self.nid, nombre="R1"))
        db_session.add(Ruta(id=self.r2, negocio_id=self.nid, nombre="R2"))
        db_session.add(Cliente(id=self.cid, negocio_id=self.nid, primer_apellido="X", nombres="Y", identity_status="PROVISIONAL"))
        db_session.add(Credito(
            id=self.cr1, negocio_id=self.nid, cliente_id=self.cid, ruta_id=self.r1,
            cuota=30000, n_cuotas=40, monto=1000000, total=1200000,
            periodicidad="DIARIO", fecha_inicio=date(2026, 7, 1), estado="ACTIVO",
        ))
        db_session.add(Credito(
            id=self.cr2, negocio_id=self.nid, cliente_id=self.cid, ruta_id=self.r2,
            cuota=50000, n_cuotas=20, monto=800000, total=1000000,
            periodicidad="DIARIO", fecha_inicio=date(2026, 7, 1), estado="ACTIVO",
        ))
        db_session.commit()

    def test_cobrador_cannot_pay_other_route(self, client, db_session):
        """Cobrador R1 tries to pay credito in R2 -> 403."""
        resp = client.post(
            f"/api/pagos?negocio_id={self.nid}&role=COBRADOR&route_id={self.r1}",
            json={
                "credito_id": str(self.cr2),
                "jornada_id": None,
                "monto": 30000,
                "clave_idempotencia": "iso-001",
            },
        )
        assert resp.status_code == 403

    def test_cobrador_can_pay_own_route(self, client, db_session):
        """Cobrador R1 pays credito in R1 -> 201."""
        resp = client.post(
            f"/api/pagos?negocio_id={self.nid}&role=COBRADOR&route_id={self.r1}",
            json={
                "credito_id": str(self.cr1),
                "jornada_id": None,
                "monto": 30000,
                "clave_idempotencia": "iso-002",
            },
        )
        assert resp.status_code == 201


class TestReversal:
    """Reversal flows."""

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.nid = uuid4()
        self.rid = uuid4()
        self.cid = uuid4()
        self.credito_id = uuid4()

        db_session.add(Negocio(id=self.nid, nombre="Negocio", nit="123"))
        db_session.add(Ruta(id=self.rid, negocio_id=self.nid, nombre="R1"))
        db_session.add(Cliente(id=self.cid, negocio_id=self.nid, primer_apellido="X", nombres="Y", identity_status="PROVISIONAL"))
        db_session.add(Credito(
            id=self.credito_id, negocio_id=self.nid, cliente_id=self.cid, ruta_id=self.rid,
            cuota=30000, n_cuotas=40, monto=1000000, total=1200000,
            periodicidad="DIARIO", fecha_inicio=date(2026, 7, 1), estado="ACTIVO",
        ))
        db_session.commit()

    def test_reversal_restores_saldo(self, client, db_session):
        """A REVERSAL reduces abono_neto, restoring saldo."""
        # Payment
        resp1 = client.post(
            f"/api/pagos?negocio_id={self.nid}",
            json={
                "credito_id": str(self.credito_id),
                "jornada_id": None,
                "monto": 30000,
                "clave_idempotencia": "rev-pay-001",
            },
        )
        assert resp1.status_code == 201

        # Reversal row
        db_session.add(Pago(
            id=uuid4(),
            negocio_id=self.nid,
            credito_id=self.credito_id,
            tipo="REVERSAL",
            monto=30000,
            clave_idempotencia="rev-rev-001",
        ))
        db_session.commit()

        from src.services.hoja_viva_service import build_hoja_viva
        result = build_hoja_viva(db_session, self.rid)
        assert len(result["clientes"]) == 1
        assert result["clientes"][0]["saldo"] == 1200000  # neto cero


class TestHojaVivaFields:
    """New hoja viva fields from the service layer."""

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.nid = uuid4()
        self.rid = uuid4()
        self.cid = uuid4()

        db_session.add(Negocio(id=self.nid, nombre="Negocio", nit="123"))
        db_session.add(Ruta(id=self.rid, negocio_id=self.nid, nombre="R1"))
        db_session.add(Cliente(id=self.cid, negocio_id=self.nid, primer_apellido="X", nombres="Y", identity_status="PROVISIONAL"))
        db_session.add(Credito(
            id=uuid4(), negocio_id=self.nid, cliente_id=self.cid, ruta_id=self.rid,
            cuota=30000, n_cuotas=40, monto=1000000, total=1200000,
            periodicidad="DIARIO", fecha_inicio=date(2026, 7, 1), estado="ACTIVO",
        ))
        db_session.add(Credito(
            id=uuid4(), negocio_id=self.nid, cliente_id=self.cid, ruta_id=self.rid,
            cuota=50000, n_cuotas=12, monto=500000, total=600000,
            periodicidad="SEMANAL", fecha_inicio=date(2026, 7, 1), estado="ACTIVO",
        ))
        db_session.commit()

    def test_dc_legacy_all_periodicities(self, client, db_session):
        """DC_LEGACY = Σ cuota of ALL active credits (diario + semanal)."""
        resp = client.get(f"/api/rutas/{self.rid}/hoja-viva?negocio_id={self.nid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["dc_legacy"] == 80000  # 30000 + 50000

    def test_vence_hoy_fields_present(self, client, db_session):
        """vence_hoy_monto and cuotas_que_vencen_hoy in response."""
        resp = client.get(f"/api/rutas/{self.rid}/hoja-viva?negocio_id={self.nid}")
        assert resp.status_code == 200
        data = resp.json()
        assert "vence_hoy_monto" in data
        assert "cuotas_que_vencen_hoy" in data

    def test_semaforo_always_gris(self, client, db_session):
        """Semáforo = GRIS until score_snapshot exists."""
        resp = client.get(f"/api/rutas/{self.rid}/hoja-viva?negocio_id={self.nid}")
        assert resp.status_code == 200
        for c in resp.json()["clientes"]:
            assert c["semaforo"] == "GRIS"


class TestIdempotenciaFinanciera:
    """Idempotencia financiera — auditoria 206b376.

    _check_idempotency debe exigir que la fila existente sea REALMENTE un
    PAYMENT con el payload completo (credito+monto+jornada); en reversos una
    colision de key no puede devolver una fila que no sea el reverso
    correspondiente (reversal_of_payment_id == pago_id).
    """

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.nid = uuid4()
        self.rid = uuid4()
        self.cid = uuid4()
        self.credito_id = uuid4()

        db_session.add(Negocio(id=self.nid, nombre="Negocio", nit="123"))
        db_session.add(Ruta(id=self.rid, negocio_id=self.nid, nombre="R1"))
        db_session.add(Cliente(id=self.cid, negocio_id=self.nid, primer_apellido="X", nombres="Y", identity_status="PROVISIONAL"))
        db_session.add(Credito(
            id=self.credito_id, negocio_id=self.nid, cliente_id=self.cid, ruta_id=self.rid,
            cuota=30000, n_cuotas=40, monto=1000000, total=1200000,
            periodicidad="DIARIO", fecha_inicio=date(2026, 7, 1), estado="ACTIVO",
        ))
        db_session.commit()

    def test_payment_key_no_colisiona_con_reversal(self, client, db_session):
        """Un PAYMENT no puede reutilizar la clave de un REVERSAL: 409."""
        # PAYMENT original
        r1 = client.post(
            f"/api/pagos?negocio_id={self.nid}",
            json={
                "credito_id": str(self.credito_id),
                "jornada_id": None,
                "monto": 30000,
                "clave_idempotencia": "fin-colision-001",
            },
        )
        assert r1.status_code == 201

        # REVERSAL con la misma clave (fila que colisiona, no PAYMENT)
        db_session.add(Pago(
            id=uuid4(),
            negocio_id=self.nid,
            credito_id=self.credito_id,
            tipo="REVERSAL",
            monto=30000,
            clave_idempotencia="fin-colision-002",
        ))
        db_session.commit()

        # PAYMENT con clave del REVERSAL -> 409 (no puede devolver un REVERSAL
        # como si fuera el pago idempotente)
        r2 = client.post(
            f"/api/pagos?negocio_id={self.nid}",
            json={
                "credito_id": str(self.credito_id),
                "jornada_id": None,
                "monto": 30000,
                "clave_idempotencia": "fin-colision-002",
            },
        )
        assert r2.status_code == 409

    def test_payment_key_distinta_jornada_es_conflicto(self, client, db_session):
        """Misma clave con distinta jornada -> 409 (payload no coincide)."""
        j1 = uuid4()
        j2 = uuid4()
        db_session.add(Jornada(
            id=j1, negocio_id=self.nid, ruta_id=self.rid, fecha=date(2026, 7, 1),
            estado="OPEN",
        ))
        db_session.add(Jornada(
            id=j2, negocio_id=self.nid, ruta_id=self.rid, fecha=date(2026, 7, 2),
            estado="OPEN",
        ))
        db_session.commit()

        r1 = client.post(
            f"/api/pagos?negocio_id={self.nid}",
            json={
                "credito_id": str(self.credito_id),
                "jornada_id": str(j1),
                "monto": 30000,
                "clave_idempotencia": "fin-jornada-001",
            },
        )
        assert r1.status_code == 201

        r2 = client.post(
            f"/api/pagos?negocio_id={self.nid}",
            json={
                "credito_id": str(self.credito_id),
                "jornada_id": str(j2),
                "monto": 30000,
                "clave_idempotencia": "fin-jornada-001",
            },
        )
        assert r2.status_code == 409

    def test_reversal_idempotente_devuelve_mismo_reversal(self, client, db_session):
        """Misma clave de reverso devuelve el MISMO REVERSAL (no un PAYMENT)."""
        r1 = client.post(
            f"/api/pagos?negocio_id={self.nid}",
            json={
                "credito_id": str(self.credito_id),
                "jornada_id": None,
                "monto": 30000,
                "clave_idempotencia": "fin-rev-001",
            },
        )
        assert r1.status_code == 201
        pago_id = r1.json()["id"]

        # Reversal con clave explicita
        rv = client.post(
            f"/api/pagos/{pago_id}/reversar?negocio_id={self.nid}",
            json={"motivo": "error"},
        )
        assert rv.status_code == 201, rv.text
        assert rv.json()["tipo"] == "REVERSAL"

        # Reversar de nuevo: devuelve el MISMO reversal (idempotente por
        # reversal_of_payment_id), nunca un PAYMENT
        rv2 = client.post(
            f"/api/pagos/{pago_id}/reversar?negocio_id={self.nid}",
            json={"motivo": "error"},
        )
        assert rv2.status_code == 201
        assert rv2.json()["id"] == rv.json()["id"]
        assert rv2.json()["tipo"] == "REVERSAL"
