"""Authorization dependencies for Daily System.

Bloque 7 (D7-01): auth productiva por JWT firmado por el servidor.

- El dependency lee el header `Authorization: Bearer <jwt>`.
- Valida el JWT (HS256, allow-list fija) contra el secreto del servidor.
- Deriva rol y ruta de la BASE en cada request (usuario.rol, ruta activa del
  cobrador): el JWT nunca lleva role ni route_id (autoridad geografica fuera
  del token y del cliente).
- Valida dispositivo.estado == ACTIVE y version_asignacion == claim: una
  revocacion/reemplazo (bump) mata tokens vigentes de forma inmediata.

Dev/tests: el stub por query-param queda SOLO en DAILY_ENV test/development
(las suites existentes no emiten JWT). Fuera de esos ambientes, query-param
auth devuelve 401.
"""

import os
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.auth.token import TokenError, decode_token
from src.database import get_db
from src.models import Dispositivo, Ruta, Usuario

DbSession = Annotated[Session, Depends(get_db)]

ALLOWED_ROLES = ("ADMINISTRADOR", "COBRADOR", "INVERSIONISTA")


def _env() -> str:
    return os.getenv("DAILY_ENV", "")


def _context_from_jwt(request: Request, db: Session) -> RequestContext:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="Credencial de sesion (Bearer JWT) requerida",
        )
    token = auth.split(" ", 1)[1].strip()
    try:
        claims = decode_token(token)
    except TokenError as e:
        raise HTTPException(status_code=401, detail=str(e))

    negocio_id = UUID(claims["negocio_id"])
    usuario_id = UUID(claims["usuario_id"])
    dispositivo_id = UUID(claims["dispositivo_id"])
    token_version = int(claims["version_asignacion"])

    dispositivo = (
        db.query(Dispositivo)
        .filter(Dispositivo.id == dispositivo_id)
        .first()
    )
    if not dispositivo or dispositivo.estado != "ACTIVE":
        raise HTTPException(
            status_code=401,
            detail="Dispositivo no activo",
        )
    if (dispositivo.version_asignacion or 1) != token_version:
        raise HTTPException(
            status_code=401,
            detail="Asignacion del dispositivo revocada o reemplazada",
        )
    if dispositivo.negocio_id != negocio_id:
        raise HTTPException(status_code=401, detail="Negocio del token no coincide")

    usuario = (
        db.query(Usuario)
        .filter(Usuario.id == usuario_id)
        .first()
    )
    if not usuario or usuario.activo != 1:
        raise HTTPException(status_code=401, detail="Usuario no activo")
    if usuario.negocio_id != negocio_id:
        raise HTTPException(status_code=401, detail="Usuario de otro negocio")

    role = usuario.rol
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=401, detail=f"Rol no valido: {role}")

    route_id: UUID | None = None
    if role == "COBRADOR":
        ruta = (
            db.query(Ruta)
            .filter(
                Ruta.cobrador_id == usuario_id,
                Ruta.activa == 1,
                Ruta.negocio_id == negocio_id,
            )
            .first()
        )
        if not ruta:
            raise HTTPException(
                status_code=401,
                detail="El cobrador no tiene una ruta activa asignada",
            )
        route_id = ruta.id

    return RequestContext(
        user_id=usuario_id,
        negocio_id=negocio_id,
        role=role,
        route_id=route_id,
        device_id=dispositivo_id,
    )


def _context_from_query(
    negocio_id: UUID | None,
    role: str | None,
    route_id: UUID | None,
    user_id: UUID | None,
    device_id: UUID | None,
    require_route: bool,
) -> RequestContext:
    env = _env()
    if env not in ("dev", "development", "test"):
        raise HTTPException(
            status_code=401,
            detail="query-param auth disabled — use Bearer JWT",
        )
    role = role or "ADMINISTRADOR"
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=f"Rol no válido: {role}")
    if role == "COBRADOR" and route_id is None and require_route:
        raise HTTPException(status_code=400, detail="COBRADOR requiere route_id")
    return RequestContext(
        user_id=user_id,
        negocio_id=negocio_id,
        role=role,
        route_id=route_id,
        device_id=device_id,
    )


def get_request_context(
    request: Request,
    db: DbSession,
    negocio_id: UUID | None = Query(default=None),
    role: str | None = Query(default=None),
    route_id: UUID | None = Query(default=None),
    user_id: UUID | None = Query(default=None),
    device_id: UUID | None = Query(default=None),
) -> RequestContext:
    """Contexto de la request: JWT productivo, o stub query en dev/test."""
    if request.headers.get("authorization"):
        return _context_from_jwt(request, db)
    return _context_from_query(
        negocio_id=negocio_id,
        role=role,
        route_id=route_id,
        user_id=user_id,
        device_id=device_id,
        require_route=True,
    )


def get_request_context_optional(
    request: Request,
    db: DbSession,
    negocio_id: UUID | None = Query(default=None),
    role: str | None = Query(default=None),
    route_id: UUID | None = Query(default=None),
    user_id: UUID | None = Query(default=None),
    device_id: UUID | None = Query(default=None),
) -> RequestContext:
    """Como get_request_context pero COBRADOR no exige route_id."""
    if request.headers.get("authorization"):
        return _context_from_jwt(request, db)
    return _context_from_query(
        negocio_id=negocio_id,
        role=role,
        route_id=route_id,
        user_id=user_id,
        device_id=device_id,
        require_route=False,
    )
