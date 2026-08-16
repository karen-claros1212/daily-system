"""W3 — Backend tests para Cartera y Créditos (panel premium).

Cobertura obligatoria:
  - /me capabilities: ADMIN creditos:ver+creditos:gestionar; COBRADOR
    creditos:ver (sin gestionar); INVERSIONISTA conserva creditos:ver
    (read-only, sin gestionar)
  - POST crear (ADMIN) -> 201, total=cuota*n_cuotas, schedule generado,
    auditoria CREDITO_CREADO sin PII sensible; COBRADOR -> 403;
    INVERSIONISTA -> 403 (gap de seguridad cerrado); 422 invalido;
    ruta/cliente inexistentes -> 404
  - GET list: envelope {items,total,limit,offset}, busqueda q por nombre,
    filtros estado/ruta_id, paginacion, sort allowlist (+ saldo derivado)
  - COBRADOR list scoped a su ruta; ruta_id de otra ruta -> 404
  - INVERSIONISTA list/detail 200 read-only con cliente_nombre/cliente_id
    en None (PII minimizada) y financiero presente
  - GET /resumen: agregados scoped por rol (nunca calculados en el browser)
  - GET detalle: ADMIN tenant-wide con financiero+nombres; COBRADOR propia
    ruta 200 / otra ruta 404; inexistente/cross-tenant -> 404
"""

import base64
import hashlib
from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest

from src.auth.token import issue_token
from src.models import AuditLog, Credito, CuotaProgramada, Dispositivo, Negocio, Ruta, Usuario
from src.services.hoja_viva_service import today_bogota


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
def w3_negocio(db_session):
    nid = uuid4()
    db_session.add(Negocio(id=nid, nombre="W3 Test", nit="903", pais="CO", moneda="COP"))
    db_session.flush()
    return nid


@pytest.fixture
def w3_admin(db_session, w3_negocio):
    admin_id = uuid4()
    db_session.add(Usuario(id=admin_id, negocio_id=w3_negocio, rol="ADMINISTRADOR", nombre="Admin W3"))
    db_session.flush()
    return admin_id


@pytest.fixture
def auth_admin(w3_negocio, w3_admin):
    return {"negocio_id": str(w3_negocio), "role": "ADMINISTRADOR", "user_id": str(w3_admin)}


@pytest.fixture
def auth_inv(w3_negocio, db_session):
    inv_id = uuid4()
    db_session.add(Usuario(id=inv_id, negocio_id=w3_negocio, rol="INVERSIONISTA", nombre="Inv"))
    db_session.flush()
    return {"negocio_id": str(w3_negocio), "role": "INVERSIONISTA", "user_id": str(inv_id)}


@pytest.fixture
def auth_cobrador(w3_negocio, db_session):
    cob_id = uuid4()
    db_session.add(Usuario(id=cob_id, negocio_id=w3_negocio, rol="COBRADOR", nombre="Cob"))
    rid = uuid4()
    db_session.add(Ruta(id=rid, negocio_id=w3_negocio, nombre="Ruta Cob", cobrador_id=cob_id, activa=1))
    db_session.flush()
    return {"negocio_id": str(w3_negocio), "role": "COBRADOR", "user_id": str(cob_id), "route_id": str(rid)}


# === helpers ===


def _crear_cliente(client, auth, **campos):
    body = {
        "primer_apellido": "Perez",
        "nombres": "Juan",
        "tipo_documento": "CC",
        "documento_normalizado": "3030303030",
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
        "fecha_inicio": today_bogota().isoformat(),
        "periodicidad": "DIARIO",
    }
    body.update(campos)
    return client.post("/api/creditos", params=auth, json=body)


def _seed(client, auth_admin, auth_cobrador, db_session):
    """Cliente + credito en la ruta del cobrador. Devuelve (cliente_id, credito_id)."""
    c = _crear_cliente(client, auth_admin)
    c_id = UUID(c.json()["id"])
    ruta_id = UUID(auth_cobrador["route_id"])
    cr = _crear_credito(client, auth_admin, c_id, ruta_id)
    assert cr.status_code == 201, cr.text
    return c_id, UUID(cr.json()["id"])


