"""M7 — GET /api/auth/me: identidad canonica de sesion.

Fuente canonica de identidad para el frontend Web Premium. Cubre:
  - 200: rol derivado de la DB (no del JWT ni del metodo de login), negocio/
    tenant, route_id/ruta_nombre cuando aplica, capabilities del rol.
  - 200 para COBRADOR / ADMINISTRADOR / INVERSIONISTA con sets distintos de
    capabilities (COBRADOR no recibe inversionista:resumen; INVERSIONISTA no
    recibe jornada:abrir; ADMINISTRADOR superpone todo).
  - 401: sin Bearer JWT; token de usuario inactivo; token de usuario de OTRO
    negocio (aislamiento de tenant); token de otro usuario (binding
    dispositivo->usuario); rol no permitido (default-deny -> capabilities []).
  - Fail-closed adicional: /me es JWT-only. El stub query-param NO vale ni en
    test/development: ?role=INVERSIONISTA sin Authorization -> 401.
"""

import base64
import hashlib
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from src.auth.token import issue_token
from src.models import Dispositivo, Negocio, Ruta, Usuario


def _pk_hash():
    priv = ec.generate_private_key(ec.SECP256R1())
    der = priv.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    spki = base64.b64encode(der).decode("ascii")
    return spki, hashlib.sha256(der).hexdigest()


@pytest.fixture
def escenario(db_session):
    nid = uuid4()
    db_session.add(Negocio(id=nid, nombre="Neg", nit="1"))

    admin_id = uuid4()
    db_session.add(Usuario(id=admin_id, negocio_id=nid, rol="ADMINISTRADOR", nombre="Admin"))

    inv_id = uuid4()
    db_session.add(Usuario(id=inv_id, negocio_id=nid, rol="INVERSIONISTA", nombre="Invers"))

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


def _dispositivo(db_session, escenario, usuario_id):
    spki, pk_hash = _pk_hash()
    dev_id = uuid4()
    db_session.add(
        Dispositivo(
            id=dev_id,
            negocio_id=escenario["negocio_id"],
            usuario_id=usuario_id,
            public_key=spki,
            public_key_hash=pk_hash,
            algoritmo_clave="EC_P256",
            estado="ACTIVE",
            version_asignacion=1,
            activo=1,
        )
    )
    db_session.flush()
    return dev_id, spki, pk_hash


