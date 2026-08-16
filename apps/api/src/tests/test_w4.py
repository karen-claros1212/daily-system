"""W4 — Rutas y Cobradores: read model, creación con 409 de dominio, S4.

Escenario sintético: 1 negocio, admin, 2 cobradores con R1/R2, un cobrador sin
ruta y una ruta sin cobrador.

Cubre el contrato W4:
  - GET /api/rutas devuelve envelope {items,total,limit,offset} con RutaListItem
    (ruta_id, cobrador_nombre resuelto) — no lista plana.
  - Filtros q/activa/cobrador_id (solo ADMIN), paginación, sort/order allowlist.
  - GET /api/rutas/resumen: conteos por estado, scoped por rol.
  - POST /api/rutas: validaciones 400 de dominio y 409 de conflicto
    (nombre duplicado, una sola ruta activa por cobrador).
  - S4: PATCH /api/rutas/{id}/reasignar R1→R2 mismo cobrador, bump de
    version_asignacion, R1 inactiva, provenance preservada.
  - Auditoría RUTA_CREADA / RUTA_REASIGNADA.
  - COBRADOR scoped a su ruta activa; INVERSIONISTA read-only.
"""

from uuid import UUID, uuid4

from src.models import AuditLog, Dispositivo, Negocio, Ruta, Usuario


def _auth(nid, role="ADMINISTRADOR", route_id=None, user_id=None, device_id=None):
    params = {"negocio_id": str(nid), "role": role}
    if route_id:
        params["route_id"] = str(route_id)
    if user_id:
        params["user_id"] = str(user_id)
    if device_id:
        params["device_id"] = str(device_id)
    return params


class TestW4ListadoReadModel:
    """GET /api/rutas: envelope + cobrador_nombre resuelto + filtros."""

    def _setup(self, db_session):
        nid = uuid4()
        db_session.add(Negocio(id=nid, nombre="W4", nit="41"))
        admin = uuid4()
        db_session.add(Usuario(id=admin, negocio_id=nid, rol="ADMINISTRADOR", nombre="Admin"))

        c1, c2 = uuid4(), uuid4()
        db_session.add(Usuario(id=c1, negocio_id=nid, rol="COBRADOR", nombre="Cob Uno"))
        db_session.add(Usuario(id=c2, negocio_id=nid, rol="COBRADOR", nombre="Cob Dos"))

        r1, r2 = uuid4(), uuid4()
        db_session.add(Ruta(id=r1, negocio_id=nid, nombre="Ruta Norte", cobrador_id=c1))
        db_session.add(Ruta(id=r2, negocio_id=nid, nombre="Ruta Sur", cobrador_id=c2))

        r_sin_cob = uuid4()
        db_session.add(Ruta(id=r_sin_cob, negocio_id=nid, nombre="Ruta Futura"))
        db_session.commit()
        return {"nid": nid, "admin": admin, "c1": c1, "c2": c2, "r1": r1, "r2": r2, "rs": r_sin_cob}

    def test_lista_envelope_con_nombre_cobrador(self, client, db_session):
        s = self._setup(db_session)
        r = client.get("/api/rutas", params=_auth(s["nid"]))
        assert r.status_code == 200
        body = r.json()
        assert set(body.keys()) == {"items", "total", "limit", "offset"}
        assert body["total"] == 3
        assert body["limit"] == 50
        assert body["offset"] == 0
        assert len(body["items"]) == 3
        ids = {i["ruta_id"] for i in body["items"]}
        assert ids == {str(s["r1"]), str(s["r2"]), str(s["rs"])}
        por_id = {i["ruta_id"]: i for i in body["items"]}
        assert por_id[str(s["r1"])]["cobrador_nombre"] == "Cob Uno"
        assert por_id[str(s["r2"])]["cobrador_nombre"] == "Cob Dos"
        assert por_id[str(s["rs"])]["cobrador_nombre"] is None
        assert "id" not in por_id[str(s["r1"])]

    def test_filtro_busqueda_nombre(self, client, db_session):
        s = self._setup(db_session)
        r = client.get("/api/rutas", params={**_auth(s["nid"]), "q": "Norte"})
        assert r.status_code == 200
        items = r.json()["items"]
        assert [i["nombre"] for i in items] == ["Ruta Norte"]

    def test_filtro_activa(self, client, db_session):
        s = self._setup(db_session)
        db_session.query(Ruta).filter(Ruta.id == s["r2"]).update({"activa": 0})
        db_session.commit()
        r = client.get("/api/rutas", params={**_auth(s["nid"]), "activa": 1})
        assert {i["ruta_id"] for i in r.json()["items"]} == {str(s["r1"]), str(s["rs"])}
        r2 = client.get("/api/rutas", params={**_auth(s["nid"]), "activa": 0})
        assert {i["ruta_id"] for i in r2.json()["items"]} == {str(s["r2"])}

    def test_filtro_cobrador_solo_admin(self, client, db_session):
        s = self._setup(db_session)
        r = client.get("/api/rutas", params={**_auth(s["nid"]), "cobrador_id": str(s["c1"])})
        assert r.status_code == 200
        assert [i["ruta_id"] for i in r.json()["items"]] == [str(s["r1"])]

    def test_sort_order_allowlist(self, client, db_session):
        s = self._setup(db_session)
        r = client.get("/api/rutas", params={**_auth(s["nid"]), "sort": "nombre", "order": "asc"})
        assert r.status_code == 200
        assert [i["nombre"] for i in r.json()["items"]] == ["Ruta Futura", "Ruta Norte", "Ruta Sur"]
        r_bad = client.get("/api/rutas", params={**_auth(s["nid"]), "sort": "cobrador_id;drop"})
        assert r_bad.status_code == 422
        r_bad2 = client.get("/api/rutas", params={**_auth(s["nid"]), "order": "desc;drop"})
        assert r_bad2.status_code == 422

    def test_paginacion(self, client, db_session):
        s = self._setup(db_session)
        r = client.get("/api/rutas", params={**_auth(s["nid"]), "limit": 2, "offset": 2})
        assert r.status_code == 200
        assert r.json()["total"] == 3
        assert len(r.json()["items"]) == 1
        assert r.json()["limit"] == 2
        assert r.json()["offset"] == 2

    def test_resumen(self, client, db_session):
        s = self._setup(db_session)
        db_session.query(Ruta).filter(Ruta.id == s["r2"]).update({"activa": 0})
        db_session.commit()
        r = client.get("/api/rutas/resumen", params=_auth(s["nid"]))
        assert r.status_code == 200
        assert r.json() == {"total_rutas": 3, "activas": 2, "inactivas": 1}


