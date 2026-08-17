"""W7 Gate 1 — Business Date Colombia.

Tests deterministas de frontera para la fecha financiera:
- before/after day change Colombia
- UTC timestamps belonging to previous/next day vs Colombia
- custom range inclusive/exclusive
"""

from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models import Credito, Negocio, Pago, Ruta, Usuario
from src.services.hoja_viva_service import BOGOTA_TZ, today_bogota
from src.services.inversionista_service import get_inversionista_summary


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def negocio(db):
    n = Negocio(id=uuid4(), nombre="Test", nit="123", estado_suscripcion="al_dia")
    db.add(n)
    db.commit()
    return n


@pytest.fixture
def ruta(db, negocio):
    r = Ruta(id=uuid4(), negocio_id=negocio.id, nombre="Ruta Test", activa=1)
    db.add(r)
    db.commit()
    return r


@pytest.fixture
def credito(db, negocio, ruta):
    c = Credito(
        id=uuid4(),
        negocio_id=negocio.id,
        ruta_id=ruta.id,
        monto=100000,
        total=300000,
        cuota=100000,
        n_cuotas=3,
        estado="ACTIVO",
        fecha_inicio=date(2026, 1, 1),
    )
    db.add(c)
    db.commit()
    return c


def _make_pago(db, negocio, credito, tipo, monto, ts, n=1):
    p = Pago(
        id=uuid4(),
        negocio_id=negocio.id,
        credito_id=credito.id,
        tipo=tipo,
        monto=monto,
        recibido_el_servidor=ts,
        clave_idempotencia=f"w7-bd-{n}-{uuid4().hex[:8]}",
    )
    db.add(p)
    db.commit()
    return p


class TestBusinessDateColombia:
    """La fecha financiera debe usar America/Bogota, no UTC ni date.today()."""

    def test_today_bogota_returns_date(self):
        d = today_bogota()
        assert isinstance(d, date)

    def test_bogota_tz_is_minus5(self):
        assert BOGOTA_TZ.utcoffset(None) == timedelta(hours=-5)

    def test_recaudo_uses_bogota_range_not_utc(self, db, negocio, credito):
        """Un pago a las 23:00 UTC (18:00 Bogota) del día D debe contar como recaudo del día D Colombia."""
        ts = datetime(2026, 8, 17, 23, 0, tzinfo=timezone.utc)
        _make_pago(db, negocio, credito, "PAYMENT", 50000, ts)

        result = get_inversionista_summary(db, negocio.id, today=date(2026, 8, 17))
        assert result["portfolio"]["recaudo_hoy"] == 50000

    def test_recaudo_0030_utc_next_day_bogota(self, db, negocio, credito):
        """00:30 UTC del día D+1 = 19:30 Bogota del día D. Debe contar como recaudo del día D Colombia."""
        ts = datetime(2026, 8, 18, 0, 30, tzinfo=timezone.utc)
        _make_pago(db, negocio, credito, "PAYMENT", 30000, ts)

        result = get_inversionista_summary(db, negocio.id, today=date(2026, 8, 17))
        assert result["portfolio"]["recaudo_hoy"] == 30000

    def test_recaudo_0430_utc_next_day_bogota_next(self, db, negocio, credito):
        """05:30 UTC del día D+1 = 00:30 Bogota del día D+1. NO debe contar como recaudo del día D Colombia."""
        ts = datetime(2026, 8, 18, 5, 30, tzinfo=timezone.utc)
        _make_pago(db, negocio, credito, "PAYMENT", 20000, ts)

        result = get_inversionista_summary(db, negocio.id, today=date(2026, 8, 17))
        assert result["portfolio"]["recaudo_hoy"] == 0

    def test_recaudo_0459_utc_same_day_bogota_previous(self, db, negocio, credito):
        """04:59 UTC del día D+1 = 23:59 Bogota del día D. SÍ debe contar como recaudo del día D Colombia."""
        ts = datetime(2026, 8, 18, 4, 59, tzinfo=timezone.utc)
        _make_pago(db, negocio, credito, "PAYMENT", 10000, ts)

        result = get_inversionista_summary(db, negocio.id, today=date(2026, 8, 17))
        assert result["portfolio"]["recaudo_hoy"] == 10000

    def test_recaudo_0500_utc_same_day_bogota_next(self, db, negocio, credito):
        """05:00 UTC del día D+1 = 00:00 Bogota del día D+1. NO debe contar como recaudo del día D Colombia."""
        ts = datetime(2026, 8, 18, 5, 0, tzinfo=timezone.utc)
        _make_pago(db, negocio, credito, "PAYMENT", 15000, ts)

        result = get_inversionista_summary(db, negocio.id, today=date(2026, 8, 17))
        assert result["portfolio"]["recaudo_hoy"] == 0

    def test_recaudo_exclusive_end(self, db, negocio, credito):
        """El rango es [inicio, fin) — un pago exactamente a 00:00 Bogota del día siguiente NO cuenta."""
        ts = datetime(2026, 8, 18, 5, 0, tzinfo=timezone.utc)
        _make_pago(db, negocio, credito, "PAYMENT", 25000, ts)

        result = get_inversionista_summary(db, negocio.id, today=date(2026, 8, 17))
        assert result["portfolio"]["recaudo_hoy"] == 0

    def test_recaudo_inclusive_start(self, db, negocio, credito):
        """El rango incluye el inicio: un pago a 00:00:00 Bogota del día D SÍ cuenta."""
        ts = datetime(2026, 8, 17, 5, 0, tzinfo=timezone.utc)
        _make_pago(db, negocio, credito, "PAYMENT", 35000, ts)

        result = get_inversionista_summary(db, negocio.id, today=date(2026, 8, 17))
        assert result["portfolio"]["recaudo_hoy"] == 35000

    def test_recaudo_net_payment_minus_reversal(self, db, negocio, credito):
        """Recaudo neto = PAYMENT - REVERSAL en el rango Bogota."""
        ts1 = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
        ts2 = datetime(2026, 8, 17, 15, 0, tzinfo=timezone.utc)
        _make_pago(db, negocio, credito, "PAYMENT", 100000, ts1, n=1)
        _make_pago(db, negocio, credito, "REVERSAL", 30000, ts2, n=2)

        result = get_inversionista_summary(db, negocio.id, today=date(2026, 8, 17))
        assert result["portfolio"]["recaudo_hoy"] == 70000

    def test_tenant_isolation(self, db, negocio, credito, ruta):
        """Pagos de otro negocio no deben contar."""
        otro_negocio = Negocio(id=uuid4(), nombre="Otro", nit="456", estado_suscripcion="al_dia")
        db.add(otro_negocio)
        db.commit()

        otra_ruta = Ruta(id=uuid4(), negocio_id=otro_negocio.id, nombre="Ruta Otro", activa=1)
        db.add(otra_ruta)
        db.commit()

        otro_credito = Credito(
            id=uuid4(),
            negocio_id=otro_negocio.id,
            ruta_id=otra_ruta.id,
            monto=50000,
            total=150000,
            cuota=50000,
            n_cuotas=3,
            estado="ACTIVO",
            fecha_inicio=date(2026, 1, 1),
        )
        db.add(otro_credito)
        db.commit()

        ts = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
        _make_pago(db, otro_negocio, otro_credito, "PAYMENT", 99999, ts)

        result = get_inversionista_summary(db, negocio.id, today=date(2026, 8, 17))
        assert result["portfolio"]["recaudo_hoy"] == 0
