"""M1 gate closure tests — schedule auto-generation, QUINCENAL, UNICA validation,
renewal with RequestContext, payment isolation, and traceability fields.
"""

from datetime import date
from uuid import uuid4

from src.models import Negocio, Ruta, Cliente, Credito, CuotaProgramada, Pago
from src.services.schedule_service import generate_schedule_for_id, validate_schedule
from src.services.renewal_service import renew_credito, RenewalNotFoundError, RenewalRouteError
from src.auth.context import RequestContext


class TestCreditoAutoGeneratesSchedule:
    """POST /api/creditos auto-generates its contractual schedule."""

    def test_create_credito_generates_schedule(self, client, db_session):
        """Creating a credit via API generates cuotas_programadas."""
        nid = uuid4()
        rid = uuid4()
        cid = uuid4()
        credito_id = uuid4()

        db_session.add(Negocio(id=nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=rid, negocio_id=nid, nombre="R1"))
        db_session.add(Cliente(
            id=cid, negocio_id=nid,
            primer_apellido="X", nombres="Y", identity_status="PROVISIONAL",
        ))
        db_session.commit()

        # Create credit via API
        resp = client.post(
            f"/api/creditos?negocio_id={nid}",
            json={
                "cliente_id": str(cid),
                "ruta_id": str(rid),
                "cuota": 30000,
                "n_cuotas": 40,
                "monto": 1000000,
                "fecha_inicio": date(2026, 7, 1).isoformat(),
                "periodicidad": "DIARIO",
            },
        )
        assert resp.status_code == 201

        # Verify schedule was generated via direct DB query
        from src.models import Credito as CreditoModel
        credito = db_session.query(CreditoModel).filter(
            CreditoModel.id == uuid4().__class__(resp.json()["id"])
        ).first()
        assert credito is not None

        cuotas = db_session.query(CuotaProgramada).filter(
            CuotaProgramada.credito_id == credito.id
        ).all()
        assert len(cuotas) == 40
        assert cuotas[0].monto == 30000

    def test_create_credito_generates_schedule_semanal(self, client, db_session):
        """SEMANAL credit generates weekly schedule."""
        nid = uuid4()
        rid = uuid4()
        cid = uuid4()

        db_session.add(Negocio(id=nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=rid, negocio_id=nid, nombre="R1"))
        db_session.add(Cliente(
            id=cid, negocio_id=nid,
            primer_apellido="X", nombres="Y", identity_status="PROVISIONAL",
        ))
        db_session.commit()

        resp = client.post(
            f"/api/creditos?negocio_id={nid}",
            json={
                "cliente_id": str(cid),
                "ruta_id": str(rid),
                "cuota": 50000,
                "n_cuotas": 12,
                "monto": 500000,
                "fecha_inicio": date(2026, 7, 1).isoformat(),
                "periodicidad": "SEMANAL",
            },
        )
        assert resp.status_code == 201

        from src.models import Credito as CreditoModel
        credito = db_session.query(CreditoModel).filter(
            CreditoModel.id == uuid4().__class__(resp.json()["id"])
        ).first()
        cuotas = db_session.query(CuotaProgramada).filter(
            CuotaProgramada.credito_id == credito.id
        ).all()
        assert len(cuotas) == 12


