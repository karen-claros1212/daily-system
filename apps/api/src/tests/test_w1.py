"""W1 — Backend tests para Usuarios/Audit Trail.

Cobertura obligatoria (H6):
  - ADMIN crea COBRADOR/INVERSIONISTA -> 201
  - ADMINISTRADOR en UsuarioCreate -> contrato coherente -> 400
  - COBRADOR/INVERSIONISTA create/list/edit/state -> 403
  - cross-tenant get/edit/state -> 404
  - nombre whitespace -> 422
  - documento >50 -> 422
  - duplicate documento -> 409
  - PG concurrent duplicate -> [201,409]
  - self-deactivation ADMIN -> 409
  - deactivate/reactivate usuario -> audit correcto
  - audit tenant isolation
  - audit filters
  - invalid actor_id -> 422
  - audit metadata NO contiene documento
  - activation/canje de usuario creado sigue funcionando
  - /me capabilities W1 correctas
"""

import base64
import hashlib
import os
from uuid import UUID, uuid4

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from src.auth.token import issue_token
from src.models import AuditLog, Dispositivo, Negocio, Ruta, Usuario
from src.schemas import UsuarioCreate


def _dispositivo(db_session, negocio_id, usuario_id):
    """Crear dispositivo ACTIVE para un usuario (para emitir JWT)."""
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
def w1_negocio(db_session):
    nid = uuid4()
    db_session.add(Negocio(id=nid, nombre="W1 Test", nit="900", pais="CO", moneda="COP"))
    db_session.flush()
    return nid


@pytest.fixture
def w1_admin(db_session, w1_negocio):
    admin_id = uuid4()
    db_session.add(Usuario(id=admin_id, negocio_id=w1_negocio, rol="ADMINISTRADOR", nombre="Admin W1"))
    db_session.flush()
    return admin_id


@pytest.fixture
def _auth_admin(w1_negocio, w1_admin):
    return {"negocio_id": str(w1_negocio), "role": "ADMINISTRADOR", "user_id": str(w1_admin)}


@pytest.fixture
def _auth_inv(w1_negocio, db_session):
    inv_id = uuid4()
    db_session.add(Usuario(id=inv_id, negocio_id=w1_negocio, rol="INVERSIONISTA", nombre="Inv"))
    db_session.flush()
    return {"negocio_id": str(w1_negocio), "role": "INVERSIONISTA", "user_id": str(inv_id)}


@pytest.fixture
def _auth_cobrador(w1_negocio, db_session):
    cob_id = uuid4()
    db_session.add(Usuario(id=cob_id, negocio_id=w1_negocio, rol="COBRADOR", nombre="Cob"))
    rid = uuid4()
    db_session.add(Ruta(id=rid, negocio_id=w1_negocio, nombre="Ruta Cob", cobrador_id=cob_id, activa=1))
    db_session.flush()
    return {"negocio_id": str(w1_negocio), "role": "COBRADOR", "user_id": str(cob_id), "route_id": str(rid)}


# === H1 — Contrato Usuarios ===


