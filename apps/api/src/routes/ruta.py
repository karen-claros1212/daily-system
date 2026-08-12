from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.auth.deps import get_request_context
from src.database import get_db, get_db_transaction
from src.models import Dispositivo, Negocio, Ruta, Usuario
from src.schemas import RutaCreate, RutaResponse, RutaReasignarRequest, RutaReasignarResponse


def _uuid_eq(column, val: str | UUID):
    """Comparar columna UUID con valor string o UUID."""
    if isinstance(val, str):
        return column == UUID(val)
    if isinstance(val, UUID):
        return column == val
    return column == val


router = APIRouter(prefix="/api/rutas", tags=["rutas"])

WriteSession = Annotated[
    Session,
    Depends(get_db_transaction, scope="function"),
]


@router.post("", response_model=RutaResponse, status_code=201)
def crear_ruta(
    data: RutaCreate,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    # Creacion de rutas es exclusiva del ADMINISTRADOR: el cobrador no puede
    # asignarse rutas ni crear rutas con otro cobrador a cargo.
    if not ctx.is_admin():
        raise HTTPException(status_code=403, detail="Solo el administrador puede crear rutas")

    negocio = db.query(Negocio).filter(_uuid_eq(Negocio.id, ctx.negocio_id)).first()
    if not negocio:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")

    # No se confia en el tenant enviado por el cliente: el cobrador asignado
    # debe existir, pertenecer al mismo negocio y tener rol COBRADOR.
    cobrador_id = data.cobrador_id
    if cobrador_id is not None:
        cobrador = db.query(Usuario).filter(
            _uuid_eq(Usuario.id, cobrador_id),
            _uuid_eq(Usuario.negocio_id, ctx.negocio_id),
        ).first()
        if not cobrador or cobrador.rol != "COBRADOR":
            raise HTTPException(status_code=400, detail="Cobrador no encontrado en este negocio o no tiene rol COBRADOR")
        if cobrador.activo != 1:
            raise HTTPException(status_code=400, detail="El cobrador no está activo")

    ruta = Ruta(
        negocio_id=ctx.negocio_id,
        nombre=data.nombre,
        cobrador_id=data.cobrador_id,
    )
    db.add(ruta)
    db.flush()
    db.refresh(ruta)
    return RutaResponse.model_validate(ruta)


@router.get("", response_model=list[RutaResponse])
def listar_rutas(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    q = db.query(Ruta).filter(_uuid_eq(Ruta.negocio_id, ctx.negocio_id))
    if ctx.is_cobrador():
        q = q.filter(_uuid_eq(Ruta.id, ctx.route_id))
    return [RutaResponse.model_validate(r) for r in q.filter(Ruta.activa == 1).all()]


@router.get("/{ruta_id}", response_model=RutaResponse)
def obtener_ruta(
    ruta_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    if ctx.is_cobrador() and not ctx.has_route(ruta_id):
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    ruta = db.query(Ruta).filter(
        _uuid_eq(Ruta.id, ruta_id),
        _uuid_eq(Ruta.negocio_id, ctx.negocio_id),
    ).first()
    if not ruta:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    return RutaResponse.model_validate(ruta)


@router.patch("/{ruta_id}/reasignar", response_model=RutaReasignarResponse, status_code=200)
def reasignar_ruta(
    ruta_id: UUID,
    data: RutaReasignarRequest,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    """S4 — Reasignacion productiva R1→R2.

    Desactiva la ruta actual (R1), crea/activa R2 para el mismo cobrador,
    bump version_asignacion del dispositivo del cobrador (invalida JWT viejo).

    Contrato:
      - SOLO ADMINISTRADOR
      - Mismo negocio, cobrador valido
      - R1 deja de ser la ruta activa del cobrador
      - R2 queda como la UNICA ruta activa
      - Transaccion unica
      - Servidor es autoridad
      - Movil nunca selecciona ruta
      - version_asignacion se incrementa → JWT anterior queda invalido
    """
    if not ctx.is_admin():
        raise HTTPException(status_code=403, detail="Solo el administrador puede reasignar rutas")

    negocio = db.query(Negocio).filter(_uuid_eq(Negocio.id, ctx.negocio_id)).first()
    if not negocio:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")

    # 1. Validar R1: debe existir, del mismo negocio, activa, con cobrador.
    ruta_actual = db.query(Ruta).filter(
        _uuid_eq(Ruta.id, ruta_id),
        _uuid_eq(Ruta.negocio_id, ctx.negocio_id),
        Ruta.activa == 1,
    ).first()
    if not ruta_actual:
        raise HTTPException(status_code=404, detail="Ruta activa no encontrada")
    if not ruta_actual.cobrador_id:
        raise HTTPException(status_code=400, detail="La ruta no tiene cobrador asignado")

    # 2. Validar cobrador: debe existir, del mismo negocio, activo, rol COBRADOR.
    cobrador = db.query(Usuario).filter(
        _uuid_eq(Usuario.id, ruta_actual.cobrador_id),
        _uuid_eq(Usuario.negocio_id, ctx.negocio_id),
        Usuario.rol == "COBRADOR",
        Usuario.activo == 1,
    ).first()
    if not cobrador:
        raise HTTPException(status_code=400, detail="Cobrador no encontrado en este negocio o no activo")

    # Asegurar cobrador.id como UUID puro para queries subsiguientes.
    cobrador_id_val = cobrador.id
    if not isinstance(cobrador_id_val, UUID):
        cobrador_id_val = UUID(cobrador_id_val)

    # 3. Validar nuevo nombre de ruta (R2).
    nuevo_nombre = data.nombre
    if not nuevo_nombre or len(nuevo_nombre) < 1 or len(nuevo_nombre) > 100:
        raise HTTPException(status_code=400, detail="nombre debe tener entre 1 y 100 caracteres")

    # 3a. Verificar que el nombre no esté ocupado por otra ruta activa de otro cobrador.
    #     La ruta activa del cobrador actual (R1) ya tiene nombre diferente (se reasigna).
    ruta_ocupada = db.query(Ruta).filter(
        _uuid_eq(Ruta.negocio_id, ctx.negocio_id),
        Ruta.nombre == nuevo_nombre,
        Ruta.activa == 1,
        _uuid_eq(Ruta.cobrador_id, cobrador_id_val) == False,
    ).first()
    if ruta_ocupada:
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe ruta activa '{nuevo_nombre}' para otro cobrador ({ruta_ocupada.id})",
        )

    # 4. Desactivar R1.
    ruta_actual.activa = 0
    ruta_actual.version = (ruta_actual.version or 1) + 1
    db.flush()

    # 5. Crear o reactivar R2 para el mismo cobrador.
    #    El constraint unico: cobrador_id + activa == 1 → max una activa por cobrador.
    r2 = db.query(Ruta).filter(
        _uuid_eq(Ruta.cobrador_id, cobrador_id_val),
        _uuid_eq(Ruta.negocio_id, ctx.negocio_id),
        Ruta.activa == 1,
    ).first()
    if r2:
        # Ya existe R2 activa (del cobrador en este negocio) → reutilizar.
        r2.nombre = nuevo_nombre
        r2.version = (r2.version or 1) + 1
    else:
        # Crear R2 nueva.
        r2 = Ruta(
            negocio_id=ctx.negocio_id,
            nombre=nuevo_nombre,
            cobrador_id=cobrador_id_val,
            activa=1,
            version=1,
        )
        db.add(r2)

    # 6. Bump version_asignacion del dispositivo activo del cobrador.
    dispositivo = db.query(Dispositivo).filter(
        _uuid_eq(Dispositivo.usuario_id, cobrador_id_val),
        Dispositivo.estado == "ACTIVE",
    ).first()
    nueva_version = 1
    if dispositivo:
        nueva_version = (dispositivo.version_asignacion or 1) + 1
        dispositivo.version_asignacion = nueva_version
    # Sin dispositivo activo: no hay JWT activo que invalidar, version sin cambios.

    db.flush()

    return RutaReasignarResponse(
        ruta_anterior_id=ruta_actual.id,
        ruta_anterior_nombre=ruta_actual.nombre,
        ruta_nueva_id=r2.id,
        ruta_nueva_nombre=r2.nombre,
        cobrador_id=cobrador_id_val,
        cobrador_nombre=cobrador.nombre,
        version_asignacion=nueva_version,
    )