class TestW4Creacion:
    """POST /api/rutas: validaciones 400 + 409 de dominio + auditoría."""

    def _setup(self, db_session):
        nid = uuid4()
        db_session.add(Negocio(id=nid, nombre="W4C", nit="42"))
        admin = uuid4()
        db_session.add(Usuario(id=admin, negocio_id=nid, rol="ADMINISTRADOR", nombre="Admin"))
        cob = uuid4()
        db_session.add(Usuario(id=cob, negocio_id=nid, rol="COBRADOR", nombre="Cob Libre"))
        db_session.commit()
        return {"nid": nid, "admin": admin, "cob": cob}

    def test_crea_ruta_con_cobrador(self, client, db_session):
        s = self._setup(db_session)
        r = client.post("/api/rutas", params=_auth(s["nid"], user_id=s["admin"]),
                        json={"nombre": "Ruta Nueva", "cobrador_id": str(s["cob"])})
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["nombre"] == "Ruta Nueva"
        assert data["cobrador_id"] == str(s["cob"])
        assert data["cobrador_nombre"] == "Cob Libre"
        assert data["activa"] == 1
        assert data["version"] == 1

        audit = db_session.query(AuditLog).filter_by(
            action="RUTA_CREADA", entity_id=UUID(data["id"])
        ).first()
        assert audit is not None
        assert audit.actor_id == s["admin"]
        assert audit.entity_type == "RUTA"
        assert audit.metadata_col["nombre"] == "Ruta Nueva"

    def test_nombre_duplicado_409(self, client, db_session):
        s = self._setup(db_session)
        r1 = client.post("/api/rutas", params=_auth(s["nid"], user_id=s["admin"]),
                         json={"nombre": "Ruta A"})
        assert r1.status_code == 201, r1.text
        r2 = client.post("/api/rutas", params=_auth(s["nid"], user_id=s["admin"]),
                         json={"nombre": "Ruta A"})
        assert r2.status_code == 409
        assert "Ruta A" in r2.json()["detail"]

    def test_cobrador_ya_tiene_ruta_activa_409(self, client, db_session):
        s = self._setup(db_session)
        r1 = client.post("/api/rutas", params=_auth(s["nid"], user_id=s["admin"]),
                         json={"nombre": "Ruta Uno", "cobrador_id": str(s["cob"])})
        assert r1.status_code == 201, r1.text
        r2 = client.post("/api/rutas", params=_auth(s["nid"], user_id=s["admin"]),
                         json={"nombre": "Ruta Dos", "cobrador_id": str(s["cob"])})
        assert r2.status_code == 409

    def test_cobrador_inactivo_400(self, client, db_session):
        s = self._setup(db_session)
        db_session.query(Usuario).filter(Usuario.id == s["cob"]).update({"activo": 0})
        db_session.commit()
        r = client.post("/api/rutas", params=_auth(s["nid"], user_id=s["admin"]),
                        json={"nombre": "Ruta X", "cobrador_id": str(s["cob"])})
        assert r.status_code == 400

    def test_cobrador_otro_negocio_400(self, client, db_session):
        s = self._setup(db_session)
        otro_nid = uuid4()
        db_session.add(Negocio(id=otro_nid, nombre="Otro", nit="43"))
        otro_cob = uuid4()
        db_session.add(Usuario(id=otro_cob, negocio_id=otro_nid, rol="COBRADOR", nombre="Externo"))
        db_session.commit()
        r = client.post("/api/rutas", params=_auth(s["nid"], user_id=s["admin"]),
                        json={"nombre": "Ruta X", "cobrador_id": str(otro_cob)})
        assert r.status_code == 400

    def test_inversionista_no_crea_403(self, client, db_session):
        s = self._setup(db_session)
        inv = uuid4()
        db_session.add(Usuario(id=inv, negocio_id=s["nid"], rol="INVERSIONISTA", nombre="Inv"))
        db_session.commit()
        r = client.post("/api/rutas", params=_auth(s["nid"], role="INVERSIONISTA", user_id=inv),
                        json={"nombre": "Ruta X"})
        assert r.status_code == 403


