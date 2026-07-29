"""Pytest configuration for Daily System API."""

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure query-param auth works in tests
os.environ.setdefault("DAILY_ENV", "test")

from src.database import Base, get_db, get_db_transaction

# Import models so they register with Base before tables are created
from src.models import Negocio, Ruta, Cliente, Credito, CuotaProgramada, Jornada, Pago, MovimientoCaja  # noqa: F401

# Use in-memory SQLite for tests (no Docker needed)
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session")
def test_db():
    """Create test database schema."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


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
    import sys

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_db_transaction] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def negocio_id(db_session):
    """Create a test negocio and return its ID."""
    from src.models import Negocio
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
    from src.models import Ruta
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
    from src.models import Cliente
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
