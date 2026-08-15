"""Audit trail — W1 (A1).

GET /api/audit — consultar logs de auditoria.
Solo ADMINISTRADOR.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.auth.deps import get_request_context
from src.database import get_db
from src.schemas import AuditLogQuery, AuditLogResponse
from src.services import audit_service

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogResponse])
def consultar_audit(
    action: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Consultar audit trail con filtros opcionales.

    Filtros:
      - action: filtrar por tipo de accion
      - entity_type: filtrar por tipo de entidad
      - actor_id: filtrar por ID del actor (string o UUID)
      - since: solo registros despues de esta fecha
      - limit: maximo de resultados (1-200)

    Orden: mas reciente primero.
    """
    if not ctx.is_admin():
        raise HTTPException(status_code=403, detail="Solo ADMINISTRADOR puede consultar audit trail")

    actor_uuid = UUID(actor_id) if actor_id else None

    registros = audit_service.consultar_audit(
        db=db,
        negocio_id=ctx.negocio_id,
        action=action,
        entity_type=entity_type,
        actor_id=actor_uuid,
        since=since,
        limit=limit,
    )

    return [
        AuditLogResponse(
            id=r.id,
            negocio_id=r.negocio_id,
            actor_id=r.actor_id,
            action=r.action,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            metadata=r.metadata_col,
            ip_address=r.ip_address,
            user_agent=r.user_agent,
            creado_el=r.creado_el,
        )
        for r in registros
    ]