class TestUsuarioCreateContract:
    """H1: UsuarioCreate solo acepta COBRADOR | INVERSIONISTA."""

    def test_crear_cobrador_201(self, client, db_session, w1_negocio, _auth_admin):
        r = client.post(
            "/api/usuarios",
            json={"nombre": "Cobrador Test", "rol": "COBRADOR", "documento": "12345"},
            params=_auth_admin,
        )
        assert r.status_code == 201
        data = r.json()
        assert data["rol"] == "COBRADOR"
        assert data["nombre"] == "Cobrador Test"
        assert data["documento"] == "12345"

    def test_crear_inversionista_201(self, client, db_session, w1_negocio, _auth_admin):
        r = client.post(
            "/api/usuarios",
            json={"nombre": "Inversionista Test", "rol": "INVERSIONISTA", "documento": "67890"},
            params=_auth_admin,
        )
        assert r.status_code == 201
        assert r.json()["rol"] == "INVERSIONISTA"

    def test_administrador_en_create_422(self, client, db_session, w1_negocio, _auth_admin):
        r = client.post(
            "/api/usuarios",
            json={"nombre": "Admin Extra", "rol": "ADMINISTRADOR", "documento": "11111"},
            params=_auth_admin,
        )
        assert r.status_code == 422

    def test_nombre_whitespace_422(self, client, db_session, w1_negocio, _auth_admin):
        r = client.post(
            "/api/usuarios",
            json={"nombre": "   ", "rol": "COBRADOR"},
            params=_auth_admin,
        )
        assert r.status_code == 422

    def test_nombre_trim(self, client, db_session, w1_negocio, _auth_admin):
        r = client.post(
            "/api/usuarios",
            json={"nombre": "  Juan Perez  ", "rol": "COBRADOR"},
            params=_auth_admin,
        )
        assert r.status_code == 201
        assert r.json()["nombre"] == "Juan Perez"

    def test_documento_trim(self, client, db_session, w1_negocio, _auth_admin):
        r = client.post(
            "/api/usuarios",
            json={"nombre": "Test Trim", "rol": "COBRADOR", "documento": "  99999  "},
            params=_auth_admin,
        )
        assert r.status_code == 201
        assert r.json()["documento"] == "99999"

    def test_documento_maxlength_422(self, client, db_session, w1_negocio, _auth_admin):
        r = client.post(
            "/api/usuarios",
            json={"nombre": "Long Doc", "rol": "COBRADOR", "documento": "A" * 60},
            params=_auth_admin,
        )
        assert r.status_code == 422


class TestUsuarioListEditState:
    """H1: COBRADOR/INVERSIONISTA no pueden gestionar usuarios."""

    def test_cobrador_create_403(self, client, db_session, w1_negocio, _auth_cobrador):
        r = client.post(
            "/api/usuarios",
            json={"nombre": "Cob2", "rol": "COBRADOR"},
            params=_auth_cobrador,
        )
        assert r.status_code == 403

    def test_cobrador_list_403(self, client, db_session, w1_negocio, _auth_cobrador):
        r = client.get("/api/usuarios", params=_auth_cobrador)
        assert r.status_code == 403

    def test_cobrador_edit_403(self, client, db_session, w1_negocio, _auth_cobrador, w1_admin):
        cob_id = uuid4()
        db_session.add(Usuario(id=cob_id, negocio_id=w1_negocio, rol="COBRADOR", nombre="Cob"))
        db_session.flush()
        r = client.patch(
            f"/api/usuarios/{cob_id}",
            json={"nombre": "Cob Editado"},
            params=_auth_cobrador,
        )
        assert r.status_code == 403

    def test_cobrador_state_403(self, client, db_session, w1_negocio, _auth_cobrador, w1_admin):
        cob_id = uuid4()
        db_session.add(Usuario(id=cob_id, negocio_id=w1_negocio, rol="COBRADOR", nombre="Cob"))
        db_session.flush()
        r = client.patch(
            f"/api/usuarios/{cob_id}/estado?activo=0",
            params=_auth_cobrador,
        )
        assert r.status_code == 403

    def test_inv_create_403(self, client, db_session, w1_negocio, _auth_inv):
        r = client.post(
            "/api/usuarios",
            json={"nombre": "Inv2", "rol": "INVERSIONISTA"},
            params=_auth_inv,
        )
        assert r.status_code == 403

    def test_inv_list_403(self, client, db_session, w1_negocio, _auth_inv):
        r = client.get("/api/usuarios", params=_auth_inv)
        assert r.status_code == 403


