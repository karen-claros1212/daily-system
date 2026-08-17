"""Movimiento routes — append-only caja movements + W5 web read-model."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.auth.deps import get_request_context
from src.database import get_db, get_db_transaction
from src.models import Jornada, MovimientoCaja, Ruta, Usuario
from src.rbac import tiene_capability
from src.schemas import MovimientoCreate, MovimientoResponse
from src.services.movimiento_service import (
    MovimientoAjusteError,
    MovimientoIdempotencyError,
    MovimientoJornadaError,
    MovimientoMontoInvalido,
    MovimientoNaturalezaInvalida,
    MovimientoNotaObligatoria,
    MovimientoNotFoundError,
    MovimientoTipoInvalido,
    get_movimiento,
    list_movimientos,
    register_movimiento,
)

router = APIRouter(prefix="/api/movimientos", tags=["movimientos"])

WriteSession = Annotated[
    Session,
    Depends(get_db_transaction, scope="function"),
]

VALID_SORTS = frozenset({"creado_el", "monto", "tipo"})


@router.post("", response_model=MovimientoResponse, status_code=201)
def registrar_movimiento(
    data: MovimientoCreate,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    try:
        movimiento = register_movimiento(db, data.model_dump(), ctx)
        return MovimientoResponse.model_validate(movimiento)
    except MovimientoJornadaError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except MovimientoIdempotencyError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except MovimientoTipoInvalido as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except MovimientoNaturalezaInvalida as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except MovimientoMontoInvalido as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except MovimientoAjusteError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except MovimientoNotaObligatoria as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except MovimientoError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("", response_model=list[MovimientoResponse])
def listar_movimientos(
    jornada_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    try:
        movimientos = list_movimientos(db, jornada_id, ctx)
        return [MovimientoResponse.model_validate(m) for m in movimientos]
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ─── W5: Web read-model (envelope, filtros, sort, paginación, role scoping) ───
# IMPORTANT: /web y /resumen DEBEN ir antes de /{movimiento_id} (route ordering).


@router.get("/web")
def listar_movimientos_web(
    q: str | None = Query(default=None, max_length=100),
    tipo: str | None = Query(default=None),
    naturaleza: str | None = Query(default=None),
    ruta_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="creado_el"),
    order: str = Query(default="desc"),
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Web read-model: envelope con filtros, sort, paginación y role scoping.

    - ADMINISTRADOR: todos los movimientos del negocio.
    - INVERSIONISTA: todos (PII minimizada: creado_por_nombre → null).
    - COBRADOR: scoped a su ruta activa (404 fuera de scope).
    """
    if not tiene_capability(ctx.role, "movimientos:ver") and not ctx.is_cobrador():
        raise HTTPException(status_code=403, detail="Forbidden: sin capability de movimientos")

    if sort not in VALID_SORTS:
        raise HTTPException(status_code=422, detail=f"sort inválido: {sort} (permitidos: {', '.join(sorted(VALID_SORTS))})")
    dir_order = -1 if order.lower() == "desc" else 1

    query = db.query(MovimientoCaja).filter(
        MovimientoCaja.negocio_id == ctx.negocio_id,
    )

    # COBRADOR: scoped a su ruta activa.
    if ctx.is_cobrador():
        query = query.join(Jornada, Jornada.id == MovimientoCaja.jornada_id).filter(
            Jornada.ruta_id == ctx.route_id
        )

    # Filtros.
    if q:
        query = query.filter(MovimientoCaja.nota.ilike(f"%{q}%"))
    if tipo:
        query = query.filter(MovimientoCaja.tipo == tipo)
    if naturaleza:
        query = query.filter(MovimientoCaja.naturaleza == naturaleza)
    if ruta_id:
        query = query.join(Jornada, Jornada.id == MovimientoCaja.jornada_id).filter(
            Jornada.ruta_id == ruta_id
        )

    total = query.count()

    sort_col = getattr(MovimientoCaja, sort, MovimientoCaja.creado_el)
    query = query.order_by(sort_col.desc() if dir_order == -1 else sort_col.asc()).limit(limit).offset(offset)
    items = query.all()

    # Resolver nombres para el read-model.
    resultado = []
    ids_creador = {m.creado_por for m in items if m.creado_por}
    usuarios = {u.id: u.nombre for u in db.query(Usuario).filter(Usuario.id.in_(ids_creador)).all()} if ids_creador else {}
    ids_jornada = {m.jornada_id for m in items if m.jornada_id}
    jornadas = {j.id: j for j in db.query(Jornada).filter(Jornada.id.in_(ids_jornada)).all()} if ids_jornada else {}
    ids_ruta = {j.ruta_id for j in jornadas.values() if j.ruta_id}
    rutas = {r.id: r.nombre for r in db.query(Ruta).filter(Ruta.id.in_(ids_ruta)).all()} if ids_ruta else {}

    for m in items:
        j = jornadas.get(m.jornada_id) if m.jornada_id else None
        ruta_nombre = rutas.get(j.ruta_id) if j and j.ruta_id else None
        creado_por_nombre = usuarios.get(m.creado_por) if m.creado_por else None
        # INVERSIONISTA: PII minimizada.
        if ctx.role == "INVERSIONISTA":
            creado_por_nombre = None
        resultado.append({
            "id": str(m.id),
            "negocio_id": str(m.negocio_id),
            "jornada_id": str(m.jornada_id) if m.jornada_id else None,
            "tipo": m.tipo,
            "naturaleza": m.naturaleza,
            "monto": m.monto,
            "nota": m.nota,
            "clave_idempotencia": m.clave_idempotencia,
            "creado_por": str(m.creado_por) if m.creado_por else None,
            "creado_por_nombre": creado_por_nombre,
            "creado_el": m.creado_el.isoformat() if m.creado_el else None,
            "jornada_fecha": j.fecha.isoformat() if j and j.fecha else None,
            "ruta_id": str(j.ruta_id) if j and j.ruta_id else None,
            "ruta_nombre": ruta_nombre,
        })

    return {"items": resultado, "total": total, "limit": limit, "offset": offset}


