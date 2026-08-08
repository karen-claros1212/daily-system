"""M6 PostgreSQL concurrency — Bloque 7 gate B (evidencia real en PG).

Cubren los cinco escenarios obligatorios del cierre del Bloque 7:
  1. Doble canje concurrente del MISMO challenge (un solo dispositivo).
  2. Revocacion concurrente frente al canje (invariancia de un solo ACTIVE).
  3. Reasignacion de ruta y request posterior con token existente.
  4. Constraint de UNA ruta activa por cobrador (uq_ruta_activa_cobrador).
  5. Constraint de UN dispositivo ACTIVE por cobrador
     (uq_dispositivo_activo_cobrador).

Requiere PostgreSQL real: las sesiones de concurrencia usan SessionLocal de
src.database (transacciones reales + SELECT FOR UPDATE). Se salta en SQLite.

IMPORTANTE: los escenarios se crean con SessionLocal + commit (no con el
fixture db_session del conftest, que revierte) para que sean visibles a
multiples threads y a las transacciones FOR UPDATE.
"""

import base64
import hashlib
import secrets
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy.exc import IntegrityError

from src.database import SessionLocal
from src.models import (
    CodigoActivacion,
    DesafioAuth,
    Dispositivo,
    IntentoActivacion,
    Negocio,
    Ruta,
    Usuario,
)
from src.services.jcs import PROTOCOL_VERSION, build_signed_payload

pytestmark = pytest.mark.skipif(
    str(SessionLocal().get_bind().dialect.name) != "postgresql",
    reason="concurrencia real y constraints parciales exigen PostgreSQL",
)

# === helpers criptograficos ===


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


