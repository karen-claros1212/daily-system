"""Servicio de audit trail — W1 (A1).

Solo ADMINISTRADOR puede consultar el audit trail de su negocio.
Filtros: action, entity_type, actor_id, since (>=), limit.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from src.models import AuditLog


def consultar_audit(
    db: Session,
    negocio_id: UUID,
    action: str | None = None,
    entity_type: str | None = None,
    actor_id: UUID | None = None,
    since: datetime | None = None,
    limit: int = 50,
) -> list[AuditLog]:
    """Consultar audit trail con filtros opcionales."""
    q = db.query(AuditLog).filter(AuditLog.negocio_id == negocio_id)

    if action:
        q = q.filter(AuditLog.action == action)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if actor_id:
        q = q.filter(AuditLog.actor_id == actor_id)
    if since:
        q = q.filter(AuditLog.creado_el >= since)

    return q.order_by(desc(AuditLog.creado_el)).limit(limit).all()