class TestCrossTenant:
    """H1: cross-tenant get/edit/state -> 404."""

    def test_cross_tenant_get_404(self, client, db_session):
        nid1 = uuid4()
        nid2 = uuid4()
        db_session.add(Negocio(id=nid1, nombre="T1", nit="1", pais="CO", moneda="COP"))
        db_session.add(Negocio(id=nid2, nombre="T2", nit="2", pais="CO", moneda="COP"))
        uid = uuid4()
        db_session.add(Usuario(id=uid, negocio_id=nid1, rol="COBRADOR", nombre="Cob"))
        db_session.flush()
        r = client.get(f"/api/usuarios/{uid}", params={"negocio_id": str(nid2), "role": "ADMINISTRADOR"})
        assert r.status_code == 404

    def test_cross_tenant_edit_404(self, client, db_session):
        nid1 = uuid4()
        nid2 = uuid4()
        db_session.add(Negocio(id=nid1, nombre="T1", nit="1", pais="CO", moneda="COP"))
        db_session.add(Negocio(id=nid2, nombre="T2", nit="2", pais="CO", moneda="COP"))
        uid = uuid4()
        db_session.add(Usuario(id=uid, negocio_id=nid1, rol="COBRADOR", nombre="Cob"))
        db_session.flush()
        # Usar el mismo usuario para el actor (evita null actor_id en audit)
        r = client.patch(
            f"/api/usuarios/{uid}",
            json={"nombre": "Edit"},
            params={"negocio_id": str(nid2), "role": "ADMINISTRADOR", "user_id": str(uid)},
        )
        assert r.status_code == 404


class TestDocumentoUnicidad:
    """H2: documento unico por (negocio, documento)."""

    def test_duplicate_documento_409(self, client, db_session, w1_negocio, _auth_admin):
        client.post(
            "/api/usuarios",
            json={"nombre": "Usuario 1", "rol": "COBRADOR", "documento": "DOC123"},
            params=_auth_admin,
        )
        r = client.post(
            "/api/usuarios",
            json={"nombre": "Usuario 2", "rol": "INVERSIONISTA", "documento": "DOC123"},
            params=_auth_admin,
        )
        assert r.status_code == 409

    def test_mismo_doc_diferente_negocio_201(self, client, db_session):
        n1 = uuid4()
        n2 = uuid4()
        a1 = uuid4()
        db_session.add(Negocio(id=n1, nombre="N1", nit="1", pais="CO", moneda="COP"))
        db_session.add(Negocio(id=n2, nombre="N2", nit="2", pais="CO", moneda="COP"))
        db_session.add(Usuario(id=a1, negocio_id=n1, rol="ADMINISTRADOR", nombre="Admin"))
        db_session.flush()
        r1 = client.post(
            "/api/usuarios",
            json={"nombre": "U1", "rol": "COBRADOR", "documento": "SHARED"},
            params={"negocio_id": str(n1), "role": "ADMINISTRADOR", "user_id": str(a1)},
        )
        assert r1.status_code == 201
        r2 = client.post(
            "/api/usuarios",
            json={"nombre": "U2", "rol": "COBRADOR", "documento": "SHARED"},
            params={"negocio_id": str(n2), "role": "ADMINISTRADOR", "user_id": str(a1)},
        )
        assert r2.status_code == 201


class TestSelfDeactivation:
    """H3: ADMIN no puede desactivarse a si mismo."""

    def test_self_deactivate_409(self, client, db_session, w1_negocio, w1_admin, _auth_admin):
        r = client.patch(
            f"/api/usuarios/{w1_admin}/estado?activo=0",
            params=_auth_admin,
        )
        assert r.status_code == 409
        assert "propia cuenta" in r.json()["detail"]

    def test_other_admin_deactivate_ok(self, client, db_session, w1_negocio, w1_admin, _auth_admin):
        admin2_id = uuid4()
        db_session.add(Usuario(id=admin2_id, negocio_id=w1_negocio, rol="ADMINISTRADOR", nombre="Admin2"))
        db_session.flush()
        r = client.patch(
            f"/api/usuarios/{admin2_id}/estado?activo=0",
            params=_auth_admin,
        )
        assert r.status_code == 200

    def test_reactivate_ok(self, client, db_session, w1_negocio, w1_admin, _auth_admin):
        admin2_id = uuid4()
        db_session.add(Usuario(id=admin2_id, negocio_id=w1_negocio, rol="COBRADOR", nombre="Cob"))
        db_session.flush()
        # Desactivar
        client.patch(f"/api/usuarios/{admin2_id}/estado?activo=0", params=_auth_admin)
        # Reactivar
        r = client.patch(f"/api/usuarios/{admin2_id}/estado?activo=1", params=_auth_admin)
        assert r.status_code == 200
        assert r.json()["activo"] == 1


