"""Servicio de audit trail — W1 (A1).

Solo ADMINISTRADOR puede consultar el audit trail de su negocio.
Filtros: action, entity_type, actor_id, since (>=), limit.

El read model incluye actor_nombre (join con usuario) para evitar N+1 en el
frontend. El actor_id se conserva para trazabilidad completa.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session, joinedload

from src.models import AuditLog, Usuario


def consultar_audit(
    db: Session,
    negocio_id: UUID,
    action: str | None = None,
    entity_type: str | None = None,
    actor_id: UUID | None = None,
    since: datetime | None = None,
    limit: int = 50,
) -> list[tuple[AuditLog, str | None]]:
    """Consultar audit trail con filtros opcionales.

    Devuelve lista de (AuditLog, actor_nombre) — el actor_nombre sale de un
    LEFT JOIN con usuario (un solo query, sin N+1).
    """
    q = (
        db.query(AuditLog, Usuario.nombre)
        .outerjoin(Usuario, AuditLog.actor_id == Usuario.id)
        .filter(AuditLog.negocio_id == negocio_id)
    )

    if action:
        q = q.filter(AuditLog.action == action)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if actor_id:
        q = q.filter(AuditLog.actor_id == actor_id)
    if since:
        q = q.filter(AuditLog.creado_el >= since)

    return q.order_by(desc(AuditLog.creado_el)).limit(limit).all()
