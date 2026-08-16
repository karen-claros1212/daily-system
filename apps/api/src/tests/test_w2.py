"""W2 — Backend tests para Cliente 360 (panel administrador).

Cobertura obligatoria:
  - /me capabilities: ADMIN clientes:ver+clientes:gestionar; COBRADOR
    clientes:ver (sin gestionar); INVERSIONISTA ninguna (PII protegida)
  - crear cliente (ADMIN) -> 201, todos los campos, identity PROVISIONAL
  - documento duplicado del negocio -> POSSIBLE_DUPLICATE
  - create invalido -> 422 (faltan campos / longitud)
  - listar: envelope {items,total,limit,offset}, busqueda q (apellido/nombres/
    documento), filtros tipo_documento/identity_status, paginacion
  - COBRADOR list scoped a su ruta (solo clientes con credito en su ruta)
  - INVERSIONISTA list/detail/create -> 403
  - detalle 360: creditos con saldo/mora/cuotas/pico + ruta/cobrador nombres,
    pagos_recientes y saldo_total (autoridad compartida con hoja viva)
  - COBRADOR detalle de cliente de otra ruta -> 404; de su ruta -> 200
  - PATCH edita (ADMIN) -> 200 + audit CLIENTE_EDITADO; campos de identidad
    -> 422 (extra=forbid); cliente inexistente -> 404; cross-tenant -> 404;
    COBRADOR -> 403
  - auditoria: CLIENTE_CREADO / CLIENTE_EDITADO, metadata sin PII
"""

import base64
import hashlib
from uuid import UUID, uuid4

import pytest

from src.auth.token import issue_token
from src.models import AuditLog, Dispositivo, Negocio, Ruta, Usuario