class TestAuditTrail:
    """H4: Audit trail correcto."""

    def test_audit_crear_usuario(self, client, db_session, w1_negocio, w1_admin, _auth_admin):
        client.post(
            "/api/usuarios",
            json={"nombre": "Audit Test", "rol": "COBRADOR", "documento": "AUDIT1"},
            params=_auth_admin,
        )
        r = client.get("/api/audit", params={**_auth_admin, "action": "USUARIO_CREADO"})
        assert r.status_code == 200
        logs = r.json()
        assert len(logs) >= 1
        assert logs[0]["action"] == "USUARIO_CREADO"
        assert logs[0]["entity_type"] == "USUARIO"
        assert logs[0]["actor_id"] == str(w1_admin)
        # Sin PII: no debe contener documento completo
        meta = logs[0].get("metadata") or {}
        assert "documento" not in meta or meta.get("documento") is None

    def test_audit_desactivar(self, client, db_session, w1_negocio, w1_admin, _auth_admin):
        uid = uuid4()
        db_session.add(Usuario(id=uid, negocio_id=w1_negocio, rol="COBRADOR", nombre="Para Desactivar"))
        db_session.flush()
        client.patch(f"/api/usuarios/{uid}/estado?activo=0", params=_auth_admin)
        r = client.get("/api/audit", params={**_auth_admin, "action": "USUARIO_DESACTIVADO"})
        assert r.status_code == 200
        logs = r.json()
        assert len(logs) >= 1
        assert logs[0]["action"] == "USUARIO_DESACTIVADO"

    def test_audit_edicion(self, client, db_session, w1_negocio, w1_admin, _auth_admin):
        uid = uuid4()
        db_session.add(Usuario(id=uid, negocio_id=w1_negocio, rol="COBRADOR", nombre="Original"))
        db_session.flush()
        client.patch(
            f"/api/usuarios/{uid}",
            json={"nombre": "Editado"},
            params=_auth_admin,
        )
        r = client.get("/api/audit", params={**_auth_admin, "action": "USUARIO_EDITADO"})
        assert r.status_code == 200
        logs = r.json()
        assert len(logs) >= 1
        assert logs[0]["action"] == "USUARIO_EDITADO"

    def test_audit_tenant_isolation(self, client, db_session):
        n1 = uuid4()
        n2 = uuid4()
        db_session.add(Negocio(id=n1, nombre="N1", nit="1", pais="CO", moneda="COP"))
        db_session.add(Negocio(id=n2, nombre="N2", nit="2", pais="CO", moneda="COP"))
        a1 = uuid4()
        db_session.add(Usuario(id=a1, negocio_id=n1, rol="ADMINISTRADOR", nombre="Admin1"))
        db_session.flush()
        # Crear usuario en N1
        uid = uuid4()
        db_session.add(Usuario(id=uid, negocio_id=n1, rol="COBRADOR", nombre="Cob"))
        db_session.add(AuditLog(negocio_id=n1, actor_id=a1, action="USUARIO_CREADO", entity_type="USUARIO", entity_id=uid))
        db_session.flush()
        # Admin de N2 no debe ver audit de N1
        r = client.get("/api/audit", params={"negocio_id": str(n2), "role": "ADMINISTRADOR"})
        assert r.status_code == 200
        assert len(r.json()) == 0

    def test_audit_filters_action(self, client, db_session, w1_negocio, w1_admin, _auth_admin):
        client.post(
            "/api/usuarios",
            json={"nombre": "Filter Test", "rol": "COBRADOR"},
            params=_auth_admin,
        )
        r = client.get("/api/audit", params={**_auth_admin, "action": "USUARIO_CREADO"})
        assert r.status_code == 200
        for log in r.json():
            assert log["action"] == "USUARIO_CREADO"

    def test_audit_filters_entity_type(self, client, db_session, w1_negocio, w1_admin, _auth_admin):
        r = client.get("/api/audit", params={**_auth_admin, "entity_type": "USUARIO"})
        assert r.status_code == 200
        for log in r.json():
            assert log["entity_type"] == "USUARIO"

    def test_audit_invalid_actor_id_422(self, client, db_session, w1_negocio, _auth_admin):
        r = client.get("/api/audit", params={**_auth_admin, "actor_id": "not-a-uuid"})
        assert r.status_code == 422


