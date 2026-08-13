"""Identity canonica de sesion — GET /api/auth/me.

Fuente canonica de identidad para el frontend (Web Premium): tras autenticarse,
el cliente consulta /me y obtiene rol, negocio/tenant y capabilities, SIN
deducir el rol del JWT ni asumirlo por el metodo de login.

Autoridad: el backend. El rol se deriva de la DB en cada request (deps.py
> _context_from_jwt) y se revalida contra el usuario aqui (fail-closed: un
usuario inactivo o de otro negocio nunca llega a /me con 200).

Aislamiento de tenant: TODO el alcance sale del RequestContext (JWT), nunca de
query/body. COBRADOR ademas trae route_id derivado por el servidor.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.auth.deps import get_request_context_jwt
from src.database import get_db
from src.models import Negocio, Ruta, Usuario
from src.rbac import capabilities_de_rol
from src.schemas import MeResponse, NegocioInfo
from src.time_utils import as_utc

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me", response_model=MeResponse)
def obtener_me(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context_jwt),
):
    """Identidad canonica de la sesion: rol/tenant/capabilities desde la DB.

    JWT-only (get_request_context_jwt): ni siquiera en test/development el
    stub query-param vale para /me. Un cliente no puede pedir su identidad
    con ?role=... — la identidad sale exclusivamente de la sesion firmada.
    """
    if not ctx.user_id or not ctx.negocio_id or not ctx.role:
        raise HTTPException(status_code=401, detail="Credencial de sesion (Bearer JWT) requerida")

    usuario = db.query(Usuario).filter(Usuario.id == ctx.user_id).first()
    if not usuario or usuario.activo != 1:
        raise HTTPException(status_code=401, detail="Usuario no activo")
    if usuario.negocio_id != ctx.negocio_id:
        raise HTTPException(status_code=401, detail="Usuario de otro negocio")

    negocio = db.query(Negocio).filter(Negocio.id == ctx.negocio_id).first()
    if not negocio:
        raise HTTPException(status_code=401, detail="Negocio no encontrado")

    now = datetime.now(timezone.utc)
    suscripcion_activa = negocio.estado_suscripcion == "al_dia" and (
        as_utc(negocio.paid_through_at) is None
        or as_utc(negocio.paid_through_at) > now
    )

    ruta_nombre: str | None = None
    if ctx.route_id:
        ruta = db.query(Ruta).filter(Ruta.id == ctx.route_id).first()
        if ruta:
            ruta_nombre = ruta.nombre

    return MeResponse(
        user_id=usuario.id,
        usuario_nombre=usuario.nombre,
        rol=usuario.rol,
        activo=usuario.activo == 1,
        negocio=NegocioInfo(
            negocio_id=negocio.id,
            nombre=negocio.nombre,
            plan=negocio.plan,
            moneda=negocio.moneda,
            zona_horaria=negocio.zona_horaria,
            estado_suscripcion=negocio.estado_suscripcion,
            suscripcion_activa=suscripcion_activa,
        ),
        route_id=ctx.route_id,
        route_nombre=ruta_nombre,
        device_id=ctx.device_id,
        version_asignacion=ctx.version_asignacion,
        capabilities=capabilities_de_rol(usuario.rol),
    )
