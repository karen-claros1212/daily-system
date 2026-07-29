"""M1 advanced tests: reversal endpoint, idempotency 409, schedule, renewal."""

from datetime import date
from uuid import uuid4

from src.models import Negocio, Ruta, Cliente, Credito, Pago, Renovacion
from src.services.schedule_service import generate_schedule_for_id
from src.services.renewal_service import renew_credito


class TestReversalEndpoint:
    """Tests for POST /api/pagos/{id}/reversar."""

    def setup(self, db_session):
        self.nid = uuid4()
        self.rid = uuid4()
        self.cid = uuid4()
        self.credito_id = uuid4()

        db_session.add(Negocio(id=self.nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=self.rid, negocio_id=self.nid, nombre="R1"))
        db_session.add(Cliente(
            id=self.cid, negocio_id=self.nid,
            primer_apellido="X", nombres="Y", identity_status="PROVISIONAL",
        ))
        db_session.add(Credito(
            id=self.credito_id, negocio_id=self.nid, cliente_id=self.cid,
            ruta_id=self.rid, cuota=30000, n_cuotas=40, monto=1000000,
            total=1200000, periodicidad="DIARIO", fecha_inicio=date(2026, 7, 1),
            estado="ACTIVO",
        ))
        db_session.commit()

    def test_reversal_via_endpoint(self, client, db_session):
        """POST /api/pagos/{id}/reversar creates REVERSAL row."""
        self.setup(db_session)

        # Payment first
        p = client.post(
            f"/api/pagos?negocio_id={self.nid}",
            json={
                "credito_id": str(self.credito_id), "jornada_id": None,
                "monto": 30000, "clave_idempotencia": "rev-ep-001",
            },
        )
        assert p.status_code == 201
        pago_id = p.json()["id"]

        # Reversal
        r = client.post(
            f"/api/pagos/{pago_id}/reversar?negocio_id={self.nid}",
            json={"motivo": "Cliente no pagó"},
        )
        assert r.status_code == 201
        assert r.json()["tipo"] == "REVERSAL"

    def test_double_reversal_idempotent(self, client, db_session):
        """Reversing twice returns the same reversal."""
        self.setup(db_session)

        p = client.post(
            f"/api/pagos?negocio_id={self.nid}",
            json={
                "credito_id": str(self.credito_id), "jornada_id": None,
                "monto": 30000, "clave_idempotencia": "rev-ep-002",
            },
        )
        pago_id = p.json()["id"]

        r1 = client.post(
            f"/api/pagos/{pago_id}/reversar?negocio_id={self.nid}",
            json={"motivo": "Error"},
        )
        r2 = client.post(
            f"/api/pagos/{pago_id}/reversar?negocio_id={self.nid}",
            json={"motivo": "Error"},
        )
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["id"] == r2.json()["id"]

    def test_cannot_reverse_reversal(self, client, db_session):
        """POST /reversar on a REVERSAL row -> 400."""
        self.setup(db_session)

        p = client.post(
            f"/api/pagos?negocio_id={self.nid}",
            json={
                "credito_id": str(self.credito_id), "jornada_id": None,
                "monto": 30000, "clave_idempotencia": "rev-ep-003",
            },
        )
        pago_id = p.json()["id"]

        r = client.post(
            f"/api/pagos/{pago_id}/reversar?negocio_id={self.nid}",
            json={"motivo": "Error"},
        )
        rev_id = r.json()["id"]

        r2 = client.post(
            f"/api/pagos/{rev_id}/reversar?negocio_id={self.nid}",
            json={"motivo": "Re-reversión"},
        )
        assert r2.status_code == 400


class TestIdempotencyConflict:
    """Idempotency: same key + different payload -> 409."""

    def test_same_key_diff_payload_409(self, client, db_session):
        nid = uuid4()
        rid = uuid4()
        cid = uuid4()
        cr1 = uuid4()
        cr2 = uuid4()

        db_session.add(Negocio(id=nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=rid, negocio_id=nid, nombre="R1"))
        db_session.add(Cliente(
            id=cid, negocio_id=nid, primer_apellido="X",
            nombres="Y", identity_status="PROVISIONAL",
        ))
        db_session.add(Credito(
            id=cr1, negocio_id=nid, cliente_id=cid, ruta_id=rid,
            cuota=30000, n_cuotas=40, monto=1000000, total=1200000,
            periodicidad="DIARIO", fecha_inicio=date(2026, 7, 1), estado="ACTIVO",
        ))
        db_session.add(Credito(
            id=cr2, negocio_id=nid, cliente_id=cid, ruta_id=rid,
            cuota=50000, n_cuotas=20, monto=800000, total=1000000,
            periodicidad="DIARIO", fecha_inicio=date(2026, 7, 1), estado="ACTIVO",
        ))
        db_session.commit()

        # First payment with key
        r1 = client.post(
            f"/api/pagos?negocio_id={nid}",
            json={
                "credito_id": str(cr1), "jornada_id": None,
                "monto": 30000, "clave_idempotencia": "same-key-001",
            },
        )
        assert r1.status_code == 201

        # Same key, different credito -> 409
        r2 = client.post(
            f"/api/pagos?negocio_id={nid}",
            json={
                "credito_id": str(cr2), "jornada_id": None,
                "monto": 50000, "clave_idempotencia": "same-key-001",
            },
        )
        assert r2.status_code == 409


