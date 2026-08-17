"""Dashboard Ejecutivo — endpoint typed para ADMINISTRADOR (W8).

GET /api/dashboard/ejecutivo
Capability: dashboard:ejecutivo (SOLO ADMINISTRADOR en W8; default-deny).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database import get_db
from src.auth.deps import get_request_context
from src.auth.context import RequestContext
from src.rbac import tiene_capability
from src.services.dashboard_service import dashboard_ejecutivo

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/ejecutivo")
def dashboard_ejecutivo_endpoint(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Centro ejecutivo de decisión: KPIs del día, tendencia 7d, riesgo, alertas."""
    if not tiene_capability(ctx.role, "dashboard:ejecutivo"):
        raise HTTPException(status_code=403, detail="Forbidden: sin capability de dashboard ejecutivo")
    return dashboard_ejecutivo(db, negocio_id=ctx.negocio_id, role=ctx.role)
