"""W6 — Cobranza: aging, mora, worklist, promise to pay."""

from uuid import uuid4
from datetime import date, timedelta

from src.models import (
    Cliente,
    Credito,
    CuotaProgramada,
    Negocio,
    PromesaPago,
    Ruta,
    Usuario,
)


def _auth(nid, role="ADMINISTRADOR", route_id=None, user_id=None):
    params = {"negocio_id": str(nid), "role": role}
    if route_id:
        params["route_id"] = str(route_id)
    if user_id:
        params["user_id"] = str(user_id)
    return params


def _setup(db_session, n_creditos=3, dias_mora_base=10):
    nid = uuid4()
    db_session.add(Negocio(id=nid, nombre="W6", nit="900000006"))
    admin = uuid4()
    db_session.add(Usuario(id=admin, negocio_id=nid, rol="ADMINISTRADOR", nombre="Admin W6"))
    cob = uuid4()
    db_session.add(Usuario(id=cob, negocio_id=nid, rol="COBRADOR", nombre="Cob W6"))
    inv = uuid4()
    db_session.add(Usuario(id=inv, negocio_id=nid, rol="INVERSIONISTA", nombre="Inv W6"))

    r1 = uuid4()
    db_session.add(Ruta(id=r1, negocio_id=nid, nombre="Ruta W6", cobrador_id=cob))

    creditos = []
    for i in range(n_creditos):
        cid = uuid4()
        clid = uuid4()
        db_session.add(Cliente(id=clid, negocio_id=nid, nombres=f"Cliente {i}", primer_apellido=f"Apel {i}"))
        creditos.append((cid, clid, i))
        db_session.add(Credito(
            id=cid, negocio_id=nid, cliente_id=clid, ruta_id=r1,
            cuota=10000, n_cuotas=30, total=300000, monto=10000,
            periodicidad="DIARIO", fecha_inicio=date.today() - timedelta(days=30 + i * 5),
            estado="ACTIVO",
        ))
        # Create cuotas with vencimientos in the past
        for j in range(1, 11):
            db_session.add(CuotaProgramada(
                id=uuid4(), negocio_id=nid, credito_id=cid,
                numero=j, fecha_vencimiento=date.today() - timedelta(days=30 + i * 5 - j),
                monto=10000, estado="PENDIENTE",
            ))

    db_session.commit()
    return {"nid": nid, "admin": admin, "cob": cob, "inv": inv, "r1": r1, "creditos": creditos}


