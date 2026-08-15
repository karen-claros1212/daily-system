"""Pytest configuration for Daily System API."""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

# Ensure query-param auth works in tests
os.environ.setdefault("DAILY_ENV", "test")
os.environ.setdefault("API_DATABASE_URL", "sqlite:///:memory:")
IS_SQLITE = os.environ["API_DATABASE_URL"].startswith("sqlite")

# Claves ES256 de prueba para el JWT productivo (D7-H1): se generan una vez y
# se exponen por env para todo el proceso pytest. Fail-closed en codigo: sin
# estas variables, emitir/validar tokens lanza TokenConfigError.
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

_TEST_KEY = ec.generate_private_key(ec.SECP256R1())
os.environ["AUTH_JWT_PRIVATE_KEY"] = _TEST_KEY.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
).decode("ascii")
os.environ["AUTH_JWT_PUBLIC_KEY"] = _TEST_KEY.public_key().public_bytes(
    serialization.Encoding.PEM,
    serialization.PublicFormat.SubjectPublicKeyInfo,
).decode("ascii")


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    """Render postgresql.UUID as CHAR(32) on SQLite (test-only override).

    SQLAlchemy renders postgresql.UUID as a bare "UUID" type on SQLite, which
    has NUMERIC column affinity. A UUID whose hex digits are all 0-9 (produced
    e.g. by the hash()-derived device ids) is then stored as a REAL number and
    comes back as a float, breaking uuid.UUID(value). CHAR(32) gives TEXT
    affinity so the hex string round-trips as text. Production/PostgreSQL is
    untouched: this compiles() override only fires for the SQLite dialect used
    by the test infrastructure.
    """
    return "CHAR(32)"


from src.database import Base, get_db, get_db_transaction


def pg_truncate_permitted(env: str, db_name: str, opt_in: str | None) -> bool:
    """Guard de TRUNCATE sobre PostgreSQL (conjuncion estricta, G3).

    Solo se permite si las TRES condiciones son verdaderas simultaneamente:
      DAILY_ENV == "test"  Y  el nombre real de la DB es de test/scratch
      Y  ALLOW_PG_TRUNCATE == "1". ALLOW_PG_TRUNCATE NO es un bypass
      independiente del nombre ni del entorno.
    """
    env_is_test = env == "test"
    db_is_test = (
        db_name.endswith(("_test", "_scratch"))
        or "_scratch" in db_name
        or "test" in db_name
    )
    return bool(env_is_test and db_is_test and opt_in == "1")

# Import models so they register with Base before tables are created
from src.models import (  # noqa: F401
    Cliente,
    CodigoActivacion,
    Credito,
    CuotaProgramada,
    DesafioAuth,
    Dispositivo,
    IntentoActivacion,
    Jornada,
    MovimientoCaja,
    Negocio,
    Pago,
    Ruta,
)

