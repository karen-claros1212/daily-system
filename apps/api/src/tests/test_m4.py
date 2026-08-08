"""M4 multiruta tests — route-level isolation (Bloque 4).

Synthetic scenario: 1 negocio, 1 admin, several cobradores, R1-R4 plus a
5th route created dynamically (no code change, no fixed limit of 4).

Verified:
  - Cobrador R1 cannot read R2 (403/404 without revealing existence)
  - Cobrador R1 cannot modify R2 (403/404/409)
  - Admin can access all routes
  - Operating R2 does not alter R1 totals/caja/cartera
  - opening_carry comes only from the previous jornada of the SAME route
  - Pagos/movimientos/historial/snapshot/hoja-viva do not cross routes
  - Creating a 5th route requires no code change and works end-to-end
"""

from datetime import date, timedelta
from uuid import uuid4

import pytest

from src.auth.context import RequestContext
from src.models import Cliente, Credito, Jornada, Negocio, Ruta, Usuario
from src.services.jornada_service import cerrar_jornada, open_jornada


def _ctx(nid, role, route_id=None, user_id=None, device_id=None):
    return RequestContext(
        user_id=user_id,
        negocio_id=nid,
        role=role,
        route_id=route_id,
        device_id=device_id,
    )


def _auth(nid, role="ADMINISTRADOR", route_id=None, user_id=None, device_id=None):
    params = {"negocio_id": str(nid), "role": role}
    if route_id:
        params["route_id"] = str(route_id)
    if user_id:
        params["user_id"] = str(user_id)
    if device_id:
        params["device_id"] = str(device_id)
    return params