# === H1 — capabilities W3 ===


class TestCapabilitiesW3:
    def test_admin_tiene_creditos_ver_y_gestionar(self, client, db_session, w3_negocio, w3_admin):
        dev_id, _, pk_hash = _dispositivo(db_session, w3_negocio, w3_admin)
        token = _issue_token(w3_negocio, w3_admin, dev_id, pk_hash)
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        caps = r.json()["capabilities"]
        assert "creditos:ver" in caps
        assert "creditos:gestionar" in caps

    def test_cobrador_tiene_creditos_ver_sin_gestionar(self, client, db_session, w3_negocio, auth_cobrador):
        cob_id = UUID(auth_cobrador["user_id"])
        dev_id, _, pk_hash = _dispositivo(db_session, w3_negocio, cob_id)
        token = _issue_token(w3_negocio, cob_id, dev_id, pk_hash)
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        caps = r.json()["capabilities"]
        assert "creditos:ver" in caps
        assert "creditos:gestionar" not in caps

    def test_inv_conserva_creditos_ver_read_only(self, client, db_session, w3_negocio, auth_inv):
        inv_id = UUID(auth_inv["user_id"])
        dev_id, _, pk_hash = _dispositivo(db_session, w3_negocio, inv_id)
        token = _issue_token(w3_negocio, inv_id, dev_id, pk_hash)
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        caps = r.json()["capabilities"]
        assert "creditos:ver" in caps
        assert "creditos:gestionar" not in caps


# === H2 — crear credito (solo ADMINISTRADOR) ===


class TestCrearCredito:
    def test_crear_201_schedule_total_y_audit(self, client, db_session, auth_admin, auth_cobrador):
        c_id, _ = _seed(client, auth_admin, auth_cobrador, db_session)
        ruta_id = UUID(auth_cobrador["route_id"])
        r = _crear_credito(client, auth_admin, c_id, ruta_id, fecha_inicio="2026-07-01")
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["total"] == 100000
        assert data["estado"] == "ACTIVO"
        assert data["periodicidad"] == "DIARIO"

        credito_id = UUID(data["id"])
        cuotas = db_session.query(CuotaProgramada).filter(
            CuotaProgramada.credito_id == credito_id,
        ).all()
        assert len(cuotas) == 10
        assert cuotas[0].monto == 10000

        audit = db_session.query(AuditLog).filter_by(action="CREDITO_CREADO").first()
        assert audit is not None
        assert audit.entity_type == "CREDITO"
        assert "documento" not in audit.metadata_col

    def test_crear_periodicidad_unica_una_cuota(self, client, auth_admin, auth_cobrador):
        c_id = UUID(_crear_cliente(client, auth_admin).json()["id"])
        ruta_id = UUID(auth_cobrador["route_id"])
        r = _crear_credito(client, auth_admin, c_id, ruta_id, periodicidad="UNICA", n_cuotas=1)
        assert r.status_code == 201, r.text

    def test_crear_422_invalido(self, client, auth_admin, auth_cobrador):
        c_id = UUID(_crear_cliente(client, auth_admin).json()["id"])
        ruta_id = UUID(auth_cobrador["route_id"])
        r = _crear_credito(client, auth_admin, c_id, ruta_id, cuota=0)
        assert r.status_code == 422
        r = _crear_credito(client, auth_admin, c_id, ruta_id, periodicidad="MENSUAL")
        assert r.status_code == 422

    def test_crear_cobrador_403(self, client, auth_admin, auth_cobrador):
        c_id = UUID(_crear_cliente(client, auth_admin).json()["id"])
        r = _crear_credito(client, auth_cobrador, c_id, UUID(auth_cobrador["route_id"]))
        assert r.status_code == 403

    def test_crear_inversionista_403(self, client, auth_admin, auth_cobrador, auth_inv):
        # Gap de seguridad cerrado: inversionista autenticado no origina.
        c_id = UUID(_crear_cliente(client, auth_admin).json()["id"])
        r = _crear_credito(client, auth_inv, c_id, UUID(auth_cobrador["route_id"]))
        assert r.status_code == 403

    def test_crear_cliente_inexistente_404(self, client, auth_admin, auth_cobrador):
        r = _crear_credito(client, auth_admin, uuid4(), UUID(auth_cobrador["route_id"]))
        assert r.status_code == 404

    def test_crear_ruta_inexistente_404(self, client, auth_admin, auth_cobrador):
        c_id = UUID(_crear_cliente(client, auth_admin).json()["id"])
        r = _crear_credito(client, auth_admin, c_id, uuid4())
        assert r.status_code == 404


