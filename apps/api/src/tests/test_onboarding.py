"""Onboarding de negocios (Etapa 3 + HARDENING FINAL) — tests del alta segura.

Cubren:
  1. Alta valida: Negocio + ADMINISTRADOR inicial + codigo bootstrap en la
     misma transaccion, con defaults comerciales reales del modelo.
  2. Rollback total si falla el paso del codigo (todo-o-nada), verificado con
     un boundary transaccional HONESTO (SAVEPOINT con semantica productiva:
     commit on success / rollback on exception), sin rollback manual del test.
  3. NIT: normalizacion minima + conflicto server-side -> 409 (nunca 500).
     La autoridad final es el indice unico uq_negocio_nit (migracion
     m8_negocio_nit): una colision real de la base se mapea a 409, y una
     carrera en Postgres produce exactamente un 201 y un 409 (nunca 201+201).
  4. NIT vacio == sin NIT (multiples negocios sin NIT conviven).
  5. Payload invalido -> 422 (extra=forbid: ni negocio_id ni rol ni plan) y
     limites de contrato (nit/documento <= 50 caracteres).
  6. Sin creacion cross-tenant: el body publico no puede dirigir tenancy.
  7. POST /api/negocios legado NO existe como fabrica de tenants (404): la
     frontera de registro es unicamente POST /api/onboarding/negocios.
  8. El admin inicial completa el flujo real de login (desafio/canje/sesion)
     con el codigo bootstrap y /api/auth/me devuelve ADMINISTRADOR del negocio.
"""

import base64
import hashlib
import threading
import uuid
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.database import SessionLocal
from src.models import CodigoActivacion, Negocio, Usuario
from src.services.activacion_service import ActivacionError
from src.services.auth_jcs import (
    PURPOSE_ISSUE_ACCESS_TOKEN,
    build_signed_payload as build_auth_payload,
)
from src.services.jcs import PROTOCOL_VERSION, build_signed_payload
from src.services.onboarding_service import (
    OnboardingError,
    crear_negocio_con_admin,
)

ONBOARDING_URL = "/api/onboarding/negocios"


# === helpers criptograficos (misma estrategia que test_m5_activacion) ===


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


def _payload_alta(nombre="Negocio Nuevo", nit="900123456", documento="CC 1"):
    return {
        "nombre": nombre,
        "nit": nit,
        "administrador": {"nombre": "Admin Nuevo", "documento": documento},
    }


def _desafio(client, token, spki):
    return client.post(
        "/api/activaciones/desafio",
        json={
            "token": token,
            "clave_publica": spki,
            "modelo": "Chrome",
            "plataforma": "web",
        },
    )


def _firma_valida(desafio_resp, private_key, pk_hash):
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


def _primer_jwt(client, credencial_bootstrap, dispositivo_id, private_key, pk_hash):
    """Primer access token de sesion (daily-auth-v1) con la credencial."""
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