def _rfc3339(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _firma_intento(intento: IntentoActivacion, private_key, environment) -> str:
    payload = build_signed_payload(
        protocol_version=PROTOCOL_VERSION,
        environment=environment,
        attempt_id=str(intento.id),
        nonce=intento.nonce,
        public_key_hash=intento.public_key_hash,
        expires_at=_rfc3339(intento.expira_el),
    )
    return _sign(private_key, payload)


# === fixtures ===


@pytest.fixture
def escenario_pg():
    """Escenario COMMITEADO (visible entre threads): negocio+admin+cobrador+ruta."""
    nid = uuid4()
    admin_id = uuid4()
    cob_id = uuid4()
    r1_id = uuid4()

    s = SessionLocal()
    try:
        s.add(Negocio(id=nid, nombre="Neg-PG", nit="1"))
        s.add(Usuario(id=admin_id, negocio_id=nid, rol="ADMINISTRADOR", nombre="Admin"))
        s.add(Usuario(id=cob_id, negocio_id=nid, rol="COBRADOR", nombre="Cob"))
        s.add(Ruta(id=r1_id, negocio_id=nid, nombre="R1", cobrador_id=cob_id, activa=1))
        s.commit()
    finally:
        s.close()

    yield {
        "negocio_id": nid,
        "admin_id": admin_id,
        "cobrador_id": cob_id,
        "ruta_id": r1_id,
    }

    _limpiar(nid)


def _limpiar(negocio_id):
    """Borra el arbol del escenario (FK order; CASCADE en codigo->intento)."""
    s = SessionLocal()
    try:
        s.query(DesafioAuth).filter(
            DesafioAuth.dispositivo_id.in_(
                s.query(Dispositivo.id).filter(
                    Dispositivo.negocio_id == negocio_id
                )
            )
        ).delete(synchronize_session=False)
        s.query(IntentoActivacion).filter(
            IntentoActivacion.codigo_id.in_(
                s.query(CodigoActivacion.id).filter(
                    CodigoActivacion.negocio_id == negocio_id
                )
            )
        ).delete(synchronize_session=False)
        s.query(CodigoActivacion).filter(
            CodigoActivacion.negocio_id == negocio_id
        ).delete(synchronize_session=False)
        s.query(Dispositivo).filter(
            Dispositivo.negocio_id == negocio_id
        ).delete(synchronize_session=False)
        s.query(Ruta).filter(Ruta.negocio_id == negocio_id).delete(
            synchronize_session=False
        )
        s.query(Usuario).filter(Usuario.negocio_id == negocio_id).delete(
            synchronize_session=False
        )
        s.query(Negocio).filter(Negocio.id == negocio_id).delete(
            synchronize_session=False
        )
        s.commit()
    finally:
        s.close()


def _emitir_codigo(escenario_pg) -> tuple[str, CodigoActivacion]:
    """Crea un codigo PENDING; devuelve (token_plano, codigo).

    El token en claro se necesita para `desafio`; la base solo guarda el hash.
    """
    token = secrets.token_urlsafe(32)
    s = SessionLocal()
    try:
        codigo = CodigoActivacion(
            negocio_id=escenario_pg["negocio_id"],
            cobrador_id=escenario_pg["cobrador_id"],
            hash_codigo=hashlib.sha256(token.encode()).hexdigest(),
            prefijo=token[:8],
            expira_el=datetime.now(timezone.utc) + timedelta(minutes=10),
            estado="PENDING",
            creado_por=escenario_pg["admin_id"],
            entregado_el=datetime.now(timezone.utc),
        )
        s.add(codigo)
        s.commit()
        s.refresh(codigo)
        return token, codigo
    finally:
        s.close()


def _desafio_y_firma(token: str, private_key, spki):
    """desafio + firma JCS del intento; devuelve (intento_id, firma, environment)."""
    from src.services.activacion_service import desafio

    s = SessionLocal()
    try:
        r = desafio(s, token=token, clave_publica=spki)
        s.commit()
        intento = s.get(IntentoActivacion, r.intento_id)
        firma = _firma_intento(intento, private_key, r.environment)
        return r.intento_id, firma, r.environment
    finally:
        s.close()


# === gate B: evidencia real ===


class TestDobleCanjeConcurrente:
    def test_01_doble_canje_mismo_challenge_un_solo_dispositivo(self, escenario_pg):
        """Dos canjes del MISMO intento en paralelo: una sola creacion de
        dispositivo, un solo CONSUMO, el segundo reintento idempotente."""
        from src.services.activacion_service import canjear

        private_key, spki, pk_hash = _ec_keypair()
        token, _codigo = _emitir_codigo(escenario_pg)
        intento_id, firma, _env = _desafio_y_firma(token, private_key, spki)

        resultados = []

        def canjear_thread():
            s2 = SessionLocal()
            try:
                res = canjear(s2, intento_id=intento_id, firma=firma)
                s2.commit()
                resultados.append(("ok", str(res.dispositivo_id), res.idempotente))
            except Exception as e:  # noqa: BLE001
                s2.rollback()
                resultados.append(("err", type(e).__name__))
            finally:
                s2.close()

        t1 = threading.Thread(target=canjear_thread)
        t2 = threading.Thread(target=canjear_thread)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        ok = [r for r in resultados if r[0] == "ok"]
        assert len(ok) == 2, f"ambos canjes deben completarse: {resultados}"
        assert len({r[1] for r in ok}) == 1, "un solo dispositivo creado"
        assert len([r for r in ok if not r[2]]) == 1, "una unica creacion"
        n_dispositivos = (
            SessionLocal()
            .query(Dispositivo)
            .filter(Dispositivo.public_key_hash == pk_hash)
            .count()
        )
        assert n_dispositivos == 1


class TestRevocacionConcurrenteFrenteACanje:
    def test_02_revocacion_concurrente_frente_a_canje(self, escenario_pg):
        """Revoca D1 (ACTIVE) mientras se canjea un codigo nuevo.

        Invariante tras la carrera: a lo sumo UN dispositivo ACTIVE por
        cobrador. Si el canje gano, D2 es el unico ACTIVE y D1 quedo REVOKED.
        Si la revocacion gano, el canje fue rechazado por COBRADOR_YA_ACTIVO.
        En ningun caso quedan dos ACTIVE (lo garantiza tambien el indice unico
        parcial uq_dispositivo_activo_cobrador).
        """
        from src.services.activacion_service import canjear
        from src.services.dispositivo_service import revocar_dispositivo

        cob_id = escenario_pg["cobrador_id"]
        neg_id = escenario_pg["negocio_id"]

        # Dispositivo ACTIVE preexistente (D1) del cobrador.
        d1 = Dispositivo(
            id=uuid4(),
            negocio_id=neg_id,
            usuario_id=cob_id,
            public_key="pk-d1",
            public_key_hash=hashlib.sha256(b"d1").hexdigest(),
            algoritmo_clave="EC_P256",
            estado="ACTIVE",
            version_asignacion=1,
            activo=1,
        )
        s = SessionLocal()
        try:
            s.add(d1)
            s.commit()
        finally:
            s.close()

        # Codigo nuevo + intento + firma (para el canje).
        private_key, spki, _pk_hash = _ec_keypair()
        token, _codigo = _emitir_codigo(escenario_pg)
        intento_id, firma, _env = _desafio_y_firma(token, private_key, spki)

        resultados = []
        barrier = threading.Barrier(2)

        def revocar_thread():
            s2 = SessionLocal()
            try:
                barrier.wait()
                revocar_dispositivo(s2, d1.id, neg_id)
                s2.commit()
                resultados.append(("revocar", "ok"))
            except Exception as e:  # noqa: BLE001
                s2.rollback()
                resultados.append(("revocar", type(e).__name__))
            finally:
                s2.close()

        def canjear_thread():
            s2 = SessionLocal()
            try:
                barrier.wait()
                res = canjear(s2, intento_id=intento_id, firma=firma)
                s2.commit()
                resultados.append(("canje", "ok", str(res.dispositivo_id)))
            except Exception as e:  # noqa: BLE001
                s2.rollback()
                code = getattr(e, "code", type(e).__name__)
                resultados.append(("canje", code))
            finally:
                s2.close()

        t1 = threading.Thread(target=revocar_thread)
        t2 = threading.Thread(target=canjear_thread)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Invariante dura: un solo ACTIVE.
        n_activos = (
            SessionLocal()
            .query(Dispositivo)
            .filter(
                Dispositivo.usuario_id == cob_id,
                Dispositivo.estado == "ACTIVE",
            )
            .count()
        )
        assert n_activos <= 1, f"invariancia de un ACTIVE rota: {resultados}"

        canje = [r for r in resultados if r[0] == "canje"]
        assert len(canje) == 1, resultados
        assert canje[0][1] in ("ok", "COBRADOR_YA_ACTIVO"), canje
        if canje[0][1] == "ok":
            d1_estado = SessionLocal().get(Dispositivo, d1.id).estado
            assert d1_estado == "REVOKED", "D1 debe quedar REVOKED si el canje triunfa"
            assert n_activos == 1


class TestReasignacionRuta:
    def test_03_reasignacion_ruta_request_posterior_token_existente(self, escenario_pg):
        """Reasignar la ruta activa y derivarla con un token existente.

        El servidor deriva la ruta desde la BASE en cada request: un token
        emitido para R1 debe terminar sirviendo R2 tras la reasignacion, sin
        re-emitir token.
        """
        from src.auth.token import decode_token, issue_token
        from src.services.auth_service import derivar_ruta_activa

        cob_id = escenario_pg["cobrador_id"]
        neg_id = escenario_pg["negocio_id"]

        # Token emitido mientras R1 estaba activa.
        token_viejo = issue_token(
            negocio_id=neg_id,
            usuario_id=cob_id,
            dispositivo_id=uuid4(),
            public_key_hash=hashlib.sha256(b"pk").hexdigest(),
            version_asignacion=1,
        )
        claims = decode_token(token_viejo)
        assert claims["sub"] == str(cob_id)

        s = SessionLocal()
        try:
            r1 = (
                s.query(Ruta)
                .filter(Ruta.negocio_id == neg_id, Ruta.activa == 1)
                .one()
            )
            assert r1.id == escenario_pg["ruta_id"]
            # Reasignacion: desactivar R1, crear R2 activa para el mismo cobrador.
            r1.activa = 0
            r2 = Ruta(
                id=uuid4(),
                negocio_id=neg_id,
                nombre="R2",
                cobrador_id=cob_id,
                activa=1,
            )
            s.add(r2)
            s.commit()

            # Request posterior con el token existente: la ruta derivada es R2.
            ruta_derivada = derivar_ruta_activa(s, cob_id)
            assert ruta_derivada is not None
            assert ruta_derivada.id == r2.id
            assert ruta_derivada.nombre == "R2"
        finally:
            s.close()


class TestConstraintRutaActiva:
    def test_04_constraint_una_ruta_activa_por_cobrador(self, escenario_pg):
        """La segunda ruta activa del mismo cobrador viola uq_ruta_activa_cobrador."""
        s = SessionLocal()
        try:
            r2 = Ruta(
                id=uuid4(),
                negocio_id=escenario_pg["negocio_id"],
                nombre="R2-dup",
                cobrador_id=escenario_pg["cobrador_id"],
                activa=1,
            )
            s.add(r2)
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()
        finally:
            s.close()


class TestConstraintDispositivoActive:
    def test_05_constraint_un_dispositivo_active_por_cobrador(self, escenario_pg):
        """Un segundo ACTIVE del mismo cobrador viola uq_dispositivo_activo_cobrador."""
        cob_id = escenario_pg["cobrador_id"]
        neg_id = escenario_pg["negocio_id"]
        s = SessionLocal()
        try:
            s.add(
                Dispositivo(
                    id=uuid4(),
                    negocio_id=neg_id,
                    usuario_id=cob_id,
                    public_key="pk-a",
                    public_key_hash=hashlib.sha256(b"a").hexdigest(),
                    algoritmo_clave="EC_P256",
                    estado="ACTIVE",
                    version_asignacion=1,
                    activo=1,
                )
            )
            s.commit()
            s.add(
                Dispositivo(
                    id=uuid4(),
                    negocio_id=neg_id,
                    usuario_id=cob_id,
                    public_key="pk-b",
                    public_key_hash=hashlib.sha256(b"b").hexdigest(),
                    algoritmo_clave="EC_P256",
                    estado="ACTIVE",
                    version_asignacion=1,
                    activo=1,
                )
            )
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()
        finally:
            s.close()


class TestCanjeDesafioConcurrente:
    def test_06_canje_desafio_concurrente_single_use(self, escenario_pg):
        """Dos canjes del MISMO challenge en paralelo (D7-H2): un solo exito,
        el segundo replay recibe CHALLENGE_YA_USADO (409). Un unico token."""
        from src.services.auth_service import canjear_desafio, solicitar_desafio

        private_key, spki, pk_hash = _ec_keypair()
        dev_id = uuid4()
        s = SessionLocal()
        try:
            s.add(
                Dispositivo(
                    id=dev_id,
                    negocio_id=escenario_pg["negocio_id"],
                    usuario_id=escenario_pg["cobrador_id"],
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

        # Token de sesion para autenticar el desafio.
        from src.auth.token import issue_token

        token = issue_token(
            negocio_id=escenario_pg["negocio_id"],
            usuario_id=escenario_pg["cobrador_id"],
            dispositivo_id=dev_id,
            public_key_hash=pk_hash,
            version_asignacion=1,
        )

        # Desafio COMMITEADO (visible a las transacciones concurrentes).
        s = SessionLocal()
        try:
            desafio = solicitar_desafio(s, token)
            s.commit()
        finally:
            s.close()

        from src.services.auth_jcs import (
            PURPOSE_ISSUE_ACCESS_TOKEN,
            build_signed_payload,
        )

        payload = build_signed_payload(
            purpose=PURPOSE_ISSUE_ACCESS_TOKEN,
            environment=desafio.environment,
            challenge_id=str(desafio.challenge_id),
            device_id=str(dev_id),
            nonce=desafio.nonce,
            public_key_hash=pk_hash,
            expires_at=desafio.expira_el,
        )
        firma = _sign(private_key, payload)

        resultados = []

        def canjear_thread():
            s2 = SessionLocal()
            try:
                res = canjear_desafio(
                    s2, challenge_id=desafio.challenge_id, firma=firma
                )
                s2.commit()
                resultados.append(("ok", res.token))
            except Exception as e:  # noqa: BLE001
                s2.rollback()
                resultados.append(("err", getattr(e, "code", type(e).__name__)))
            finally:
                s2.close()

        t1 = threading.Thread(target=canjear_thread)
        t2 = threading.Thread(target=canjear_thread)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        ok = [r for r in resultados if r[0] == "ok"]
        replay = [r for r in resultados if r[0] == "err"]
        assert len(ok) == 1, f"un solo canje exitoso: {resultados}"
        assert any(r[1] == "CHALLENGE_YA_USADO" for r in replay), (
            f"el segundo canje debe ser replay 409: {resultados}"
        )
        assert len({r[1] for r in ok}) == 1, "un unico token emitido"

        # La fila quedo consumida una sola vez.
        s = SessionLocal()
        try:
            fila = s.get(DesafioAuth, desafio.challenge_id)
            assert fila is not None and fila.consumido_el is not None
            assert s.query(DesafioAuth).count() == 1
        finally:
            s.close()
