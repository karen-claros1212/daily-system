"""Schedule service — generates contractual cuotas for creditos."""

from datetime import date, timedelta
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from src.models import Credito, CuotaProgramada


def generate_schedule(db: Session, credito: Credito) -> list[CuotaProgramada]:
    if credito.periodicidad == "UNICA":
        return _generate_unica(db, credito)
    elif credito.periodicidad == "SEMANAL":
        return _generate_weekly(db, credito)
    elif credito.periodicidad == "QUINCENAL":
        return _generate_biweekly(db, credito)
    else:
        return _generate_daily(db, credito)


def generate_schedule_for_id(db: Session, credito_id: UUID) -> list[CuotaProgramada]:
    credito = db.query(Credito).filter(Credito.id == credito_id).first()
    if not credito:
        return []
    return generate_schedule(db, credito)


def _generate_daily(db: Session, credito: Credito) -> list[CuotaProgramada]:
    start = credito.fecha_inicio or date.today()
    q = db.query(CuotaProgramada).filter(
        CuotaProgramada.credito_id == credito.id,
    )
    existing_count = q.count()
    if existing_count > 0:
        return q.all()

    cuotas = []
    for i in range(credito.n_cuotas):
        cuotas.append(CuotaProgramada(
            id=uuid4(),
            negocio_id=credito.negocio_id,
            credito_id=credito.id,
            numero=i + 1,
            fecha_vencimiento=start + timedelta(days=i),
            monto=credito.cuota,
            estado="PENDIENTE",
        ))
    db.add_all(cuotas)
    db.flush()
    return cuotas


def _generate_weekly(db: Session, credito: Credito) -> list[CuotaProgramada]:
    start = credito.fecha_inicio or date.today()
    q = db.query(CuotaProgramada).filter(
        CuotaProgramada.credito_id == credito.id,
    )
    existing_count = q.count()
    if existing_count > 0:
        return q.all()

    cuotas = []
    for i in range(credito.n_cuotas):
        cuotas.append(CuotaProgramada(
            id=uuid4(),
            negocio_id=credito.negocio_id,
            credito_id=credito.id,
            numero=i + 1,
            fecha_vencimiento=start + timedelta(weeks=i),
            monto=credito.cuota,
            estado="PENDIENTE",
        ))
    db.add_all(cuotas)
    db.flush()
    return cuotas


def _generate_biweekly(db: Session, credito: Credito) -> list[CuotaProgramada]:
    start = credito.fecha_inicio or date.today()
    q = db.query(CuotaProgramada).filter(
        CuotaProgramada.credito_id == credito.id,
    )
    existing_count = q.count()
    if existing_count > 0:
        return q.all()

    cuotas = []
    for i in range(credito.n_cuotas):
        cuotas.append(CuotaProgramada(
            id=uuid4(),
            negocio_id=credito.negocio_id,
            credito_id=credito.id,
            numero=i + 1,
            fecha_vencimiento=start + timedelta(weeks=2 * i),
            monto=credito.cuota,
            estado="PENDIENTE",
        ))
    db.add_all(cuotas)
    db.flush()
    return cuotas


def _generate_unica(db: Session, credito: Credito) -> list[CuotaProgramada]:
    start = credito.fecha_inicio or date.today()
    q = db.query(CuotaProgramada).filter(
        CuotaProgramada.credito_id == credito.id,
    )
    existing_count = q.count()
    if existing_count > 0:
        return q.all()

    cuota = CuotaProgramada(
        id=uuid4(),
        negocio_id=credito.negocio_id,
        credito_id=credito.id,
        numero=1,
        fecha_vencimiento=start,
        monto=credito.total,
        estado="PENDIENTE",
    )
    db.add(cuota)
    db.flush()
    return [cuota]
