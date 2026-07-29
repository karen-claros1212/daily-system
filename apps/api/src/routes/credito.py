from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from src.database import get_db
from src.models import Credito, Ruta, Cliente, Negocio
from src.schemas import CreditoCreate, CreditoResponse
from src.auth.deps import get_request_context
from src.auth.context import RequestContext
from src.services.schedule_service import generate_schedule


def _uuid_eq(column, val: str | UUID):
    if isinstance(val, str):
        return column == UUID(val)
    return column == val


router = APIRouter(prefix="/api/creditos", tags=["creditos"])


@router.post("", response_model=CreditoResponse, status_code=201)
def crear_credito(
    data: CreditoCreate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    negocio = db.query(Negocio).filter(_uuid_eq(Negocio.id, ctx.negocio_id)).first()
    if not negocio:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")

    ruta = db.query(Ruta).filter(
        _uuid_eq(Ruta.id, data.ruta_id),
        _uuid_eq(Ruta.negocio_id, ctx.negocio_id),
    ).first()
    if not ruta:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")

    if ctx.is_cobrador() and not ctx.has_route(data.ruta_id):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta ruta")

    cliente = db.query(Cliente).filter(
        _uuid_eq(Cliente.id, data.cliente_id),
        _uuid_eq(Cliente.negocio_id, ctx.negocio_id),
    ).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    total = data.cuota * data.n_cuotas

    credito = Credito(
        negocio_id=ctx.negocio_id,
        cliente_id=data.cliente_id,
        ruta_id=data.ruta_id,
        origination_type="NEW",
        cuota=data.cuota,
        n_cuotas=data.n_cuotas,
        monto=data.monto,
        total=total,
        periodicidad=data.periodicidad or "DIARIO",
        fecha_inicio=data.fecha_inicio,
        estado="ACTIVO",
    )
    db.add(credito)
    db.flush()

    # Auto-generate contractual schedule for the credit
    generate_schedule(db, credito)

    db.commit()
    db.refresh(credito)
    return CreditoResponse.model_validate(credito)


@router.get("", response_model=list[CreditoResponse])
def listar_creditos(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    q = db.query(Credito).filter(_uuid_eq(Credito.negocio_id, ctx.negocio_id))
    if ctx.is_cobrador():
        q = q.filter(_uuid_eq(Credito.ruta_id, ctx.route_id))
    return [CreditoResponse.model_validate(c) for c in q.all()]


@router.get("/{credito_id}", response_model=CreditoResponse)
def obtener_credito(
    credito_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    credito = db.query(Credito).filter(
        _uuid_eq(Credito.id, credito_id),
        _uuid_eq(Credito.negocio_id, ctx.negocio_id),
    ).first()
    if not credito:
        raise HTTPException(status_code=404, detail="Crédito no encontrado")
    if ctx.is_cobrador() and not ctx.has_route(credito.ruta_id):
        raise HTTPException(status_code=403, detail="No tienes acceso a este crédito")
    return CreditoResponse.model_validate(credito)