class TestAltaSegura:
    def test_01_crea_negocio_admin_y_codigo_en_una_transaccion(self, client, db_session):
        r = client.post(ONBOARDING_URL, json=_payload_alta())
        assert r.status_code == 201, r.text
        data = r.json()

        assert data["siguiente_paso"] == "activar_codigo"

        # Negocio con defaults comerciales reales del modelo (sin inventar).
        negocio = data["negocio"]
        assert negocio["nombre"] == "Negocio Nuevo"
        assert negocio["nit"] == "900123456"
        assert negocio["pais"] == "CO"
        assert negocio["moneda"] == "COP"
        assert negocio["plan"] == "basic"
        assert negocio["estado_suscripcion"] == "al_dia"
        assert "creado_el" in negocio

        # Admin inicial: rol ADMINISTRADOR, activo, del negocio exacto.
        admin = data["administrador"]
        assert admin["rol"] == "ADMINISTRADOR"
        assert admin["activo"] == 1
        assert admin["nombre"] == "Admin Nuevo"
        assert admin["documento"] == "CC 1"
        assert admin["negocio_id"] == negocio["id"]

        # Codigo bootstrap: token entregado una vez, digest persistido.
        codigo = data["codigo_activacion"]
        assert codigo["codigo_id"]
        assert codigo["token"]
        assert codigo["prefijo"] == codigo["token"][:8]
        assert "expira_el" in codigo

        # Estado real en DB (misma transaccion del request).
        db_negocio = db_session.query(Negocio).filter(Negocio.id == uuid.UUID(negocio["id"])).one()
        assert db_negocio.nit == "900123456"
        db_admin = db_session.query(Usuario).filter(Usuario.id == uuid.UUID(admin["id"])).one()
        assert db_admin.rol == "ADMINISTRADOR"
        assert db_admin.activo == 1
        db_codigo = db_session.query(CodigoActivacion).filter(
            CodigoActivacion.id == uuid.UUID(codigo["codigo_id"])
        ).one()
        assert db_codigo.hash_codigo == hashlib.sha256(codigo["token"].encode()).hexdigest()
        assert db_codigo.estado == "PENDING"
        assert db_codigo.negocio_id == db_negocio.id
        assert db_codigo.cobrador_id == db_admin.id

    def test_02_rollback_total_si_falla_el_bootstrap(self, client_atomico, db_session, monkeypatch):
        """Todo-o-nada verificado con un boundary transaccional HONESTO.

        En produccion el route escribe con get_db_transaction (commit on
        success / rollback on exception). El override comun de `client` es
        yield-only, lo que hacia esta prueba un FALSO POSITIVO: el rollback lo
        ejecutaba el propio test con db_session.rollback() a mano. Aqui
        `client_atomico` mantiene la semantica productiva dentro de un
        SAVEPOINT: ante el fallo del codigo el route debe revertir el todo por
        si mismo. Sin rollback manual: si algo sobrevive, es un defecto real.
        """

        def _falla(*args, **kwargs):
            raise ActivacionError("fallo simulado", "SIMULADO", 409)

        monkeypatch.setattr(
            "src.services.onboarding_service.generar_codigo",
            _falla,
        )

        r = client_atomico.post(ONBOARDING_URL, json=_payload_alta(nombre="Rollback SA"))
        assert r.status_code == 409, r.text
        assert r.json()["detail"] == "fallo simulado"

        # Las filas de la misma transaccion (negocio + admin + codigo) no deben
        # persistir: el boundary del fixture revirtio el SAVEPOINT ante la
        # excepcion. Ningun rollback manual aqui.
        assert db_session.query(Negocio).filter(Negocio.nombre == "Rollback SA").count() == 0
        assert (
            db_session.query(Usuario)
            .filter(Usuario.nombre == "Admin Nuevo", Usuario.rol == "ADMINISTRADOR")
            .count()
            == 0
        )
        assert db_session.query(CodigoActivacion).count() == 0

    def test_03_nit_duplicado_409_y_normalizado(self, client, db_session):
        r1 = client.post(ONBOARDING_URL, json=_payload_alta(nit="  900  ")
                         )
        # nit "  900  " se guarda sin espacios
        assert r1.status_code == 201, r1.text
        assert r1.json()["negocio"]["nit"] == "900"

        r2 = client.post(ONBOARDING_URL, json=_payload_alta(nombre="Otro", nit="900"))
        assert r2.status_code == 409, r2.text
        assert r2.json()["detail"] == "El NIT ya esta registrado"

        assert db_session.query(Negocio).filter(Negocio.nit == "900").count() == 1

    def test_04_nit_vacio_se_trata_como_sin_nit(self, client, db_session):
        for nombre in ("Sin Nit A", "Sin Nit B"):
            r = client.post(ONBOARDING_URL, json=_payload_alta(nombre=nombre, nit="   "))
            assert r.status_code == 201, r.text
            assert r.json()["negocio"]["nit"] is None
        assert db_session.query(Negocio).filter(Negocio.nit.is_(None)).count() == 2

    def test_05_payload_invalido_422(self, client, db_session):
        casos = [
            {},  # sin campos
            {"nombre": "Solo Nombre"},  # sin administrador
            {"nombre": "", "administrador": {"nombre": "A"}},  # nombre vacio
            {"nombre": "X", "administrador": {"nombre": ""}},  # admin sin nombre
            {**_payload_alta(), "negocio_id": str(uuid4())},  # tenancy por body
            {**_payload_alta(), "rol": "COBRADOR"},  # rol por body
            {**_payload_alta(), "plan": "premium"},  # plan por body
            {**_payload_alta(), "estado_suscripcion": "al_dia"},  # estado por body
        ]
        for caso in casos:
            r = client.post(ONBOARDING_URL, json=caso)
            assert r.status_code == 422, f"se esperaba 422 para {caso!r}: {r.text}"
        assert db_session.query(Negocio).count() == 0

    def test_06_body_publico_no_dirige_tenancy(self, client, db_session):
        """El alta es de tenancy nueva; ningun campo del body referencia ajenos."""
        payload = _payload_alta()
        payload["administrador"]["negocio_id"] = str(uuid4())
        r = client.post(ONBOARDING_URL, json=payload)
        assert r.status_code == 422, r.text
        assert db_session.query(Negocio).count() == 0

    def test_10_integridad_db_nit_es_autoridad_409(self, client_atomico, db_session, monkeypatch):
        """HARDENING: la colision de la base (uq_negocio_nit) se mapea a 409.

        El fast-path del servicio (SELECT) se neutraliza para forzar que la
        duplicidad la detecte el indice unico REAL de la base de datos: la
        autoridad de "el NIT ya esta registrado" es la DB, nunca una 500.
        """
        def _sin_fastpath(db, nit):
            return None

        monkeypatch.setattr(
            "src.services.onboarding_service.verificar_nit_disponible",
            _sin_fastpath,
        )

        r1 = client_atomico.post(ONBOARDING_URL, json=_payload_alta(nit="555"))
        assert r1.status_code == 201, r1.text

        r2 = client_atomico.post(
            ONBOARDING_URL,
            json=_payload_alta(nombre="Otro", nit="555"),
        )
        assert r2.status_code == 409, r2.text
        assert r2.json()["detail"] == "El NIT ya esta registrado"
        assert db_session.query(Negocio).filter(Negocio.nit == "555").count() == 1

    def test_11_nit_mayor_a_50_caracteres_422(self, client, db_session):
        """HARDENING: contrato publico nit <= 50 (422, nunca DataError/500)."""
        nit_largo = "9" * 51
        r = client.post(ONBOARDING_URL, json=_payload_alta(nit=nit_largo))
        assert r.status_code == 422, r.text
        assert db_session.query(Negocio).count() == 0

    def test_12_documento_mayor_a_50_caracteres_422(self, client, db_session):
        """HARDENING: contrato publico documento <= 50 (422, nunca 500)."""
        doc_largo = "D" * 51
        r = client.post(
            ONBOARDING_URL,
            json=_payload_alta(documento=doc_largo),
        )
        assert r.status_code == 422, r.text
        assert db_session.query(Negocio).count() == 0


