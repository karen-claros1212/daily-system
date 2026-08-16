"""M5 activacion tests — Contrato de activacion (Bloque 6, revision 4).

Cubren las pruebas obligatorias del contrato seccion 8 aplicables al backend
(1-7, 10, 13) mas el vector JCS de la seccion 13.4, el gate admin del
dispositivo (seccion 10) y la concurrencia del canje. Las pruebas 8, 9, 11,
12 y 14 corresponden a reasignacion/config/movil y se cubren en sus bloques.

Estrategia:
- flujo completo por HTTP con pares EC P-256 reales (prueba de posesion real).
- firma construida con los bytes JCS exactos (RFC 8785) que produce el
  servidor, replicando lo que haria el cliente movil.
- concurrencia: canje del mismo intento desde 2 threads (requiere PostgreSQL,
  SELECT FOR UPDATE; se salta en SQLite).
"""

import base64
import hashlib
import threading
import uuid
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from src.models import (
    CodigoActivacion,
    Dispositivo,
    IntentoActivacion,
    Negocio,
    Ruta,
    Usuario,
)
from src.services.activacion_service import desafio
from src.services.auth_jcs import (
    PURPOSE_ISSUE_ACCESS_TOKEN,
)
from src.services.auth_jcs import (
    build_signed_payload as build_auth_payload,
)
from src.services.jcs import PROTOCOL_VERSION, build_signed_payload

# === helpers criptograficos ===