def _dispositivo(db_session, negocio_id, usuario_id):
    """Crear dispositivo ACTIVE para un usuario (para emitir JWT)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    private_key = ec.generate_private_key(ec.SECP256R1())
    der = private_key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    spki = base64.b64encode(der).decode("ascii")
    pk_hash = hashlib.sha256(der).hexdigest()

    dev_id = uuid4()
    db_session.add(Dispositivo(
        id=dev_id,
        negocio_id=negocio_id,
        usuario_id=usuario_id,
        public_key=spki,
        public_key_hash=pk_hash,
        estado="ACTIVE",
        version_asignacion=1,
    ))
    db_session.flush()
    return dev_id, spki, pk_hash


def _issue_token(negocio_id, usuario_id, dev_id, pk_hash):
    return issue_token(
        negocio_id=negocio_id,
        usuario_id=usuario_id,
        dispositivo_id=dev_id,
        public_key_hash=pk_hash,
        version_asignacion=1,
    )


# === fixtures ===


@pytest.fixture
def w2_negocio(db_session):
    nid = uuid4()
    db_session.add(Negocio(id=nid, nombre="W2 Test", nit="901", pais="CO", moneda="COP"))
    db_session.flush()
    return nid


@pytest.fixture
def w2_admin(db_session, w2_negocio):
    admin_id = uuid4()
    db_session.add(Usuario(id=admin_id, negocio_id=w2_negocio, rol="ADMINISTRADOR", nombre="Admin W2"))
    db_session.flush()
    return admin_id


@pytest.fixture
def auth_admin(w2_negocio, w2_admin):
    return {"negocio_id": str(w2_negocio), "role": "ADMINISTRADOR", "user_id": str(w2_admin)}


@pytest.fixture
def auth_inv(w2_negocio, db_session):
    inv_id = uuid4()
    db_session.add(Usuario(id=inv_id, negocio_id=w2_negocio, rol="INVERSIONISTA", nombre="Inv"))
    db_session.flush()
    return {"negocio_id": str(w2_negocio), "role": "INVERSIONISTA", "user_id": str(inv_id)}


@pytest.fixture
def auth_cobrador(w2_negocio, db_session):
    cob_id = uuid4()
    db_session.add(Usuario(id=cob_id, negocio_id=w2_negocio, rol="COBRADOR", nombre="Cob"))
    rid = uuid4()
    db_session.add(Ruta(id=rid, negocio_id=w2_negocio, nombre="Ruta Cob", cobrador_id=cob_id, activa=1))
    db_session.flush()
    return {"negocio_id": str(w2_negocio), "role": "COBRADOR", "user_id": str(cob_id), "route_id": str(rid)}


# === helpers ===


def _crear_cliente(client, auth, **campos):
    body = {
        "primer_apellido": "Perez",
        "nombres": "Juan",
        "tipo_documento": "CC",
        "documento_normalizado": "1010101010",
        "telefono_1": "3001112233",
        "ciudad": "Bogota",
    }
    body.update(campos)
    return client.post("/api/clientes", params=auth, json=body)


def _crear_credito(client, auth, cliente_id, ruta_id, **campos):
    body = {
        "cliente_id": str(cliente_id),
        "ruta_id": str(ruta_id),
        "cuota": 10000,
        "n_cuotas": 10,
        "monto": 100000,
        "fecha_inicio": "2026-07-01",
        "periodicidad": "DIARIO",
    }
    body.update(campos)
    return client.post("/api/creditos", params=auth, json=body)


# === H1 — capabilities W2 ===


class TestCapabilitiesW2:
    def test_admin_tiene_clientes(self, client, db_session, w2_negocio, w2_admin):
        dev_id, _, pk_hash = _dispositivo(db_session, w2_negocio, w2_admin)
        token = _issue_token(w2_negocio, w2_admin, dev_id, pk_hash)
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        caps = r.json()["capabilities"]
        assert "clientes:ver" in caps
        assert "clientes:gestionar" in caps

    def test_cobrador_tiene_clientes_ver_sin_gestionar(self, client, db_session, w2_negocio, auth_cobrador):
        cob_id = UUID(auth_cobrador["user_id"])
        dev_id, _, pk_hash = _dispositivo(db_session, w2_negocio, cob_id)
        token = _issue_token(w2_negocio, cob_id, dev_id, pk_hash)
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        caps = r.json()["capabilities"]
        assert "clientes:ver" in caps
        assert "clientes:gestionar" not in caps

    def test_inv_no_tiene_clientes(self, client, db_session, w2_negocio, auth_inv):
        inv_id = UUID(auth_inv["user_id"])
        dev_id, _, pk_hash = _dispositivo(db_session, w2_negocio, inv_id)
        token = _issue_token(w2_negocio, inv_id, dev_id, pk_hash)
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        caps = r.json()["capabilities"]
        assert "clientes:ver" not in caps
        assert "clientes:gestionar" not in caps


# === H2 — crear cliente ===


class TestCrearCliente:
    def test_crear_cliente_201_todos_los_campos(self, client, db_session, auth_admin):
        r = _crear_cliente(client, auth_admin, segundo_apellido="Gomez", telefono_2="3009998877",
                           direccion="Cra 1 #2-3", barrio="Centro", ocupacion="Comerciante")
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["identity_status"] == "PROVISIONAL"
        assert data["segundo_apellido"] == "Gomez"
        assert data["telefono_2"] == "3009998877"
        assert data["direccion"] == "Cra 1 #2-3"
        assert data["barrio"] == "Centro"
        assert data["ocupacion"] == "Comerciante"
        assert data["tipo_documento"] == "CC"

        audit = db_session.query(AuditLog).filter_by(action="CLIENTE_CREADO").first()
        assert audit is not None
        assert audit.entity_type == "CLIENTE"
        assert "documento" not in audit.metadata_col

    def test_crear_documento_duplicado_possible_duplicate(self, client, auth_admin):
        r1 = _crear_cliente(client, auth_admin)
        assert r1.status_code == 201
        r2 = _crear_cliente(client, auth_admin, nombres="Carlos")
        assert r2.status_code == 201
        assert r2.json()["identity_status"] == "POSSIBLE_DUPLICATE"

    def test_crear_cliente_422_sin_campos(self, client, auth_admin):
        r = client.post("/api/clientes", params=auth_admin, json={})
        assert r.status_code == 422
        r = _crear_cliente(client, auth_admin, primer_apellido="   ")
        assert r.status_code == 422

    def test_cobrador_no_crea(self, client, auth_cobrador):
        r = _crear_cliente(client, auth_cobrador)
        assert r.status_code == 403

    def test_inversionista_no_crea(self, client, auth_inv):
        r = _crear_cliente(client, auth_inv)
        assert r.status_code == 403


# === H3 — listar con busqueda/filtros/paginacion ===


class TestListarClientes:
    def _seed(self, client, auth_admin, auth_cobrador):
        c1 = _crear_cliente(client, auth_admin, documento_normalizado="DOC001", ciudad="Bogota")
        c2 = _crear_cliente(client, auth_admin, documento_normalizado="DOC002", primer_apellido="Rojas",
                            nombres="Maria", ciudad="Medellin")
        c3 = _crear_cliente(client, auth_admin, documento_normalizado="DOC003", primer_apellido="Lopez",
                            nombres="Ana", ciudad="Bogota", tipo_documento="NIT")
        c1_id = UUID(c1.json()["id"])
        c2_id = UUID(c2.json()["id"])
        c3_id = UUID(c3.json()["id"])
        # Credito de c1 en la ruta del cobrador; c2/c3 sin credito.
        ruta_id = UUID(auth_cobrador["route_id"])
        r1 = _crear_credito(client, auth_admin, c1_id, ruta_id)
        assert r1.status_code == 201, r1.text
        return c1_id, c2_id, c3_id

    def test_lista_paginada_admin(self, client, auth_admin, auth_cobrador):
        c1_id, c2_id, c3_id = self._seed(client, auth_admin, auth_cobrador)
        r = client.get("/api/clientes", params=auth_admin)
        assert r.status_code == 200
        data = r.json()
        assert set(data.keys()) == {"items", "total", "limit", "offset"}
        assert data["total"] == 3
        assert data["limit"] == 50
        assert data["offset"] == 0
        assert {item["id"] for item in data["items"]} == {str(c1_id), str(c2_id), str(c3_id)}
        por_id = {item["id"]: item for item in data["items"]}
        assert por_id[str(c1_id)]["creditos_activos"] == 1
        assert por_id[str(c2_id)]["creditos_activos"] == 0
        assert por_id[str(c1_id)]["documento_normalizado"] == "DOC001"

    def test_paginacion_limit_offset(self, client, auth_admin, auth_cobrador):
        self._seed(client, auth_admin, auth_cobrador)
        r = client.get("/api/clientes", params={**auth_admin, "limit": 2, "offset": 1})
        data = r.json()
        assert len(data["items"]) == 2
        assert data["total"] == 3
        r = client.get("/api/clientes", params={**auth_admin, "limit": 2, "offset": 2})
        assert len(r.json()["items"]) == 1

    def test_busqueda_por_nombre(self, client, auth_admin, auth_cobrador):
        c1_id, c2_id, c3_id = self._seed(client, auth_admin, auth_cobrador)
        r = client.get("/api/clientes", params={**auth_admin, "q": "ROJAS"})
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == str(c2_id)
        # documento tambien busca
        r = client.get("/api/clientes", params={**auth_admin, "q": "DOC001"})
        assert r.json()["total"] == 1
        assert r.json()["items"][0]["id"] == str(c1_id)

    def test_filtro_tipo_documento(self, client, auth_admin, auth_cobrador):
        c1_id, c2_id, c3_id = self._seed(client, auth_admin, auth_cobrador)
        r = client.get("/api/clientes", params={**auth_admin, "tipo_documento": "NIT"})
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == str(c3_id)

    def test_filtro_identity_status(self, client, auth_admin, auth_cobrador):
        self._seed(client, auth_admin, auth_cobrador)
        r = client.get("/api/clientes", params={**auth_admin, "identity_status": "POSSIBLE_DUPLICATE"})
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_cobrador_list_scoped_a_su_ruta(self, client, auth_admin, auth_cobrador):
        c1_id, c2_id, c3_id = self._seed(client, auth_admin, auth_cobrador)
        r = client.get("/api/clientes", params=auth_cobrador)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == str(c1_id)

    def test_inversionista_list_403(self, client, auth_inv):
        r = client.get("/api/clientes", params=auth_inv)
        assert r.status_code == 403

    def test_limit_invalido_422(self, client, auth_admin):
        r = client.get("/api/clientes", params={**auth_admin, "limit": 0})
        assert r.status_code == 422


# === H4 — detalle Cliente 360 ===


class TestDetalleCliente360:
    def _seed_con_pago(self, client_atomico, db_session, auth_admin, auth_cobrador):
        """Cliente con credito en la ruta del cobrador + un pago de 40000."""
        c = _crear_cliente(client_atomico, auth_admin)
        c_id = UUID(c.json()["id"])
        ruta_id = UUID(auth_cobrador["route_id"])
        cr = _crear_credito(client_atomico, auth_admin, c_id, ruta_id)
        cr_id = UUID(cr.json()["id"])
        p = client_atomico.post("/api/pagos", params=auth_cobrador, json={
            "credito_id": str(cr_id),
            "monto": 40000,
            "clave_idempotencia": "w2-pago-1",
        })
        assert p.status_code == 201, p.text
        return c_id, cr_id

    def test_detalle_360_admin(self, client_atomico, db_session, auth_admin, auth_cobrador):
        from datetime import date

        from src.services.hoja_viva_service import today_bogota

        c_id, cr_id = self._seed_con_pago(client_atomico, db_session, auth_admin, auth_cobrador)
        r = client_atomico.get(f"/api/clientes/{c_id}", params=auth_admin)
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == str(c_id)
        assert data["identity_status"] == "PROVISIONAL"
        # total = 10000 * 10 = 100000; pago 40000 -> saldo 60000
        assert data["saldo_total"] == 60000
        assert len(data["creditos"]) == 1
        credito = data["creditos"][0]
        assert credito["id"] == str(cr_id)
        assert credito["saldo"] == 60000
        mora_esperada = max((today_bogota() - date(2026, 7, 1)).days - 1 - 4, 0)
        assert credito["mora_legacy"] == mora_esperada
        assert credito["cuotas_pagadas"] == 4
        assert credito["pico"] == 0
        assert credito["ruta_nombre"] == "Ruta Cob"
        assert credito["cobrador_nombre"] == "Cob"
        assert len(data["pagos_recientes"]) == 1
        assert data["pagos_recientes"][0]["monto"] == 40000
        assert data["pagos_recientes"][0]["tipo"] == "PAYMENT"

    def test_detalle_cobrador_propia_ruta_200(self, client_atomico, db_session, auth_admin, auth_cobrador):
        c_id, cr_id = self._seed_con_pago(client_atomico, db_session, auth_admin, auth_cobrador)
        r = client_atomico.get(f"/api/clientes/{c_id}", params=auth_cobrador)
        assert r.status_code == 200
        assert r.json()["id"] == str(c_id)
        assert r.json()["saldo_total"] == 60000

    def test_detalle_cobrador_otra_ruta_404(self, client_atomico, db_session, auth_admin, auth_cobrador):
        c_id, cr_id = self._seed_con_pago(client_atomico, db_session, auth_admin, auth_cobrador)
        # Un cobrador de OTRA ruta no ve este cliente.
        otro_cob = uuid4()
        db_session.add(Usuario(id=otro_cob, negocio_id=UUID(auth_admin["negocio_id"]), rol="COBRADOR", nombre="Cob2"))
        otra_ruta = uuid4()
        db_session.add(Ruta(id=otra_ruta, negocio_id=UUID(auth_admin["negocio_id"]), nombre="Ruta2",
                            cobrador_id=otro_cob, activa=1))
        db_session.flush()
        auth_cob2 = {"negocio_id": auth_admin["negocio_id"], "role": "COBRADOR",
                     "user_id": str(otro_cob), "route_id": str(otra_ruta)}
        r = client_atomico.get(f"/api/clientes/{c_id}", params=auth_cob2)
        assert r.status_code == 404

    def test_detalle_inversionista_403(self, client, auth_inv):
        r = client.get("/api/clientes/11111111-1111-4111-8111-111111111111", params=auth_inv)
        assert r.status_code == 403

    def test_detalle_inexistente_404(self, client, auth_admin):
        r = client.get("/api/clientes/11111111-1111-4111-8111-111111111111", params=auth_admin)
        assert r.status_code == 404


# === H5 — editar cliente ===


class TestEditarCliente:
    def test_patch_edita_campos_editables(self, client, db_session, auth_admin):
        c = _crear_cliente(client, auth_admin)
        c_id = c.json()["id"]
        r = client.patch(f"/api/clientes/{c_id}", params=auth_admin, json={
            "primer_apellido": "Ramirez",
            "telefono_1": "3005556666",
            "ciudad": "Cali",
            "segundo_apellido": "",
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["primer_apellido"] == "Ramirez"
        assert data["telefono_1"] == "3005556666"
        assert data["ciudad"] == "Cali"
        assert data["segundo_apellido"] is None
        assert data["identity_status"] == "PROVISIONAL"

        audit = db_session.query(AuditLog).filter_by(action="CLIENTE_EDITADO").first()
        assert audit is not None
        assert audit.metadata_col["campos"] == ["ciudad", "primer_apellido", "segundo_apellido", "telefono_1"]

    def test_patch_campos_identidad_422(self, client, auth_admin):
        c = _crear_cliente(client, auth_admin)
        c_id = c.json()["id"]
        for campo, valor in (
            ("tipo_documento", "CE"),
            ("documento_normalizado", "999"),
            ("identity_status", "VERIFIED"),
        ):
            r = client.patch(f"/api/clientes/{c_id}", params=auth_admin, json={campo: valor})
            assert r.status_code == 422, f"{campo}: {r.status_code}"

    def test_patch_inexistente_404(self, client, auth_admin):
        r = client.patch("/api/clientes/11111111-1111-4111-8111-111111111111",
                         params=auth_admin, json={"ciudad": "X"})
        assert r.status_code == 404

    def test_patch_cobrador_403(self, client, auth_admin, auth_cobrador):
        c = _crear_cliente(client, auth_admin)
        c_id = c.json()["id"]
        r = client.patch(f"/api/clientes/{c_id}", params=auth_cobrador, json={"ciudad": "X"})
        assert r.status_code == 403


# === H6 — aislamiento de tenant ===


class TestTenantIsolation:
    def test_cross_tenant_list_vacio(self, client, db_session, auth_admin):
        _crear_cliente(client, auth_admin)
        otro_negocio = uuid4()
        db_session.add(Negocio(id=otro_negocio, nombre="Otro", nit="902", pais="CO", moneda="COP"))
        db_session.flush()
        r = client.get("/api/clientes", params={
            "negocio_id": str(otro_negocio), "role": "ADMINISTRADOR",
        })
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_cross_tenant_detail_404(self, client, db_session, auth_admin):
        c = _crear_cliente(client, auth_admin)
        c_id = c.json()["id"]
        otro_negocio = uuid4()
        db_session.add(Negocio(id=otro_negocio, nombre="Otro", nit="902", pais="CO", moneda="COP"))
        db_session.flush()
        r = client.get(f"/api/clientes/{c_id}", params={
            "negocio_id": str(otro_negocio), "role": "ADMINISTRADOR",
        })
        assert r.status_code == 404
