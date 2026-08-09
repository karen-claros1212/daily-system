"""Mobile sync — dataset de la ruta activa del cobrador (Bloque offline sync).

GET /api/mobile/sync (S1/S2):
- El scope se deriva COMPLETO del RequestContext productivo (JWT ES256 -> base):
  negocio, cobrador, ruta activa unica. El movil nunca envia route_id como
  autoridad, nunca elige ruta y nunca descarga otras rutas ni todos los tenants.
- Devuelve en una sola respuesta los cinco datasets del primer sync, limitados
  a la ruta activa unica: clientes, creditos, cuotas, pagos, movimientos y
  jornadas. El movil escribe cada lista en su propia transaccion local.
- Fail-closed: la ruta ya fue exigida por get_request_context_jwt en deps.py
  (0 y >1 rutas activas -> 401 antes de llegar aqui). Este servicio revalida
  que el contexto sea de COBRADOR con ruta activa vigente.
"""

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.models import (
    Cliente,
    Credito,
    CuotaProgramada,
    Jornada,
    MovimientoCaja,
    Pago,
    Ruta,
    Usuario,
)
from src.services.auth_service import AuthError


@dataclass(frozen=True)
class SyncResult:
    """Dataset completo de la ruta activa unica del cobrador."""

    negocio_id: UUID
    cobrador_id: UUID
    ruta_id: UUID
    ruta_version: int
    clientes: list[Cliente] = field(default_factory=list)
    creditos: list[Credito] = field(default_factory=list)
    cuotas: list[CuotaProgramada] = field(default_factory=list)
    pagos: list[Pago] = field(default_factory=list)
    movimientos: list[MovimientoCaja] = field(default_factory=list)
    jornadas: list[Jornada] = field(default_factory=list)


def _exigir_ruta_vigente(db: Session, ctx: RequestContext) -> tuple[UUID, int]:
    """Revalida el rol y la ruta activa unica del cobrador (fail-closed).

    get_request_context_jwt ya exige exactamente una ruta activa (0 y >1 ->
    401 en deps.py); aqui se revalida contra la base por consistencia con
    bootstrap_productivo: sin cobrador activo o sin ruta activa vigente, el
    sync no se sirve.
    """
    if not ctx.is_cobrador() or not ctx.route_id:
        raise AuthError(
            "El sync esta disponible solo para cobradores con ruta activa",
            "ROL_NO_PERMITIDO",
            401,
        )

    cobrador = db.query(Usuario).filter(Usuario.id == ctx.user_id).first()
    if not cobrador or cobrador.rol != "COBRADOR" or cobrador.activo != 1:
        raise AuthError("Cobrador no activo", "COBRADOR_INACTIVO", 401)

    ruta = db.query(Ruta).filter(Ruta.id == ctx.route_id).first()
    if not ruta or ruta.activa != 1 or ruta.cobrador_id != ctx.user_id:
        raise AuthError("Ruta no activa", "RUTA_INACTIVA", 401)

    return ruta.id, ruta.version or 1


def sync_dataset(db: Session, ctx: RequestContext) -> SyncResult:
    """Consulta el dataset completo de la ruta activa unica del cobrador.

    Cada dataset se limita a la ruta derivada del contexto (nunca del cliente).
    Los pagos y movimientos quedan aislados por ruta via join a sus entidades
    de ruta (Credito / Jornada), igual que en los list endpoints de cobrador.
    """
    ruta_id, ruta_version = _exigir_ruta_vigente(db, ctx)

    clientes = (
        db.query(Cliente)
        .join(Credito, Credito.cliente_id == Cliente.id)
        .filter(Credito.ruta_id == ruta_id)
        .filter(Cliente.negocio_id == ctx.negocio_id)
        .distinct()
        .all()
    )

    creditos = (
        db.query(Credito)
        .filter(Credito.ruta_id == ruta_id)
        .filter(Credito.negocio_id == ctx.negocio_id)
        .all()
    )

    cuotas = (
        db.query(CuotaProgramada)
        .join(Credito, Credito.id == CuotaProgramada.credito_id)
        .filter(Credito.ruta_id == ruta_id)
        .filter(CuotaProgramada.negocio_id == ctx.negocio_id)
        .all()
    )

    pagos = (
        db.query(Pago)
        .join(Credito, Credito.id == Pago.credito_id)
        .filter(Credito.ruta_id == ruta_id)
        .filter(Pago.negocio_id == ctx.negocio_id)
        .all()
    )

    movimientos = (
        db.query(MovimientoCaja)
        .join(Jornada, Jornada.id == MovimientoCaja.jornada_id)
        .filter(Jornada.ruta_id == ruta_id)
        .filter(MovimientoCaja.negocio_id == ctx.negocio_id)
        .all()
    )

    jornadas = (
        db.query(Jornada)
        .filter(Jornada.ruta_id == ruta_id)
        .filter(Jornada.negocio_id == ctx.negocio_id)
        .all()
    )

    return SyncResult(
        negocio_id=ctx.negocio_id,
        cobrador_id=ctx.user_id,
        ruta_id=ruta_id,
        ruta_version=ruta_version,
        clientes=clientes,
        creditos=creditos,
        cuotas=cuotas,
        pagos=pagos,
        movimientos=movimientos,
        jornadas=jornadas,
    )