# === H3 — listar read model (envelope/filtros/paginacion/sort) ===


class TestListarCreditos:
    def test_lista_paginada_admin(self, client, db_session, auth_admin, auth_cobrador):
        c1_id, _ = _seed(client, auth_admin, auth_cobrador, db_session)
        c2 = _crear_cliente(client, auth_admin, documento_normalizado="3030303031")
        r = _crear_credito(client, auth_admin, UUID(c2.json()["id"]), UUID(auth_cobrador["route_id"]),
                           cuota=5000, n_cuotas=6, monto=30000, fecha_inicio=(today_bogota() - timedelta(days=5)).isoformat())
        assert r.status_code == 201

        resp = client.get("/api/creditos", params=auth_admin)
        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) == {"items", "total", "limit", "offset"}
        assert data["total"] == 2
        assert data["limit"] == 50
        assert data["offset"] == 0
        por_id = {item["id"]: item for item in data["items"]}
        assert len(por_id) == 2
        item = por_id[str(r.json()["id"])]
        assert item["cliente_nombre"] == "Juan Perez"
        assert item["ruta_nombre"] == "Ruta Cob"
        assert item["cobrador_nombre"] == "Cob"
        assert item["saldo"] == item["total"]
        assert item["mora"] == 4  # 5 dias - 1 - 0 pagadas
        assert item["cuotas_pagadas"] == 0

    def test_paginacion_limit_offset(self, client, db_session, auth_admin, auth_cobrador):
        for i in range(3):
            c = _crear_cliente(client, auth_admin, documento_normalizado=f"3030{i}")
            r = _crear_credito(client, auth_admin, UUID(c.json()["id"]), UUID(auth_cobrador["route_id"]))
            assert r.status_code == 201
        r = client.get("/api/creditos", params={**auth_admin, "limit": 2, "offset": 1})
        data = r.json()
        assert len(data["items"]) == 2
        assert data["total"] == 3
        r = client.get("/api/creditos", params={**auth_admin, "limit": 2, "offset": 2})
        assert len(r.json()["items"]) == 1

    def test_busqueda_por_nombre(self, client, db_session, auth_admin, auth_cobrador):
        c1_id, cr1_id = _seed(client, auth_admin, auth_cobrador, db_session)
        c2 = _crear_cliente(client, auth_admin, primer_apellido="Rojas", nombres="Maria",
                            documento_normalizado="3030303040")
        r2 = _crear_credito(client, auth_admin, UUID(c2.json()["id"]), UUID(auth_cobrador["route_id"]))
        assert r2.status_code == 201

        r = client.get("/api/creditos", params={**auth_admin, "q": "ROJAS"})
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == r2.json()["id"]

    def test_filtro_estado_y_ruta(self, client, db_session, auth_admin, auth_cobrador):
        c1_id, cr1_id = _seed(client, auth_admin, auth_cobrador, db_session)
        otra_ruta = uuid4()
        db_session.add(Ruta(id=otra_ruta, negocio_id=UUID(auth_admin["negocio_id"]), nombre="Ruta B", activa=1))
        db_session.flush()
        c2 = _crear_cliente(client, auth_admin, documento_normalizado="3030303050")
        r2 = _crear_credito(client, auth_admin, UUID(c2.json()["id"]), otra_ruta)
        assert r2.status_code == 201

        r = client.get("/api/creditos", params={**auth_admin, "estado": "ACTIVO"})
        assert r.json()["total"] == 2
        r = client.get("/api/creditos", params={**auth_admin, "ruta_id": str(otra_ruta)})
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == r2.json()["id"]

    def test_sort_allowlist_y_saldo(self, client, db_session, auth_admin, auth_cobrador):
        c1_id, cr1_id = _seed(client, auth_admin, auth_cobrador, db_session)
        c2 = _crear_cliente(client, auth_admin, documento_normalizado="3030303060")
        r2 = _crear_credito(client, auth_admin, UUID(c2.json()["id"]), UUID(auth_cobrador["route_id"]),
                            cuota=50000, n_cuotas=4, monto=100000)
        assert r2.status_code == 201

        r = client.get("/api/creditos", params={**auth_admin, "sort": "saldo", "order": "desc"})
        data = r.json()
        assert data["items"][0]["id"] == r2.json()["id"]  # 200000 > 100000

        r = client.get("/api/creditos", params={**auth_admin, "sort": "saldo", "order": "asc"})
        assert r.json()["items"][0]["id"] == str(cr1_id)

        r = client.get("/api/creditos", params={**auth_admin, "sort": "nombre_cliente"})
        assert r.status_code == 422

    def test_cobrador_list_scoped_y_ruta_ajena_404(self, client, db_session, auth_admin, auth_cobrador):
        c1_id, cr1_id = _seed(client, auth_admin, auth_cobrador, db_session)
        otra_ruta = uuid4()
        db_session.add(Ruta(id=otra_ruta, negocio_id=UUID(auth_admin["negocio_id"]), nombre="Ruta C", activa=1))
        db_session.flush()
        c2 = _crear_cliente(client, auth_admin, documento_normalizado="3030303070")
        r2 = _crear_credito(client, auth_admin, UUID(c2.json()["id"]), otra_ruta)
        assert r2.status_code == 201

        r = client.get("/api/creditos", params=auth_cobrador)
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == str(cr1_id)

        # Filtrar por una ruta que no es la suya: 404 (no revelar existencia).
        r = client.get("/api/creditos", params={**auth_cobrador, "ruta_id": str(otra_ruta)})
        assert r.status_code == 404

    def test_inversionista_list_pii_minimizada(self, client, db_session, auth_admin, auth_cobrador, auth_inv):
        c1_id, cr1_id = _seed(client, auth_admin, auth_cobrador, db_session)
        r = client.get("/api/creditos", params=auth_inv)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        item = data["items"][0]
        assert item["id"] == str(cr1_id)
        assert item["cliente_nombre"] is None
        assert item["cliente_id"] is None
        # Autoridad financiera presente para el inversionista.
        assert item["saldo"] == 100000
        assert item["ruta_nombre"] == "Ruta Cob"
        assert item["estado"] == "ACTIVO"