class TestW4ScopesRol:
    """COBRADOR scoped a su ruta activa; INVERSIONISTA read-only."""

    def _setup(self, db_session):
        nid = uuid4()
        db_session.add(Negocio(id=nid, nombre="W4S", nit="44"))
        admin = uuid4()
        db_session.add(Usuario(id=admin, negocio_id=nid, rol="ADMINISTRADOR", nombre="Admin"))
        c1, c2 = uuid4(), uuid4()
        db_session.add(Usuario(id=c1, negocio_id=nid, rol="COBRADOR", nombre="Cob1"))
        db_session.add(Usuario(id=c2, negocio_id=nid, rol="COBRADOR", nombre="Cob2"))
        r1, r2 = uuid4(), uuid4()
        db_session.add(Ruta(id=r1, negocio_id=nid, nombre="R1", cobrador_id=c1))
        db_session.add(Ruta(id=r2, negocio_id=nid, nombre="R2", cobrador_id=c2))
        db_session.commit()
        return {"nid": nid, "admin": admin, "c1": c1, "c2": c2, "r1": r1, "r2": r2}

    def test_cobrador_solo_su_ruta(self, client, db_session):
        s = self._setup(db_session)
        r = client.get("/api/rutas", params=_auth(s["nid"], role="COBRADOR",
                                                  route_id=s["r1"], user_id=s["c1"]))
        assert r.status_code == 200
        assert [i["ruta_id"] for i in r.json()["items"]] == [str(s["r1"])]
        assert r.json()["total"] == 1

    def test_cobrador_resumen_scoped(self, client, db_session):
        s = self._setup(db_session)
        r = client.get("/api/rutas/resumen", params=_auth(s["nid"], role="COBRADOR",
                                                          route_id=s["r1"], user_id=s["c1"]))
        assert r.status_code == 200
        assert r.json() == {"total_rutas": 1, "activas": 1, "inactivas": 0}

    def test_cobrador_no_ve_ruta_ajena(self, client, db_session):
        s = self._setup(db_session)
        r = client.get(f"/api/rutas/{s['r2']}", params=_auth(s["nid"], role="COBRADOR",
                                                             route_id=s["r1"], user_id=s["c1"]))
        assert r.status_code == 404

    def test_cobrador_no_ve_ruta_inactiva(self, client, db_session):
        s = self._setup(db_session)
        db_session.query(Ruta).filter(Ruta.id == s["r1"]).update({"activa": 0})
        db_session.commit()
        r = client.get("/api/rutas", params=_auth(s["nid"], role="COBRADOR",
                                                  route_id=s["r1"], user_id=s["c1"]))
        assert r.status_code == 200
        assert r.json()["items"] == []
        r2 = client.get(f"/api/rutas/{s['r1']}", params=_auth(s["nid"], role="COBRADOR",
                                                              route_id=s["r1"], user_id=s["c1"]))
        assert r2.status_code == 404

    def test_inversionista_lee(self, client, db_session):
        s = self._setup(db_session)
        inv = uuid4()
        db_session.add(Usuario(id=inv, negocio_id=s["nid"], rol="INVERSIONISTA", nombre="Inv"))
        db_session.commit()
        auth = _auth(s["nid"], role="INVERSIONISTA", user_id=inv)
        r = client.get("/api/rutas", params=auth)
        assert r.status_code == 200
        assert r.json()["total"] == 2
        rs = client.get("/api/rutas/resumen", params=auth)
        assert rs.json()["total_rutas"] == 2
        det = client.get(f"/api/rutas/{s['r1']}", params=auth)
        assert det.status_code == 200
        assert det.json()["id"] == str(s["r1"])

    def test_inversionista_no_reasigna_403(self, client, db_session):
        s = self._setup(db_session)
        inv = uuid4()
        db_session.add(Usuario(id=inv, negocio_id=s["nid"], rol="INVERSIONISTA", nombre="Inv"))
        db_session.commit()
        r = client.patch(f"/api/rutas/{s['r1']}/reasignar",
                         params=_auth(s["nid"], role="INVERSIONISTA", user_id=inv),
                         json={"nombre": "R1-Nueva"})
        assert r.status_code == 403