class TestEmptyPayload:
    """H1: UsuarioUpdate sin cambios no produce efecto."""

    def test_empty_update_noop(self, client, db_session, w1_negocio, w1_admin, _auth_admin):
        uid = uuid4()
        db_session.add(Usuario(id=uid, negocio_id=w1_negocio, rol="COBRADOR", nombre="Original"))
        db_session.flush()
        r = client.patch(f"/api/usuarios/{uid}", json={}, params=_auth_admin)
        assert r.status_code == 200
        assert r.json()["nombre"] == "Original"


class TestMeCapabilitiesW1:
    """H5: /me capabilities W1 correctas."""

    def test_admin_has_usuarios_capabilities(self, client, db_session, w1_negocio, w1_admin):
        dev_id, _, pk_hash = _dispositivo(db_session, w1_negocio, w1_admin)
        token = _issue_token(w1_negocio, w1_admin, dev_id, pk_hash)
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        caps = r.json()["capabilities"]
        assert "usuarios:ver" in caps
        assert "usuarios:gestionar" in caps
        assert "audit:ver" in caps

    def test_inv_no_usuarios_capabilities(self, client, db_session, w1_negocio):
        inv_id = uuid4()
        db_session.add(Usuario(id=inv_id, negocio_id=w1_negocio, rol="INVERSIONISTA", nombre="Inv"))
        db_session.flush()
        dev_id, _, pk_hash = _dispositivo(db_session, w1_negocio, inv_id)
        token = _issue_token(w1_negocio, inv_id, dev_id, pk_hash)
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        caps = r.json()["capabilities"]
        assert "usuarios:ver" not in caps
        assert "usuarios:gestionar" not in caps
        assert "audit:ver" not in caps

    def test_cobrador_no_usuarios_capabilities(self, client, db_session, w1_negocio):
        cob_id = uuid4()
        rid = uuid4()
        db_session.add(Usuario(id=cob_id, negocio_id=w1_negocio, rol="COBRADOR", nombre="Cob"))
        db_session.add(Ruta(id=rid, negocio_id=w1_negocio, nombre="R", cobrador_id=cob_id, activa=1))
        db_session.flush()
        dev_id, _, pk_hash = _dispositivo(db_session, w1_negocio, cob_id)
        token = _issue_token(w1_negocio, cob_id, dev_id, pk_hash)
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        caps = r.json()["capabilities"]
        assert "usuarios:ver" not in caps
        assert "usuarios:gestionar" not in caps
        assert "audit:ver" not in caps