class TestScheduleValidation:
    """Schedule validation: UNICA n_cuotas=1, sum matches total."""

    def test_unica_requires_n_cuotas_1(self, db_session):
        """UNICA with n_cuotas != 1 raises ValueError."""
        nid = uuid4()
        rid = uuid4()
        cid = uuid4()

        db_session.add(Negocio(id=nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=rid, negocio_id=nid, nombre="R1"))
        db_session.add(Cliente(
            id=cid, negocio_id=nid,
            primer_apellido="X", nombres="Y", identity_status="PROVISIONAL",
        ))
        credito = Credito(
            id=uuid4(), negocio_id=nid, cliente_id=cid, ruta_id=rid,
            cuota=600000, n_cuotas=3, monto=500000, total=1800000,
            periodicidad="UNICA", fecha_inicio=date(2026, 7, 1), estado="ACTIVO",
        )
        db_session.add(credito)
        db_session.commit()

        from sqlalchemy.orm import Session as SessionType
        assert isinstance(db_session, SessionType)
        try:
            generate_schedule_for_id(db_session, credito.id)
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "n_cuotas=1" in str(e)

    def test_validate_schedule_returns_true_when_valid(self, db_session):
        """validate_schedule returns True when sum matches total."""
        nid = uuid4()
        rid = uuid4()
        cid = uuid4()

        db_session.add(Negocio(id=nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=rid, negocio_id=nid, nombre="R1"))
        db_session.add(Cliente(
            id=cid, negocio_id=nid,
            primer_apellido="X", nombres="Y", identity_status="PROVISIONAL",
        ))
        credito_id = uuid4()
        db_session.add(Credito(
            id=credito_id, negocio_id=nid, cliente_id=cid, ruta_id=rid,
            cuota=30000, n_cuotas=40, monto=1000000, total=1200000,
            periodicidad="DIARIO", fecha_inicio=date(2026, 7, 1), estado="ACTIVO",
        ))
        db_session.commit()

        generate_schedule_for_id(db_session, credito_id)
        assert validate_schedule(db_session, credito_id) is True

    def test_validate_schedule_returns_false_when_no_cuotas(self, db_session):
        """validate_schedule returns False when no cuotas exist."""
        nid = uuid4()
        db_session.add(Negocio(id=nid, nombre="N", nit="1"))
        db_session.commit()

        rid = uuid4()
        cid = uuid4()
        credito_id = uuid4()
        db_session.add(Ruta(id=rid, negocio_id=nid, nombre="R1"))
        db_session.add(Cliente(
            id=cid, negocio_id=nid,
            primer_apellido="X", nombres="Y", identity_status="PROVISIONAL",
        ))
        db_session.add(Credito(
            id=credito_id, negocio_id=nid, cliente_id=cid, ruta_id=rid,
            cuota=30000, n_cuotas=40, monto=1000000, total=1200000,
            periodicidad="DIARIO", fecha_inicio=date(2026, 7, 1), estado="ACTIVO",
        ))
        db_session.commit()

        assert validate_schedule(db_session, credito_id) is False


class TestQuincenalSchedule:
    """QUINCENAL schedule generation."""

    def test_quincenal_schedule(self, db_session):
        """QUINCENAL generates 14-day intervals."""
        nid = uuid4()
        db_session.add(Negocio(id=nid, nombre="N", nit="1"))
        db_session.commit()

        rid = uuid4()
        cid = uuid4()
        db_session.add(Ruta(id=rid, negocio_id=nid, nombre="R1"))
        db_session.add(Cliente(
            id=cid, negocio_id=nid,
            primer_apellido="X", nombres="Y", identity_status="PROVISIONAL",
        ))
        credito_id = uuid4()
        db_session.add(Credito(
            id=credito_id, negocio_id=nid, cliente_id=cid, ruta_id=rid,
            cuota=50000, n_cuotas=10, monto=400000, total=500000,
            periodicidad="QUINCENAL", fecha_inicio=date(2026, 7, 1), estado="ACTIVO",
        ))
        db_session.commit()

        cuotas = generate_schedule_for_id(db_session, credito_id)
        assert len(cuotas) == 10
        # Second cuota should be 14 days after first
        assert cuotas[1].fecha_vencimiento == date(2026, 7, 15)


