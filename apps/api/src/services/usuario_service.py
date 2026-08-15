"""Servicio de usuarios — W1 (U1).

Solo ADMINISTRADOR puede crear, listar, editar y desactivar usuarios.
INVERSIONISTA solo ve usuarios de su negocio.

Reglas:
  - COBRADOR y INVERSIONISTA: solo ADMINISTRADOR puede crearlos.
  - Un negocio puede tener multiples usuarios por rol.
  - documento: unico por (negocio, documento) para no-NULL.
  - Desactivar (activo=0) es soft-delete: no se puede reusar el documento.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.models import AuditLog, Usuario


def _now() -> datetime:
    return datetime.now(timezone.utc)


def crear_usuario(
    db: Session,
    negocio_id: UUID,
    nombre: str,
    rol: str,
    documento: str | None,
    actor_id: UUID,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Usuario:
    """Crear un nuevo usuario en el negocio.

    Solo ADMINISTRADOR. Rol debe ser COBRADOR o INVERSIONISTA.
    """
    if rol not in ("COBRADOR", "INVERSIONISTA"):
        raise HTTPException(
            status_code=400,
            detail="Rol debe ser COBRADOR o INVERSIONISTA",
        )

    if documento:
        existente = db.query(Usuario).filter(
            Usuario.negocio_id == negocio_id,
            Usuario.documento == documento,
        ).first()
        if existente:
            raise HTTPException(
                status_code=409,
                detail=f"Ya existe un usuario con documento {documento} en este negocio",
            )

    usuario = Usuario(
        negocio_id=negocio_id,
        rol=rol,
        nombre=nombre.strip(),
        documento=documento.strip() if documento else None,
        activo=1,
    )
    db.add(usuario)
    db.flush()

    # Audit log
    audit = AuditLog(
        negocio_id=negocio_id,
        actor_id=actor_id,
        action="USUARIO_CREADO",
        entity_type="USUARIO",
        entity_id=usuario.id,
        metadata_col={
            "rol": rol,
            "nombre": nombre,
            "documento": usuario.documento,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(audit)
    db.flush()
    db.refresh(usuario)
    return usuario


def listar_usuarios(
    db: Session,
    negocio_id: UUID,
    rol: str | None = None,
    activo: int | None = None,
) -> list[Usuario]:
    """Listar usuarios del negocio. Solo ADMINISTRADOR."""
    q = db.query(Usuario).filter(Usuario.negocio_id == negocio_id)
    if rol:
        q = q.filter(Usuario.rol == rol)
    if activo is not None:
        q = q.filter(Usuario.activo == activo)
    return q.order_by(Usuario.creado_el.desc()).all()


def obtener_usuario(
    db: Session,
    usuario_id: UUID,
    negocio_id: UUID,
) -> Usuario:
    """Obtener un usuario del negocio."""
    usuario = db.query(Usuario).filter(
        Usuario.id == usuario_id,
        Usuario.negocio_id == negocio_id,
    ).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return usuario


def editar_usuario(
    db: Session,
    usuario: Usuario,
    actor_id: UUID,
    nombre: str | None = None,
    documento: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Usuario:
    """Editar usuario existente. Solo ADMINISTRADOR."""
    cambios = {}
    if nombre is not None:
        if not nombre.strip():
            raise HTTPException(status_code=400, detail="nombre no puede estar vacio")
        usuario.nombre = nombre.strip()
        cambios["nombre"] = nombre
    if documento is not None:
        doc = documento.strip()
        if doc:
            existente = db.query(Usuario).filter(
                Usuario.id != usuario.id,
                Usuario.negocio_id == usuario.negocio_id,
                Usuario.documento == doc,
            ).first()
            if existente:
                raise HTTPException(
                    status_code=409,
                    detail=f"Ya existe un usuario con documento {doc} en este negocio",
                )
            usuario.documento = doc
            cambios["documento"] = doc
    db.flush()

    # Audit log
    audit = AuditLog(
        negocio_id=usuario.negocio_id,
        actor_id=actor_id,
        action="USUARIO_EDITADO",
        entity_type="USUARIO",
        entity_id=usuario.id,
        metadata_col={
            "rol": usuario.rol,
            "cambios": cambios,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(audit)
    db.flush()
    return usuario


def desactivar_usuario(
    db: Session,
    usuario: Usuario,
    actor_id: UUID,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Usuario:
    """Desactivar usuario (soft-delete). Solo ADMINISTRADOR."""
    if usuario.activo == 0:
        raise HTTPException(status_code=400, detail="Usuario ya esta desactivado")
    usuario.activo = 0

    audit = AuditLog(
        negocio_id=usuario.negocio_id,
        actor_id=actor_id,
        action="USUARIO_DESATIVADO",
        entity_type="USUARIO",
        entity_id=usuario.id,
        metadata_col={
            "rol": usuario.rol,
            "nombre": usuario.nombre,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(audit)
    db.flush()
    return usuario


def activar_usuario(
    db: Session,
    usuario: Usuario,
    actor_id: UUID,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Usuario:
    """Reactivar usuario. Solo ADMINISTRADOR."""
    if usuario.activo == 1:
        raise HTTPException(status_code=400, detail="Usuario ya esta activo")
    usuario.activo = 1

    audit = AuditLog(
        negocio_id=usuario.negocio_id,
        actor_id=actor_id,
        action="USUARIO_ACTIVADO",
        entity_type="USUARIO",
        entity_id=usuario.id,
        metadata_col={
            "rol": usuario.rol,
            "nombre": usuario.nombre,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(audit)
    db.flush()
    return usuario