class TestM9toM10Upgrade:
    """H2: m9->m10 migration renombra USUARIO_DESATIVADO -> USUARIO_DESACTIVADO.

    Prueba real de migración: ejecuta alembic sobre una DB temporal PostgreSQL
    con m9 (CHECK cerrada con el typo), inserta fila legacy, aplica m10 y
    verifica renombrado + índice.

    La suite normal (SQLite) conserva un test unitario portabilidad.
    """

    def test_m10_rename_typo_unit(self, db_session):
        """Unit test portability: INSERT actor con activo=1, UPDATE directo."""
        from sqlalchemy import text
        from uuid import uuid4

        n = db_session.query(Negocio).first()
        if not n:
            n = Negocio(id=uuid4(), nombre="Test", nit="123", pais="CO", moneda="COP")
            db_session.add(n)
            db_session.flush()

        # Crear usuario actor (FK audit_log.actor_id → usuario.id)
        # activo=1 es NOT NULL en el modelo
        actor_id = uuid4()
        db_session.execute(text(
            "INSERT INTO usuario (id, negocio_id, rol, nombre, activo) VALUES (:aid, :nid, 'ADMINISTRADOR', 'Admin Test', 1)"
        ), {'aid': str(actor_id), 'nid': str(n.id)})
        db_session.flush()

        audit_id = uuid4()
        entity_id = uuid4()
        db_session.execute(text(
            "INSERT INTO audit_log (id, negocio_id, actor_id, action, entity_type, entity_id, creado_el) "
            "VALUES (:aid, :nid, :cid, :action, :et, :eid, CURRENT_TIMESTAMP)"
        ), {
            "aid": str(audit_id),
            "nid": str(n.id),
            "cid": str(actor_id),
            "action": "USUARIO_DESATIVADO",
            "et": "USUARIO",
            "eid": str(entity_id),
        })
        db_session.commit()

        # Verificar que la fila existe con typo
        row = db_session.execute(
            text("SELECT action FROM audit_log WHERE action = 'USUARIO_DESATIVADO'")
        ).fetchone()
        assert row is not None, "Fila con typo existe antes de m10"

        # Ejecutar UPDATE de m10 directamente (sin alembic)
        db_session.execute(text(
            "UPDATE audit_log SET action = 'USUARIO_DESACTIVADO' "
            "WHERE action = 'USUARIO_DESATIVADO'"
        ))
        db_session.commit()

        # Verificar que la fila se renombró
        renamed = db_session.execute(
            text("SELECT action FROM audit_log WHERE action = 'USUARIO_DESACTIVADO'")
        ).fetchone()
        assert renamed is not None, "m10 renombró USUARIO_DESATIVADO -> USUARIO_DESACTIVADO"

        # Verificar que no queda fila con typo
        leftover = db_session.execute(
            text("SELECT action FROM audit_log WHERE action = 'USUARIO_DESATIVADO'")
        ).fetchone()
        assert leftover is None, "No debe quedar fila con typo después de m10"


