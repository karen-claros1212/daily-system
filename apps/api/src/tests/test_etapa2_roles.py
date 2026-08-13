"""M-Etapa2 — Backend tests for the explicit multi-role session policy (Etapa 2).

Covers the policy introduced in Etapa 2 and the mandatory matrix:
  - Emission (canjear_desafio) per role through the REAL activation device flow:
      COBRADOR (with its single active ruta), INVERSIONISTA and ADMINISTRADOR.
  - Fail-closed for unknown roles; inactive user; revoked device; tenant
    mismatch; version_asignacion desactualizada; replay.
  - The route of COBRADOR (0 / exactly-1 / >1 active) is enforced; INV/ADM do
    NOT require a ruta.
  - Role is derived from the DB (never from the JWT): emitted tokens carry no
    role claim; /me returns the server-derived role + capabilities.
  - Horizontal / vertical escalation negative tests, incl. the cross-role gate:
    an INVERSIONISTA token (without ruta) CANNOT reach a COBRADOR-only
    operation (POST /api/jornadas/abrir -> 403).

The full activation flow (admin issue code -> desafio -> canjear -> bootstrap
-> session desafio -> canjear) is exercised for each role: this proves the
whole chain, not just a server-minted token.
"""

import base64
import hashlib
from uuid import UUID, uuid4

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from src.auth.token import decode_token, issue_token
from src.models import Dispositivo, Negocio, Ruta, Usuario
from src.services.auth_jcs import (
    PURPOSE_ISSUE_ACCESS_TOKEN,
    build_signed_payload as build_auth_payload,
)
from src.services.auth_service import AuthError, exigir_elegibilidad_sesion
from src.services.jcs import PROTOCOL_VERSION, build_signed_payload


# === crypto helpers (mirror test_m5) ===


def _ec_keypair():
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


def _auth(nid, role="ADMINISTRADOR", user_id=None):
    params = {"negocio_id": str(nid), "role": role}
    if user_id:
        params["user_id"] = str(user_id)
    return params


# === fixtures ===


@pytest.fixture
def escenario(db_session):
    """Negocio + admin + cobrador (con ruta activa) + inversionista."""
    nid = uuid4()
    db_session.add(Negocio(id=nid, nombre="Neg", nit="1", pais="CO", moneda="COP"))

    admin_id = uuid4()
    db_session.add(Usuario(id=admin_id, negocio_id=nid, rol="ADMINISTRADOR", nombre="Admin"))

    inv_id = uuid4()
    db_session.add(Usuario(id=inv_id, negocio_id=nid, rol="INVERSIONISTA", nombre="Inv"))

    cob_id = uuid4()
    db_session.add(Usuario(id=cob_id, negocio_id=nid, rol="COBRADOR", nombre="Cob"))

    r1_id = uuid4()
    db_session.add(Ruta(id=r1_id, negocio_id=nid, nombre="R1", cobrador_id=cob_id, activa=1))
    db_session.flush()
    return {
        "negocio_id": nid,
        "admin_id": admin_id,
        "inv_id": inv_id,
        "cobrador_id": cob_id,
        "ruta_id": r1_id,
    }


# === step helpers (real activation device flow per role) ===


def _emitir_codigo(client, escenario, usuario_id):
    r = client.post(
        "/api/activaciones/codigos",
        params=_auth(escenario["negocio_id"], user_id=escenario["admin_id"]),
        json={"usuario_id": str(usuario_id), "expira_minutos": 10},
    )
    assert r.status_code == 201, r.text
    return r.json()["token"]


def _activar(client, codigo_token, private_key, spki, pk_hash):
    """desafio + canje de activacion -> (canje_response, dispositivo_id)."""
    r = client.post(
        "/api/activaciones/desafio",
        json={
            "token": codigo_token,
            "clave_publica": spki,
            "modelo": "Web",
            "plataforma": "web",
        },
    )
    assert r.status_code == 200, r.text
    d = r.json()
    payload = build_signed_payload(
        protocol_version=PROTOCOL_VERSION,
        environment=d["environment"],
        attempt_id=d["intento_id"],
        nonce=d["nonce"],
        public_key_hash=pk_hash,
        expires_at=d["expira_el"],
    )
    firma = _sign(private_key, payload)
    r2 = client.post(
        "/api/activaciones/canjear",
        json={"intento_id": d["intento_id"], "firma": firma},
    )
    assert r2.status_code == 200, r2.text
    canje = r2.json()
    return canje, canje["dispositivo_id"]