@router.get("/resumen")
def resumen_movimientos(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Resumen financiero: gastos por tipo, totales, counts."""
    if not tiene_capability(ctx.role, "movimientos:ver") and not ctx.is_cobrador():
        raise HTTPException(status_code=403, detail="Forbidden: sin capability de movimientos")

    query = db.query(MovimientoCaja).filter(
        MovimientoCaja.negocio_id == ctx.negocio_id,
    )
    if ctx.is_cobrador():
        query = query.join(Jornada, Jornada.id == MovimientoCaja.jornada_id).filter(
            Jornada.ruta_id == ctx.route_id
        )

    total_movimientos = query.count()
    total_monto = db.query(func.sum(MovimientoCaja.monto)).filter(
        MovimientoCaja.negocio_id == ctx.negocio_id,
    ).scalar() or 0
    if ctx.is_cobrador():
        total_monto = db.query(func.sum(MovimientoCaja.monto)).join(
            Jornada, Jornada.id == MovimientoCaja.jornada_id
        ).filter(
            MovimientoCaja.negocio_id == ctx.negocio_id,
            Jornada.ruta_id == ctx.route_id,
        ).scalar() or 0

    # Gastos por tipo.
    gastos_por_tipo = (
        db.query(MovimientoCaja.tipo, func.sum(MovimientoCaja.monto), func.count(MovimientoCaja.id))
        .filter(MovimientoCaja.negocio_id == ctx.negocio_id)
        .filter(MovimientoCaja.naturaleza == "GASTO")
        .group_by(MovimientoCaja.tipo)
        .all()
    )
    if ctx.is_cobrador():
        gastos_por_tipo = (
            db.query(MovimientoCaja.tipo, func.sum(MovimientoCaja.monto), func.count(MovimientoCaja.id))
            .join(Jornada, Jornada.id == MovimientoCaja.jornada_id)
            .filter(MovimientoCaja.negocio_id == ctx.negocio_id)
            .filter(Jornada.ruta_id == ctx.route_id)
            .filter(MovimientoCaja.naturaleza == "GASTO")
            .group_by(MovimientoCaja.tipo)
            .all()
        )

    return {
        "total_movimientos": total_movimientos,
        "total_monto": int(total_monto),
        "gastos_por_tipo": [
            {"tipo": t, "total": int(s), "count": c}
            for t, s, c in gastos_por_tipo
        ],
    }


@router.get("/{movimiento_id}", response_model=MovimientoResponse)
def obtener_movimiento(
    movimiento_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    try:
        movimiento = get_movimiento(db, movimiento_id, ctx)
        return MovimientoResponse.model_validate(movimiento)
    except MovimientoNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
