"""Authorization dependencies for Daily System.

M1: Stub implementation — query parameters, RESTRICTED TO DEV/TEST ONLY.
Production: must use JWT claims from signed tokens. Do NOT deploy with query auth.
"""

import os

from fastapi import Depends, HTTPException, Query
from uuid import UUID

from src.auth.context import RequestContext


def get_request_context(
    negocio_id: UUID = Query(..., description="DEV ONLY: Negocio ID (will come from JWT)"),
    role: str = Query(default="ADMINISTRADOR", description="DEV ONLY: Role (will come from JWT)"),
    route_id: UUID | None = Query(default=None, description="DEV ONLY: Route ID (will come from JWT)"),
    user_id: UUID | None = Query(default=None, description="DEV ONLY: User ID (will come from JWT)"),
    device_id: UUID | None = Query(default=None, description="DEV ONLY: Device ID (will come from JWT)"),
) -> RequestContext:
    env = os.getenv("DAILY_ENV", "")
    if env not in ("dev", "development", "test"):
        raise HTTPException(
            status_code=401,
            detail="query-param auth disabled — set DAILY_ENV=dev for local dev",
        )

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


def get_request_context_optional(
    negocio_id: UUID = Query(..., description="DEV ONLY: Negocio ID (will come from JWT)"),
    role: str = Query(default="COBRADOR", description="DEV ONLY: Role (will come from JWT)"),
    route_id: UUID | None = Query(default=None, description="DEV ONLY: Route ID (will come from JWT)"),
    user_id: UUID | None = Query(default=None, description="DEV ONLY: User ID (will come from JWT)"),
    device_id: UUID | None = Query(default=None, description="DEV ONLY: Device ID (will come from JWT)"),
) -> RequestContext:
    """Like get_request_context but COBRADOR doesn't require route_id."""
    env = os.getenv("DAILY_ENV", "")
    if env not in ("dev", "development", "test"):
        raise HTTPException(
            status_code=401,
            detail="query-param auth disabled — set DAILY_ENV=dev for local dev",
        )

    if role not in ("ADMINISTRADOR", "COBRADOR", "INVERSIONISTA"):
        raise HTTPException(status_code=400, detail=f"Rol no válido: {role}")
    return RequestContext(
        user_id=user_id,
        negocio_id=negocio_id,
        role=role,
        route_id=route_id,
        device_id=device_id,
    )
