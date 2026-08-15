"""Gestion de usuarios — W1 (U1).

Todos los endpoints requieren ADMINISTRADOR.
  POST   /api/usuarios            — crear usuario
  GET    /api/usuarios            — listar usuarios
  GET    /api/usuarios/{id}       — obtener usuario
  PATCH  /api/usuarios/{id}       — editar usuario
  PATCH  /api/usuarios/{id}/estado — activar/desactivar
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.auth.deps import get_request_context
from src.database import get_db, get_db_transaction
from src.models import Usuario
from src.schemas import (
    UsuarioCreate,
    UsuarioListResponse,
    UsuarioResponse,
    UsuarioUpdate,
)
from src.services import usuario_service

router = APIRouter(prefix="/api/usuarios", tags=["usuarios"])

WriteSession = Annotated[
    Session,
    Depends(get_db_transaction, scope="function"),
]


@router.post("", response_model=UsuarioResponse, status_code=201)
def crear_usuario(
    data: UsuarioCreate,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    if not ctx.is_admin():
        raise HTTPException(status_code=403, detail="Solo ADMINISTRADOR puede crear usuarios")

    usuario = usuario_service.crear_usuario(
        db=db,
        negocio_id=ctx.negocio_id,
        nombre=data.nombre,
        rol=data.rol,
        documento=data.documento,
        actor_id=ctx.user_id,
    )
    return UsuarioResponse.model_validate(usuario)


@router.get("", response_model=list[UsuarioListResponse])
def listar_usuarios(
    rol: str | None = Query(default=None),
    activo: int | None = Query(default=None),
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    if not ctx.is_admin():
        raise HTTPException(status_code=403, detail="Solo ADMINISTRADOR puede listar usuarios")

    usuarios = usuario_service.listar_usuarios(
        db=db,
        negocio_id=ctx.negocio_id,
        rol=rol,
        activo=activo,
    )
    return [
        UsuarioListResponse(
            id=u.id,
            rol=u.rol,
            nombre=u.nombre,
            documento=u.documento,
            activo=u.activo,
            creado_el=u.creado_el,
        )
        for u in usuarios
    ]


@router.get("/{usuario_id}", response_model=UsuarioResponse)
def obtener_usuario(
    usuario_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    if not ctx.is_admin():
        raise HTTPException(status_code=403, detail="Solo ADMINISTRADOR puede ver usuarios")

    usuario = usuario_service.obtener_usuario(
        db=db,
        usuario_id=usuario_id,
        negocio_id=ctx.negocio_id,
    )
    return UsuarioResponse.model_validate(usuario)


@router.patch("/{usuario_id}", response_model=UsuarioResponse)
def editar_usuario(
    usuario_id: UUID,
    data: UsuarioUpdate,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    if not ctx.is_admin():
        raise HTTPException(status_code=403, detail="Solo ADMINISTRADOR puede editar usuarios")

    usuario = usuario_service.obtener_usuario(
        db=db,
        usuario_id=usuario_id,
        negocio_id=ctx.negocio_id,
    )
    usuario = usuario_service.editar_usuario(
        db=db,
        usuario=usuario,
        actor_id=ctx.user_id,
        nombre=data.nombre,
        documento=data.documento,
    )
    return UsuarioResponse.model_validate(usuario)


@router.patch("/{usuario_id}/estado", response_model=UsuarioResponse)
def cambiar_estado_usuario(
    usuario_id: UUID,
    db: WriteSession,
    activo: int = Query(..., ge=0, le=1),
    ctx: RequestContext = Depends(get_request_context),
):
    """Activar (activo=1) o desactivar (activo=0) un usuario."""
    if not ctx.is_admin():
        raise HTTPException(status_code=403, detail="Solo ADMINISTRADOR puede cambiar estado de usuarios")

    usuario = usuario_service.obtener_usuario(
        db=db,
        usuario_id=usuario_id,
        negocio_id=ctx.negocio_id,
    )

    if activo == 0:
        usuario = usuario_service.desactivar_usuario(
            db=db,
            usuario=usuario,
            actor_id=ctx.user_id,
        )
    elif activo == 1:
        usuario = usuario_service.activar_usuario(
            db=db,
            usuario=usuario,
            actor_id=ctx.user_id,
        )
    else:
        raise HTTPException(status_code=400, detail="activo debe ser 0 o 1")

    return UsuarioResponse.model_validate(usuario)
