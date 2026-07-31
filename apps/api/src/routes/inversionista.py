"""Investor aggregates routes for Etapa 3 — "que se venda".

Read-only endpoints for the Mini App inversionista.
Returns aggregated data without PII (no debtor names, documents, or addresses).
"""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.auth.deps import get_request_context
from src.database import get_db
from src.models import Negocio
from src.schemas import InversionistaSummaryResponse, SuscripcionStatusResponse
from src.services.inversionista_service import get_inversionista_summary

router = APIRouter(prefix="/api/inversionista", tags=["inversionista"])


@router.get("/resumen", response_model=InversionistaSummaryResponse)
def obtener_resumen_inversionista(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
    today: date | None = None,
):
    """Get investor summary for the negocio (from ctx) — no PII.

    Only INVERSIONISTA or ADMINISTRADOR can access.
    """
    if not (ctx.is_admin() or ctx.role == "INVERSIONISTA"):
        raise HTTPException(
            status_code=403,
            detail="Solo INVERSIONISTA o ADMINISTRADOR puede ver resumen",
        )

    negocio = db.query(Negocio).filter(Negocio.id == ctx.negocio_id).first()
    if not negocio:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")

    if negocio.estado_suscripcion != "al_dia":
        raise HTTPException(
            status_code=403,
            detail=f"Suscripcion: {negocio.estado_suscripcion}",
        )

    if negocio.paid_through_at and negocio.paid_through_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=403, detail="Suscripcion vencida")

    summary = get_inversionista_summary(db, ctx.negocio_id, today)
    summary["negocio_nombre"] = negocio.nombre
    summary["plan"] = negocio.plan
    summary["moneda"] = negocio.moneda
    summary["zona_horaria"] = negocio.zona_horaria
    return summary


@router.get("/suscripcion", response_model=SuscripcionStatusResponse)
def obtener_suscripcion(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Get subscription status for the negocio (from ctx)."""
    if ctx.role not in ("INVERSIONISTA", "ADMINISTRADOR"):
        raise HTTPException(
            status_code=403,
            detail="Solo INVERSIONISTA o ADMINISTRADOR puede ver suscripcion",
        )

    negocio = (
        db.query(Negocio)
        .filter(Negocio.id == ctx.negocio_id)
        .first()
    )
    if not negocio:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")

    return SuscripcionStatusResponse(
        negocio_id=negocio.id,
        estado_suscripcion=negocio.estado_suscripcion,
        plan=negocio.plan,
        paid_through_at=negocio.paid_through_at,
        activa=negocio.estado_suscripcion == "al_dia" and (
            negocio.paid_through_at is None
            or negocio.paid_through_at > datetime.now(timezone.utc)
        ),
    )