class TestW6CobranzaWeb:
    """GET /api/cobranza/web — worklist con aging y prioridad."""

    def test_admin_worklist_envelope(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/cobranza/web?limit=50", params=_auth(s["nid"]))
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 3
        assert len(body["items"]) == 3
        item = body["items"][0]
        assert "days_past_due" in item
        assert "overdue_amount" in item
        assert "aging_bucket" in item
        assert "priority" in item
        assert "priority_score" in item
        assert "priority_factors" in item
        assert item["days_past_due"] > 0
        assert item["overdue_installments"] > 0

    def test_admin_filtro_bucket(self, client, db_session):
        s = _setup(db_session, dias_mora_base=20)
        r = client.get("/api/cobranza/web?bucket=16-30", params=_auth(s["nid"]))
        assert r.status_code == 200
        body = r.json()
        for item in body["items"]:
            assert item["aging_bucket"] == "16-30"

    def test_admin_sort_dpd_desc(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/cobranza/web?sort=days_past_due&order=desc", params=_auth(s["nid"]))
        assert r.status_code == 200
        body = r.json()
        dpds = [i["days_past_due"] for i in body["items"]]
        assert dpds == sorted(dpds, reverse=True)

    def test_admin_sort_invalido_422(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/cobranza/web?sort=invalido", params=_auth(s["nid"]))
        assert r.status_code == 422

    def test_admin_order_invalido_422(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/cobranza/web?order=invalido", params=_auth(s["nid"]))
        assert r.status_code == 422

    def test_cobrador_scoped(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/cobranza/web", params=_auth(s["nid"], role="COBRADOR", route_id=s["r1"], user_id=s["cob"]))
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 3

    def test_inversionista_pii(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/cobranza/web", params=_auth(s["nid"], role="INVERSIONISTA", user_id=s["inv"]))
        assert r.status_code == 200
        body = r.json()
        for item in body["items"]:
            assert item["cliente_nombre"] is None
            assert item["cliente_id"] is None


class TestW6Resumen:
    """GET /api/cobranza/resumen — KPIs + aging distribution."""

    def test_admin_resumen(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/cobranza/resumen", params=_auth(s["nid"]))
        assert r.status_code == 200
        body = r.json()
        assert "total_cartera" in body
        assert "total_vencido" in body
        assert "pct_vencido" in body
        assert "clientes_en_mora" in body
        assert "aging_distribution" in body
        assert body["total_cartera"] > 0
        assert body["total_vencido"] > 0
        assert body["clientes_en_mora"] > 0

    def test_cobrador_resumen_scoped(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/cobranza/resumen", params=_auth(s["nid"], role="COBRADOR", route_id=s["r1"], user_id=s["cob"]))
        assert r.status_code == 200
        body = r.json()
        assert body["total_cartera"] > 0


class TestW6Promesas:
    """Promise to Pay — crear, cumplir, incumplir, cancelar."""

    def test_admin_crear_promesa(self, client, db_session):
        s = _setup(db_session)
        cid = s["creditos"][0][0]
        r = client.post("/api/cobranza/promesas", json={
            "credito_id": str(cid),
            "amount": 50000,
            "promised_date": "2026-08-20",
            "nota": "Promesa de pago",
            "clave_idempotencia": "w6-prom-1",
        }, params=_auth(s["nid"]))
        assert r.status_code == 201
        body = r.json()
        assert body["estado"] == "ACTIVE"
        assert body["amount"] == 50000

    def test_admin_cumplir_promesa(self, client, db_session):
        s = _setup(db_session)
        cid = s["creditos"][0][0]
        r1 = client.post("/api/cobranza/promesas", json={
            "credito_id": str(cid), "amount": 50000,
            "promised_date": "2026-08-20", "clave_idempotencia": "w6-prom-2",
        }, params=_auth(s["nid"]))
        pid = r1.json()["id"]
        r2 = client.post(f"/api/cobranza/promesas/{pid}/cumplir", params=_auth(s["nid"]))
        assert r2.status_code == 200
        assert r2.json()["estado"] == "FULFILLED"

    def test_admin_incumplir_promesa(self, client, db_session):
        s = _setup(db_session)
        cid = s["creditos"][0][0]
        r1 = client.post("/api/cobranza/promesas", json={
            "credito_id": str(cid), "amount": 50000,
            "promised_date": "2026-08-20", "clave_idempotencia": "w6-prom-3",
        }, params=_auth(s["nid"]))
        pid = r1.json()["id"]
        r2 = client.post(f"/api/cobranza/promesas/{pid}/incumplir", params=_auth(s["nid"]))
        assert r2.status_code == 200
        assert r2.json()["estado"] == "BROKEN"

    def test_admin_cancelar_promesa(self, client, db_session):
        s = _setup(db_session)
        cid = s["creditos"][0][0]
        r1 = client.post("/api/cobranza/promesas", json={
            "credito_id": str(cid), "amount": 50000,
            "promised_date": "2026-08-20", "clave_idempotencia": "w6-prom-4",
        }, params=_auth(s["nid"]))
        pid = r1.json()["id"]
        r2 = client.post(f"/api/cobranza/promesas/{pid}/cancelar", params=_auth(s["nid"]))
        assert r2.status_code == 200
        assert r2.json()["estado"] == "CANCELLED"

    def test_promesa_estado_transicion_invalida_409(self, client, db_session):
        s = _setup(db_session)
        cid = s["creditos"][0][0]
        r1 = client.post("/api/cobranza/promesas", json={
            "credito_id": str(cid), "amount": 50000,
            "promised_date": "2026-08-20", "clave_idempotencia": "w6-prom-5",
        }, params=_auth(s["nid"]))
        pid = r1.json()["id"]
        client.post(f"/api/cobranza/promesas/{pid}/cumplir", params=_auth(s["nid"]))
        r2 = client.post(f"/api/cobranza/promesas/{pid}/cumplir", params=_auth(s["nid"]))
        assert r2.status_code == 409

    def test_cobrador_crear_promesa(self, client, db_session):
        s = _setup(db_session)
        cid = s["creditos"][0][0]
        r = client.post("/api/cobranza/promesas", json={
            "credito_id": str(cid), "amount": 30000,
            "promised_date": "2026-08-21", "clave_idempotencia": "w6-prom-6",
        }, params=_auth(s["nid"], role="COBRADOR", route_id=s["r1"], user_id=s["cob"]))
        assert r.status_code == 201