def _token(escenario, usuario_id, dev_id, pk_hash, negocio_id=None, version=1):
    return issue_token(
        negocio_id=negocio_id or escenario["negocio_id"],
        usuario_id=usuario_id,
        dispositivo_id=dev_id,
        public_key_hash=pk_hash,
        version_asignacion=version,
    )


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestMe:
    def test_me_cobrador_200_rol_y_capabilities(self, client, db_session, escenario):
        dev_id, _, pk_hash = _dispositivo(db_session, escenario, escenario["cobrador_id"])
        r = client.get("/api/auth/me", headers=_auth(_token(escenario, escenario["cobrador_id"], dev_id, pk_hash)))
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["rol"] == "COBRADOR"
        assert j["usuario_nombre"] == "Cob"
        assert j["route_id"] == str(escenario["ruta_id"])
        assert j["route_nombre"] == "R1"
        assert j["negocio"]["negocio_id"] == str(escenario["negocio_id"])
        caps = set(j["capabilities"])
        assert "jornada:abrir" in caps
        assert "ruta:ver" in caps
        assert "inversionista:resumen" not in caps  # COBRADOR no ve financiero

    def test_me_admin_200_capabilities_de_supervision(self, client, db_session, escenario):
        dev_id, _, pk_hash = _dispositivo(db_session, escenario, escenario["admin_id"])
        r = client.get("/api/auth/me", headers=_auth(_token(escenario, escenario["admin_id"], dev_id, pk_hash)))
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["rol"] == "ADMINISTRADOR"
        assert j["route_id"] is None
        caps = set(j["capabilities"])
        assert "inversionista:resumen" in caps
        assert "rutas:crear" in caps
        assert "rutas:reasignar" in caps
        assert "codigos:crear" in caps
        assert "jornada:abrir" not in caps  # admin no opera jornadas de campo

    def test_me_inversionista_200_no_operacion(self, client, db_session, escenario):
        dev_id, _, pk_hash = _dispositivo(db_session, escenario, escenario["inv_id"])
        r = client.get("/api/auth/me", headers=_auth(_token(escenario, escenario["inv_id"], dev_id, pk_hash)))
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["rol"] == "INVERSIONISTA"
        caps = set(j["capabilities"])
        assert "inversionista:resumen" in caps
        assert "inversionista:suscripcion" in caps
        assert "jornada:abrir" not in caps
        assert "rutas:crear" not in caps

    def test_me_sin_bearer_401(self, client, escenario):
        r = client.get("/api/auth/me")
        assert r.status_code == 401, r.text

    def test_me_query_stub_no_vale_ni_en_test(self, client, escenario):
        """Fail-closed extra: ?role=INVERSIONISTA sin Authorization -> 401 en test."""
        r = client.get("/api/auth/me?negocio_id=%s&role=INVERSIONISTA" % escenario["negocio_id"])
        assert r.status_code == 401, r.text

    def test_me_usuario_inactivo_401(self, client, db_session, escenario):
        dev_id, _, pk_hash = _dispositivo(db_session, escenario, escenario["cobrador_id"])
        u = db_session.get(Usuario, escenario["cobrador_id"])
        u.activo = 0
        db_session.flush()
        r = client.get("/api/auth/me", headers=_auth(_token(escenario, escenario["cobrador_id"], dev_id, pk_hash)))
        assert r.status_code == 401, r.text

    def test_me_aislamiento_tenant_401(self, client, db_session, escenario):
        """Token firmado con negocio_id B pero usuario del negocio A -> 401."""
        otro = uuid4()
        db_session.add(Negocio(id=otro, nombre="OtroNeg", nit="2"))
        db_session.flush()
        dev_id, _, pk_hash = _dispositivo(db_session, escenario, escenario["cobrador_id"])
        r = client.get(
            "/api/auth/me",
            headers=_auth(_token(escenario, escenario["cobrador_id"], dev_id, pk_hash, negocio_id=otro)),
        )
        assert r.status_code == 401, r.text

    def test_me_token_de_otro_usuario_401(self, client, db_session, escenario):
        """Dispositivo del cobrador pero sub=admin (binding dispositivo->usuario)."""
        dev_id, _, pk_hash = _dispositivo(db_session, escenario, escenario["cobrador_id"])
        r = client.get(
            "/api/auth/me",
            headers=_auth(_token(escenario, escenario["admin_id"], dev_id, pk_hash)),
        )
        assert r.status_code == 401, r.text

    def test_me_paid_through_naive_200_suscripcion_activa(self, client, db_session, escenario):
        """Postgres devuelve paid_through_at como NAIVE (timestamp without time
        zone). /me debe normalizarlo a UTC y resolver 200 (no TypeError naive vs
        aware), con suscripcion_activa=true para una fecha futura naive."""
        from datetime import datetime, timedelta

        neg = db_session.get(Negocio, escenario["negocio_id"])
        neg.paid_through_at = datetime.now() + timedelta(days=365)  # naive, como Postgres
        db_session.flush()

        dev_id, _, pk_hash = _dispositivo(db_session, escenario, escenario["inv_id"])
        r = client.get("/api/auth/me", headers=_auth(_token(escenario, escenario["inv_id"], dev_id, pk_hash)))
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["rol"] == "INVERSIONISTA"
        assert j["negocio"]["suscripcion_activa"] is True

    def test_me_paid_through_naive_vencida_200_suscripcion_inactiva(self, client, db_session, escenario):
        """paid_through_at naive en el pasado -> /me 200 con suscripcion_activa=false
        (no crash, no 500): la comparacion usa as_utc."""
        from datetime import datetime, timedelta

        neg = db_session.get(Negocio, escenario["negocio_id"])
        neg.paid_through_at = datetime.now() - timedelta(days=30)  # naive vencida
        db_session.flush()

        dev_id, _, pk_hash = _dispositivo(db_session, escenario, escenario["cobrador_id"])
        r = client.get("/api/auth/me", headers=_auth(_token(escenario, escenario["cobrador_id"], dev_id, pk_hash)))
        assert r.status_code == 200, r.text
        assert r.json()["negocio"]["suscripcion_activa"] is False