def _ec_keypair():
    """Genera un par EC P-256; devuelve (privada, spki_b64, sha256_spki_hex)."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    der = private_key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    spki = base64.b64encode(der).decode("ascii")
    return private_key, spki, hashlib.sha256(der).hexdigest()


def _sign(private_key, payload: bytes) -> str:
    sig = private_key.sign(payload, ec.ECDSA(hashes.SHA256()))
    return base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")


def _rfc3339(dt) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _auth(nid, role="ADMINISTRADOR", user_id=None):
    params = {"negocio_id": str(nid), "role": role}
    if user_id:
        params["user_id"] = str(user_id)
    return params


def _desafio(client, token, spki, modelo="Pixel 8", plataforma="android"):
    return client.post(
        "/api/activaciones/desafio",
        json={
            "token": token,
            "clave_publica": spki,
            "modelo": modelo,
            "plataforma": plataforma,
        },
    )


def _firma_valida(desafio_resp, private_key, pk_hash):
    """Reconstruye los bytes JCS exactos del intento y firma el nonce."""
    d = desafio_resp.json()
    payload = build_signed_payload(
        protocol_version=PROTOCOL_VERSION,
        environment=d["environment"],
        attempt_id=d["intento_id"],
        nonce=d["nonce"],
        public_key_hash=pk_hash,
        expires_at=d["expira_el"],
    )
    return d["intento_id"], _sign(private_key, payload)


def _firma_sobre_intento(intento, private_key, environment):
    """Firma el payload JCS directamente sobre el objeto IntentoActivacion."""
    payload = build_signed_payload(
        protocol_version=PROTOCOL_VERSION,
        environment=environment,
        attempt_id=str(intento.id),
        nonce=intento.nonce,
        public_key_hash=intento.public_key_hash,
        expires_at=_rfc3339(intento.expira_el),
    )
    return _sign(private_key, payload)


def _canje(client, intento_id, firma):
    return client.post(
        "/api/activaciones/canjear",
        json={"intento_id": intento_id, "firma": firma},
    )


def _flujo_completo(client, token, private_key, spki, pk_hash):
    """desafio + canje exitosos; devuelve la respuesta del canje."""
    r = _desafio(client, token, spki)
    assert r.status_code == 200, r.text
    intento_id, firma = _firma_valida(r, private_key, pk_hash)
    return _canje(client, intento_id, firma)


def _primer_jwt(client, credencial_bootstrap, dispositivo_id, private_key, pk_hash):
    """Primer JWT de sesion: desafio + canje autenticado con la credencial.

    La credencial bootstrap NO autentica el bootstrap productivo; su unica
    funcion post-canje es obtener el primer access token (D7-H2).
    """
    r = client.post(
        "/api/auth/device/desafio",
        headers={"Authorization": f"Bearer {credencial_bootstrap}"},
    )
    assert r.status_code == 200, r.text
    d = r.json()
    payload = build_auth_payload(
        purpose=PURPOSE_ISSUE_ACCESS_TOKEN,
        environment=d["environment"],
        challenge_id=d["challenge_id"],
        device_id=str(dispositivo_id),
        nonce=d["nonce"],
        public_key_hash=pk_hash,
        expires_at=d["expira_el"],
    )
    firma = _sign(private_key, payload)
    r = client.post(
        "/api/auth/device/canjear",
        json={"challenge_id": d["challenge_id"], "firma": firma},
    )
    assert r.status_code == 200, r.text
    return r.json()["token"]


# === fixtures ===


@pytest.fixture
def escenario(db_session):
    """Negocio + admin + cobrador + ruta activa (cobrador_id)."""
    nid = uuid4()
    db_session.add(Negocio(id=nid, nombre="Neg", nit="1"))

    admin_id = uuid4()
    db_session.add(Usuario(id=admin_id, negocio_id=nid, rol="ADMINISTRADOR", nombre="Admin"))

    cob_id = uuid4()
    db_session.add(Usuario(id=cob_id, negocio_id=nid, rol="COBRADOR", nombre="Cob"))

    r1_id = uuid4()
    db_session.add(Ruta(id=r1_id, negocio_id=nid, nombre="R1", cobrador_id=cob_id, activa=1))
    db_session.flush()
    return {
        "negocio_id": nid,
        "admin_id": admin_id,
        "cobrador_id": cob_id,
        "ruta_id": r1_id,
    }


def _emitir_codigo(client, escenario, cobrador_id=None, expira_minutos=10):
    r = client.post(
        "/api/activaciones/codigos",
        params=_auth(escenario["negocio_id"], role="ADMINISTRADOR", user_id=escenario["admin_id"]),
        json={
            "cobrador_id": str(cobrador_id or escenario["cobrador_id"]),
            "expira_minutos": expira_minutos,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


# === vector JCS (contrato 13.4) ===


class TestVectorJCS:
    def test_vector_jcs_13_4_bytes_exactos(self):
        """La salida JCS del payload congelado son los 285 bytes del contrato."""
        payload = build_signed_payload(
            protocol_version="daily-v1",
            environment="production",
            attempt_id="3f2a1b0c-9d4e-4f8a-b6c1-2d5e7a9b0c1d",
            nonce="GGcDkg5kNS7t1zK9JkXLPgq6QszvUdmYPMdfXSJHS_Q",
            public_key_hash="92561e1d2633d5b7680ebefd7f92bc3e4084708ffabf82073bf028a24a90f24b",
            expires_at="2026-08-06T15:00:00Z",
        )
        assert len(payload) == 285
        expected_hex = (
            "7b22617474656d70745f6964223a2233663261316230632d396434652d346638612d"
            "623663312d326435653761396230633164222c22656e7669726f6e6d656e74223a22"
            "70726f64756374696f6e222c22657870697265735f6174223a22323032362d30382d"
            "30365431353a30303a30305a222c226e6f6e6365223a22474763446b67356b4e5337"
            "74317a4b394a6b584c5067713651737a7655646d59504d646658534a48535f51222c"
            "2270726f746f636f6c5f76657273696f6e223a226461696c792d7631222c22707562"
            "6c69635f6b65795f68617368223a2239323536316531643236333364356237363830"
            "65626566643766393262633365343038343730386666616266383230373362663032"
            "3861323461393066323462227d"
        )
        assert payload.hex() == expected_hex

    def test_vector_jcs_rechaza_environment_invalido(self):
        with pytest.raises(ValueError):
            build_signed_payload(
                protocol_version="daily-v1",
                environment="produccion",
                attempt_id=str(uuid4()),
                nonce="x" * 43,
                public_key_hash="a" * 64,
                expires_at="2026-08-06T15:00:00Z",
            )

    def test_vector_jcs_rechaza_representacion_lexica_no_conforme(self):
        """La representacion lexical es vinculante: uuid/nonce/hash/timestamp exactos."""
        base = {
            "protocol_version": "daily-v1",
            "environment": "production",
            "attempt_id": "3f2a1b0c-9d4e-4f8a-b6c1-2d5e7a9b0c1d",
            "nonce": "GGcDkg5kNS7t1zK9JkXLPgq6QszvUdmYPMdfXSJHS_Q",
            "public_key_hash": "92561e1d2633d5b7680ebefd7f92bc3e4084708ffabf82073bf028a24a90f24b",
            "expires_at": "2026-08-06T15:00:00Z",
        }
        casos = [
            {"attempt_id": "3F2A1B0C-9D4E-4F8A-B6C1-2D5E7A9B0C1D"},  # UUID uppercase
            {"attempt_id": "no-es-un-uuid"},
            {"nonce": "x" * 42},  # 42 chars (debe ser 43)
            {"nonce": "GGcDkg5kNS7t1zK9JkXLPgq6QszvUdmYPMdfXSJHS_Q="},  # padding
            {"public_key_hash": "A" * 64},  # hex uppercase
            {"public_key_hash": "a" * 63},  # corto
            {"expires_at": "2026-08-06 15:00:00"},  # formato incorrecto
            {"expires_at": "2026-08-06T15:00:00.000Z"},  # con milisegundos
        ]
        for extra in casos:
            with pytest.raises(ValueError):
                build_signed_payload(**{**base, **extra})


# === flujo principal ===


class TestFlujoActivacion:
    def test_01_codigo_desafio_canje_bootstrap_solo_r1(self, client, db_session, escenario):
        """Admin emite codigo; D1 canjea con firma y obtiene bootstrap con SOLO R1.

        Ademas verifica el punto de la seccion 10: `usuario_id` del dispositivo
        es el cobrador derivado del codigo, nunca el solicitante/admin.
        """
        private_key, spki, pk_hash = _ec_keypair()
        codigo = _emitir_codigo(client, escenario)

        r = _flujo_completo(client, codigo["token"], private_key, spki, pk_hash)
        assert r.status_code == 200, r.text
        canje = r.json()
        assert canje["idempotente"] is False
        assert canje["cobrador_id"] == str(escenario["cobrador_id"])
        assert canje["negocio_id"] == str(escenario["negocio_id"])

        dev = db_session.query(Dispositivo).filter(Dispositivo.id == uuid.UUID(canje["dispositivo_id"])).first()
        assert dev is not None
        assert dev.estado == "ACTIVE"
        assert dev.usuario_id == escenario["cobrador_id"]
        assert dev.negocio_id == escenario["negocio_id"]
        assert dev.public_key_hash == pk_hash
        assert dev.algoritmo_clave == "EC_P256"
        assert dev.huella is None

        # Primer JWT de sesion (la credencial bootstrap autentica el desafio)
        jwt_token = _primer_jwt(
            client,
            canje["credencial_bootstrap"],
            canje["dispositivo_id"],
            private_key,
            pk_hash,
        )

        # Bootstrap productivo devuelve SOLO R1 + negocio/cobrador/versiones
        b = client.get(
            "/api/mobile/bootstrap",
            headers={"Authorization": f"Bearer {jwt_token}"},
        )
        assert b.status_code == 200, b.text
        data = b.json()
        assert data["ruta_id"] == str(escenario["ruta_id"])
        assert data["ruta_nombre"] == "R1"
        assert data["ruta_version"] == 1
        assert data["cobrador_id"] == str(escenario["cobrador_id"])
        assert data["cobrador_nombre"] == "Cob"
        assert data["dispositivo_id"] == str(canje["dispositivo_id"])
        assert data["version_asignacion"] == 1
        assert data["rol"] == "COBRADOR"
        assert data["negocio_id"] == str(escenario["negocio_id"])
        assert data["negocio_nombre"] == "Neg"

    def test_02_dispositivo_solo_r1_no_ve_r2(self, client, db_session, escenario):
        """D1 (bootstrap) y el cobrador solo ven/operan R1; R2 invisible."""
        cob2 = uuid4()
        db_session.add(Usuario(id=cob2, negocio_id=escenario["negocio_id"], rol="COBRADOR", nombre="Cob2"))
        r2_id = uuid4()
        db_session.add(Ruta(id=r2_id, negocio_id=escenario["negocio_id"], nombre="R2", cobrador_id=cob2, activa=1))
        db_session.flush()

        private_key, spki, pk_hash = _ec_keypair()
        codigo = _emitir_codigo(client, escenario)
        r = _flujo_completo(client, codigo["token"], private_key, spki, pk_hash)
        assert r.status_code == 200, r.text
        canje = r.json()
        jwt_token = _primer_jwt(
            client,
            canje["credencial_bootstrap"],
            canje["dispositivo_id"],
            private_key,
            pk_hash,
        )

        b = client.get("/api/mobile/bootstrap", headers={"Authorization": f"Bearer {jwt_token}"})
        assert b.json()["ruta_id"] == str(escenario["ruta_id"])

        # El cobrador autenticado (query-auth dev) solo lista su ruta
        rutas = client.get(
            "/api/rutas",
            params=_auth(escenario["negocio_id"], role="COBRADOR",
                         user_id=escenario["cobrador_id"])
            | {"route_id": str(escenario["ruta_id"])},
        )
        assert rutas.status_code == 200
        assert {x["ruta_id"] for x in rutas.json()["items"]} == {str(escenario["ruta_id"])}
        assert rutas.json()["total"] == 1

    def test_03_prueba_de_posesion_tercero_sin_privada(self, client, db_session, escenario):
        """Un tercero con el token pero SIN la privada del par es rechazado.

        Se presenta una clave publica arbitraria en el desafio y el canje se
        firma con OTRA clave: la firma no corresponde al par presentado -> 401.
        El codigo queda PENDING y no se crea ningun dispositivo.
        """
        _attacker, spki_presentada, _h = _ec_keypair()
        _third, _s, _pk = _ec_keypair()

        codigo = _emitir_codigo(client, escenario)
        r = _desafio(client, codigo["token"], spki_presentada)
        assert r.status_code == 200, r.text

        # Firma con la clave del tercero (no la del par presentado)
        _, firma = _firma_valida(r, _third, _pk)
        r2 = _canje(client, r.json()["intento_id"], firma)
        assert r2.status_code == 401
        assert "posesión" in r2.json()["detail"] or "no posee" in r2.json()["detail"]

        assert db_session.query(Dispositivo).count() == 0
        codigo_row = db_session.query(CodigoActivacion).first()
        assert codigo_row.estado == "PENDING"

    def test_04_desafio_no_consume_codigo(self, client, db_session, escenario):
        """Un desafio no crea dispositivo y NO consume el codigo (PENDING)."""
        _private_key, spki, _ = _ec_keypair()
        codigo = _emitir_codigo(client, escenario)

        r = _desafio(client, codigo["token"], spki)
        assert r.status_code == 200
        assert len(r.json()["nonce"]) == 43  # base64url sin padding, 32 bytes

        assert db_session.query(Dispositivo).count() == 0
        codigo_row = db_session.query(CodigoActivacion).first()
        assert codigo_row.estado == "PENDING"
        assert codigo_row.consumido_el is None

    def test_05_vencido_usado_y_agotado(self, client, db_session, escenario):
        """Token usado, token vencido, intento vencido e intentos_fallidos -> EXPIRED."""
        private_key, spki, pk_hash = _ec_keypair()
        codigo = _emitir_codigo(client, escenario)

        # (a) uso unico: tras consumir, un segundo desafio con el mismo token -> 409
        r = _flujo_completo(client, codigo["token"], private_key, spki, pk_hash)
        assert r.status_code == 200
        r2 = _desafio(client, codigo["token"], spki)
        assert r2.status_code == 409
        assert r2.json()["detail"] == "Codigo ya consumido"

        # (b) token vencido -> 409 EXPIRADO
        codigo2 = _emitir_codigo(client, escenario)
        fila = db_session.query(CodigoActivacion).filter(CodigoActivacion.prefijo == codigo2["prefijo"]).first()
        fila.expira_el = datetime.now(timezone.utc) - timedelta(minutes=1)
        db_session.flush()
        r3 = _desafio(client, codigo2["token"], spki)
        assert r3.status_code == 409
        assert r3.json()["detail"] == "Codigo expirado"

        # (c) intento vencido -> 410
        codigo3 = _emitir_codigo(client, escenario)
        rd = _desafio(client, codigo3["token"], spki)
        intento = db_session.query(IntentoActivacion).filter(
            IntentoActivacion.id == uuid.UUID(rd.json()["intento_id"])
        ).first()
        intento.expira_el = datetime.now(timezone.utc) - timedelta(minutes=1)
        db_session.flush()
        _, firma = _firma_valida(rd, private_key, pk_hash)
        r4 = _canje(client, rd.json()["intento_id"], firma)
        assert r4.status_code == 410
        assert r4.json()["detail"] == "Intento de activacion expirado"

        # (d) codigo manual: MAX_INTENTOS_FALLIDOS firmas invalidas -> EXPIRED
        from src.services.activacion_service import MAX_INTENTOS_FALLIDOS

        codigo4 = _emitir_codigo(client, escenario)
        wrong_key, _s, wrong_hash = _ec_keypair()
        for i in range(MAX_INTENTOS_FALLIDOS):
            rd2 = _desafio(client, codigo4["token"], spki)
            _, firma_wrong = _firma_valida(rd2, wrong_key, wrong_hash)
            r5 = _canje(client, rd2.json()["intento_id"], firma_wrong)
            assert r5.status_code == 401
        fila4 = db_session.query(CodigoActivacion).filter(CodigoActivacion.prefijo == codigo4["prefijo"]).first()
        assert fila4.estado == "EXPIRED"
        assert fila4.intentos_fallidos == MAX_INTENTOS_FALLIDOS
        r6 = _desafio(client, codigo4["token"], spki)
        assert r6.status_code == 409
        assert r6.json()["detail"] == "Codigo expirado"

    def test_06_revocar_invalida_token_y_bootstrap(self, client, db_session, escenario):
        """Revocar D1 -> su JWT de sesion deja de funcionar en el bootstrap (401)."""
        private_key, spki, pk_hash = _ec_keypair()
        codigo = _emitir_codigo(client, escenario)
        r = _flujo_completo(client, codigo["token"], private_key, spki, pk_hash)
        assert r.status_code == 200
        canje = r.json()
        cred = canje["credencial_bootstrap"]
        dev_id = canje["dispositivo_id"]
        jwt_token = _primer_jwt(client, cred, dev_id, private_key, pk_hash)

        b = client.get("/api/mobile/bootstrap", headers={"Authorization": f"Bearer {jwt_token}"})
        assert b.status_code == 200

        resp = client.post(
            f"/api/dispositivos/{dev_id}/revocar",
            params=_auth(escenario["negocio_id"], role="ADMINISTRADOR", user_id=escenario["admin_id"]),
        )
        assert resp.status_code == 200

        dev = db_session.query(Dispositivo).filter(Dispositivo.id == uuid.UUID(dev_id)).first()
        assert dev.estado == "REVOKED"

        # El JWT muere por el bump de version_asignacion
        b2 = client.get("/api/mobile/bootstrap", headers={"Authorization": f"Bearer {jwt_token}"})
        assert b2.status_code == 401

        # La credencial bootstrap tampoco autentica el bootstrap productivo
        b3 = client.get("/api/mobile/bootstrap", headers={"Authorization": f"Bearer {cred}"})
        assert b3.status_code == 401

    def test_07_reemplazo_d1_d2_historia_conservada(self, client, db_session, escenario):
        """Reemplazo D1->D2: D1 REPLACED, D2 ACTIVE, historia de D1 conservada."""
        private_key, spki, pk_hash = _ec_keypair()
        codigo = _emitir_codigo(client, escenario)
        r = _flujo_completo(client, codigo["token"], private_key, spki, pk_hash)
        assert r.status_code == 200
        d1_id = r.json()["dispositivo_id"]

        # Admin reemplaza: D1 -> REPLACED, nuevo codigo emitido
        resp = client.post(
            f"/api/dispositivos/{d1_id}/reemplazar",
            params=_auth(escenario["negocio_id"], role="ADMINISTRADOR", user_id=escenario["admin_id"]),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["dispositivo"]["estado"] == "REPLACED"
        nuevo_token = data["nuevo_codigo"]["token"]
        for campo in ("huella", "public_key_hash", "algoritmo_clave", "negocio_id", "autorizado_por"):
            assert campo not in data["dispositivo"], f"reemplazo no filtra {campo}"

        d1 = db_session.query(Dispositivo).filter(Dispositivo.id == uuid.UUID(d1_id)).first()
        assert d1.estado == "REPLACED"
        assert d1.activo == 0
        # historia conservada: fila intacta, mismo negocio/cobrador
        assert d1.negocio_id == escenario["negocio_id"]
        assert d1.usuario_id == escenario["cobrador_id"]
        assert d1.public_key_hash == pk_hash

        # D2 nace ACTIVE con el nuevo codigo
        key2, spki2, hash2 = _ec_keypair()
        r2 = _flujo_completo(client, nuevo_token, key2, spki2, hash2)
        assert r2.status_code == 200, r2.text
        d2 = db_session.query(Dispositivo).filter(Dispositivo.id == uuid.UUID(r2.json()["dispositivo_id"])).first()
        assert d2.estado == "ACTIVE"
        assert d2.id != d1_id
        assert d2.usuario_id == escenario["cobrador_id"]

        activos = (
            db_session.query(Dispositivo)
            .filter(Dispositivo.estado == "ACTIVE")
            .count()
        )
        assert activos == 1

    def test_08_reactivar_conflicto_otro_activo_409(self, client, db_session, escenario):
        """Reactivar un REVOKED cuando el cobrador ya tiene otro ACTIVE -> 409.

        RBAC review: la invariante "un ACTIVE por cobrador" se verifica
        explicitamente (409 controlado), no por crash del indice unico parcial
        (uq_dispositivo_activo_cobrador -> 500). Camino canonico: reemplazar.
        """
        private_key, spki, pk_hash = _ec_keypair()
        codigo = _emitir_codigo(client, escenario)
        r = _flujo_completo(client, codigo["token"], private_key, spki, pk_hash)
        assert r.status_code == 200
        d1_id = r.json()["dispositivo_id"]

        # Dispositivo REVOKED del MISMO cobrador (historia previa)
        d2_id = uuid4()
        db_session.add(
            Dispositivo(
                id=d2_id,
                negocio_id=escenario["negocio_id"],
                usuario_id=escenario["cobrador_id"],
                estado="REVOKED",
                activo=0,
                revocado_el=datetime.now(timezone.utc),
                version_asignacion=1,
            )
        )
        db_session.flush()

        params = _auth(escenario["negocio_id"], role="ADMINISTRADOR", user_id=escenario["admin_id"])

        # D1 sigue ACTIVE -> reactivar D2 colisiona -> 409 (no 500)
        resp = client.post(f"/api/dispositivos/{d2_id}/reactivar", params=params)
        assert resp.status_code == 409, resp.text
        assert "ACTIVE" in resp.json()["detail"]

        # Revocar D1 libera el slot -> reactivar D2 ahora SI procede
        r_revoke = client.post(f"/api/dispositivos/{d1_id}/revocar", params=params)
        assert r_revoke.status_code == 200, r_revoke.text
        resp2 = client.post(f"/api/dispositivos/{d2_id}/reactivar", params=params)
        assert resp2.status_code == 200, resp2.text
        assert resp2.json()["estado"] == "ACTIVE"
        assert resp2.json()["id"] == str(d2_id)

    def test_09_reactivar_actualiza_autorizado_por(self, client, db_session, escenario):
        """Reactivar deja constancia de QUIEN autorizo la reactivacion.

        RBAC review: `autorizado_por` es la autorizacion vigente del dispositivo.
        Al reactivar no puede quedarse en el valor historico del alta
        (codigo.creado_por): el servicio lo sobreescribe y la ruta le pasa
        ctx.user_id (el ADMINISTRADOR que ejecuta). Se reactiva con un user_id
        distinto del creador para probar que el servicio SI lo actualiza.
        """
        private_key, spki, pk_hash = _ec_keypair()
        codigo = _emitir_codigo(client, escenario)
        r = _flujo_completo(client, codigo["token"], private_key, spki, pk_hash)
        assert r.status_code == 200
        d1_id = r.json()["dispositivo_id"]

        otro_admin = uuid4()
        params_creador = _auth(
            escenario["negocio_id"], role="ADMINISTRADOR", user_id=escenario["admin_id"]
        )
        params_react = _auth(
            escenario["negocio_id"], role="ADMINISTRADOR", user_id=otro_admin
        )

        # Nace con la autorizacion del creador del codigo (canje)
        d1 = db_session.query(Dispositivo).filter(Dispositivo.id == uuid.UUID(d1_id)).first()
        assert d1.autorizado_por == escenario["admin_id"]

        r_revoke = client.post(f"/api/dispositivos/{d1_id}/revocar", params=params_creador)
        assert r_revoke.status_code == 200, r_revoke.text

        r_react = client.post(f"/api/dispositivos/{d1_id}/reactivar", params=params_react)
        assert r_react.status_code == 200, r_react.text

        d1 = db_session.query(Dispositivo).filter(Dispositivo.id == uuid.UUID(d1_id)).first()
        assert d1.estado == "ACTIVE"
        # La reactivacion sobreescribe la autorizacion con el admin que la hizo
        assert d1.autorizado_por == otro_admin
        assert d1.autorizado_el is not None


# === regla del body publico (contrato 8.13) ===

class TestBodyPublico:
    def test_13_desafio_rechaza_campos_privados(self, client, escenario):
        """El body publico NO acepta negocio_id/cobrador_id/ruta_id/rol/estado."""
        for extra in ("negocio_id", "cobrador_id", "ruta_id", "rol", "estado", "dispositivo_id"):
            r = client.post(
                "/api/activaciones/desafio",
                json={
                    "token": "x",
                    "clave_publica": "c2Vsb3M=",
                    extra: "aaa",
                },
            )
            assert r.status_code == 422, (extra, r.text)

    def test_13_canjear_rechaza_campos_privados(self, client, escenario):
        for extra in ("negocio_id", "cobrador_id", "ruta_id", "rol", "estado"):
            r = client.post(
                "/api/activaciones/canjear",
                json={"intento_id": str(uuid4()), "firma": "f", extra: "x"},
            )
            assert r.status_code == 422, (extra, r.text)

    def test_13_bootstrap_ignora_route_id_en_url(self, client, escenario):
        """Manipular route_id/negocio_id/rol en la URL no amplia permisos."""
        private_key, spki, pk_hash = _ec_keypair()
        codigo = _emitir_codigo(client, escenario)
        r = _flujo_completo(client, codigo["token"], private_key, spki, pk_hash)
        canje = r.json()
        jwt_token = _primer_jwt(
            client,
            canje["credencial_bootstrap"],
            canje["dispositivo_id"],
            private_key,
            pk_hash,
        )

        b = client.get(
            "/api/mobile/bootstrap",
            headers={"Authorization": f"Bearer {jwt_token}"},
            params={
                "route_id": str(uuid4()),
                "rol": "ADMINISTRADOR",
                "negocio_id": str(uuid4()),
            },
        )
        assert b.status_code == 200
        assert b.json()["ruta_id"] == str(escenario["ruta_id"])
        assert b.json()["rol"] == "COBRADOR"


# === gate admin (contrato 10) ===


class TestGateAdmin:
    def test_gate_codigos_requiere_admin(self, client, escenario):
        """Solo ADMINISTRADOR genera codigos de activacion."""
        r = client.post(
            "/api/activaciones/codigos",
            params=_auth(escenario["negocio_id"], role="COBRADOR")
            | {"route_id": str(escenario["ruta_id"]), "user_id": str(escenario["cobrador_id"])},
            json={"cobrador_id": str(escenario["cobrador_id"])},
        )
        assert r.status_code == 403

    def test_cobrador_no_puede_registrar_dispositivo(self, client, escenario):
        """Seccion 10: cobrador NO puede crear dispositivo directo (403)."""
        r = client.post(
            "/api/dispositivos",
            params=_auth(escenario["negocio_id"], role="COBRADOR")
            | {"route_id": str(escenario["ruta_id"]), "user_id": str(escenario["cobrador_id"])},
            json={"huella": "h1"},
        )
        assert r.status_code == 403

    def test_reemplazar_requiere_admin(self, client, escenario):
        r = client.post(
            f"/api/dispositivos/{uuid4()}/reemplazar",
            params=_auth(escenario["negocio_id"], role="COBRADOR")
            | {"route_id": str(escenario["ruta_id"])},
        )
        assert r.status_code == 403


# === idempotencia y no-herencia (casos A, B, C, D) ===


class TestIdempotenciaCasosABCD:
    def _dispositivos(self, db_session, pk_hash=None):
        q = db_session.query(Dispositivo)
        if pk_hash:
            q = q.filter(Dispositivo.public_key_hash == pk_hash)
        return q.count()

    def test_a_mismo_intento_misma_firma_idempotente(self, client, db_session, escenario):
        """A: replay exacto (mismo intento_id + misma firma) -> idempotente, mismo dispositivo."""
        private_key, spki, pk_hash = _ec_keypair()
        codigo = _emitir_codigo(client, escenario)
        rd = _desafio(client, codigo["token"], spki)
        intento_id, firma = _firma_valida(rd, private_key, pk_hash)

        r1 = _canje(client, intento_id, firma)
        assert r1.status_code == 200, r1.text
        j1 = r1.json()
        assert j1["idempotente"] is False
        assert j1["dispositivo_id"]

        r2 = _canje(client, intento_id, firma)
        assert r2.status_code == 200, r2.text
        j2 = r2.json()
        assert j2["idempotente"] is True
        assert j2["dispositivo_id"] == j1["dispositivo_id"]
        assert j2["credencial_bootstrap"] == j1["credencial_bootstrap"]
        assert self._dispositivos(db_session) == 1

    def test_b_mismo_intento_firma_distinta_rechazado(self, client, db_session, escenario):
        """B: mismo intento, firma distinta -> rechazo; NO hereda el dispositivo por idempotencia."""
        private_key, spki, pk_hash = _ec_keypair()
        atacante_key, _atacante_spki, atacante_hash = _ec_keypair()
        codigo = _emitir_codigo(client, escenario)
        rd = _desafio(client, codigo["token"], spki)
        intento_id, firma = _firma_valida(rd, private_key, pk_hash)

        r1 = _canje(client, intento_id, firma)
        assert r1.status_code == 200, r1.text

        firma_atacante = _firma_valida(rd, atacante_key, atacante_hash)[1]
        assert firma_atacante != firma

        r2 = _canje(client, intento_id, firma_atacante)
        assert r2.status_code in (401, 409), r2.text
        assert "credencial_bootstrap" not in r2.text
        assert "dispositivo_id" not in r2.text
        assert self._dispositivos(db_session) == 1

    def test_c_dos_intentos_mismo_codigo_un_solo_consumo(self, client, db_session, escenario):
        """C: dos intentos del MISMO codigo -> el segundo NO se vuelve exito idempotente."""
        private_key, spki, pk_hash = _ec_keypair()
        key2, spki2, hash2 = _ec_keypair()
        codigo = _emitir_codigo(client, escenario)

        rd1 = _desafio(client, codigo["token"], spki)
        assert rd1.status_code == 200, rd1.text
        intento1, firma1 = _firma_valida(rd1, private_key, pk_hash)

        rd2 = _desafio(client, codigo["token"], spki2)
        assert rd2.status_code == 200, rd2.text
        intento2 = rd2.json()["intento_id"]
        assert intento2 != intento1
        firma2 = _firma_valida(rd2, key2, hash2)[1]

        assert _canje(client, intento1, firma1).status_code == 200

        r2 = _canje(client, intento2, firma2)
        assert r2.status_code == 409, r2.text
        assert self._dispositivos(db_session) == 1

    def test_d_un_activo_por_cobrador_dos_codigos(self, client, db_session, escenario):
        """D: dos codigos distintos del mismo cobrador -> UN solo dispositivo ACTIVE."""
        private_key, spki, pk_hash = _ec_keypair()
        key2, spki2, hash2 = _ec_keypair()

        codigo1 = _emitir_codigo(client, escenario)
        rd1 = _desafio(client, codigo1["token"], spki)
        r1 = _canje(client, *_firma_valida(rd1, private_key, pk_hash))
        assert r1.status_code == 200, r1.text
        assert r1.json()["idempotente"] is False

        codigo2 = _emitir_codigo(client, escenario)
        rd2 = _desafio(client, codigo2["token"], spki2)
        r2 = _canje(client, *_firma_valida(rd2, key2, hash2))
        assert r2.status_code == 409, r2.text
        assert "ACTIVE" in r2.json().get("detail", ""), r2.text

        activos = (
            db_session.query(Dispositivo)
            .filter(Dispositivo.usuario_id == escenario["cobrador_id"], Dispositivo.estado == "ACTIVE")
            .count()
        )
        assert activos == 1
        assert self._dispositivos(db_session) == 1


# === concurrencia del canje (requiere PostgreSQL, SELECT FOR UPDATE) ===


class TestCanjeConcurrente:
    def test_un_solo_consumo_por_codigo(self):
        """Dos canjes simultaneos del mismo intento: UN solo dispositivo."""
        from src.database import SessionLocal
        from src.services.activacion_service import canjear as canjear_svc

        dialect = SessionLocal().get_bind().dialect.name
        if dialect != "postgresql":
            pytest.skip("concurrencia real exige PostgreSQL (SELECT FOR UPDATE)")

        nid, admin_id, cob_id, r1_id = uuid4(), uuid4(), uuid4(), uuid4()
        s = SessionLocal()
        try:
            s.add(Negocio(id=nid, nombre="Neg", nit="1"))
            s.add(Usuario(id=admin_id, negocio_id=nid, rol="ADMINISTRADOR", nombre="Admin"))
            s.add(Usuario(id=cob_id, negocio_id=nid, rol="COBRADOR", nombre="Cob"))
            s.add(Ruta(id=r1_id, negocio_id=nid, nombre="R1", cobrador_id=cob_id, activa=1))
            s.commit()
        finally:
            s.close()

        private_key, spki, pk_hash = _ec_keypair()
        token = uuid.uuid4().hex
        s = SessionLocal()
        try:
            s.add(
                CodigoActivacion(
                    negocio_id=nid,
                    cobrador_id=cob_id,
                    hash_codigo=hashlib.sha256(token.encode()).hexdigest(),
                    prefijo=token[:8],
                    expira_el=datetime.now(timezone.utc) + timedelta(minutes=10),
                    estado="PENDING",
                    creado_por=admin_id,
                    entregado_el=datetime.now(timezone.utc),
                )
            )
            s.commit()
        finally:
            s.close()

        s = SessionLocal()
        try:
            rd = desafio(s, token=token, clave_publica=spki)
            s.commit()
            intento = s.get(IntentoActivacion, rd.intento_id)
            firma = _firma_sobre_intento(intento, private_key, rd.environment)
            intento_id = rd.intento_id
        finally:
            s.close()

        resultados = []

        def canjear_thread():
            s = SessionLocal()
            try:
                r = canjear_svc(s, intento_id, firma)
                s.commit()
                resultados.append(("ok", str(r.dispositivo_id), r.idempotente))
            except Exception as e:  # noqa: BLE001
                s.rollback()
                resultados.append(("err", type(e).__name__, str(e)))
            finally:
                s.close()

        t1 = threading.Thread(target=canjear_thread)
        t2 = threading.Thread(target=canjear_thread)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        ok = [r for r in resultados if r[0] == "ok"]
        assert len(ok) == 2, resultados
        consumos = [r for r in ok if not r[2]]
        assert len(consumos) == 1, resultados
        assert len({r[1] for r in ok}) == 1, resultados
        dispositivo_count = (
            SessionLocal()
            .query(Dispositivo)
            .filter(Dispositivo.public_key_hash == pk_hash)
            .count()
        )
        assert dispositivo_count == 1

        s = SessionLocal()
        try:
            s.query(IntentoActivacion).filter(
                IntentoActivacion.codigo_id.in_(
                    s.query(CodigoActivacion.id).filter(
                        CodigoActivacion.negocio_id == nid
                    )
                )
            ).delete(synchronize_session=False)
            s.query(CodigoActivacion).filter(
                CodigoActivacion.negocio_id == nid
            ).delete(synchronize_session=False)
            s.query(Dispositivo).filter(
                Dispositivo.negocio_id == nid
            ).delete(synchronize_session=False)
            s.query(Ruta).filter(Ruta.negocio_id == nid).delete(
                synchronize_session=False
            )
            s.query(Usuario).filter(Usuario.negocio_id == nid).delete(
                synchronize_session=False
            )
            s.query(Negocio).filter(Negocio.id == nid).delete(
                synchronize_session=False
            )
            s.commit()
        finally:
            s.close()