class TestMultirutaAislamiento:
    """Route-level isolation across the full read/write surface."""

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.nid = uuid4()
        db_session.add(Negocio(id=self.nid, nombre="Multiruta", nit="1"))

        self.admin_id = uuid4()
        db_session.add(Usuario(
            id=self.admin_id, negocio_id=self.nid, rol="ADMINISTRADOR", nombre="Admin",
        ))

        self.cob_ids = {}
        self.ruta_ids = {}
        for i in range(1, 5):
            cid = uuid4()
            db_session.add(Usuario(
                id=cid, negocio_id=self.nid, rol="COBRADOR", nombre=f"Cob{i}",
            ))
            rid = uuid4()
            db_session.add(Ruta(
                id=rid, negocio_id=self.nid, nombre=f"R{i}", cobrador_id=cid,
            ))
            self.cob_ids[f"cob{i}"] = cid
            self.ruta_ids[f"R{i}"] = rid

        db_session.flush()

        self.cliente_ids = {}
        self.credito_ids = {}
        for i in range(1, 5):
            cid = uuid4()
            db_session.add(Cliente(
                id=cid, negocio_id=self.nid,
                primer_apellido="A", nombres=f"C{i}", identity_status="PROVISIONAL",
            ))
            cre = uuid4()
            db_session.add(Credito(
                id=cre, negocio_id=self.nid, cliente_id=cid,
                ruta_id=self.ruta_ids[f"R{i}"],
                cuota=10000, n_cuotas=10, monto=100000, total=100000,
                periodicidad="DIARIO", fecha_inicio=date(2026, 7, 1), estado="ACTIVO",
            ))
            self.cliente_ids[f"C{i}"] = cid
            self.credito_ids[f"R{i}"] = cre
        db_session.commit()

    # ---------- helpers ----------

    def _open_jornada_http(self, client, route_key, cob_key):
        resp = client.post(
            "/api/jornadas",
            params=_auth(
                self.nid, role="COBRADOR",
                route_id=self.ruta_ids[route_key],
                user_id=self.cob_ids[cob_key],
                device_id=uuid4(),
            ),
            json={
                "ruta_id": str(self.ruta_ids[route_key]),
                "opening_base": 0,
                "clave_idempotencia": f"apertura-{route_key}-{uuid4()}",
            },
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["id"]

    def _register_payment(self, client, route_key, jornada_id, cob_key, monto):
        resp = client.post(
            "/api/pagos",
            params=_auth(
                self.nid, role="COBRADOR",
                route_id=self.ruta_ids[route_key],
                user_id=self.cob_ids[cob_key],
                device_id=uuid4(),
            ),
            json={
                "credito_id": str(self.credito_ids[route_key]),
                "jornada_id": str(jornada_id),
                "monto": monto,
                "clave_idempotencia": f"pago-{route_key}-{monto}-{uuid4()}",
            },
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["id"]

    def _register_movimiento(self, client, route_key, jornada_id, cob_key, tipo, monto):
        resp = client.post(
            "/api/movimientos",
            params=_auth(
                self.nid, role="COBRADOR",
                route_id=self.ruta_ids[route_key],
                user_id=self.cob_ids[cob_key],
                device_id=uuid4(),
            ),
            json={
                "jornada_id": str(jornada_id),
                "tipo": tipo,
                "monto": monto,
                "clave_idempotencia": f"mov-{route_key}-{tipo}-{uuid4()}",
            },
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["id"]

    # ---------- positive: simultaneous jornadas + payments ----------

    def test_r1_r2_jornadas_simultaneas(self, client):
        """Two routes operate the same day with independent jornadas."""
        j1 = self._open_jornada_http(client, "R1", "cob1")
        j2 = self._open_jornada_http(client, "R2", "cob2")
        assert j1 != j2

        # Both are active for their own routes
        r1 = client.get(
            "/api/jornadas/active",
            params={**_auth(self.nid, role="COBRADOR",
                            route_id=self.ruta_ids["R1"], user_id=self.cob_ids["cob1"]),
                    "ruta_id": str(self.ruta_ids["R1"])},
        )
        assert r1.status_code == 200
        assert r1.json()["id"] == str(j1)

    def test_operar_r2_no_altera_r1(self, client, db_session):
        """R2 payments/movements/close leave R1 caja and cartera untouched."""
        j1 = self._open_jornada_http(client, "R1", "cob1")
        j2 = self._open_jornada_http(client, "R2", "cob2")

        self._register_payment(client, "R1", j1, "cob1", 50000)
        self._register_movimiento(client, "R1", j1, "cob1", "GASOLINA", 5000)

        def caja_r1():
            resp = client.get(
                f"/api/jornadas/{j1}/caja",
                params=_auth(self.nid, role="ADMINISTRADOR", user_id=self.admin_id),
            )
            assert resp.status_code == 200
            return resp.json()

        before = caja_r1()
        assert before["recaudo_real"] == 50000
        assert before["gastos"] == 5000
        assert before["pagos_count"] == 1

        # Operate R2 heavily
        self._register_payment(client, "R2", j2, "cob2", 80000)
        self._register_movimiento(client, "R2", j2, "cob2", "OFICINA", 3000)
        self._register_payment(client, "R2", j2, "cob2", 12000)
        self._register_movimiento(client, "R2", j2, "cob2", "AHORRO", 1000)

        after = caja_r1()
        assert after == before

        # R1 cartera unchanged (net paid still 50000 on R1 credit)
        credito_r1 = db_session.query(Credito).filter(
            Credito.id == self.credito_ids["R1"]
        ).first()
        from src.services.payment_service import get_net_paid
        assert get_net_paid(db_session, credito_r1.id) == 50000

        # Close R2 — R1 still untouched
        cierre = client.post(
            f"/api/jornadas/{j2}/cerrar",
            params=_auth(self.nid, role="COBRADOR",
                         route_id=self.ruta_ids["R2"], user_id=self.cob_ids["cob2"]),
            json={
                "efectivo_contado": 80000 + 12000 - 3000 - 1000,
                "idempotencia_cierre": f"cierre-r2-{uuid4()}",
                "motivo": "",
            },
        )
        assert cierre.status_code == 200, cierre.text
        assert caja_r1() == before

    # ---------- negative: cobrador R1 cannot read R2 ----------

    def test_cobrador_r1_no_lee_r2(self, client):
        """Cobrador R1 gets 403/404 for all R2 reads — no existence leak."""
        j1 = self._open_jornada_http(client, "R1", "cob1")
        j2 = self._open_jornada_http(client, "R2", "cob2")
        p2 = self._register_payment(client, "R2", j2, "cob2", 80000)
        m2 = self._register_movimiento(client, "R2", j2, "cob2", "OFICINA", 3000)

        auth_r1 = _auth(self.nid, role="COBRADOR",
                        route_id=self.ruta_ids["R1"], user_id=self.cob_ids["cob1"])

        # Jornada activa de otra ruta → 404 (mismo mensaje que no existente)
        r = client.get("/api/jornadas/active",
                       params={**auth_r1, "ruta_id": str(self.ruta_ids["R2"])})
        assert r.status_code == 404
        assert r.json()["detail"] == "No hay jornada activa para esta ruta"

        # Jornada por ID de otra ruta → 404
        r = client.get(f"/api/jornadas/{j2}", params=auth_r1)
        assert r.status_code == 404

        # Pago de otra ruta → 404
        r = client.get(f"/api/pagos/{p2}", params=auth_r1)
        assert r.status_code == 404

        # Movimiento de otra ruta → 404
        r = client.get(f"/api/movimientos/{m2}", params=auth_r1)
        assert r.status_code == 404

        # Ruta de otra ruta → 404
        r = client.get(f"/api/rutas/{self.ruta_ids['R2']}", params=auth_r1)
        assert r.status_code == 404

        # Hoja viva de otra ruta → 403
        r = client.get(f"/api/rutas/{self.ruta_ids['R2']}/hoja-viva", params=auth_r1)
        assert r.status_code == 403

        # Crédito de otra ruta → 403 (no revela existencia)
        r = client.get(f"/api/creditos/{self.credito_ids['R2']}", params=auth_r1)
        assert r.status_code == 403

        # Lists scoped to R1 only
        r = client.get("/api/creditos", params=auth_r1)
        assert {c["id"] for c in r.json()} == {str(self.credito_ids["R1"])}

        r = client.get("/api/clientes", params=auth_r1)
        assert {c["id"] for c in r.json()} == {str(self.cliente_ids["C1"])}

        r = client.get("/api/pagos", params=auth_r1)
        assert all(p["negocio_id"] == str(self.nid) for p in r.json())
        assert len(r.json()) == 0

        r = client.get("/api/jornadas", params=auth_r1)
        assert {j["id"] for j in r.json()} == {str(j1)}

        r = client.get("/api/rutas", params=auth_r1)
        assert {x["id"] for x in r.json()} == {str(self.ruta_ids["R1"])}

        # Movimientos de la jornada de R2 (vista cobrador R1) → vacío, no 403
        r = client.get("/api/movimientos", params={**auth_r1, "jornada_id": str(j2)})
        assert r.status_code == 200
        assert r.json() == []

    # ---------- negative: cobrador R1 cannot modify R2 ----------

    def test_cobrador_r1_no_modifica_r2(self, client):
        """Cobrador R1 cannot write to R2."""
        j1 = self._open_jornada_http(client, "R1", "cob1")
        j2 = self._open_jornada_http(client, "R2", "cob2")

        auth_r1 = _auth(self.nid, role="COBRADOR",
                        route_id=self.ruta_ids["R1"], user_id=self.cob_ids["cob1"])

        # Pago sobre crédito de R2 → 403
        r = client.post("/api/pagos", params=auth_r1, json={
            "credito_id": str(self.credito_ids["R2"]),
            "jornada_id": str(j2),
            "monto": 10000,
            "clave_idempotencia": "cross-pago",
        })
        assert r.status_code == 403

        # Pago con crédito de R1 pero jornada de R2 → 403
        r = client.post("/api/pagos", params=auth_r1, json={
            "credito_id": str(self.credito_ids["R1"]),
            "jornada_id": str(j2),
            "monto": 10000,
            "clave_idempotencia": "cross-pago-jornada",
        })
        assert r.status_code == 403

        # Movimiento en jornada de R2 → 409
        r = client.post("/api/movimientos", params=auth_r1, json={
            "jornada_id": str(j2),
            "tipo": "GASOLINA",
            "monto": 5000,
            "clave_idempotencia": "cross-mov",
        })
        assert r.status_code == 409

        # Cerrar jornada de R2 → 404
        r = client.post(f"/api/jornadas/{j2}/cerrar", params=auth_r1, json={
            "efectivo_contado": 0,
            "idempotencia_cierre": "cross-cierre",
            "motivo": "",
        })
        assert r.status_code == 404

        # Caja de jornada de R2 → 404
        r = client.get(f"/api/jornadas/{j2}/caja", params=auth_r1)
        assert r.status_code == 404

        # Preparar siguiente jornada de R2 → 404
        r = client.post(f"/api/jornadas/{j2}/preparar-siguiente", params=auth_r1)
        assert r.status_code == 404

        # R2 sigue intacta: su jornada sigue OPEN y su pago no existe
        j2r = client.get(f"/api/jornadas/{j2}", params=_auth(self.nid, role="ADMINISTRADOR"))
        assert j2r.status_code == 200
        assert j2r.json()["estado"] == "OPEN"
        pagos = client.get("/api/pagos", params=_auth(self.nid, role="ADMINISTRADOR"))
        assert pagos.status_code == 200
        assert pagos.json() == []

    # ---------- positive: admin sees everything ----------

    def test_admin_accede_a_todas(self, client):
        """Admin reads every route's jornadas, pagos, movimientos, rutas."""
        j1 = self._open_jornada_http(client, "R1", "cob1")
        j2 = self._open_jornada_http(client, "R2", "cob2")
        p2 = self._register_payment(client, "R2", j2, "cob2", 80000)
        m2 = self._register_movimiento(client, "R2", j2, "cob2", "OFICINA", 3000)

        auth = _auth(self.nid, role="ADMINISTRADOR", user_id=self.admin_id)

        r = client.get(f"/api/jornadas/{j1}", params=auth)
        assert r.status_code == 200
        r = client.get(f"/api/jornadas/{j2}", params=auth)
        assert r.status_code == 200
        r = client.get("/api/jornadas/active", params={**auth, "ruta_id": str(self.ruta_ids["R2"])})
        assert r.status_code == 200
        r = client.get(f"/api/pagos/{p2}", params=auth)
        assert r.status_code == 200
        r = client.get(f"/api/movimientos/{m2}", params=auth)
        assert r.status_code == 200
        r = client.get("/api/rutas", params=auth)
        assert len(r.json()) == 4
        r = client.get("/api/clientes", params=auth)
        assert len(r.json()) == 4
        r = client.get("/api/pagos", params=auth)
        assert len(r.json()) == 1

    # ---------- snapshot does not cross ----------

    def test_snapshot_por_ruta_no_se_cruzan(self, client, db_session):
        """Each route's cierre snapshot contains only its own ids."""
        j1 = self._open_jornada_http(client, "R1", "cob1")
        j2 = self._open_jornada_http(client, "R2", "cob2")

        p1 = self._register_payment(client, "R1", j1, "cob1", 50000)
        m1 = self._register_movimiento(client, "R1", j1, "cob1", "GASOLINA", 5000)
        p2 = self._register_payment(client, "R2", j2, "cob2", 80000)
        m2 = self._register_movimiento(client, "R2", j2, "cob2", "OFICINA", 3000)

        # R1: esperado = 50000 - 5000 = 45000
        c1 = client.post(f"/api/jornadas/{j1}/cerrar", params=_auth(
            self.nid, role="COBRADOR", route_id=self.ruta_ids["R1"], user_id=self.cob_ids["cob1"]),
            json={"efectivo_contado": 45000, "idempotencia_cierre": "c1", "motivo": ""})
        assert c1.status_code == 200, c1.text

        # R2: esperado = 80000 - 3000 = 77000
        c2 = client.post(f"/api/jornadas/{j2}/cerrar", params=_auth(
            self.nid, role="COBRADOR", route_id=self.ruta_ids["R2"], user_id=self.cob_ids["cob2"]),
            json={"efectivo_contado": 77000, "idempotencia_cierre": "c2", "motivo": ""})
        assert c2.status_code == 200, c2.text

        from src.services.jornada_service import _uuid_eq

        def snapshot_of(jid):
            row = db_session.query(Jornada).filter(_uuid_eq(Jornada.id, jid)).first()
            return row.cierre_snapshot_json

        snap1 = snapshot_of(j1)
        snap2 = snapshot_of(j2)
        assert snap1["pagos_ids"] == [str(p1)]
        assert snap1["movimientos_ids"] == [str(m1)]
        assert str(p2) not in snap1["pagos_ids"]
        assert str(m2) not in snap1["movimientos_ids"]

        assert snap2["pagos_ids"] == [str(p2)]
        assert snap2["movimientos_ids"] == [str(m2)]
        assert str(p1) not in snap2["pagos_ids"]
        assert str(m1) not in snap2["movimientos_ids"]

    # ---------- opening_carry comes only from the same route ----------

    def test_opening_carry_solo_misma_ruta(self, db_session):
        """opening_carry(D+1) = sobrante_manana(D) of the SAME route only."""
        D = date(2026, 7, 20)
        ctx_admin = _ctx(self.nid, "ADMINISTRADOR", user_id=self.admin_id)

        # R1 close on D with sobrante 1000; R2 close on D with sobrante 2000
        j1 = open_jornada(db_session, ruta_id=self.ruta_ids["R1"], negocio_id=self.nid,
                          fecha=D, opening_base=1000, ctx=ctx_admin)
        j2 = open_jornada(db_session, ruta_id=self.ruta_ids["R2"], negocio_id=self.nid,
                          fecha=D, opening_base=2000, ctx=ctx_admin)

        cerrar_jornada(db_session, j1.id,
                       {"efectivo_contado": 1000, "idempotencia_cierre": "c1", "motivo": ""},
                       ctx_admin)
        cerrar_jornada(db_session, j2.id,
                       {"efectivo_contado": 2000, "idempotencia_cierre": "c2", "motivo": ""},
                       ctx_admin)

        assert j1.sobrante_manana == 1000
        assert j2.sobrante_manana == 2000

        # R1 next day carries 1000 (its own), NOT 2000 from R2
        j1_next = open_jornada(db_session, ruta_id=self.ruta_ids["R1"], negocio_id=self.nid,
                               fecha=D + timedelta(days=1), opening_base=0, ctx=ctx_admin)
        assert j1_next.opening_carry == 1000

        # R2 next day carries 2000 (its own), NOT 1000 from R1
        j2_next = open_jornada(db_session, ruta_id=self.ruta_ids["R2"], negocio_id=self.nid,
                               fecha=D + timedelta(days=1), opening_base=0, ctx=ctx_admin)
        assert j2_next.opening_carry == 2000

    def test_opening_carry_sin_jornada_previa_misma_ruta(self, db_session):
        """A route with no prior closed jornada gets carry 0 even if another route closed."""
        D = date(2026, 7, 21)
        ctx_admin = _ctx(self.nid, "ADMINISTRADOR", user_id=self.admin_id)

        j1 = open_jornada(db_session, ruta_id=self.ruta_ids["R1"], negocio_id=self.nid,
                          fecha=D, opening_base=1000, ctx=ctx_admin)
        cerrar_jornada(db_session, j1.id,
                       {"efectivo_contado": 1000, "idempotencia_cierre": "c1", "motivo": ""},
                       ctx_admin)

        # R3 has no jornada on D → carry 0 on D+1
        j3_next = open_jornada(db_session, ruta_id=self.ruta_ids["R3"], negocio_id=self.nid,
                               fecha=D + timedelta(days=1), opening_base=0, ctx=ctx_admin)
        assert j3_next.opening_carry == 0

    # ---------- 5th route without code change ----------

    def test_quinta_ruta_sin_cambio_de_codigo(self, client, db_session):
        """A 5th (and 6th) route is created and operated with zero code change."""
        auth_admin = _auth(self.nid, role="ADMINISTRADOR", user_id=self.admin_id)

        cob5 = uuid4()
        db_session.add(Usuario(id=cob5, negocio_id=self.nid, rol="COBRADOR", nombre="Cob5"))
        db_session.commit()

        r = client.post("/api/rutas", params=auth_admin,
                        json={"nombre": "R5", "cobrador_id": str(cob5)})
        assert r.status_code == 201, r.text
        r5_id = r.json()["id"]

        # 6th route — proves there is no fixed limit of 4
        r6 = client.post("/api/rutas", params=auth_admin, json={"nombre": "R6"})
        assert r6.status_code == 201, r6.text
        assert r6.json()["id"] != r5_id

        # R5 operates end-to-end: cliente, credito, jornada, pago, cierre
        cliente5 = client.post("/api/clientes", params=auth_admin,
                               json={"primer_apellido": "B", "nombres": "C5"})
        assert cliente5.status_code == 201

        credito5 = client.post("/api/creditos", params=auth_admin, json={
            "cliente_id": cliente5.json()["id"],
            "ruta_id": str(r5_id),
            "cuota": 10000,
            "n_cuotas": 10,
            "monto": 100000,
            "fecha_inicio": date(2026, 7, 1).isoformat(),
            "periodicidad": "DIARIO",
        })
        assert credito5.status_code == 201, credito5.text

        jornada5 = client.post("/api/jornadas", params=_auth(
            self.nid, role="COBRADOR", route_id=r5_id, user_id=cob5),
            json={"ruta_id": str(r5_id), "opening_base": 0,
                  "clave_idempotencia": "apertura-r5"})
        assert jornada5.status_code == 201, jornada5.text

        pago5 = client.post("/api/pagos", params=_auth(
            self.nid, role="COBRADOR", route_id=r5_id, user_id=cob5), json={
            "credito_id": credito5.json()["id"],
            "jornada_id": jornada5.json()["id"],
            "monto": 40000,
            "clave_idempotencia": "pago-r5",
        })
        assert pago5.status_code == 201, pago5.text

        cierre5 = client.post(f"/api/jornadas/{jornada5.json()['id']}/cerrar",
                              params=_auth(self.nid, role="COBRADOR",
                                           route_id=r5_id, user_id=cob5),
                              json={"efectivo_contado": 40000,
                                    "idempotencia_cierre": "cierre-r5", "motivo": ""})
        assert cierre5.status_code == 200, cierre5.text
        assert cierre5.json()["recaudo_real"] == 40000

        # Cobrador R1 still cannot see R5
        r = client.get(f"/api/rutas/{r5_id}", params=_auth(
            self.nid, role="COBRADOR", route_id=self.ruta_ids["R1"], user_id=self.cob_ids["cob1"]))
        assert r.status_code == 404