class TestScheduleGeneration:
    """Cuotas contractuales para DIARIO, SEMANAL, UNICA."""

    def _make_credito(self, db_session, nid, **kw):
        rid = uuid4()
        cid_cli = uuid4()
        db_session.add(Ruta(id=rid, negocio_id=nid, nombre="R"))
        db_session.add(Cliente(
            id=cid_cli, negocio_id=nid, primer_apellido="X",
            nombres="Y", identity_status="PROVISIONAL",
        ))
        cid = uuid4()
        db_session.add(Credito(
            id=cid, negocio_id=nid, cliente_id=cid_cli, ruta_id=rid,
            cuota=kw.get("cuota", 30000), n_cuotas=kw.get("n_cuotas", 40),
            monto=kw.get("monto", 1000000), total=kw.get("total", 1200000),
            periodicidad=kw.get("periodicidad", "DIARIO"),
            fecha_inicio=kw.get("fecha_inicio", date(2026, 7, 1)),
            estado="ACTIVO",
        ))
        db_session.commit()
        return cid

    def test_daily_schedule(self, db_session):
        nid = uuid4()
        db_session.add(Negocio(id=nid, nombre="N", nit="1"))
        db_session.commit()
        cid = self._make_credito(db_session, nid)

        cuotas = generate_schedule_for_id(db_session, cid)
        assert len(cuotas) == 40
        assert cuotas[0].monto == 30000
        assert cuotas[0].fecha_vencimiento == date(2026, 7, 1)

    def test_weekly_schedule(self, db_session):
        nid = uuid4()
        db_session.add(Negocio(id=nid, nombre="N", nit="1"))
        db_session.commit()
        cid = self._make_credito(db_session, nid,
            cuota=50000, n_cuotas=12, monto=500000, total=600000,
            periodicidad="SEMANAL")

        cuotas = generate_schedule_for_id(db_session, cid)
        assert len(cuotas) == 12  # exactly n_cuotas
        assert cuotas[1].fecha_vencimiento == date(2026, 7, 8)  # 1 week later

    def test_unica_schedule(self, db_session):
        nid = uuid4()
        db_session.add(Negocio(id=nid, nombre="N", nit="1"))
        db_session.commit()
        cid = self._make_credito(db_session, nid,
            cuota=600000, n_cuotas=1, monto=500000, total=600000,
            periodicidad="UNICA")

        cuotas = generate_schedule_for_id(db_session, cid)
        assert len(cuotas) == 1
        assert cuotas[0].monto == 600000  # total

    def test_idempotent_schedule(self, db_session):
        """Calling generate twice doesn't duplicate."""
        nid = uuid4()
        db_session.add(Negocio(id=nid, nombre="N", nit="1"))
        db_session.commit()
        cid = self._make_credito(db_session, nid)

        c1 = generate_schedule_for_id(db_session, cid)
        c2 = generate_schedule_for_id(db_session, cid)
        assert len(c1) == len(c2)


class TestVenceHoyReal:
    """VENCE_HOY with real cuota_programada data."""

    def test_vence_hoy_with_scheduled_cuotas(self, client, db_session):
        nid = uuid4()
        rid = uuid4()
        cid = uuid4()
        credito_id = uuid4()

        db_session.add(Negocio(id=nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=rid, negocio_id=nid, nombre="R1"))
        db_session.add(Cliente(
            id=cid, negocio_id=nid, primer_apellido="X",
            nombres="Y", identity_status="PROVISIONAL",
        ))
        db_session.add(Credito(
            id=credito_id, negocio_id=nid, cliente_id=cid, ruta_id=rid,
            cuota=30000, n_cuotas=40, monto=1000000, total=1200000,
            periodicidad="DIARIO", fecha_inicio=date.today(), estado="ACTIVO",
        ))
        db_session.commit()

        # Generate schedule
        cuotas = generate_schedule_for_id(db_session, credito_id)
        vencen_hoy = [c for c in cuotas if c.fecha_vencimiento == date.today()]
        assert len(vencen_hoy) >= 1  # at least one cuota due today

        resp = client.get(f"/api/rutas/{rid}/hoja-viva?negocio_id={nid}")
        assert resp.status_code == 200
        data = resp.json()
        # vence_hoy should reflect the scheduled cuotas
        assert data["cuotas_que_vencen_hoy"] >= 1
        assert data["vence_hoy_monto"] >= 30000


class TestRenewalTransaction:
    """End-to-end renewal transaction."""

    def test_renew_credito_flow(self, db_session):
        nid = uuid4()
        rid = uuid4()
        cid = uuid4()
        credito_id = uuid4()

        db_session.add(Negocio(id=nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=rid, negocio_id=nid, nombre="R1"))
        db_session.add(Cliente(
            id=cid, negocio_id=nid, primer_apellido="X",
            nombres="Y", identity_status="PROVISIONAL",
        ))
        db_session.add(Credito(
            id=credito_id, negocio_id=nid, cliente_id=cid, ruta_id=rid,
            cuota=30000, n_cuotas=40, monto=1000000, total=1200000,
            periodicidad="DIARIO", fecha_inicio=date(2026, 7, 1), estado="ACTIVO",
        ))
        db_session.commit()

        result = renew_credito(
            db=db_session,
            credito_id=credito_id,
            pago_efectivo=0,
            nueva_cuota=30000,
            nuevas_n_cuotas=45,
            nuevo_monto=1200000,
            nueva_periodicidad="DIARIO",
            recargo_pct=20,
        )

        assert result["credito_viejo_id"] is not None
        assert result["credito_nuevo_id"] is not None
        assert result["cuotas_generadas"] >= 40
        assert result["total_contractual"] == 1350000  # 30000 * 45

        from src.models import Credito as CreditoModel
        old = db_session.query(CreditoModel).filter(
            CreditoModel.id == credito_id
        ).first()
        assert old.estado == "REFINANCIADO"

        new = db_session.query(CreditoModel).filter(
            CreditoModel.id == result["credito_nuevo_id"]
        ).first()
        assert new.estado == "ACTIVO"
        assert new.origination_type == "RENEWAL"
        assert new.credito_anterior_id == credito_id