# Use in-memory SQLite for tests by default; honor API_DATABASE_URL to run
# the suite against a real PostgreSQL (concurrency gates of Bloque 7).
TEST_DATABASE_URL = os.environ["API_DATABASE_URL"]

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session")
def test_db():
    """Create test database schema."""
    if IS_SQLITE:
        Base.metadata.create_all(bind=engine)
        yield
        Base.metadata.drop_all(bind=engine)
    else:
        # PostgreSQL: schema comes from Alembic migrations (cobro_test).
        # Truncate so the suite sees the same empty slate as the in-memory
        # SQLite DB (tests assert on global row counts).
        #
        # GUARD: el TRUNCATE ... CASCADE solo se ejecuta si las TRES
        # condiciones son verdaderas simultaneamente (conjuncion estricta):
        #   1. DAILY_ENV == "test"
        #   2. el nombre real de la DB identifica una DB de test/scratch
        #   3. ALLOW_PG_TRUNCATE == "1" (opt-in explicito)
        # ALLOW_PG_TRUNCATE NO es un bypass independiente: sin la conjuncion
        # completa, abortar antes de ejecutar SQL.
        from sqlalchemy import text

        db_name = TEST_DATABASE_URL.rsplit("/", 1)[-1].split("?")[0]
        truncate_ok = pg_truncate_permitted(
            os.getenv("DAILY_ENV", ""),
            db_name,
            os.getenv("ALLOW_PG_TRUNCATE"),
        )
        if not truncate_ok:
            raise RuntimeError(
                "Negado: test_db haria TRUNCATE sobre la base "
                f"'{db_name}' de API_DATABASE_URL (DAILY_ENV="
                f"{os.getenv('DAILY_ENV')!r}, ALLOW_PG_TRUNCATE="
                f"{os.getenv('ALLOW_PG_TRUNCATE')!r}). Solo se permite si "
                "DAILY_ENV==test, el nombre contiene 'test'/'scratch' y "
                "ALLOW_PG_TRUNCATE=1, simultaneamente."
            )
        tbl = ", ".join(sorted(Base.metadata.tables.keys()))
        with engine.connect() as conn:
            conn.execute(text(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE"))
            conn.commit()
        yield


@pytest.fixture(scope="function")
def db_session(test_db):
    """Provide a transactional database session."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """Provide a test client with mocked database."""

    from fastapi.testclient import TestClient

    from src.main import app

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_db_transaction():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_db_transaction] = override_get_db_transaction
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def client_atomico(db_session):
    """TestClient cuyo get_db_transaction replica la SEMANTICA productiva.

    En produccion el route escribe con get_db_transaction (commit on success,
    rollback on exception). El override comun de `client` es yield-only y no
    distingue exito de fallo: sirve para tests de lectura, pero convierte en
    falso positivo cualquier assert de atomicidad (el rollback lo tendria que
    hacer el TEST a mano).

    Este fixture ejecuta el boundary transaccional dentro de un SAVEPOINT del
    fixture db_session: ante una excepcion del request revierte al SAVEPOINT
    (todo-o-nada real), y en exito deja los cambios DENTRO del SAVEPOINT, bajo
    la transaccion exterior del fixture (visibles al test; el rollback del
    teardown aísla cada corrida).

    Por que NO se libera el SAVEPOINT en exito (savepoint.commit()): la sesion
    esta ligada a un Connection (no a un Engine) para que todos los overrides
    compartan la MISMA transaccion, y en ese binding liberar el SAVEPOINT via
    el Session COMMITEA la transaccion exterior en SQLite. Verificado
    empiricamente (repro con echo y conteo paso a paso): una fila insertada en
    el SAVEPOINT y liberada con commit() sobrevive al transaction.rollback()
    del teardown y contamina el test siguiente. En la bibliografia el commit de
    una transaccion NESTED solo libera el SAVEPOINT, pero eso vale para
    sesiones ligadas a un Engine con transaccion propia; aqui no. Dejar el
    SAVEPOINT abierto no afecta visibilidad (los datos estan en la transaccion
    del fixture) ni aislamiento (el teardown lo deshace junto con todo).
    """
    from fastapi.testclient import TestClient

    from src.main import app

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_db_transaction():
        # Calienta la sesion para que SU transaccion se una a la del connection
        # (de lo contrario begin_nested() inicia un root ajeno al fixture).
        db_session.connection()
        savepoint = db_session.begin_nested()
        try:
            yield db_session
        except Exception:
            # NOTA: el rollback NO se condiciona a savepoint.is_active. Tras un
            # flush fallido (p.ej. IntegrityError de uq_negocio_nit) SQLAlchemy
            # marca el SAVEPOINT como inactivo (is_active=False) pero la sesion
            # queda en pending-rollback: sin este rollback el estado se contagia
            # al resto del test. rollback() solo deshace hasta el SAVEPOINT.
            savepoint.rollback()
            raise
        else:
            # EXITO: los cambios quedan DENTRO del SAVEPOINT, bajo la
            # transaccion exterior del fixture (visibles al test; su teardown
            # los revierte). NO se libera con savepoint.commit(): la sesion
            # ligada a un Connection hace que el commit del SAVEPOINT sea un
            # commit de la transaccion exterior en SQLite (verificado
            # empiricamente: la fila sobrevive al rollback del teardown y
            # contamina el test siguiente). Detalle en el docstring.
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_db_transaction] = override_get_db_transaction
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def negocio_id(db_session):
    """Create a test negocio and return its ID."""
    from uuid import uuid4

    n = Negocio(
        id=uuid4(),
        nombre="Test Negocio",
        nit="900123456",
        pais="CO",
        moneda="COP",
    )
    db_session.add(n)
    db_session.commit()
    db_session.refresh(n)
    return n.id


@pytest.fixture
def ruta_id(db_session, negocio_id):
    """Create a test ruta and return its ID."""
    from uuid import uuid4

    r = Ruta(
        id=uuid4(),
        negocio_id=negocio_id,
        nombre="Ruta Test",
    )
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)
    return r.id


@pytest.fixture
def cliente_id(db_session, negocio_id):
    """Create a test cliente and return its ID."""
    from uuid import uuid4

    c = Cliente(
        id=uuid4(),
        negocio_id=negocio_id,
        primer_apellido="Test",
        nombres="Cliente",
        identity_status="PROVISIONAL",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c.id
