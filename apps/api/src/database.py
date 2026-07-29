"""Database configuration for Daily System."""

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

DATABASE_URL = os.getenv("API_DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "API_DATABASE_URL environment variable is required. "
        "Example: postgresql://user:password@host:port/dbname"
    )

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Read-only session. No commit/rollback — caller owns the transaction."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_transaction() -> Generator[Session, None, None]:
    """Write session with single transaction boundary.

    - commit on success
    - rollback on any exception
    - close always
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