class TestW4Reasignacion:
    """S4: R1→R2, bump de version_asignacion, R1 inactiva, auditoría."""

    def test_reasignacion_bump_y_auditoria(self, client, db_session):
        nid = uuid4()
        db_session.add(Negocio(id=nid, nombre="W4R", nit="45"))
        admin = uuid4()
        db_session.add(Usuario(id=admin, negocio_id=nid, rol="ADMINISTRADOR", nombre="Admin"))
        cob = uuid4()
        db_session.add(Usuario(id=cob, negocio_id=nid, rol="COBRADOR", nombre="Cob"))
        r1 = uuid4()
        db_session.add(Ruta(id=r1, negocio_id=nid, nombre="R1-Original", cobrador_id=cob, activa=1))
        dev = uuid4()
        db_session.add(Dispositivo(
            id=dev, negocio_id=nid, usuario_id=cob, estado="ACTIVE",
            version_asignacion=1, activo=1,
        ))
        db_session.commit()

        r = client.patch(f"/api/rutas/{r1}/reasignar",
                         params=_auth(nid, user_id=admin),
                         json={"nombre": "R2-Nueva"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ruta_anterior_id"] == str(r1)
        assert data["ruta_anterior_nombre"] == "R1-Original"
        assert data["ruta_nueva_id"] != str(r1)
        assert data["ruta_nueva_nombre"] == "R2-Nueva"
        assert data["cobrador_id"] == str(cob)
        assert data["version_asignacion"] == 2

        r1_row = db_session.get(Ruta, r1)
        assert r1_row.activa == 0
        assert r1_row.cobrador_id == cob
        r2_row = db_session.get(Ruta, UUID(data["ruta_nueva_id"]))
        assert r2_row.activa == 1
        assert r2_row.cobrador_id == cob
        dev_row = db_session.get(Dispositivo, dev)
        assert dev_row.version_asignacion == 2

        audit = db_session.query(AuditLog).filter_by(action="RUTA_REASIGNADA").first()
        assert audit is not None
        assert audit.actor_id == admin
        assert audit.metadata_col["ruta_anterior_id"] == str(r1)
        assert audit.metadata_col["ruta_nueva_id"] == data["ruta_nueva_id"]
        assert audit.metadata_col["version_asignacion"] == 2

        r3 = client.patch(f"/api/rutas/{data['ruta_nueva_id']}/reasignar",
                          params=_auth(nid, user_id=admin),
                          json={"nombre": "R3-Nueva"})
        assert r3.status_code == 200, r3.text
        assert r3.json()["version_asignacion"] == 3
        assert db_session.get(Ruta, r1).activa == 0
        assert db_session.get(Ruta, UUID(data["ruta_nueva_id"])).activa == 0