# === H4 — resumen de cartera ===


class TestResumenCartera:
    def test_resumen_admin_con_pago(self, client_atomico, db_session, auth_admin, auth_cobrador):
        c = _crear_cliente(client_atomico, auth_admin)
        c_id = UUID(c.json()["id"])
        ruta_id = UUID(auth_cobrador["route_id"])
        cr = _crear_credito(client_atomico, auth_admin, c_id, ruta_id,
                            fecha_inicio=(today_bogota() - timedelta(days=10)).isoformat())
        assert cr.status_code == 201, cr.text
        cr1_id = UUID(cr.json()["id"])
        p = client_atomico.post("/api/pagos", params=auth_cobrador, json={
            "credito_id": str(cr1_id),
            "monto": 40000,
            "clave_idempotencia": "w3-pago-1",
        })
        assert p.status_code == 201, p.text

        r = client_atomico.get("/api/creditos/resumen", params=auth_admin)
        assert r.status_code == 200
        data = r.json()
        assert set(data.keys()) == {"total_creditos", "activos", "saldo_total_cartera", "en_mora"}
        assert data["total_creditos"] == 1
        assert data["activos"] == 1
        assert data["saldo_total_cartera"] == 60000
        assert data["en_mora"] == 1  # credito con mora_legacy > 0

    def test_resumen_scoped_cobrador(self, client, db_session, auth_admin, auth_cobrador):
        c1_id, cr1_id = _seed(client, auth_admin, auth_cobrador, db_session)
        r = client.get("/api/creditos/resumen", params=auth_cobrador)
        assert r.status_code == 200
        data = r.json()
        assert data["total_creditos"] == 1
        assert data["saldo_total_cartera"] == 100000

    def test_resumen_inversionista_read_only(self, client, db_session, auth_admin, auth_cobrador, auth_inv):
        c1_id, cr1_id = _seed(client, auth_admin, auth_cobrador, db_session)
        r = client.get("/api/creditos/resumen", params=auth_inv)
        assert r.status_code == 200
        assert r.json()["total_creditos"] == 1


