"""Cobranza routes — W6 web read model (aging, worklist, promise to pay)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.auth.deps import get_request_context
from src.database import get_db, get_db_transaction
from src.models import PromesaPago
from src.rbac import tiene_capability
from src.services.cobranza_service import (
    AGING_BUCKETS,
    list_cobranza,
    resumen_cobranza,
)

router = APIRouter(prefix="/api/cobranza", tags=["cobranza"])

WriteSession = Annotated[
    Session,
    Depends(get_db_transaction, scope="function"),
]

VALID_SORTS = frozenset({
    "days_past_due",
    "overdue_amount",
    "total_outstanding",
    "oldest_unpaid_due_date",
    "cliente_nombre",
    "priority_score",
})


@router.get("/web")
def listar_cobranza_web(
    q: str | None = Query(default=None, max_length=100),
    bucket: str | None = Query(default=None),
    ruta_id: UUID | None = Query(default=None),
    estado: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    dpd_min: int | None = Query(default=None, ge=0),
    dpd_max: int | None = Query(default=None, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="days_past_due"),
    order: str = Query(default="desc"),
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Worklist de cobranza: envelope con aging, prioridad, filtros."""
    if not tiene_capability(ctx.role, "cobranza:ver"):
        raise HTTPException(status_code=403, detail="Forbidden: sin capability de cobranza")

    if sort not in VALID_SORTS:
        raise HTTPException(status_code=422, detail=f"sort inválido: {sort} (permitidos: {', '.join(sorted(VALID_SORTS))})")
    if order not in ("asc", "desc"):
        raise HTTPException(status_code=422, detail=f"order inválido: {order} (permitidos: asc, desc)")
    if bucket and not any(b[0] == bucket for b in AGING_BUCKETS):
        raise HTTPException(status_code=422, detail=f"bucket inválido: {bucket}")

    return list_cobranza(
        db,
        negocio_id=ctx.negocio_id,
        role=ctx.role,
        route_id=ctx.route_id,
        search=q,
        bucket=bucket,
        ruta_id=str(ruta_id) if ruta_id else None,
        estado=estado,
        priority=priority,
        dpd_min=dpd_min,
        dpd_max=dpd_max,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
    )


@router.get("/resumen")
def resumen_cobranza_endpoint(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Resumen de cobranza: KPIs + aging distribution."""
    if not tiene_capability(ctx.role, "cobranza:ver"):
        raise HTTPException(status_code=403, detail="Forbidden: sin capability de cobranza")

    return resumen_cobranza(
        db,
        negocio_id=ctx.negocio_id,
        role=ctx.role,
        route_id=ctx.route_id,
    )


# ─── Promise to Pay ───────────────────────────────────────────────────────────


@router.post("/promesas", status_code=201)
def crear_promesa(
    data: dict,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    """Crear promesa de pago. Requiere promesas:crear."""
    if not tiene_capability(ctx.role, "promesas:crear"):
        raise HTTPException(status_code=403, detail="Forbidden: sin capability de promesas")

    credito_id = data.get("credito_id")
    amount = data.get("amount")
    promised_date = data.get("promised_date")
    nota = data.get("nota")
    clave = data.get("clave_idempotencia")

    if not credito_id or not amount or not promised_date:
        raise HTTPException(status_code=422, detail="credito_id, amount, promised_date requeridos")
    if amount <= 0:
        raise HTTPException(status_code=422, detail="amount debe ser > 0")

    from datetime import date as _date
    try:
        promised_date_obj = _date.fromisoformat(promised_date)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="promised_date debe ser ISO format (YYYY-MM-DD)")

    promesa = PromesaPago(
        negocio_id=ctx.negocio_id,
        credito_id=UUID(credito_id),
        amount=int(amount),
        promised_date=promised_date_obj,
        estado="ACTIVE",
        nota=nota,
        created_by=ctx.user_id,
        clave_idempotencia=clave,
    )
    db.add(promesa)
    db.commit()
    db.refresh(promesa)

    return {
        "id": str(promesa.id),
        "credito_id": str(promesa.credito_id),
        "amount": promesa.amount,
        "promised_date": promesa.promised_date.isoformat(),
        "estado": promesa.estado,
        "nota": promesa.nota,
        "creado_el": promesa.creado_el.isoformat() if promesa.creado_el else None,
    }


@router.post("/promesas/{promesa_id}/cumplir", status_code=200)
def cumplir_promesa(
    promesa_id: UUID,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    """Marcar promesa como FULFILLED. Requiere promesas:actualizar."""
    if not tiene_capability(ctx.role, "promesas:actualizar"):
        raise HTTPException(status_code=403, detail="Forbidden")

    from datetime import datetime, timezone
    promesa = db.query(PromesaPago).filter(
        PromesaPago.id == promesa_id,
        PromesaPago.negocio_id == ctx.negocio_id,
    ).first()
    if not promesa:
        raise HTTPException(status_code=404, detail="Promesa no encontrada")
    if promesa.estado != "ACTIVE":
        raise HTTPException(status_code=409, detail=f"Promesa ya está {promesa.estado}")

    promesa.estado = "FULFILLED"
    promesa.fulfilled_at = datetime.now(timezone.utc)
    db.commit()
    return {"id": str(promesa.id), "estado": promesa.estado}


@router.post("/promesas/{promesa_id}/incumplir", status_code=200)
def incumplir_promesa(
    promesa_id: UUID,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    """Marcar promesa como BROKEN. Requiere promesas:actualizar."""
    if not tiene_capability(ctx.role, "promesas:actualizar"):
        raise HTTPException(status_code=403, detail="Forbidden")

    from datetime import datetime, timezone
    promesa = db.query(PromesaPago).filter(
        PromesaPago.id == promesa_id,
        PromesaPago.negocio_id == ctx.negocio_id,
    ).first()
    if not promesa:
        raise HTTPException(status_code=404, detail="Promesa no encontrada")
    if promesa.estado != "ACTIVE":
        raise HTTPException(status_code=409, detail=f"Promesa ya está {promesa.estado}")

    promesa.estado = "BROKEN"
    promesa.broken_at = datetime.now(timezone.utc)
    db.commit()
    return {"id": str(promesa.id), "estado": promesa.estado}


@router.post("/promesas/{promesa_id}/cancelar", status_code=200)
def cancelar_promesa(
    promesa_id: UUID,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    """Marcar promesa como CANCELLED. Requiere promesas:actualizar."""
    if not tiene_capability(ctx.role, "promesas:actualizar"):
        raise HTTPException(status_code=403, detail="Forbidden")

    from datetime import datetime, timezone
    promesa = db.query(PromesaPago).filter(
        PromesaPago.id == promesa_id,
        PromesaPago.negocio_id == ctx.negocio_id,
    ).first()
    if not promesa:
        raise HTTPException(status_code=404, detail="Promesa no encontrada")
    if promesa.estado != "ACTIVE":
        raise HTTPException(status_code=409, detail=f"Promesa ya está {promesa.estado}")

    promesa.estado = "CANCELLED"
    promesa.cancelled_at = datetime.now(timezone.utc)
    db.commit()
    return {"id": str(promesa.id), "estado": promesa.estado}
