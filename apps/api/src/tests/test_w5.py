"""W5 — Centro Financiero: movimientos web read-model + resumen."""

from uuid import uuid4
from datetime import datetime, timezone

from src.models import (
    Dispositivo,
    Jornada,
    MovimientoCaja,
    Negocio,
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


def _setup(db_session):
    nid = uuid4()
    db_session.add(Negocio(id=nid, nombre="W5", nit="900000001"))
    admin = uuid4()
    db_session.add(Usuario(id=admin, negocio_id=nid, rol="ADMINISTRADOR", nombre="Admin W5"))
    cob = uuid4()
    db_session.add(Usuario(id=cob, negocio_id=nid, rol="COBRADOR", nombre="Cob W5"))
    inv = uuid4()
    db_session.add(Usuario(id=inv, negocio_id=nid, rol="INVERSIONISTA", nombre="Inv W5"))

    r1 = uuid4()
    db_session.add(Ruta(id=r1, negocio_id=nid, nombre="Ruta W5", cobrador_id=cob))

    j1 = uuid4()
    db_session.add(Jornada(id=j1, negocio_id=nid, ruta_id=r1, estado="OPEN", opening_base=1000, fecha=datetime(2026, 8, 16, tzinfo=timezone.utc)))

    m1 = uuid4()
    db_session.add(MovimientoCaja(id=m1, negocio_id=nid, jornada_id=j1, tipo="GASOLINA", naturaleza="GASTO", monto=50000, nota="Gasolina ruta", clave_idempotencia="w5-1", creado_por=cob))
    m2 = uuid4()
    db_session.add(MovimientoCaja(id=m2, negocio_id=nid, jornada_id=j1, tipo="OFICINA", naturaleza="GASTO", monto=20000, nota="Material oficina", clave_idempotencia="w5-2", creado_por=cob))
    m3 = uuid4()
    db_session.add(MovimientoCaja(id=m3, negocio_id=nid, jornada_id=j1, tipo="RECIBIDO", naturaleza="CUENTA_POR_COBRAR", monto=100000, nota="Cobro cliente", clave_idempotencia="w5-3", creado_por=cob))
    db_session.commit()

    return {"nid": nid, "admin": admin, "cob": cob, "inv": inv, "r1": r1, "j1": j1, "m1": m1, "m2": m2, "m3": m3}


class TestW5MovimientosWeb:
    """GET /api/movimientos/web — envelope, filtros, sort, role scoping."""

    def test_admin_lista_envelope(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/movimientos/web", params={**_auth(s["nid"]), "limit": 50})
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 3
        assert len(body["items"]) == 3
        assert body["limit"] == 50
        assert body["offset"] == 0
        item = body["items"][0]
        assert "id" in item
        assert "tipo" in item
        assert "monto" in item
        assert "creado_por_nombre" in item
        assert item["creado_por_nombre"] == "Cob W5"
        assert item["ruta_nombre"] == "Ruta W5"

    def test_admin_filtro_tipo(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/movimientos/web", params={**_auth(s["nid"]), "tipo": "GASOLINA"})
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["tipo"] == "GASOLINA"

    def test_admin_filtro_naturaleza(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/movimientos/web", params={**_auth(s["nid"]), "naturaleza": "GASTO"})
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 2

    def test_admin_sort_monto_desc(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/movimientos/web", params={**_auth(s["nid"]), "sort": "monto", "order": "desc"})
        assert r.status_code == 200
        body = r.json()
        montos = [i["monto"] for i in body["items"]]
        assert montos == sorted(montos, reverse=True)

    def test_admin_sort_invalido_422(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/movimientos/web", params={**_auth(s["nid"]), "sort": "invalido"})
        assert r.status_code == 422

    def test_cobrador_scoped(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/movimientos/web", params=_auth(s["nid"], role="COBRADOR", route_id=s["r1"], user_id=s["cob"]))
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 3

    def test_inversionista_pii_minimizada(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/movimientos/web", params=_auth(s["nid"], role="INVERSIONISTA", user_id=s["inv"]))
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 3
        for item in body["items"]:
            assert item["creado_por_nombre"] is None

    def test_paginacion(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/movimientos/web", params={**_auth(s["nid"]), "limit": 2, "offset": 0})
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 3
        assert len(body["items"]) == 2
        assert body["limit"] == 2

        r2 = client.get("/api/movimientos/web", params={**_auth(s["nid"]), "limit": 2, "offset": 2})
        body2 = r2.json()
        assert len(body2["items"]) == 1


class TestW5Resumen:
    """GET /api/movimientos/resumen — agregados financieros."""

    def test_admin_resumen(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/movimientos/resumen", params=_auth(s["nid"]))
        assert r.status_code == 200
        body = r.json()
        assert body["total_movimientos"] == 3
        assert body["total_monto"] == 170000
        gastos = {g["tipo"]: g["total"] for g in body["gastos_por_tipo"]}
        assert gastos.get("GASOLINA") == 50000
        assert gastos.get("OFICINA") == 20000
        assert "RECIBIDO" not in gastos

    def test_cobrador_resumen_scoped(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/movimientos/resumen", params=_auth(s["nid"], role="COBRADOR", route_id=s["r1"], user_id=s["cob"]))
        assert r.status_code == 200
        body = r.json()
        assert body["total_movimientos"] == 3

    def test_inversionista_resumen(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/movimientos/resumen", params=_auth(s["nid"], role="INVERSIONISTA", user_id=s["inv"]))
        assert r.status_code == 200
        body = r.json()
        assert body["total_movimientos"] == 3
