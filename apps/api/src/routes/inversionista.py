"""Investor aggregates routes for Etapa 3 — "que se venda".

Read-only endpoints for the Mini App inversionista.
Returns aggregated data without PII (no debtor names, documents, or addresses).
"""

from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.database import get_db
from src.schemas import InversionistaSummaryResponse, SuscripcionStatusResponse
from src.services.inversionista_service import get_inversionista_summary
from src.services.subscription_service import check_negocio_suscripcion, SuscripcionError

router = APIRouter(prefix="/api/inversionista", tags=["inversionista"])


@router.get("/resumen", response_model=InversionistaSummaryResponse)
def obtener_resumen_inversionista(
    db: Session = Depends(get_db),
    negocio_id: UUID = Query(..., description="Negocio ID"),
    today: date | None = None,
):
    """Get investor summary for the negocio — no PII."""
    from src.models import Negocio

    negocio = db.query(Negocio).filter(Negocio.id == negocio_id).first()
    if not negocio:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")

    if negocio.estado_suscripcion != "al_dia":
        raise HTTPException(status_code=403, detail=f"Suscripcion: {negocio.estado_suscripcion}")

    if negocio.paid_through_at and negocio.paid_through_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=403, detail="Suscripcion vencida")

    summary = get_inversionista_summary(db, negocio_id, today)
    return summary


@router.get("/suscripcion", response_model=SuscripcionStatusResponse)
def obtener_suscripcion(
    db: Session = Depends(get_db),
    negocio_id: UUID = Query(..., description="Negocio ID"),
):
    """Get subscription status for the negocio."""
    from src.models import Negocio

    negocio = (
        db.query(Negocio)
        .filter(Negocio.id == negocio_id)
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
            or negocio.paid_through_at > __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        ),
    )
