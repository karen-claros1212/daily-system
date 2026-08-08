"""M6 auth tests — Auth productiva JWT (Bloque 7, D7-01/02).

Cubren:
  - Emision/validacion de JWT: HS256, allow-list fija, payload minimo sin
    role/route_id, jti unico por token (anti-replay), rechazo de tokens
    firmados con alg distinto (alg-confusion) y de tokens manipulados.
  - Derivacion de rol + ruta desde la BASE en cada request (no desde el JWT):
    cobrador sin ruta activa -> 401; admin/root sin ruta -> ok.
  - Revocacion/reemplazo con efecto inmediato: bump de version_asignacion
    mata tokens vigentes aunque `exp` no haya llegado.
  - Renovacion challenge-response JCS daily-auth-v1: firma valida renueva,
    firma invalida 401, token viejo/expirado 401.
  - Concurrencia real PostgreSQL: renovaciones simultaneas del mismo
    dispositivo (requiere PG; se salta en SQLite).

El payload JCS daily-auth-v1 es SEPARADO del protocolo de activacion
(daily-v1): campos distintos, mismo motor canonico RFC 8785.
"""

import base64
import hashlib
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from src.auth.token import TokenError, decode_token, issue_token
from src.models import Dispositivo, Negocio, Ruta, Usuario
from src.services.auth_jcs import build_signed_payload

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


def _rfc3339_futura(minutos=5) -> str:
    dt = datetime.now(timezone.utc) + timedelta(minutes=minutos)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


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


@pytest.fixture
def dispositivo_activo(db_session, escenario):
    """Dispositivo ACTIVE vinculado al cobrador, con clave publica registrada."""
    private_key, spki, pk_hash = _ec_keypair()
    dev_id = uuid4()
    disp = Dispositivo(
        id=dev_id,
        negocio_id=escenario["negocio_id"],
        usuario_id=escenario["cobrador_id"],
        public_key=spki,
        public_key_hash=pk_hash,
        algoritmo_clave="EC_P256",
        estado="ACTIVE",
        version_asignacion=1,
        activo=1,
    )
    db_session.add(disp)
    db_session.flush()
    return {
        "dispositivo_id": dev_id,
        "private_key": private_key,
        "public_key": spki,
        "public_key_hash": pk_hash,
    }


def _token(escenario, dispositivo_activo, version=1, ttl=3600):
    return issue_token(
        negocio_id=escenario["negocio_id"],
        usuario_id=escenario["cobrador_id"],
        dispositivo_id=dispositivo_activo["dispositivo_id"],
        version_asignacion=version,
        ttl_seconds=ttl,
    )


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# === token: emision y validacion ===