# === H5 — detalle ===


class TestDetalleCredito:
    def test_detalle_admin(self, client, db_session, auth_admin, auth_cobrador):
        c_id, cr_id = _seed(client, auth_admin, auth_cobrador, db_session)
        r = client.get(f"/api/creditos/{cr_id}", params=auth_admin)
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == str(cr_id)
        assert data["cliente_nombre"] == "Juan Perez"
        assert data["ruta_nombre"] == "Ruta Cob"
        assert data["cobrador_nombre"] == "Cob"
        assert data["saldo"] == 100000
        assert data["cuotas_pagadas"] == 0

    def test_detalle_cobrador_propia_ruta_200(self, client, db_session, auth_admin, auth_cobrador):
        c_id, cr_id = _seed(client, auth_admin, auth_cobrador, db_session)
        r = client.get(f"/api/creditos/{cr_id}", params=auth_cobrador)
        assert r.status_code == 200
        assert r.json()["cliente_nombre"] == "Juan Perez"

    def test_detalle_cobrador_otra_ruta_404(self, client, db_session, auth_admin, auth_cobrador):
        c_id, cr_id = _seed(client, auth_admin, auth_cobrador, db_session)
        otro_cob = uuid4()
        db_session.add(Usuario(id=otro_cob, negocio_id=UUID(auth_admin["negocio_id"]), rol="COBRADOR", nombre="Cob2"))
        otra_ruta = uuid4()
        db_session.add(Ruta(id=otra_ruta, negocio_id=UUID(auth_admin["negocio_id"]), nombre="Ruta2",
                            cobrador_id=otro_cob, activa=1))
        db_session.flush()
        auth_cob2 = {"negocio_id": auth_admin["negocio_id"], "role": "COBRADOR",
                     "user_id": str(otro_cob), "route_id": str(otra_ruta)}
        r = client.get(f"/api/creditos/{cr_id}", params=auth_cob2)
        assert r.status_code == 404

    def test_detalle_inversionista_pii_minimizada(self, client, db_session, auth_admin, auth_cobrador, auth_inv):
        c_id, cr_id = _seed(client, auth_admin, auth_cobrador, db_session)
        r = client.get(f"/api/creditos/{cr_id}", params=auth_inv)
        assert r.status_code == 200
        data = r.json()
        assert data["cliente_nombre"] is None
        assert data["cliente_id"] is None
        assert data["saldo"] == 100000

    def test_detalle_inexistente_404(self, client, auth_admin):
        r = client.get(f"/api/creditos/{uuid4()}", params=auth_admin)
        assert r.status_code == 404

    def test_detalle_cross_tenant_404(self, client, db_session, auth_admin, auth_cobrador):
        c_id, cr_id = _seed(client, auth_admin, auth_cobrador, db_session)
        otro_negocio = uuid4()
        db_session.add(Negocio(id=otro_negocio, nombre="Otro", nit="904", pais="CO", moneda="COP"))
        db_session.flush()
        r = client.get(f"/api/creditos/{cr_id}", params={
            "negocio_id": str(otro_negocio), "role": "ADMINISTRADOR",
        })
        assert r.status_code == 404