class TestRenewalWithContext:
    """Renewal with RequestContext, PAYMENT registration, and idempotency."""

    def test_renewal_with_context_and_payment(self, db_session):
        """Renewal with RequestContext registers PAYMENT for pago_efectivo."""
        nid = uuid4()
        rid = uuid4()
        cid = uuid4()
        credito_id = uuid4()

        db_session.add(Negocio(id=nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=rid, negocio_id=nid, nombre="R1"))
        db_session.add(Cliente(
            id=cid, negocio_id=nid,
            primer_apellido="X", nombres="Y", identity_status="PROVISIONAL",
        ))
        db_session.add(Credito(
            id=credito_id, negocio_id=nid, cliente_id=cid, ruta_id=rid,
            cuota=30000, n_cuotas=40, monto=1000000, total=1200000,
            periodicidad="DIARIO", fecha_inicio=date(2026, 7, 1), estado="ACTIVO",
        ))
        db_session.commit()

        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=nid,
            role="COBRADOR",
            route_id=rid,
            device_id=uuid4(),
        )

        result = renew_credito(
            db=db_session,
            credito_id=credito_id,
            pago_efectivo=50000,
            nueva_cuota=30000,
            nuevas_n_cuotas=45,
            nuevo_monto=1200000,
            nueva_periodicidad="DIARIO",
            ctx=ctx,
            idempotency_key="renew-001",
        )

        assert result["credito_nuevo_id"] is not None
        assert result["cuotas_generadas"] >= 40

        # Verify PAYMENT was registered for pago_efectivo
        pagos = db_session.query(Pago).filter(
            Pago.credito_id == credito_id,
            Pago.tipo == "PAYMENT",
        ).all()
        assert len(pagos) >= 1
        assert any(p.monto == 50000 for p in pagos)

        # Verify old credit is RENFINANCIADO
        old = db_session.query(Credito).filter(
            Credito.id == credito_id
        ).first()
        assert old.estado == "REFINANCIADO"

    def test_renewal_context_route_validation(self, db_session):
        """Renewal raises RenewalRouteError when cobrador cannot access route."""
        nid = uuid4()
        r1 = uuid4()
        r2 = uuid4()
        cid = uuid4()
        credito_id = uuid4()

        db_session.add(Negocio(id=nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=r1, negocio_id=nid, nombre="R1"))
        db_session.add(Ruta(id=r2, negocio_id=nid, nombre="R2"))
        db_session.add(Cliente(
            id=cid, negocio_id=nid,
            primer_apellido="X", nombres="Y", identity_status="PROVISIONAL",
        ))
        db_session.add(Credito(
            id=credito_id, negocio_id=nid, cliente_id=cid, ruta_id=r1,
            cuota=30000, n_cuotas=40, monto=1000000, total=1200000,
            periodicidad="DIARIO", fecha_inicio=date(2026, 7, 1), estado="ACTIVO",
        ))
        db_session.commit()

        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=nid,
            role="COBRADOR",
            route_id=r2,  # cobrador on different route
            device_id=uuid4(),
        )

        try:
            renew_credito(
                db=db_session,
                credito_id=credito_id,
                pago_efectivo=0,
                nueva_cuota=30000,
                nuevas_n_cuotas=40,
                nuevo_monto=1200000,
                ctx=ctx,
            )
            assert False, "Expected RenewalRouteError"
        except RenewalRouteError:
            pass  # Expected

    def test_renewal_not_found(self, db_session):
        """Renewal raises RenewalNotFoundError for non-existent credit."""
        fake_id = uuid4()
        try:
            renew_credito(
                db=db_session,
                credito_id=fake_id,
                pago_efectivo=0,
                nueva_cuota=30000,
                nuevas_n_cuotas=40,
                nuevo_monto=1200000,
            )
            assert False, "Expected RenewalNotFoundError"
        except RenewalNotFoundError:
            pass  # Expected