def _desafio_sesion(client, credencial, dev_id, private_key, pk_hash):
    """Session challenge con una credencial (bootstrap o JWT) -> {challenge_id,firma}."""
    d = client.post(
        "/api/auth/device/desafio", headers={"Authorization": f"Bearer {credencial}"}
    ).json()
    payload = build_auth_payload(
        purpose=PURPOSE_ISSUE_ACCESS_TOKEN,
        environment=d["environment"],
        challenge_id=d["challenge_id"],
        device_id=str(dev_id),
        nonce=d["nonce"],
        public_key_hash=pk_hash,
        expires_at=d["expira_el"],
    )
    return {"challenge_id": d["challenge_id"], "firma": _sign(private_key, payload)}


def _canjear_sesion(client, body):
    return client.post("/api/auth/device/canjear", json=body)


def _primer_jwt(client, bootstrap, dev_id, private_key, pk_hash):
    """Primer access token: session desafio + canjear (con la credencial bootstrap)."""
    body = _desafio_sesion(client, bootstrap, dev_id, private_key, pk_hash)
    r = _canjear_sesion(client, body)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _jwt_para_rol(client, escenario, target_usuario_id, private_key, spki, pk_hash):
    """Flujo REAL completo (admin code -> ... -> access token) para un rol."""
    token = _emitir_codigo(client, escenario, target_usuario_id)
    canje, dev_id = _activar(client, token, private_key, spki, pk_hash)
    jwt = _primer_jwt(client, canje["credencial_bootstrap"], dev_id, private_key, pk_hash)
    return jwt, canje


# === emisión por rol (real device flow) ===


class TestEmisionPorRol:
    def test_cobrador_con_una_ruta_obtiene_sesion(self, client, escenario):
        pk, spki, h = _ec_keypair()
        jwt, canje = _jwt_para_rol(client, escenario, escenario["cobrador_id"], pk, spki, h)
        claims = decode_token(jwt)
        assert claims["sub"] == str(escenario["cobrador_id"])
        assert "role" not in claims
        assert canje["rol"] == "COBRADOR"
        assert canje["usuario_id"] == str(escenario["cobrador_id"])
        assert canje["cobrador_id"] == str(escenario["cobrador_id"])  # legado

    def test_inversionista_sin_ruta_obtiene_sesion(self, client, escenario):
        pk, spki, h = _ec_keypair()
        jwt, canje = _jwt_para_rol(client, escenario, escenario["inv_id"], pk, spki, h)
        claims = decode_token(jwt)
        assert claims["sub"] == str(escenario["inv_id"])
        assert "role" not in claims
        assert canje["rol"] == "INVERSIONISTA"
        assert canje["usuario_id"] == str(escenario["inv_id"])

    def test_administrador_sin_ruta_obtiene_sesion(self, client, escenario):
        pk, spki, h = _ec_keypair()
        jwt, canje = _jwt_para_rol(client, escenario, escenario["admin_id"], pk, spki, h)
        claims = decode_token(jwt)
        assert claims["sub"] == str(escenario["admin_id"])
        assert "role" not in claims
        assert canje["rol"] == "ADMINISTRADOR"

    def test_renew_session_inversionista(self, client, escenario):
        """Renovación funciona para INV (no solo cobrador) -> nuevo jti."""
        pk, spki, h = _ec_keypair()
        jwt, canje = _jwt_para_rol(client, escenario, escenario["inv_id"], pk, spki, h)
        dev_id = UUID(canje["dispositivo_id"])
        body = _desafio_sesion(client, jwt, dev_id, pk, h)
        rr = _canjear_sesion(client, body)
        assert rr.status_code == 200, rr.text
        nuevo = decode_token(rr.json()["token"])
        assert nuevo["sub"] == str(escenario["inv_id"])
        assert nuevo["jti"] != decode_token(jwt)["jti"]


# === fail-closed ===


