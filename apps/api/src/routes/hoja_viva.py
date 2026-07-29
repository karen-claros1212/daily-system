from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import date

from src.database import get_db
from src.models import Ruta
from src.schemas import HojaVivaCliente, HojaVivaResponse
from src.services.hoja_viva_service import build_hoja_viva, today_bogota
from src.auth.deps import get_request_context
from src.auth.context import RequestContext


def _uuid_eq(column, val: str | UUID):
    if isinstance(val, str):
        return column == UUID(val)
    return column == val


router = APIRouter(tags=["hoja-viva"])


@router.get(
    "/api/rutas/{ruta_id}/hoja-viva",
    response_model=HojaVivaResponse,
)
def obtener_hoja_viva(
    ruta_id: UUID,
    fecha: date | None = None,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    ruta = db.query(Ruta).filter(_uuid_eq(Ruta.id, ruta_id)).first()
    if not ruta:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")

    if not ctx.has_negocio(ruta.negocio_id):
        raise HTTPException(status_code=403, detail="Ruta no pertenece a tu negocio")

    if ctx.is_cobrador() and not ctx.has_route(ruta_id):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta ruta")

    result = build_hoja_viva(db, ruta_id, fecha)

    clientes = [
        HojaVivaCliente(**c) for c in result["clientes"]
    ]

    return HojaVivaResponse(
        ruta_id=ruta_id,
        ruta_nombre=ruta.nombre,
        fecha=fecha or today_bogota(),
        clientes=clientes,
        vence_hoy=result["cuotas_que_vencen_hoy"],
        vence_hoy_monto=result["vence_hoy_monto"],
        cuotas_que_vencen_hoy=result["cuotas_que_vencen_hoy"],
        dc_legacy=result["dc_legacy"],
        efectivo_esperado=0,
    )