class TestPaymentIsolation:
    """GET /pagos/{id} checks route for cobrador."""

    def test_get_payment_checks_route_for_cobrador(self, client, db_session):
        """Cobrador R1 cannot GET payment from R2 via direct ID."""
        nid = uuid4()
        r1 = uuid4()
        r2 = uuid4()
        cid = uuid4()
        cr1 = uuid4()
        cr2 = uuid4()

        db_session.add(Negocio(id=nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=r1, negocio_id=nid, nombre="R1"))
        db_session.add(Ruta(id=r2, negocio_id=nid, nombre="R2"))
        db_session.add(Cliente(
            id=cid, negocio_id=nid,
            primer_apellido="X", nombres="Y", identity_status="PROVISIONAL",
        ))
        db_session.add(Credito(
            id=cr1, negocio_id=nid, cliente_id=cid, ruta_id=r1,
            cuota=30000, n_cuotas=40, monto=1000000, total=1200000,
            periodicidad="DIARIO", fecha_inicio=date(2026, 7, 1), estado="ACTIVO",
        ))
        db_session.add(Credito(
            id=cr2, negocio_id=nid, cliente_id=cid, ruta_id=r2,
            cuota=50000, n_cuotas=20, monto=800000, total=1000000,
            periodicidad="DIARIO", fecha_inicio=date(2026, 7, 1), estado="ACTIVO",
        ))
        db_session.commit()

        # Payment on R2
        p = client.post(
            f"/api/pagos?negocio_id={nid}",
            json={
                "credito_id": str(cr2), "jornada_id": None,
                "monto": 30000, "clave_idempotencia": "iso-r2-001",
            },
        )
        assert p.status_code == 201
        pago_id = p.json()["id"]

        # Cobrador R1 tries to GET payment from R2
        resp = client.get(
            f"/api/pagos/{pago_id}?negocio_id={nid}&role=COBRADOR&route_id={r1}",
        )
        assert resp.status_code == 404

    def test_cobrador_can_get_own_route_payment(self, client, db_session):
        """Cobrador R1 can GET payment from their own route."""
        nid = uuid4()
        rid = uuid4()
        cid = uuid4()
        cr = uuid4()

        db_session.add(Negocio(id=nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=rid, negocio_id=nid, nombre="R1"))
        db_session.add(Cliente(
            id=cid, negocio_id=nid,
            primer_apellido="X", nombres="Y", identity_status="PROVISIONAL",
        ))
        db_session.add(Credito(
            id=cr, negocio_id=nid, cliente_id=cid, ruta_id=rid,
            cuota=30000, n_cuotas=40, monto=1000000, total=1200000,
            periodicidad="DIARIO", fecha_inicio=date(2026, 7, 1), estado="ACTIVO",
        ))
        db_session.commit()

        p = client.post(
            f"/api/pagos?negocio_id={nid}",
            json={
                "credito_id": str(cr), "jornada_id": None,
                "monto": 30000, "clave_idempotencia": "own-r-001",
            },
        )
        assert p.status_code == 201
        pago_id = p.json()["id"]

        resp = client.get(
            f"/api/pagos/{pago_id}?negocio_id={nid}&role=COBRADOR&route_id={rid}",
        )
        assert resp.status_code == 200

    def test_admin_gets_any_payment(self, client, db_session):
        """ADMIN can GET any payment in the negocio (no route filter)."""
        nid = uuid4()
        rid = uuid4()
        cid = uuid4()
        cr = uuid4()

        db_session.add(Negocio(id=nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=rid, negocio_id=nid, nombre="R1"))
        db_session.add(Cliente(
            id=cid, negocio_id=nid,
            primer_apellido="X", nombres="Y", identity_status="PROVISIONAL",
        ))
        db_session.add(Credito(
            id=cr, negocio_id=nid, cliente_id=cid, ruta_id=rid,
            cuota=30000, n_cuotas=40, monto=1000000, total=1200000,
            periodicidad="DIARIO", fecha_inicio=date(2026, 7, 1), estado="ACTIVO",
        ))
        db_session.commit()

        p = client.post(
            f"/api/pagos?negocio_id={nid}",
            json={
                "credito_id": str(cr), "jornada_id": None,
                "monto": 30000, "clave_idempotencia": "admin-001",
            },
        )
        assert p.status_code == 201
        pago_id = p.json()["id"]

        # ADMIN gets any payment
        resp = client.get(
            f"/api/pagos/{pago_id}?negocio_id={nid}&role=ADMINISTRADOR",
        )
        assert resp.status_code == 200


