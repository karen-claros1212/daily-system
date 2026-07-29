"""Authorization dependencies for Daily System.

M1: Stub implementation — derives context from query parameters.
Future: JWT claims from signed tokens.
"""

from fastapi import Depends, HTTPException, Query
from uuid import UUID

from src.auth.context import RequestContext


def get_request_context(
    negocio_id: UUID = Query(..., description="Negocio ID (will come from JWT)"),
    role: str = Query(default="ADMINISTRADOR", description="Role (will come from JWT)"),
    route_id: UUID | None = Query(default=None, description="Route ID (will come from JWT)"),
    user_id: UUID | None = Query(default=None, description="User ID (will come from JWT)"),
    device_id: UUID | None = Query(default=None, description="Device ID (will come from JWT)"),
) -> RequestContext:
    if role not in ("ADMINISTRADOR", "COBRADOR", "INVERSIONISTA"):
        raise HTTPException(status_code=400, detail=f"Rol no válido: {role}")
    if role == "COBRADOR" and route_id is None:
        raise HTTPException(status_code=400, detail="COBRADOR requiere route_id")
    return RequestContext(
        user_id=user_id,
        negocio_id=negocio_id,
        role=role,
        route_id=route_id,
        device_id=device_id,
    )
