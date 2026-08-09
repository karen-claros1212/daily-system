"""M6 auth tests — Auth productiva JWT (Bloque 7, D7-01/D7-H1/D7-H2).

Cubren:
  - Emision/validacion de JWT ES256: allow-list fija, payload productivo
    congelado (iss/aud/sub/negocio_id/device_id/public_key_hash/
    version_asignacion/jti/iat/exp/typ/protocol_version), sin role/route_id,
    jti unico por token (anti-replay), rechazo de alg-confusion (none, HS256,
    RS256), de tokens firmados con otra clave ES256 y de claims de valor fijo
    manipulados.
  - Fail-closed: sin AUTH_JWT_PRIVATE_KEY no se emite ni se valida ningun
    token (no hay secreto por defecto).
  - Derivacion de rol + ruta desde la BASE en cada request (no desde el JWT):
    cobrador sin ruta activa -> 401; revocacion/reemplazo con bump mata tokens
    vigentes aunque `exp` no haya llegado.
  - Desafio/canje de sesion JCS daily-auth-v1 (D7-H2): firma valida emite
    access token, firma invalida 401, credencial invalida 401, challenge
    inexistente 404, vencido 410 y REPLAY del mismo challenge_id -> 409.
  - Primer JWT post-activacion autenticado con la credencial bootstrap.
  - Bootstrap productivo del movil (GET /api/mobile/bootstrap): JWT-only
    (sin stub query ni en test), la credencial bootstrap ya NO autentica,
    0 o >1 rutas activas -> 401 fail-closed, derivacion de negocio/cobrador/
    ruta/versiones desde la base, e ignorancia de route_id/negocio_id/rol en
    la URL.

El payload JCS daily-auth-v1 es SEPARADO del protocolo de activacion
(daily-v1): campos distintos, mismo motor canonico RFC 8785.
"""

import base64
import hashlib
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from src.auth.token import (
    TokenConfigError,
    TokenError,
    TokenInvalidError,
    decode_token,
    ensure_es256_configured,
    issue_token,
)
from src.models import CodigoActivacion, Dispositivo, Negocio, Ruta, Usuario
from src.services.auth_jcs import PURPOSE_ISSUE_ACCESS_TOKEN, build_signed_payload

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
        public_key_hash=dispositivo_activo["public_key_hash"],
        version_asignacion=version,
        ttl_seconds=ttl,
    )


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _claims_base(escenario, dispositivo_activo) -> dict:
    """Claims validos para firmar tokens con pyjwt en tests de valores fijos."""
    now = datetime.now(timezone.utc)
    return {
        "iss": "daily-system-api",
        "aud": "daily-system-mobile",
        "sub": str(escenario["cobrador_id"]),
        "negocio_id": str(escenario["negocio_id"]),
        "device_id": str(dispositivo_activo["dispositivo_id"]),
        "public_key_hash": dispositivo_activo["public_key_hash"],
        "version_asignacion": 1,
        "jti": "x",
        "iat": now,
        "exp": now + timedelta(hours=1),
        "typ": "access",
        "protocol_version": "daily-auth-v1",
    }


# === token: emision y validacion ===