class TestPaymentTraceability:
    """Payments save cobrador_id, dispositivo_id, jornada_id."""

    def test_payment_saves_traceability_fields(self, client, db_session):
        """PAYMENT row includes cobrador_id, dispositivo_id, jornada_id."""
        nid = uuid4()
        rid = uuid4()
        cid = uuid4()
        cr = uuid4()
        jid = uuid4()

        db_session.add(Negocio(id=nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=rid, negocio_id=nid, nombre="R1"))
        db_session.add(Cliente(
            id=cid, negocio_id=nid,
            primer_apellido="X", nombres="Y", identity_status="PROVISIONAL",
        ))
        db_session.add(Credito(
            id=cr, negocio_id=nid, cliente_id=cid, ruta_id=rid,
            cuota=30000, n_cuotas=40, monto=1000000, total=1200000,
            periodicidad="DIARIO", fecha_inicio=date(2026, 7, 1), estado="ACTIVO",
        ))
        db_session.commit()

        cobrador_id = uuid4()
        device_id = uuid4()

        p = client.post(
            f"/api/pagos?negocio_id={nid}&role=COBRADOR&route_id={rid}&user_id={cobrador_id}&device_id={device_id}",
            json={
                "credito_id": str(cr),
                "jornada_id": str(jid),
                "monto": 30000,
                "clave_idempotencia": "trace-001",
            },
        )
        assert p.status_code == 201

        pago = db_session.query(Pago).filter(Pago.id == uuid4().__class__(p.json()["id"])).first()
        assert pago.cobrador_id == cobrador_id
        assert pago.dispositivo_id == device_id
        assert pago.jornada_id == jid

    def test_reversal_saves_traceability_fields(self, client, db_session):
        """REVERSAL row includes cobrador_id, dispositivo_id."""
        nid = uuid4()
        rid = uuid4()
        cid = uuid4()
        cr = uuid4()

        db_session.add(Negocio(id=nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=rid, negocio_id=nid, nombre="R1"))
        db_session.add(Cliente(
            id=cid, negocio_id=nid,
            primer_apellido="X", nombres="Y", identity_status="PROVISIONAL",
        ))
        db_session.add(Credito(
            id=cr, negocio_id=nid, cliente_id=cid, ruta_id=rid,
            cuota=30000, n_cuotas=40, monto=1000000, total=1200000,
            periodicidad="DIARIO", fecha_inicio=date(2026, 7, 1), estado="ACTIVO",
        ))
        db_session.commit()

        cobrador_id = uuid4()
        device_id = uuid4()

        p = client.post(
            f"/api/pagos?negocio_id={nid}&role=COBRADOR&route_id={rid}&user_id={cobrador_id}&device_id={device_id}",
            json={
                "credito_id": str(cr), "jornada_id": None,
                "monto": 30000, "clave_idempotencia": "rev-trace-001",
            },
        )
        assert p.status_code == 201
        pago_id = p.json()["id"]

        r = client.post(
            f"/api/pagos/{pago_id}/reversar?negocio_id={nid}&role=COBRADOR&route_id={rid}&user_id={cobrador_id}&device_id={device_id}",
            json={"motivo": "Error de cobro"},
        )
        assert r.status_code == 201

        reversal = db_session.query(Pago).filter(
            Pago.id == uuid4().__class__(r.json()["id"])
        ).first()
        assert reversal.cobrador_id == cobrador_id
        assert reversal.dispositivo_id == device_id
        assert reversal.tipo == "REVERSAL"