class TestNitConcurrentePostgres:
    """HARDENING: dos POST con el MISMO NIT en paralelo (PostgreSQL real).

    Resultado obligatorio: exactamente un 201 y exactamente un 409. Nunca
    201+201 (lo impide el indice unico uq_negocio_nit) y nunca 500 (la
    colision real se mapea a 409 en el route). Requiere Postgres: las sesiones
    concurrentes usan SessionLocal con transacciones reales.
    """

    pytestmark = pytest.mark.skipif(
        str(SessionLocal().get_bind().dialect.name) != "postgresql",
        reason="concurrencia real de NIT exige PostgreSQL (indice unico)",
    )

    def test_13_dos_alta_concurrentes_mismo_nit_201_y_409(self):
        nit = f"9{uuid4().int % 100_000_000:08d}"
        barrier = threading.Barrier(2)
        resultados = []

        def intento(nombre):
            s = SessionLocal()
            try:
                barrier.wait()
                negocio, _admin, _codigo, _token = crear_negocio_con_admin(
                    s,
                    nombre=nombre,
                    nit=nit,
                    admin_nombre="Admin",
                    admin_documento="CC 1",
                )
                s.commit()
                resultados.append(("ok", nombre, str(negocio.id)))
            except OnboardingError as e:
                s.rollback()
                resultados.append(("conflicto", nombre, e.code))
            except IntegrityError:
                s.rollback()
                resultados.append(("conflicto", nombre, "INTEGRITY_UQ_NIT"))
            finally:
                s.close()

        t1 = threading.Thread(target=intento, args=("Concurrente A",))
        t2 = threading.Thread(target=intento, args=("Concurrente B",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        ok = [r for r in resultados if r[0] == "ok"]
        conflicto = [r for r in resultados if r[0] == "conflicto"]
        assert len(resultados) == 2, resultados
        assert len(ok) == 1, f"exactamente un 201: {resultados}"
        assert len(conflicto) == 1, f"exactamente un 409: {resultados}"
        assert conflicto[0][2] in ("NIT_YA_REGISTRADO", "INTEGRITY_UQ_NIT"), resultados

        # Estado durable: una sola fila con ese NIT y la invariante garantizada
        # por PostgreSQL (indice unico), no por la suerte del fast-path.
        s = SessionLocal()
        try:
            assert s.query(Negocio).filter(Negocio.nit == nit).count() == 1
            row = s.execute(
                text(
                    "SELECT 1 FROM pg_indexes "
                    "WHERE indexname = 'uq_negocio_nit' AND tablename = 'negocio'"
                )
            ).first()
            assert row is not None, (
                "la invariante de NIT debe estar garantizada por PostgreSQL"
            )

            neg = s.query(Negocio).filter(Negocio.nit == nit).one()
            s.query(CodigoActivacion).filter(
                CodigoActivacion.negocio_id == neg.id
            ).delete(synchronize_session=False)
            s.query(Usuario).filter(Usuario.negocio_id == neg.id).delete(
                synchronize_session=False
            )
            s.delete(neg)
            s.commit()
        finally:
            s.close()


class TestLegacyYaNoEsTenantFactory:
    def test_07_legacy_post_negocios_no_existe_405(self, client, db_session):
        """HARDENING: POST /api/negocios ya NO existe como fabrica de tenants.

        La unica frontera de registro es POST /api/onboarding/negocios
        (atomica, crea admin inicial + codigo bootstrap). Tests y seeds no
        justifican conservar un alta HTTP incompleta: con el POST retirado, la
        ruta solo responde a GET y rechaza POST con 405 Method Not Allowed.
        """
        r = client.post(
            "/api/negocios",
            json={"nombre": "Tenant Admin", "nit": "111"},
        )
        assert r.status_code == 405, r.text

    def test_08_legacy_post_negocios_405_incluso_con_nit_nuevo(self, client, db_session):
        """El alta administrativa legada no es un bypass para ningun NIT."""
        r1 = client.post(ONBOARDING_URL, json=_payload_alta(nit="777"))
        assert r1.status_code == 201, r1.text

        r2 = client.post("/api/negocios", json={"nombre": "Otro", "nit": "888"})
        assert r2.status_code == 405, r2.text
        assert db_session.query(Negocio).filter(Negocio.nit == "777").count() == 1


class TestLoginCompletoDelAdmin:
    def test_09_codigo_bootstrap_lleva_al_admin_a_sesion_real(self, client):
        """Flujo real: alta -> activacion de dispositivo -> primer JWT -> /me."""
        r = client.post(ONBOARDING_URL, json=_payload_alta(nombre="Login Admin"))
        assert r.status_code == 201, r.text
        data = r.json()
        token = data["codigo_activacion"]["token"]
        negocio_id = data["negocio"]["id"]

        private_key, spki, pk_hash = _ec_keypair()

        r = _desafio(client, token, spki)
        assert r.status_code == 200, r.text
        intento_id, firma = _firma_valida(r, private_key, pk_hash)
        r = client.post(
            "/api/activaciones/canjear",
            json={"intento_id": intento_id, "firma": firma},
        )
        assert r.status_code == 200, r.text
        canje = r.json()
        assert canje["rol"] == "ADMINISTRADOR"
        assert canje["negocio_id"] == negocio_id

        jwt = _primer_jwt(
            client,
            canje["credencial_bootstrap"],
            canje["dispositivo_id"],
            private_key,
            pk_hash,
        )

        r = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert r.status_code == 200, r.text
        me = r.json()
        assert me["rol"] == "ADMINISTRADOR"
        assert me["activo"] is True
        assert me["usuario_nombre"] == "Admin Nuevo"
        assert me["negocio"]["negocio_id"] == negocio_id
        assert me["negocio"]["nombre"] == "Login Admin"
        assert me["negocio"]["plan"] == "basic"
        assert me["negocio"]["estado_suscripcion"] == "al_dia"
        assert me["negocio"]["suscripcion_activa"] is True
        assert "codigos:crear" in me["capabilities"]
        assert "dispositivos:registrar" in me["capabilities"]