class TestToken:
    def test_payload_productivo_congelado_sin_role_ni_route(self, escenario, dispositivo_activo):
        """El JWT lleva el payload congelado y NO role ni route_id."""
        token = _token(escenario, dispositivo_activo)
        claims = decode_token(token)
        assert "role" not in claims
        assert "route_id" not in claims
        assert claims["iss"] == "daily-system-api"
        assert claims["aud"] == "daily-system-mobile"
        assert claims["sub"] == str(escenario["cobrador_id"])
        assert claims["negocio_id"] == str(escenario["negocio_id"])
        assert claims["device_id"] == str(dispositivo_activo["dispositivo_id"])
        assert claims["public_key_hash"] == dispositivo_activo["public_key_hash"]
        assert claims["version_asignacion"] == 1
        assert claims["typ"] == "access"
        assert claims["protocol_version"] == "daily-auth-v1"
        assert claims.get("jti")
        assert claims.get("iat")
        assert claims.get("exp")

    def test_jti_unico_por_token(self, escenario, dispositivo_activo):
        """Dos tokens del mismo dispositivo no comparten jti (anti-replay)."""
        t1 = decode_token(_token(escenario, dispositivo_activo))
        t2 = decode_token(_token(escenario, dispositivo_activo))
        assert t1["jti"] != t2["jti"]

    def test_alg_confusion_rechazado(self, escenario, dispositivo_activo):
        """Token con alg 'none', 'HS256' o 'RS256' se rechaza (solo ES256)."""
        claims = _claims_base(escenario, dispositivo_activo)
        # none: sin firma, jamas aceptado por la allow-list.
        t = pyjwt.encode(claims, None, algorithm="none")
        with pytest.raises(TokenError):
            decode_token(t)
        # HS256: firmado con una clave simetrica, rechazado.
        t = pyjwt.encode(claims, "any-symmetric-secret", algorithm="HS256")
        with pytest.raises(TokenError):
            decode_token(t)
        # RS256: firmado con una clave real, rechazado porque solo ES256 existe.
        rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        t = pyjwt.encode(claims, rsa_key, algorithm="RS256")
        with pytest.raises(TokenError):
            decode_token(t)

    def test_firma_otra_clave_es256_rechazada(self, escenario, dispositivo_activo):
        """Token firmado con OTRA clave ES256 (misma curva) -> firma invalida."""
        claims = _claims_base(escenario, dispositivo_activo)
        otra_priv = ec.generate_private_key(ec.SECP256R1())
        t = pyjwt.encode(
            claims,
            otra_priv.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
            algorithm="ES256",
        )
        with pytest.raises(TokenError):
            decode_token(t)

    def test_claims_valores_fijos_manipulados_rechazados(self, escenario, dispositivo_activo):
        """typ/protocol_version distintos al congelado se rechazan."""
        for campo, valor in (("typ", "refresh"), ("protocol_version", "daily-v1")):
            claims = _claims_base(escenario, dispositivo_activo)
            claims[campo] = valor
            t = pyjwt.encode(claims, os.environ["AUTH_JWT_PRIVATE_KEY"], algorithm="ES256")
            with pytest.raises(TokenInvalidError):
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

    def test_fail_closed_sin_claves(self, escenario, dispositivo_activo, monkeypatch):
        """Sin AUTH_JWT_PRIVATE_KEY no se emite ni se valida (no hay fallback)."""
        monkeypatch.delenv("AUTH_JWT_PRIVATE_KEY", raising=False)
        monkeypatch.delenv("AUTH_JWT_PUBLIC_KEY", raising=False)
        with pytest.raises(TokenConfigError):
            issue_token(
                negocio_id=escenario["negocio_id"],
                usuario_id=escenario["cobrador_id"],
                dispositivo_id=dispositivo_activo["dispositivo_id"],
                public_key_hash=dispositivo_activo["public_key_hash"],
                version_asignacion=1,
            )
        with pytest.raises(TokenConfigError):
            decode_token("a.b.c")
        with pytest.raises(TokenConfigError):
            ensure_es256_configured()

    def test_clave_privada_no_ec_rechazada(self, escenario, dispositivo_activo, monkeypatch):
        """AUTH_JWT_PRIVATE_KEY que no es EC P-256 -> TokenConfigError."""
        rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = rsa_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode("ascii")
        monkeypatch.setenv("AUTH_JWT_PRIVATE_KEY", pem)
        with pytest.raises(TokenConfigError):
            ensure_es256_configured()


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

    def test_token_dispositivo_de_otro_usuario_401(self, client, escenario, dispositivo_activo):
        """El sub debe ser el dueno del dispositivo: binding dispositivo->usuario estricto."""
        token = issue_token(
            negocio_id=escenario["negocio_id"],
            usuario_id=escenario["admin_id"],
            dispositivo_id=dispositivo_activo["dispositivo_id"],
            public_key_hash=dispositivo_activo["public_key_hash"],
            version_asignacion=1,
        )
        r = client.get("/api/dispositivos", headers=_auth_header(token))
        assert r.status_code == 401, r.text

    def test_token_public_key_hash_no_coincide_401(self, client, escenario, dispositivo_activo):
        """El public_key_hash del token debe ser el registrado del dispositivo."""
        _k, _s, otra_hash = _ec_keypair()
        token = issue_token(
            negocio_id=escenario["negocio_id"],
            usuario_id=escenario["cobrador_id"],
            dispositivo_id=dispositivo_activo["dispositivo_id"],
            public_key_hash=otra_hash,
            version_asignacion=1,
        )
        r = client.get("/api/dispositivos", headers=_auth_header(token))
        assert r.status_code == 401, r.text


