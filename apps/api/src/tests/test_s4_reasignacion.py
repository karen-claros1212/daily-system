"""S4 reasignacion de ruta — pruebas backend e integracion.

Cubren:
  - PATCH /api/rutas/{ruta_id}/reasignar: admin-only, R1→R2, bump version.
  - JWT invalidacion: token con version antigua → 401 tras reasignacion.
  - Bootstrap post-reasignacion: retorna R2, no R1.
  - Outbox R1 bajo R2: 0 HTTP, provenance preservada.
  - Flujo real challenge/canje post-reasignacion.
  - Conflictos: nombre duplicado, ruta activa de otro cobrador.
"""

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from src.auth.token import decode_token, issue_token
from src.models import Dispositivo, Negocio, Ruta, Usuario
from src.services.auth_jcs import PURPOSE_ISSUE_ACCESS_TOKEN, build_signed_payload


# === helpers criptograficos ===


def _ec_keypair():
    """Genera un par EC P-256; devuelve (privada, spki_b64, sha256_spki_hex)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    private_key = ec.generate_private_key(ec.SECP256R1())
    der = private_key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    spki = base64.b64encode(der).decode("ascii")
    return private_key, spki, hashlib.sha256(der).hexdigest()


def _sign(private_key, payload: bytes) -> str:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec

    sig = private_key.sign(payload, ec.ECDSA(hashes.SHA256()))
    return base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")


def _rfc3339_futura(minutos=5) -> str:
    dt = datetime.now(timezone.utc) + timedelta(minutes=minutos)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# === helpers ===


def _token(escenario, dev_id, pk_hash, user_id, version=1, ttl=3600):
    """Emitir JWT para user_id dado."""
    return issue_token(
        negocio_id=escenario["negocio_id"],
        usuario_id=user_id,
        dispositivo_id=dev_id,
        public_key_hash=pk_hash,
        version_asignacion=version,
        ttl_seconds=ttl,
    )


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# === fixtures ===


@pytest.fixture
def escenario_s4(db_session):
    """Negocio + admin + cobrador + R1 activa."""
    nid = uuid4()
    db_session.add(Negocio(id=nid, nombre="NegocioS4", nit="900"))

    admin_id = uuid4()
    db_session.add(
        Usuario(id=admin_id, negocio_id=nid, rol="ADMINISTRADOR", nombre="AdminS4")
    )
    cob_id = uuid4()
    db_session.add(
        Usuario(id=cob_id, negocio_id=nid, rol="COBRADOR", nombre="CobS4")
    )

    r1_id = uuid4()
    db_session.add(
        Ruta(id=r1_id, negocio_id=nid, nombre="R1-Original", cobrador_id=cob_id, activa=1)
    )
    db_session.flush()
    return {
        "negocio_id": nid,
        "admin_id": admin_id,
        "cobrador_id": cob_id,
        "ruta_id": r1_id,
    }


@pytest.fixture
def dispositivo_cobrador_s4(db_session, escenario_s4):
    """Dispositivo ACTIVE del cobrador S4 con clave EC real."""
    private_key, spki, pk_hash = _ec_keypair()
    dev_id = uuid4()
    db_session.add(
        Dispositivo(
            id=dev_id,
            negocio_id=escenario_s4["negocio_id"],
            usuario_id=escenario_s4["cobrador_id"],
            public_key=spki,
            public_key_hash=pk_hash,
            algoritmo_clave="EC_P256",
            estado="ACTIVE",
            version_asignacion=1,
            activo=1,
        )
    )
    db_session.flush()
    return {
        "dispositivo_id": dev_id,
        "public_key_hash": pk_hash,
        "private_key": private_key,
    }


@pytest.fixture
def dispositivo_admin_s4(db_session, escenario_s4):
    """Dispositivo ACTIVE del admin S4."""
    dev_id = uuid4()
    db_session.add(
        Dispositivo(
            id=dev_id,
            negocio_id=escenario_s4["negocio_id"],
            usuario_id=escenario_s4["admin_id"],
            public_key="spki-admin-s4",
            public_key_hash="pkhash-admin-s4",
            algoritmo_clave="EC_P256",
            estado="ACTIVE",
            version_asignacion=1,
            activo=1,
        )
    )
    db_session.flush()
    return {
        "dispositivo_id": dev_id,
        "public_key_hash": "pkhash-admin-s4",
    }


# === tests ===


class TestReasignacionRuta:
    """PATCH /api/rutas/{ruta_id}/reasignar."""

    def test_reasignacion_200_admin(
        self, client, db_session, escenario_s4, dispositivo_admin_s4, dispositivo_cobrador_s4
    ):
        """Admin reasigna R1→R2: 200 con nueva version."""
        token_admin = _token(
            escenario_s4,
            dispositivo_admin_s4["dispositivo_id"],
            dispositivo_admin_s4["public_key_hash"],
            escenario_s4["admin_id"],
            version=1,
        )
        r = client.patch(
            f"/api/rutas/{escenario_s4['ruta_id']}/reasignar",
            json={"nombre": "R2-Nueva"},
            headers=_auth_header(token_admin),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ruta_anterior_nombre"] == "R1-Original"
        assert body["ruta_nueva_nombre"] == "R2-Nueva"
        assert body["version_asignacion"] == 2
        assert body["cobrador_id"] == str(escenario_s4["cobrador_id"])

        # R1 desactivada
        r1 = db_session.get(Ruta, escenario_s4["ruta_id"])
        assert r1.activa == 0

        # R2 activa
        r2 = (
            db_session.query(Ruta)
            .filter(Ruta.nombre == "R2-Nueva", Ruta.activa == 1)
            .first()
        )
        assert r2 is not None
        assert r2.cobrador_id == escenario_s4["cobrador_id"]

        # version_asignacion bump (dispositivo del cobrador)
        dev = (
            db_session.query(Dispositivo)
            .filter(Dispositivo.id == dispositivo_cobrador_s4["dispositivo_id"])
            .first()
        )
        assert dev.version_asignacion == 2

    def test_reasignacion_403_cobrador(
        self, client, db_session, escenario_s4, dispositivo_cobrador_s4
    ):
        """Cobrador no puede reasignar rutas."""
        token_cob = _token(
            escenario_s4,
            dispositivo_cobrador_s4["dispositivo_id"],
            dispositivo_cobrador_s4["public_key_hash"],
            escenario_s4["cobrador_id"],
            version=1,
        )
        r = client.patch(
            f"/api/rutas/{escenario_s4['ruta_id']}/reasignar",
            json={"nombre": "R2-Nueva"},
            headers=_auth_header(token_cob),
        )
        assert r.status_code == 403

    def test_reasignacion_404_ruta_no_existe(
        self, client, db_session, escenario_s4, dispositivo_admin_s4
    ):
        """Ruta inexistente -> 404."""
        token_admin = _token(
            escenario_s4,
            dispositivo_admin_s4["dispositivo_id"],
            dispositivo_admin_s4["public_key_hash"],
            escenario_s4["admin_id"],
            version=1,
        )
        fake_id = uuid4()
        r = client.patch(
            f"/api/rutas/{fake_id}/reasignar",
            json={"nombre": "R2-Nueva"},
            headers=_auth_header(token_admin),
        )
        assert r.status_code == 404

    def test_reasignacion_ruta_sin_cobrador_400(
        self, client, db_session, escenario_s4, dispositivo_admin_s4
    ):
        """Ruta sin cobrador asignado -> 400."""
        token_admin = _token(
            escenario_s4,
            dispositivo_admin_s4["dispositivo_id"],
            dispositivo_admin_s4["public_key_hash"],
            escenario_s4["admin_id"],
            version=1,
        )
        # Crear ruta sin cobrador
        r_sin_cob = Ruta(
            id=uuid4(),
            negocio_id=escenario_s4["negocio_id"],
            nombre="R-Sin-Cob",
            activa=1,
        )
        db_session.add(r_sin_cob)
        db_session.flush()

        r = client.patch(
            f"/api/rutas/{r_sin_cob.id}/reasignar",
            json={"nombre": "R2-Nueva"},
            headers=_auth_header(token_admin),
        )
        assert r.status_code == 400

    def test_reasignacion_doble_bump_version(
        self, client, db_session, escenario_s4, dispositivo_admin_s4, dispositivo_cobrador_s4
    ):
        """Dos reasignaciones consecutivas: version se incrementa cada vez."""
        token_admin = _token(
            escenario_s4,
            dispositivo_admin_s4["dispositivo_id"],
            dispositivo_admin_s4["public_key_hash"],
            escenario_s4["admin_id"],
            version=1,
        )

        # Primera reasignacion
        r1 = client.patch(
            f"/api/rutas/{escenario_s4['ruta_id']}/reasignar",
            json={"nombre": "R2-Primera"},
            headers=_auth_header(token_admin),
        )
        assert r1.status_code == 200
        assert r1.json()["version_asignacion"] == 2

        # Segunda reasignacion
        r2 = client.patch(
            f"/api/rutas/{r1.json()['ruta_nueva_id']}/reasignar",
            json={"nombre": "R3-Segunda"},
            headers=_auth_header(token_admin),
        )
        assert r2.status_code == 200
        assert r2.json()["version_asignacion"] == 3

        # Solo R3 activa
        r3 = (
            db_session.query(Ruta)
            .filter(Ruta.nombre == "R3-Segunda", Ruta.activa == 1)
            .first()
        )
        assert r3 is not None
        assert r3.cobrador_id == escenario_s4["cobrador_id"]

        # R1 y R2 desactivadas
        r1_data = (
            db_session.query(Ruta)
            .filter(Ruta.nombre == "R1-Original", Ruta.activa == 1)
            .first()
        )
        assert r1_data is None
        r2_data = (
            db_session.query(Ruta)
            .filter(Ruta.nombre == "R2-Primera", Ruta.activa == 1)
            .first()
        )
        assert r2_data is None


class TestJWTInvalidacionPostReasignacion:
    """La reasignacion invalida JWTs antiguos via version_asignacion bump."""

    def test_token_viejo_401_tras_reasignacion(
        self, client, db_session, escenario_s4, dispositivo_admin_s4, dispositivo_cobrador_s4
    ):
        """Token del cobrador con version 1 -> 401 despues de reasignacion (version=2)."""
        token_cob = _token(
            escenario_s4,
            dispositivo_cobrador_s4["dispositivo_id"],
            dispositivo_cobrador_s4["public_key_hash"],
            escenario_s4["cobrador_id"],
            version=1,
        )

        # Token valido antes de reasignacion
        r_before = client.get(
            "/api/auth/me",
            headers=_auth_header(token_cob),
        )
        assert r_before.status_code == 200

        # Reasignar (admin)
        token_admin = _token(
            escenario_s4,
            dispositivo_admin_s4["dispositivo_id"],
            dispositivo_admin_s4["public_key_hash"],
            escenario_s4["admin_id"],
            version=1,
        )
        r_reassign = client.patch(
            f"/api/rutas/{escenario_s4['ruta_id']}/reasignar",
            json={"nombre": "R2-Nueva"},
            headers=_auth_header(token_admin),
        )
        assert r_reassign.status_code == 200

        # Mismo token del cobrador despues de reasignacion -> 401
        r_after = client.get(
            "/api/auth/me",
            headers=_auth_header(token_cob),
        )
        assert r_after.status_code == 401

    def test_flujo_challenge_canje_post_reasignacion(
        self, client, db_session, escenario_s4, dispositivo_admin_s4, dispositivo_cobrador_s4
    ):
        """Flujo productivo: reasignacion → desafio/canje real → JWT nuevo → bootstrap R2."""
        private_key = dispositivo_cobrador_s4["private_key"]

        # 1. Reasignar (admin)
        token_admin = _token(
            escenario_s4,
            dispositivo_admin_s4["dispositivo_id"],
            dispositivo_admin_s4["public_key_hash"],
            escenario_s4["admin_id"],
            version=1,
        )
        r_reassign = client.patch(
            f"/api/rutas/{escenario_s4['ruta_id']}/reasignar",
            json={"nombre": "R2-Nueva"},
            headers=_auth_header(token_admin),
        )
        assert r_reassign.status_code == 200
        nueva_version = r_reassign.json()["version_asignacion"]
        assert nueva_version == 2

        # 2. JWT v1 del cobrador -> 401 en endpoint productivo
        token_cob_v1 = _token(
            escenario_s4,
            dispositivo_cobrador_s4["dispositivo_id"],
            dispositivo_cobrador_s4["public_key_hash"],
            escenario_s4["cobrador_id"],
            version=1,
        )
        r_401 = client.get(
            "/api/auth/me",
            headers=_auth_header(token_cob_v1),
        )
        assert r_401.status_code == 401

        # 3. /desafio con JWT v1 -> 200 (accept_any_version=True)
        desafio_resp = client.post(
            "/api/auth/device/desafio",
            headers=_auth_header(token_cob_v1),
            json={
                "challenge_id": "ch-test",
                "nonce": "nonce-test",
                "expira_el": _rfc3339_futura(),
                "environment": "test",
            },
        )
        assert desafio_resp.status_code == 200
        desafio_data = desafio_resp.json()

        # 4. /canjear con firma -> 200, JWT con version 2
        payload = build_signed_payload(
            purpose=PURPOSE_ISSUE_ACCESS_TOKEN,
            environment=desafio_data["environment"],
            challenge_id=desafio_data["challenge_id"],
            device_id=str(dispositivo_cobrador_s4["dispositivo_id"]),
            nonce=desafio_data["nonce"],
            public_key_hash=dispositivo_cobrador_s4["public_key_hash"],
            expires_at=desafio_data["expira_el"],
        )
        firma = _sign(private_key, payload)
        canje_resp = client.post(
            "/api/auth/device/canjear",
            json={
                "challenge_id": desafio_data["challenge_id"],
                "firma": firma,
            },
        )
        assert canje_resp.status_code == 200
        canje_data = canje_resp.json()
        assert canje_data["version_asignacion"] == 2
        token_nuevo = canje_data["token"]

        # 5. Bootstrap con JWT nuevo -> R2
        bootstrap_resp = client.get(
            "/api/mobile/bootstrap",
            headers=_auth_header(token_nuevo),
        )
        assert bootstrap_resp.status_code == 200
        assert bootstrap_resp.json()["ruta_nombre"] == "R2-Nueva"
        assert bootstrap_resp.json()["version_asignacion"] == 2


class TestBootstrapPostReasignacion:
    """Bootstrap despues de reasignacion retorna R2."""

    def test_bootstrap_retorna_r2_tras_reasignacion(
        self, client, db_session, escenario_s4, dispositivo_admin_s4, dispositivo_cobrador_s4
    ):
        """GET /api/mobile/bootstrap devuelve R2 despues de reasignacion."""
        token_admin = _token(
            escenario_s4,
            dispositivo_admin_s4["dispositivo_id"],
            dispositivo_admin_s4["public_key_hash"],
            escenario_s4["admin_id"],
            version=1,
        )

        # Reasignar
        r_reassign = client.patch(
            f"/api/rutas/{escenario_s4['ruta_id']}/reasignar",
            json={"nombre": "R2-Nueva"},
            headers=_auth_header(token_admin),
        )
        assert r_reassign.status_code == 200

        # Token con nueva version
        nueva_version = r_reassign.json()["version_asignacion"]
        token_cob = _token(
            escenario_s4,
            dispositivo_cobrador_s4["dispositivo_id"],
            dispositivo_cobrador_s4["public_key_hash"],
            escenario_s4["cobrador_id"],
            version=nueva_version,
        )

        # Bootstrap -> R2
        r_bootstrap = client.get(
            "/api/mobile/bootstrap",
            headers=_auth_header(token_cob),
        )
        assert r_bootstrap.status_code == 200
        body = r_bootstrap.json()
        assert body["ruta_nombre"] == "R2-Nueva"
        assert body["version_asignacion"] == nueva_version


class TestOutboxR1BajoR2:
    """El outbox R1 no se pusha bajo R2 (0 HTTP).

    La logica de skipRuta se prueba en mobile (push_orchestrator_test.dart).
    Aqui solo verificamos que la reasignacion deja R1 inmutable en el historial.
    """

    def test_r1_preservada_tras_reasignacion(
        self, client, db_session, escenario_s4, dispositivo_admin_s4
    ):
        """R1 permanece con provenance intacta despues de reasignacion."""
        token_admin = _token(
            escenario_s4,
            dispositivo_admin_s4["dispositivo_id"],
            dispositivo_admin_s4["public_key_hash"],
            escenario_s4["admin_id"],
            version=1,
        )

        # Reasignar
        r_reassign = client.patch(
            f"/api/rutas/{escenario_s4['ruta_id']}/reasignar",
            json={"nombre": "R2-Nueva"},
            headers=_auth_header(token_admin),
        )
        assert r_reassign.status_code == 200
        nueva_ruta_id = r_reassign.json()["ruta_nueva_id"]

        # R1 permanece en DB (solo desactivada)
        r1 = db_session.get(Ruta, escenario_s4["ruta_id"])
        assert r1.nombre == "R1-Original"
        assert r1.activa == 0
        assert r1.cobrador_id == escenario_s4["cobrador_id"]

        # R2 es la unica activa
        r2 = db_session.get(Ruta, UUID(str(nueva_ruta_id)))
        assert r2.activa == 1
        assert r2.nombre == "R2-Nueva"
        assert r2.cobrador_id == escenario_s4["cobrador_id"]


class TestConflictosReasignacion:
    """Conflictos: nombre duplicado, ruta activa de otro cobrador."""

    def test_reasignacion_ruta_existente_mismo_cobrador(
        self, client, db_session, escenario_s4, dispositivo_admin_s4
    ):
        """R2 inactiva para este cobrador → crea nueva activa (no reutiliza inactiva).

        El endpoint solo busca rutas ACTIVAS para reutilizar. Una ruta
        inactiva del mismo cobrador no se reutiliza (queda como historial).
        """
        r2_inactiva = Ruta(
            id=uuid4(),
            negocio_id=escenario_s4["negocio_id"],
            nombre="R2-Inactiva",
            cobrador_id=escenario_s4["cobrador_id"],
            activa=0,
        )
        db_session.add(r2_inactiva)
        db_session.flush()

        token_admin = _token(
            escenario_s4,
            dispositivo_admin_s4["dispositivo_id"],
            dispositivo_admin_s4["public_key_hash"],
            escenario_s4["admin_id"],
            version=1,
        )

        r = client.patch(
            f"/api/rutas/{escenario_s4['ruta_id']}/reasignar",
            json={"nombre": "R2-Nueva"},
            headers=_auth_header(token_admin),
        )
        assert r.status_code == 200
        # Crea nueva ruta activa (no reutiliza la inactiva)
        assert r.json()["ruta_nueva_nombre"] == "R2-Nueva"
        assert r.json()["ruta_nueva_id"] != str(r2_inactiva.id)
        # R1 desactivada
        r1 = db_session.get(Ruta, escenario_s4["ruta_id"])
        assert r1.activa == 0
        # R2 inactiva permanece intacta
        r2_check = db_session.get(Ruta, r2_inactiva.id)
        assert r2_check.activa == 0

    def test_reasignacion_ruta_activa_otro_cobrador_ok(
        self, client, db_session, escenario_s4, dispositivo_admin_s4
    ):
        """R2 ya activa para otro cobrador → crea nueva R3 (no viola constraint)."""
        otro_cob = Usuario(
            id=uuid4(),
            negocio_id=escenario_s4["negocio_id"],
            rol="COBRADOR",
            nombre="OtroCob",
        )
        db_session.add(otro_cob)
        r2_otro = Ruta(
            id=uuid4(),
            negocio_id=escenario_s4["negocio_id"],
            nombre="R2-Otro",
            cobrador_id=otro_cob.id,
            activa=1,
        )
        db_session.add(r2_otro)
        db_session.flush()

        token_admin = _token(
            escenario_s4,
            dispositivo_admin_s4["dispositivo_id"],
            dispositivo_admin_s4["public_key_hash"],
            escenario_s4["admin_id"],
            version=1,
        )

        # Intentar reasignar con nombre unico
        r = client.patch(
            f"/api/rutas/{escenario_s4['ruta_id']}/reasignar",
            json={"nombre": "R2-Nuevo"},
            headers=_auth_header(token_admin),
        )
        assert r.status_code == 200
        # R1 desactivada
        r1 = db_session.get(Ruta, escenario_s4["ruta_id"])
        assert r1.activa == 0

    def test_reasignacion_sin_dispositivo_version_sin_cambios(
        self, client, db_session, escenario_s4, dispositivo_admin_s4
    ):
        """Cobrador sin dispositivo activo → version_asignacion sin cambios."""
        # Eliminar dispositivo del cobrador (solo admin tiene dispositivo)
        cobrador_id = escenario_s4["cobrador_id"]
        admin_id = escenario_s4["admin_id"]

        token_admin = _token(
            escenario_s4,
            dispositivo_admin_s4["dispositivo_id"],
            dispositivo_admin_s4["public_key_hash"],
            admin_id,
            version=1,
        )

        r = client.patch(
            f"/api/rutas/{escenario_s4['ruta_id']}/reasignar",
            json={"nombre": "R2-Sin-Dev"},
            headers=_auth_header(token_admin),
        )
        assert r.status_code == 200
        # version_asignacion = 1 (sin dispositivo, sin bump)
        assert r.json()["version_asignacion"] == 1

    def test_reasignacion_target_pertenece_otro_cobrador_conflicto(
        self, client, db_session, escenario_s4, dispositivo_admin_s4, dispositivo_cobrador_s4
    ):
        """R2-Nueva ya activa para C2 → 409, R1 intacta, sin efectos secundarios."""
        otro_cob = Usuario(
            id=uuid4(),
            negocio_id=escenario_s4["negocio_id"],
            rol="COBRADOR",
            nombre="OtroCob",
            activo=1,
        )
        db_session.add(otro_cob)
        r2_otro = Ruta(
            id=uuid4(),
            negocio_id=escenario_s4["negocio_id"],
            nombre="R2-Nueva",
            cobrador_id=otro_cob.id,
            activa=1,
        )
        db_session.add(r2_otro)
        db_session.flush()

        otro_dev = Dispositivo(
            id=uuid4(),
            negocio_id=escenario_s4["negocio_id"],
            usuario_id=otro_cob.id,
            public_key="spki-otro",
            public_key_hash="pkhash-otro",
            algoritmo_clave="EC_P256",
            estado="ACTIVE",
            version_asignacion=1,
            activo=1,
        )
        db_session.add(otro_dev)
        db_session.flush()

        token_admin = _token(
            escenario_s4,
            dispositivo_admin_s4["dispositivo_id"],
            dispositivo_admin_s4["public_key_hash"],
            escenario_s4["admin_id"],
            version=1,
        )

        # Reasignar con nombre ocupado por otro cobrador
        r = client.patch(
            f"/api/rutas/{escenario_s4['ruta_id']}/reasignar",
            json={"nombre": "R2-Nueva"},
            headers=_auth_header(token_admin),
        )
        assert r.status_code == 409
        assert "Ya existe ruta activa 'R2-Nueva'" in r.json()["detail"]

        # R1 sigue activa para C1
        r1 = db_session.get(Ruta, escenario_s4["ruta_id"])
        assert r1.activa == 1
        assert r1.nombre == "R1-Original"

        # R2 sigue activa para C2
        r2_check = db_session.get(Ruta, r2_otro.id)
        assert r2_check.activa == 1
        assert r2_check.cobrador_id == otro_cob.id

        # version_asignacion del dispositivo C1 no cambia
        cobrador_dev = db_session.query(Dispositivo).filter(
            Dispositivo.usuario_id == escenario_s4["cobrador_id"],
            Dispositivo.estado == "ACTIVE",
        ).first()
        assert cobrador_dev is not None
        assert cobrador_dev.version_asignacion == 1