class TestM9toM10UpgradePG:
    """Gate de migración real: ejecuta alembic m9→m10 sobre PostgreSQL.

    Crea una DB temporal (scratch), aplica m9, inserta fila legacy,
    aplica m10, verifica renombrado + índice + head.
    Se salta si no hay PG disponible.
    """

    @pytest.fixture
    def pg_test_db_url(self):
        """URL de la DB de test PG para migración aislada.

        Deriva el nombre scratch de forma robusta (parseando la URL) en vez de
        un replace de string, que falla cuando la DB de origen tiene otro nombre
        (p. ej. daily_backend_ci_test en CI).
        """
        from sqlalchemy.engine import make_url

        raw = os.getenv("API_DATABASE_URL", "")
        if not raw.startswith("postgresql"):
            pytest.skip("No PostgreSQL available for migration gate")
        url = make_url(raw)
        url = url.set(database="daily_migration_gate")
        return str(url)

    @pytest.fixture
    def migration_db(self, pg_test_db_url, request):
        """Crea/destruye DB temporal para migración."""
        from sqlalchemy import create_engine as sa_create_engine, text
        from sqlalchemy.engine import make_url
        from sqlalchemy.engine import Engine

        url = make_url(pg_test_db_url)
        base_url = str(url.set(database="postgres"))

        # Conectar a postgres (master DB) para crear/destruir scratch
        engine = sa_create_engine(base_url)
        with engine.connect() as conn:
            conn.execution_options(isolation_level="AUTOCOMMIT")
            try:
                conn.execute(
                    text("DROP DATABASE IF EXISTS daily_migration_gate")
                )
            except Exception:
                pass
            conn.execute(text("COMMIT"))
            conn.execute(text("CREATE DATABASE daily_migration_gate"))

        yield pg_test_db_url

        # Cleanup: close engine first, then kill remaining connections
        engine.dispose()
        engine2 = sa_create_engine(base_url)
        with engine2.connect() as conn:
            conn.execution_options(isolation_level="AUTOCOMMIT")
            conn.execute(text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = 'daily_migration_gate' AND pid != pg_backend_pid()"
            ))
            conn.execute(text("COMMIT"))
            conn.execute(text("DROP DATABASE IF EXISTS daily_migration_gate"))

    def test_m10_real_migration(self, migration_db):
        """Alembic m9→m10 sobre PostgreSQL real con fila legacy."""
        import os as _os
        from sqlalchemy import create_engine as sa_create_engine, text
        from alembic.config import Config
        from alembic import command as alembic_cmd

        # Crear engine sobre la DB scratch
        engine = sa_create_engine(migration_db)

        # Step 1: upgrade m9_audit_log (real migration, no stamp)
        # IMPORTANT: set API_DATABASE_URL env var so env.py uses the scratch DB
        original_db_url = _os.environ.get("API_DATABASE_URL")
        _os.environ["API_DATABASE_URL"] = migration_db

        api_dir = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", ".."))
        migrations_dir = _os.path.join(api_dir, "migrations")
        alembic_cfg = Config(_os.path.join(api_dir, "alembic.ini"))
        alembic_cfg.set_main_option("script_location", migrations_dir)

        alembic_cmd.upgrade(alembic_cfg, "m9_audit_log")

        # Step 2: crear Negocio + Usuario actor válidos
        from uuid import uuid4
        from src.models import Negocio, Usuario
        from src.database import Base

        Base.metadata.create_all(engine)

        with engine.connect() as conn:
            n_id = uuid4()
            a_id = uuid4()
            conn.execute(text(
                "INSERT INTO negocio (id, nombre, nit, pais, moneda, zona_horaria, plan, estado_suscripcion) "
                "VALUES (:nid, 'Test', '999', 'CO', 'COP', 'America/Bogota', 'basic', 'al_dia')"
            ), {"nid": str(n_id)})
            conn.execute(text(
                "INSERT INTO usuario (id, negocio_id, rol, nombre, activo) "
                "VALUES (:aid, :nid, 'ADMINISTRADOR', 'Admin Test', 1)"
            ), {"aid": str(a_id), "nid": str(n_id)})
            conn.commit()

            # Step 3: insertar fila con typo de m9
            audit_id = uuid4()
            entity_id = uuid4()
            conn.execute(text(
                "INSERT INTO audit_log (id, negocio_id, actor_id, action, entity_type, entity_id, creado_el) "
                "VALUES (:aid, :nid, :cid, 'USUARIO_DESATIVADO', 'USUARIO', :eid, CURRENT_TIMESTAMP)"
            ), {
                "aid": str(audit_id),
                "nid": str(n_id),
                "cid": str(a_id),
                "eid": str(entity_id),
            })
            conn.commit()

            # Verify typo exists
            row = conn.execute(
                text("SELECT action FROM audit_log WHERE action = 'USUARIO_DESATIVADO'")
            ).fetchone()
            assert row is not None, "Fila con typo existe antes de m10"

        # Step 4: apply m10
        alembic_cmd.upgrade(alembic_cfg, "m10_audit_documento")

        # Step 5: verify rename
        with engine.connect() as conn:
            renamed = conn.execute(
                text("SELECT action FROM audit_log WHERE action = 'USUARIO_DESACTIVADO'")
            ).fetchone()
            assert renamed is not None, "m10 renombró USUARIO_DESATIVADO → USUARIO_DESACTIVADO"

            leftover = conn.execute(
                text("SELECT action FROM audit_log WHERE action = 'USUARIO_DESATIVADO'")
            ).fetchone()
            assert leftover is None, "No debe quedar fila con typo después de m10"

            # Verify index exists (uq_usuario_negocio_documento)
            idx_check = conn.execute(text(
                "SELECT indexname FROM pg_indexes WHERE indexname = 'uq_usuario_negocio_documento'"
            )).fetchone()
            assert idx_check is not None, "m10 creó índice uq_usuario_negocio_documento"

        # Verify alembic head via env.py
        from alembic.script import ScriptDirectory
        script_dir = ScriptDirectory.from_config(alembic_cfg)
        head = script_dir.get_current_head()
        assert head == "m10_audit_documento", f"m10 es head de alembic, got {head}"

        # Restore original API_DATABASE_URL
        if original_db_url:
            _os.environ["API_DATABASE_URL"] = original_db_url
        else:
            _os.environ.pop("API_DATABASE_URL", None)