class TestToken:
    def test_payload_minimo_sin_role_ni_route(self, escenario, dispositivo_activo):
        """El JWT NO lleva role ni route_id (autoridad geografica fuera del token)."""
        token = _token(escenario, dispositivo_activo)
        claims = decode_token(token)
        assert "role" not in claims
        assert "route_id" not in claims
        assert claims["negocio_id"] == str(escenario["negocio_id"])
        assert claims["usuario_id"] == str(escenario["cobrador_id"])
        assert claims["dispositivo_id"] == str(dispositivo_activo["dispositivo_id"])
        assert claims["version_asignacion"] == 1
        assert claims.get("jti")

    def test_jti_unico_por_token(self, escenario, dispositivo_activo):
        """Dos tokens del mismo dispositivo no comparten jti (anti-replay)."""
        t1 = decode_token(_token(escenario, dispositivo_activo))
        t2 = decode_token(_token(escenario, dispositivo_activo))
        assert t1["jti"] != t2["jti"]

    def test_alg_confusion_rechazado(self, escenario, dispositivo_activo):
        """Token firmado con 'none' o un alg fuera de la allow-list se rechaza."""
        claims = {
            "negocio_id": str(escenario["negocio_id"]),
            "usuario_id": str(escenario["cobrador_id"]),
            "dispositivo_id": str(dispositivo_activo["dispositivo_id"]),
            "version_asignacion": 1,
            "jti": "x",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        # none: sin firma, jamas aceptado por la allow-list.
        t = pyjwt.encode(claims, None, algorithm="none")
        with pytest.raises(TokenError):
            decode_token(t)
        # RS256: firmado con una clave real, rechazado porque solo HS256 existe.
        rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        t = pyjwt.encode(claims, rsa_key, algorithm="RS256")
        with pytest.raises(TokenError):
            decode_token(t)

    def test_firma_manipulada_rechazada(self, escenario, dispositivo_activo):
        token = _token(escenario, dispositivo_activo)
        partes = token.split(".")
        partes[-1] = "A" * len(partes[-1])
        with pytest.raises(TokenError):
            decode_token(".".join(partes))

    def test_token_expirado_rechazado(self, escenario, dispositivo_activo):
        token = _token(escenario, dispositivo_activo, ttl=-10)
        with pytest.raises(TokenError):
            decode_token(token)


# === derivacion de rol y ruta desde la base ===


class TestDerivacionContexto:
    def test_cobrador_con_ruta_deriva_ruta_activa(self, client, escenario, dispositivo_activo):
        token = _token(escenario, dispositivo_activo)
        r = client.get("/api/dispositivos", headers=_auth_header(token))
        assert r.status_code == 200, r.text

    def test_cobrador_sin_ruta_activa_401(self, client, db_session, escenario, dispositivo_activo):
        """Ruta desactivada -> la base manda -> 401 (no sobrevive a reasignacion)."""
        ruta = db_session.get(Ruta, escenario["ruta_id"])
        ruta.activa = 0
        db_session.flush()
        token = _token(escenario, dispositivo_activo)
        r = client.get("/api/dispositivos", headers=_auth_header(token))
        assert r.status_code == 401, r.text

    def test_dispositivo_revocado_401_inmediato(self, client, db_session, escenario, dispositivo_activo):
        """Revocacion con bump mata el token aunque exp no llego."""
        token = _token(escenario, dispositivo_activo)
        disp = db_session.get(Dispositivo, dispositivo_activo["dispositivo_id"])
        disp.estado = "REVOKED"
        disp.version_asignacion = 2
        db_session.flush()
        r = client.get("/api/dispositivos", headers=_auth_header(token))
        assert r.status_code == 401, r.text

    def test_bump_version_solo_mata_el_token_viejo(self, client, escenario, dispositivo_activo):
        """Token con version antigua -> 401; token nuevo con la version vigente -> ok."""
        token_viejo = _token(escenario, dispositivo_activo, version=1)
        token_nuevo = _token(escenario, dispositivo_activo, version=1)
        r = client.get("/api/dispositivos", headers=_auth_header(token_viejo))
        assert r.status_code == 200, r.text
        r = client.get("/api/dispositivos", headers=_auth_header(token_nuevo))
        assert r.status_code == 200, r.text

    def test_token_sin_header_401(self, client, monkeypatch):
        """En produccion, request sin Bearer JWT -> 401 (query-param auth desactivado)."""
        monkeypatch.setenv("DAILY_ENV", "production")
        r = client.get("/api/dispositivos")
        assert r.status_code == 401, r.text


# === renovacion challenge-response JCS daily-auth-v1 ===


class TestRenovacion:
    def _payload_firma(self, token, dispositivo_activo, expires_at=None):
        claims = decode_token(token)
        exp = expires_at or _rfc3339_futura(5)
        payload = build_signed_payload(
            environment="development",
            device_id=str(dispositivo_activo["dispositivo_id"]),
            nonce=claims["jti"],
            public_key_hash=dispositivo_activo["public_key_hash"],
            expires_at=exp,
        )
        firma = _sign(dispositivo_activo["private_key"], payload)
        return payload, firma, exp

    def test_renovacion_valida_emite_token_nuevo(self, client, escenario, dispositivo_activo):
        token = _token(escenario, dispositivo_activo)
        _, firma, exp = self._payload_firma(token, dispositivo_activo)
        r = client.post(
            "/api/mobile/auth/renovar",
            json={"token": token, "firma": firma, "expires_at": exp},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["version_asignacion"] == 1
        nuevo = decode_token(body["token"])
        assert nuevo["dispositivo_id"] == str(dispositivo_activo["dispositivo_id"])
        assert nuevo["jti"] != decode_token(token)["jti"]

    def test_renovacion_firma_invalida_401(self, client, escenario, dispositivo_activo):
        token = _token(escenario, dispositivo_activo)
        claims = decode_token(token)
        payload = build_signed_payload(
            environment="development",
            device_id=str(dispositivo_activo["dispositivo_id"]),
            nonce=claims["jti"],
            public_key_hash=dispositivo_activo["public_key_hash"],
            expires_at=_rfc3339_futura(5),
        )
        otra_priv, _, _ = _ec_keypair()
        firma = _sign(otra_priv, payload)
        r = client.post(
            "/api/mobile/auth/renovar",
            json={"token": token, "firma": firma, "expires_at": _rfc3339_futura(5)},
        )
        assert r.status_code == 401, r.text

    def test_renovacion_token_expirado_401(self, client, escenario, dispositivo_activo):
        """Token expirado no se renueva fuera de vigencia (aun con firma valida)."""
        token_expirado = _token(escenario, dispositivo_activo, ttl=-10)
        token_valido = _token(escenario, dispositivo_activo)
        _, firma, exp = self._payload_firma(token_valido, dispositivo_activo)
        r = client.post(
            "/api/mobile/auth/renovar",
            json={"token": token_expirado, "firma": firma, "expires_at": exp},
        )
        assert r.status_code == 401, r.text

    def test_renovacion_expires_at_fuera_ventana_401(self, client, escenario, dispositivo_activo):
        """expires_at demasiado lejano o en el pasado -> rechazado (limita replay)."""
        token = _token(escenario, dispositivo_activo)
        for lejos in (_rfc3339_futura(60), _rfc3339_futura(-5)):
            _, firma, _ = self._payload_firma(token, dispositivo_activo, expires_at=lejos)
            r = client.post(
                "/api/mobile/auth/renovar",
                json={"token": token, "firma": firma, "expires_at": lejos},
            )
            assert r.status_code == 401, r.text

    def test_renovacion_version_desactualizada_401(self, client, db_session, escenario, dispositivo_activo):
        """Revocacion entre emision y renovacion -> renovacion falla."""
        token = _token(escenario, dispositivo_activo)
        disp = db_session.get(Dispositivo, dispositivo_activo["dispositivo_id"])
        disp.version_asignacion = 3
        db_session.flush()
        _, firma, exp = self._payload_firma(token, dispositivo_activo)
        r = client.post(
            "/api/mobile/auth/renovar",
            json={"token": token, "firma": firma, "expires_at": exp},
        )
        assert r.status_code == 401, r.text


# === concurrencia real PostgreSQL ===


class TestRenovacionConcurrente:
    def test_renovaciones_simultaneas_un_mismo_dispositivo(self):
        """Dos renovaciones en paralelo del mismo dispositivo: ambas valen, una
        sola fila, tokens nuevos con la misma version (la base manda)."""
        from src.database import SessionLocal
        from src.services.auth_service import renovar_sesion

        dialect = SessionLocal().get_bind().dialect.name
        if dialect != "postgresql":
            pytest.skip("concurrencia real exige PostgreSQL (SELECT FOR UPDATE)")

        nid, cob_id, r1_id = uuid4(), uuid4(), uuid4()
        private_key, spki, pk_hash = _ec_keypair()
        dev_id = uuid4()
        s = SessionLocal()
        try:
            s.add(Negocio(id=nid, nombre="Neg", nit="1"))
            s.add(Usuario(id=cob_id, negocio_id=nid, rol="COBRADOR", nombre="Cob"))
            s.add(Ruta(id=r1_id, negocio_id=nid, nombre="R1", cobrador_id=cob_id, activa=1))
            s.commit()
        finally:
            s.close()
        s = SessionLocal()
        try:
            s.add(
                Dispositivo(
                    id=dev_id,
                    negocio_id=nid,
                    usuario_id=cob_id,
                    public_key=spki,
                    public_key_hash=pk_hash,
                    algoritmo_clave="EC_P256",
                    estado="ACTIVE",
                    version_asignacion=1,
                    activo=1,
                )
            )
            s.commit()
        finally:
            s.close()

        dispositivo_activo = {
            "dispositivo_id": dev_id,
            "private_key": private_key,
            "public_key_hash": pk_hash,
        }
        escenario = {"negocio_id": nid, "cobrador_id": cob_id}
        token = _token(escenario, dispositivo_activo)
        claims = decode_token(token)
        exp = _rfc3339_futura(5)
        payload = build_signed_payload(
            environment="development",
            device_id=str(dispositivo_activo["dispositivo_id"]),
            nonce=claims["jti"],
            public_key_hash=dispositivo_activo["public_key_hash"],
            expires_at=exp,
        )
        firma = _sign(dispositivo_activo["private_key"], payload)

        resultados = []

        def renovar_thread():
            s = SessionLocal()
            try:
                r = renovar_sesion(s, token, firma, exp)
                s.commit()
                resultados.append(("ok", r.token))
            except Exception as e:  # noqa: BLE001
                s.rollback()
                resultados.append(("err", type(e).__name__))
            finally:
                s.close()

        t1 = threading.Thread(target=renovar_thread)
        t2 = threading.Thread(target=renovar_thread)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        ok = [r for r in resultados if r[0] == "ok"]
        assert len(ok) == 2, resultados
        tokens_nuevos = [r[1] for r in ok]
        assert len(tokens_nuevos) == 2, "dos renovaciones, dos tokens (jti unico)"
        versiones = {decode_token(t)["version_asignacion"] for t in tokens_nuevos}
        assert versiones == {1}, "la base manda: misma version en ambos tokens"
        dispositivos = {decode_token(t)["dispositivo_id"] for t in tokens_nuevos}
        assert dispositivos == {str(dispositivo_activo["dispositivo_id"])}
        dev_count = (
            SessionLocal()
            .query(Dispositivo)
            .filter(Dispositivo.id == dispositivo_activo["dispositivo_id"])
            .count()
        )
        assert dev_count == 1

        s = SessionLocal()
        try:
            s.query(Dispositivo).filter(Dispositivo.id == dev_id).delete(
                synchronize_session=False
            )
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