class TestFailClosedEmision:
    def test_rol_no_admitido_fail_closed(self, db_session, escenario):
        """exigir_elegibilidad_sesion: rol desconocido -> 401 ROL_NO_PERMITIDO."""

        class Stub:
            rol = "SUPERADMIN"
            id = escenario["admin_id"]
            negocio_id = escenario["negocio_id"]

        with pytest.raises(AuthError) as e:
            exigir_elegibilidad_sesion(db_session, Stub())  # type: ignore[arg-type]
        assert e.value.code == "ROL_NO_PERMITIDO"
        assert e.value.status_code == 401

    def test_usuario_inactivo_no_renueva_sesion(self, client, db_session, escenario):
        """Usuario inactivo: desafio permitido, pero el canje emite 401."""
        pk, spki, h = _ec_keypair()
        jwt, canje = _jwt_para_rol(client, escenario, escenario["inv_id"], pk, spki, h)
        u = db_session.get(Usuario, escenario["inv_id"])
        u.activo = 0
        db_session.flush()
        dev_id = UUID(canje["dispositivo_id"])
        body = _desafio_sesion(client, jwt, dev_id, pk, h)
        r = _canjear_sesion(client, body)
        assert r.status_code == 401, r.text

    def test_cobrador_sin_ruta_canjear_401(self, client, db_session, escenario):
        """COBRADOR con 0 rutas activas: la renovacion de sesion cae 401 (H3).

        La ruta se desactiva despues de obtener el jwt (la activacion y el
        primer canje exigen la ruta, como la politica H3 mantiene). La
        renovacion posterior revalida exigir_ruta_activa_unica -> 401.
        """
        pk, spki, h = _ec_keypair()
        jwt, canje = _jwt_para_rol(client, escenario, escenario["cobrador_id"], pk, spki, h)
        ruta = db_session.get(Ruta, escenario["ruta_id"])
        ruta.activa = 0
        db_session.flush()
        dev_id = UUID(canje["dispositivo_id"])
        body = _desafio_sesion(client, jwt, dev_id, pk, h)
        r = _canjear_sesion(client, body)
        assert r.status_code == 401, r.text  # 0 rutas -> 401 fail-closed (H3)

    def test_cobrador_dos_rutas_canjear_401(self, client, db_session, escenario):
        """COBRADOR con >1 ruta activa -> 401 (H3) o constraint parcial (PG/SQLite).

        El constraint parcial uq_ruta_activa_cobrador impide 2 rutas ACTIVE del
        mismo cobrador: ese es el guarda real. Si el constraint se cumple, la
        renovacion cae 401 en exigir_ruta_activa_unica (defensa en profundidad).
        """
        from sqlalchemy.exc import IntegrityError

        db_session.add(
            Ruta(
                id=uuid4(),
                negocio_id=escenario["negocio_id"],
                nombre="R2",
                cobrador_id=escenario["cobrador_id"],
                activa=1,
            )
        )
        try:
            db_session.flush()
        except IntegrityError:
            db_session.rollback()
            return  # constraint parcial es la evidencia equivalente
        pk, spki, h = _ec_keypair()
        jwt, canje = _jwt_para_rol(client, escenario, escenario["cobrador_id"], pk, spki, h)
        dev_id = UUID(canje["dispositivo_id"])
        db_session.add(
            Ruta(
                id=uuid4(),
                negocio_id=escenario["negocio_id"],
                nombre="R3",
                cobrador_id=escenario["cobrador_id"],
                activa=1,
            )
        )
        try:
            db_session.flush()
        except IntegrityError:
            db_session.rollback()
            return
        body = _desafio_sesion(client, jwt, dev_id, pk, h)
        r = _canjear_sesion(client, body)
        assert r.status_code == 401, r.text

    def test_tenant_mismatch_canjear_401(self, client, db_session, escenario):
        """Dispositivo de negocio A pero token firmado para negocio B -> 401."""
        pk, spki, h = _ec_keypair()
        otro_neg = uuid4()
        db_session.add(Negocio(id=otro_neg, nombre="Otro", nit="2", pais="CO", moneda="COP"))
        dev_id = uuid4()
        # el DISPOSITIVO vive en el negocio A (escenario); el TOKEN reclama B.
        db_session.add(
            Dispositivo(
                id=dev_id,
                negocio_id=escenario["negocio_id"],
                usuario_id=escenario["cobrador_id"],
                public_key=spki,
                public_key_hash=h,
                algoritmo_clave="EC_P256",
                estado="ACTIVE",
                version_asignacion=1,
                activo=1,
            )
        )
        db_session.flush()
        token = issue_token(
            negocio_id=otro_neg,
            usuario_id=escenario["cobrador_id"],
            dispositivo_id=dev_id,
            public_key_hash=h,
            version_asignacion=1,
        )
        r = client.post("/api/auth/device/desafio", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401, r.text

    def test_dispositivo_revocado_canjear_401(self, client, db_session, escenario):
        """Revocacion con bump mata la sesion: desafio 401."""
        pk, spki, h = _ec_keypair()
        jwt, canje = _jwt_para_rol(client, escenario, escenario["inv_id"], pk, spki, h)
        dev = db_session.query(Dispositivo).filter(
            Dispositivo.id == UUID(canje["dispositivo_id"])
        ).first()
        dev.estado = "REVOKED"
        dev.version_asignacion = 2
        db_session.flush()
        r = client.post("/api/auth/device/desafio", headers={"Authorization": f"Bearer {jwt}"})
        assert r.status_code == 401, r.text

    def test_replay_mismo_challenge_inv_409(self, client, escenario):
        """Single-use: replay del challenge 409 (INVERSIONISTA)."""
        pk, spki, h = _ec_keypair()
        jwt, canje = _jwt_para_rol(client, escenario, escenario["inv_id"], pk, spki, h)
        dev_id = UUID(canje["dispositivo_id"])
        body = _desafio_sesion(client, jwt, dev_id, pk, h)
        assert _canjear_sesion(client, body).status_code == 200
        assert _canjear_sesion(client, body).status_code == 409


# === me / capabilities (rol derivado de la DB) ===


class TestMePorRol:
    def test_me_inv_rol_server_derivado(self, client, escenario):
        """Vertical: rol viene de la DB, no del JWT; INV no eleva a admin."""
        pk, spki, h = _ec_keypair()
        jwt, _ = _jwt_para_rol(client, escenario, escenario["inv_id"], pk, spki, h)
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {jwt}"})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["rol"] == "INVERSIONISTA"
        caps = set(j["capabilities"])
        assert "jornada:abrir" not in caps  # INV no opera jornadas

    def test_me_admin_superpone(self, client, escenario):
        pk, spki, h = _ec_keypair()
        jwt, _ = _jwt_para_rol(client, escenario, escenario["admin_id"], pk, spki, h)
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {jwt}"})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["rol"] == "ADMINISTRADOR"
        caps = set(j["capabilities"])
        assert "inversionista:resumen" in caps
        assert "codigos:crear" in caps


# === GATE: INVERSIONISTA no accede a endpoints de COBRADOR ===


class TestGateEscalamiento:
    def test_inversionista_no_abre_jornada_403(self, client, escenario):
        """Token INVERSIONISTA (sin ruta) NO abre jornada de COBRADOR -> 403."""
        pk, spki, h = _ec_keypair()
        jwt, _ = _jwt_para_rol(client, escenario, escenario["inv_id"], pk, spki, h)
        r = client.post(
            "/api/jornadas",
            headers={"Authorization": f"Bearer {jwt}"},
            json={
                "ruta_id": str(escenario["ruta_id"]),
                "opening_base": 0,
                "clave_idempotencia": "gate-inv-1",
            },
        )
        assert r.status_code == 403, r.text
        assert "inversionista" in r.json()["detail"].lower()

    def test_cobrador_abre_su_ruta_201(self, client, escenario):
        pk, spki, h = _ec_keypair()
        jwt, _ = _jwt_para_rol(client, escenario, escenario["cobrador_id"], pk, spki, h)
        r = client.post(
            "/api/jornadas",
            headers={"Authorization": f"Bearer {jwt}"},
            json={
                "ruta_id": str(escenario["ruta_id"]),
                "opening_base": 1000,
                "clave_idempotencia": "gate-cob-1",
            },
        )
        assert r.status_code == 201, r.text

    def test_administrador_no_tiene_capabilidad_operativa_cobrador(self, client, escenario):
        """Un ADMIN no obtiene capabilities operativas de COBRADOR (supervisa)."""
        pk, spki, h = _ec_keypair()
        jwt, _ = _jwt_para_rol(client, escenario, escenario["admin_id"], pk, spki, h)
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {jwt}"})
        caps = set(r.json()["capabilities"])
        assert "jornada:abrir" not in caps
        assert "movimientos:registrar" not in caps
        assert "pagos:registrar" not in caps

    def test_horizontal_sub_dispositivo_ajeno_401(self, client, escenario):
        """sub que no es dueño del dispositivo -> 401 (binding device->user)."""
        pk, spki, h = _ec_keypair()
        jwt, canje = _jwt_para_rol(client, escenario, escenario["cobrador_id"], pk, spki, h)
        dev_id = UUID(canje["dispositivo_id"])
        token = issue_token(
            negocio_id=escenario["negocio_id"],
            usuario_id=escenario["inv_id"],
            dispositivo_id=dev_id,
            public_key_hash=h,
            version_asignacion=1,
        )
        r = client.post("/api/auth/device/desafio", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401, r.text