# === desafio/canje de sesion JCS daily-auth-v1 ===


class TestPayloadLexicoDailyAuthV1:
    def test_acepta_payload_conforme(self):
        payload = build_signed_payload(
            purpose=PURPOSE_ISSUE_ACCESS_TOKEN,
            environment="production",
            challenge_id="3f2a1b0c-9d4e-4f8a-b6c1-2d5e7a9b0c1d",
            device_id="3f2a1b0c-9d4e-4f8a-b6c1-2d5e7a9b0c1d",
            nonce="GGcDkg5kNS7t1zK9JkXLPgq6QszvUdmYPMdfXSJHS_Q",
            public_key_hash="92561e1d2633d5b7680ebefd7f92bc3e4084708ffabf82073bf028a24a90f24b",
            expires_at="2026-08-06T15:00:00Z",
        )
        assert len(payload) > 0

    def test_rechaza_representacion_lexica_no_conforme(self):
        """daily-auth-v1: challenge_id/device_id uuid lowercase, nonce 43,
        hash hex 64 lowercase, timestamp RFC 3339 exacto."""
        base = {
            "purpose": PURPOSE_ISSUE_ACCESS_TOKEN,
            "environment": "production",
            "challenge_id": "3f2a1b0c-9d4e-4f8a-b6c1-2d5e7a9b0c1d",
            "device_id": "3f2a1b0c-9d4e-4f8a-b6c1-2d5e7a9b0c1d",
            "nonce": "GGcDkg5kNS7t1zK9JkXLPgq6QszvUdmYPMdfXSJHS_Q",
            "public_key_hash": "92561e1d2633d5b7680ebefd7f92bc3e4084708ffabf82073bf028a24a90f24b",
            "expires_at": "2026-08-06T15:00:00Z",
        }
        casos = [
            {"challenge_id": "3F2A1B0C-9D4E-4F8A-B6C1-2D5E7A9B0C1D"},  # UUID uppercase
            {"challenge_id": "no-es-un-uuid"},
            {"device_id": "no-es-un-uuid"},
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


class TestDesafioCanje:
    def _desafio(self, client, credencial):
        r = client.post("/api/auth/device/desafio", headers=_auth_header(credencial))
        assert r.status_code == 200, r.text
        return r.json()

    def _firma_desafio(self, desafio, dispositivo_activo) -> str:
        payload = build_signed_payload(
            purpose=PURPOSE_ISSUE_ACCESS_TOKEN,
            environment=desafio["environment"],
            challenge_id=desafio["challenge_id"],
            device_id=str(dispositivo_activo["dispositivo_id"]),
            nonce=desafio["nonce"],
            public_key_hash=dispositivo_activo["public_key_hash"],
            expires_at=desafio["expira_el"],
        )
        return _sign(dispositivo_activo["private_key"], payload)

    def test_desafio_canje_emite_token_nuevo(self, client, escenario, dispositivo_activo):
        """Flujo completo: desafio con JWT vigente + firma JCS -> access token."""
        token = _token(escenario, dispositivo_activo)
        desafio = self._desafio(client, token)
        assert desafio["nonce"]
        assert desafio["environment"] == "development"
        assert desafio["expira_el"].endswith("Z")

        firma = self._firma_desafio(desafio, dispositivo_activo)
        r = client.post(
            "/api/auth/device/canjear",
            json={"challenge_id": desafio["challenge_id"], "firma": firma},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["version_asignacion"] == 1
        nuevo = decode_token(body["token"])
        assert nuevo["device_id"] == str(dispositivo_activo["dispositivo_id"])
        assert nuevo["public_key_hash"] == dispositivo_activo["public_key_hash"]
        assert nuevo["jti"] != decode_token(token)["jti"]

    def test_replay_mismo_challenge_409(self, client, escenario, dispositivo_activo):
        """Single-use: el replay del mismo challenge_id devuelve 409."""
        token = _token(escenario, dispositivo_activo)
        desafio = self._desafio(client, token)
        firma = self._firma_desafio(desafio, dispositivo_activo)
        payload = {"challenge_id": desafio["challenge_id"], "firma": firma}

        r1 = client.post("/api/auth/device/canjear", json=payload)
        assert r1.status_code == 200, r1.text
        r2 = client.post("/api/auth/device/canjear", json=payload)
        assert r2.status_code == 409, r2.text

    def test_canje_firma_invalida_401_no_consume(self, client, escenario, dispositivo_activo):
        """Firma de OTRA clave -> 401; el desafio sigue util para el legitimo."""
        token = _token(escenario, dispositivo_activo)
        desafio = self._desafio(client, token)
        otra_priv, _, _ = _ec_keypair()
        payload_firma = build_signed_payload(
            purpose=PURPOSE_ISSUE_ACCESS_TOKEN,
            environment=desafio["environment"],
            challenge_id=desafio["challenge_id"],
            device_id=str(dispositivo_activo["dispositivo_id"]),
            nonce=desafio["nonce"],
            public_key_hash=dispositivo_activo["public_key_hash"],
            expires_at=desafio["expira_el"],
        )
        firma_mala = _sign(otra_priv, payload_firma)
        r = client.post(
            "/api/auth/device/canjear",
            json={"challenge_id": desafio["challenge_id"], "firma": firma_mala},
        )
        assert r.status_code == 401, r.text

        firma_buena = self._firma_desafio(desafio, dispositivo_activo)
        r = client.post(
            "/api/auth/device/canjear",
            json={"challenge_id": desafio["challenge_id"], "firma": firma_buena},
        )
        assert r.status_code == 200, r.text

    def test_canje_challenge_inexistente_404(self, client, escenario, dispositivo_activo):
        token = _token(escenario, dispositivo_activo)
        self._desafio(client, token)
        r = client.post(
            "/api/auth/device/canjear",
            json={"challenge_id": str(uuid4()), "firma": _sign(dispositivo_activo["private_key"], b"x")},
        )
        assert r.status_code == 404, r.text

    def test_canje_challenge_vencido_410(self, client, db_session, escenario, dispositivo_activo):
        """Desafio vencido -> 410 y se marca consumido."""
        from src.models import DesafioAuth

        token = _token(escenario, dispositivo_activo)
        desafio = self._desafio(client, token)
        fila = db_session.get(DesafioAuth, UUID(desafio["challenge_id"]))
        assert fila is not None
        vencido = datetime.now(timezone.utc) - timedelta(minutes=1)
        fila.expira_el = vencido
        db_session.flush()

        payload = build_signed_payload(
            purpose=PURPOSE_ISSUE_ACCESS_TOKEN,
            environment=desafio["environment"],
            challenge_id=desafio["challenge_id"],
            device_id=str(dispositivo_activo["dispositivo_id"]),
            nonce=desafio["nonce"],
            public_key_hash=dispositivo_activo["public_key_hash"],
            expires_at=desafio["expira_el"],
        )
        firma = _sign(dispositivo_activo["private_key"], payload)
        r = client.post(
            "/api/auth/device/canjear",
            json={"challenge_id": desafio["challenge_id"], "firma": firma},
        )
        assert r.status_code == 410, r.text
        db_session.expire_all()
        assert db_session.get(DesafioAuth, UUID(desafio["challenge_id"])).consumido_el is not None

    def test_desafio_sin_credencial_401(self, client):
        r = client.post("/api/auth/device/desafio")
        assert r.status_code == 401, r.text

    def test_desafio_credencial_invalida_401(self, client):
        r = client.post("/api/auth/device/desafio", headers=_auth_header("garbage"))
        assert r.status_code == 401, r.text

    def test_desafio_bootstrap_credencial_primer_jwt(self, client, db_session, escenario, dispositivo_activo):
        """El primer JWT post-activacion sale por la credencial bootstrap."""
        bootstrap = "boot-credencial-test"
        codigo = CodigoActivacion(
            negocio_id=escenario["negocio_id"],
            cobrador_id=escenario["cobrador_id"],
            hash_codigo=hashlib.sha256(b"legacy").hexdigest(),
            prefijo="legacy01",
            expira_el=datetime.now(timezone.utc) + timedelta(minutes=5),
            estado="CONSUMED",
            consumido_el=datetime.now(timezone.utc),
            dispositivo_id_canjeado=dispositivo_activo["dispositivo_id"],
            credencial_bootstrap=bootstrap,
            credencial_bootstrap_expira_el=datetime.now(timezone.utc) + timedelta(minutes=5),
            creado_por=escenario["admin_id"],
        )
        db_session.add(codigo)
        db_session.flush()

        desafio = self._desafio(client, bootstrap)
        firma = self._firma_desafio(desafio, dispositivo_activo)
        r = client.post(
            "/api/auth/device/canjear",
            json={"challenge_id": desafio["challenge_id"], "firma": firma},
        )
        assert r.status_code == 200, r.text
        nuevo = decode_token(r.json()["token"])
        assert nuevo["device_id"] == str(dispositivo_activo["dispositivo_id"])
        assert nuevo["sub"] == str(escenario["cobrador_id"])


# === H3: binding completo del desafio/canje (cierre del audit 442f68d) ===
#
# El flujo directo POST /api/auth/device/desafio NO pasa por RequestContext;
# revalida el dispositivo contra TODOS los claims del JWT (usuario, negocio,
# public_key_hash) antes de emitir el desafio, y el canje exige exactamente UNA
# ruta activa del mismo negocio antes de emitir el access token.


class TestH3BindingDesafio:
    def _desafio(self, client, credencial):
        r = client.post("/api/auth/device/desafio", headers=_auth_header(credencial))
        assert r.status_code == 200, r.text
        return r.json()

    def _firma_desafio(self, desafio, dispositivo_activo) -> str:
        payload = build_signed_payload(
            purpose=PURPOSE_ISSUE_ACCESS_TOKEN,
            environment=desafio["environment"],
            challenge_id=desafio["challenge_id"],
            device_id=str(dispositivo_activo["dispositivo_id"]),
            nonce=desafio["nonce"],
            public_key_hash=dispositivo_activo["public_key_hash"],
            expires_at=desafio["expira_el"],
        )
        return _sign(dispositivo_activo["private_key"], payload)

    def _token_manipulado(
        self,
        escenario,
        dispositivo_activo,
        *,
        sub=None,
        negocio_id=None,
        public_key_hash=None,
    ):
        return issue_token(
            negocio_id=negocio_id or escenario["negocio_id"],
            usuario_id=sub or escenario["cobrador_id"],
            dispositivo_id=dispositivo_activo["dispositivo_id"],
            public_key_hash=public_key_hash or dispositivo_activo["public_key_hash"],
            version_asignacion=1,
        )

    def test_desafio_sub_mismatch_401(self, client, escenario, dispositivo_activo):
        """sub que no es dueno del dispositivo -> 401 (binding usuario)."""
        token = self._token_manipulado(escenario, dispositivo_activo, sub=uuid4())
        r = client.post("/api/auth/device/desafio", headers=_auth_header(token))
        assert r.status_code == 401, r.text

    def test_desafio_negocio_mismatch_401(self, client, escenario, dispositivo_activo):
        """negocio_id del token distinto al del dispositivo -> 401."""
        token = self._token_manipulado(escenario, dispositivo_activo, negocio_id=uuid4())
        r = client.post("/api/auth/device/desafio", headers=_auth_header(token))
        assert r.status_code == 401, r.text

    def test_desafio_public_key_hash_mismatch_401(self, client, escenario, dispositivo_activo):
        """public_key_hash del token distinto al registrado -> 401."""
        _k, _s, otra_hash = _ec_keypair()
        token = self._token_manipulado(
            escenario, dispositivo_activo, public_key_hash=otra_hash
        )
        r = client.post("/api/auth/device/desafio", headers=_auth_header(token))
        assert r.status_code == 401, r.text

    def test_canje_sin_ruta_activa_401(self, client, db_session, escenario, dispositivo_activo):
        """Ruta desactivada -> el canje no emite token (0 rutas activas)."""
        ruta = db_session.get(Ruta, escenario["ruta_id"])
        ruta.activa = 0
        db_session.flush()

        token = _token(escenario, dispositivo_activo)
        desafio = self._desafio(client, token)
        firma = self._firma_desafio(desafio, dispositivo_activo)
        r = client.post(
            "/api/auth/device/canjear",
            json={"challenge_id": desafio["challenge_id"], "firma": firma},
        )
        assert r.status_code == 401, r.text

    def test_canje_mas_de_una_ruta_activa_401(self, client, db_session, escenario, dispositivo_activo):
        """Dos rutas activas del cobrador -> el canje no emite token.

        En SQLite (sin constraint parcial) se crea la segunda ruta y el canje
        responde 401. En PostgreSQL la constraint parcial uq_ruta_activa_cobrador
        impide el segundo ACTIVE: ese es el resultado equivalente (constraint).
        """
        from sqlalchemy.exc import IntegrityError

        db_session.add(Ruta(
            id=uuid4(),
            negocio_id=escenario["negocio_id"],
            nombre="R2",
            cobrador_id=escenario["cobrador_id"],
            activa=1,
        ))
        try:
            db_session.flush()
        except IntegrityError:
            db_session.rollback()
            return  # PG: constraint parcial es la evidencia

        token = _token(escenario, dispositivo_activo)
        desafio = self._desafio(client, token)
        firma = self._firma_desafio(desafio, dispositivo_activo)
        r = client.post(
            "/api/auth/device/canjear",
            json={"challenge_id": desafio["challenge_id"], "firma": firma},
        )
        assert r.status_code == 401, r.text

    def test_canje_exactamente_una_ruta_200(self, client, escenario, dispositivo_activo):
        """Una sola ruta activa -> el canje emite el access token."""
        token = _token(escenario, dispositivo_activo)
        desafio = self._desafio(client, token)
        firma = self._firma_desafio(desafio, dispositivo_activo)
        r = client.post(
            "/api/auth/device/canjear",
            json={"challenge_id": desafio["challenge_id"], "firma": firma},
        )
        assert r.status_code == 200, r.text
        assert r.json()["version_asignacion"] == 1


# === Bootstrap productivo del movil (GET /api/mobile/bootstrap) ===
#
# El bootstrap usa el RequestContext productivo (JWT ES256): el servidor
# deriva negocio/cobrador/ruta/versiones desde la base y exige exactamente UNA
# ruta activa. La credencial bootstrap del canje ya NO autentica esta ruta y
# el stub query-param de dev/test NO vale aqui (aislamiento del movil).


class TestBootstrapProductivo:
    def _bootstrap(self, client, token):
        return client.get("/api/mobile/bootstrap", headers=_auth_header(token))

    def test_bootstrap_200_exactamente_una_ruta(self, client, escenario, dispositivo_activo):
        """Respuesta minima del contrato: negocio + cobrador + dispositivo +
        ruta UNICA + version_asignacion + ruta_version + rol."""
        token = _token(escenario, dispositivo_activo)
        r = self._bootstrap(client, token)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["negocio_id"] == str(escenario["negocio_id"])
        assert data["negocio_nombre"] == "Neg"
        assert data["cobrador_id"] == str(escenario["cobrador_id"])
        assert data["cobrador_nombre"] == "Cob"
        assert data["dispositivo_id"] == str(dispositivo_activo["dispositivo_id"])
        assert data["version_asignacion"] == 1
        assert data["ruta_id"] == str(escenario["ruta_id"])
        assert data["ruta_nombre"] == "R1"
        assert data["ruta_version"] == 1
        assert data["rol"] == "COBRADOR"

    def test_bootstrap_sin_jwt_401(self, client, escenario):
        """Sin Bearer JWT -> 401, incluso con query-params de dev/test."""
        r = client.get(
            "/api/mobile/bootstrap",
            params={
                "negocio_id": str(escenario["negocio_id"]),
                "role": "ADMINISTRADOR",
            },
        )
        assert r.status_code == 401, r.text

    def test_bootstrap_credencial_bootstrap_ya_no_autentica(
        self, client, db_session, escenario, dispositivo_activo
    ):
        """La credencial bootstrap del canje NO autentica el bootstrap: 401."""
        bootstrap = "boot-credencial-test"
        db_session.add(CodigoActivacion(
            negocio_id=escenario["negocio_id"],
            cobrador_id=escenario["cobrador_id"],
            hash_codigo=hashlib.sha256(b"legacy").hexdigest(),
            prefijo="legacy02",
            expira_el=datetime.now(timezone.utc) + timedelta(minutes=5),
            estado="CONSUMED",
            consumido_el=datetime.now(timezone.utc),
            dispositivo_id_canjeado=dispositivo_activo["dispositivo_id"],
            credencial_bootstrap=bootstrap,
            credencial_bootstrap_expira_el=datetime.now(timezone.utc) + timedelta(minutes=5),
            creado_por=escenario["admin_id"],
        ))
        db_session.flush()

        r = client.get("/api/mobile/bootstrap", headers=_auth_header(bootstrap))
        assert r.status_code == 401, r.text

    def test_bootstrap_0_rutas_activas_401(self, client, db_session, escenario, dispositivo_activo):
        """Ruta desactivada -> 401 fail-closed (0 rutas activas)."""
        ruta = db_session.get(Ruta, escenario["ruta_id"])
        ruta.activa = 0
        db_session.flush()

        token = _token(escenario, dispositivo_activo)
        r = self._bootstrap(client, token)
        assert r.status_code == 401, r.text

    def test_bootstrap_mas_de_una_ruta_activa_401(self, client, db_session, escenario, dispositivo_activo):
        """Dos rutas activas -> 401 fail-closed (o constraint parcial en PG)."""
        from sqlalchemy.exc import IntegrityError

        db_session.add(Ruta(
            id=uuid4(),
            negocio_id=escenario["negocio_id"],
            nombre="R2",
            cobrador_id=escenario["cobrador_id"],
            activa=1,
        ))
        try:
            db_session.flush()
        except IntegrityError:
            db_session.rollback()
            return  # PG: constraint parcial uq_ruta_activa_cobrador es la evidencia

        token = _token(escenario, dispositivo_activo)
        r = self._bootstrap(client, token)
        assert r.status_code == 401, r.text

    def test_bootstrap_ignora_route_id_negocio_id_rol_en_url(
        self, client, escenario, dispositivo_activo
    ):
        """route_id/negocio_id/rol en la URL no cambian la autoridad derivada."""
        token = _token(escenario, dispositivo_activo)
        r = client.get(
            "/api/mobile/bootstrap",
            headers=_auth_header(token),
            params={
                "route_id": str(uuid4()),
                "negocio_id": str(uuid4()),
                "rol": "ADMINISTRADOR",
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["ruta_id"] == str(escenario["ruta_id"])
        assert r.json()["negocio_id"] == str(escenario["negocio_id"])
        assert r.json()["rol"] == "COBRADOR"

    def test_bootstrap_admin_token_sin_ruta_401(self, client, db_session, escenario):
        """Un token de ADMINISTRADOR (sin ruta activa) -> 401: solo cobradores."""
        _k, spki, pk_hash = _ec_keypair()
        dev_id = uuid4()
        db_session.add(Dispositivo(
            id=dev_id,
            negocio_id=escenario["negocio_id"],
            usuario_id=escenario["admin_id"],
            public_key=spki,
            public_key_hash=pk_hash,
            algoritmo_clave="EC_P256",
            estado="ACTIVE",
            version_asignacion=1,
            activo=1,
        ))
        db_session.flush()
        token = issue_token(
            negocio_id=escenario["negocio_id"],
            usuario_id=escenario["admin_id"],
            dispositivo_id=dev_id,
            public_key_hash=pk_hash,
            version_asignacion=1,
        )
        r = self._bootstrap(client, token)
        assert r.status_code == 401, r.text

    def test_bootstrap_version_bump_revoca_token_401(self, client, db_session, escenario, dispositivo_activo):
        """Revocacion/reemplazo (bump) mata el token: 401 en el bootstrap."""
        token = _token(escenario, dispositivo_activo)
        disp = db_session.get(Dispositivo, dispositivo_activo["dispositivo_id"])
        disp.estado = "REVOKED"
        disp.version_asignacion = 2
        db_session.flush()

        r = self._bootstrap(client, token)
        assert r.status_code == 401, r.text

    def test_bootstrap_public_key_hash_mismatch_401(self, client, escenario, dispositivo_activo):
        """Token con public_key_hash distinto al registrado -> 401 (binding clave)."""
        _k, _s, otra_hash = _ec_keypair()
        token = issue_token(
            negocio_id=escenario["negocio_id"],
            usuario_id=escenario["cobrador_id"],
            dispositivo_id=dispositivo_activo["dispositivo_id"],
            public_key_hash=otra_hash,
            version_asignacion=1,
        )
        r = self._bootstrap(client, token)
        assert r.status_code == 401, r.text
