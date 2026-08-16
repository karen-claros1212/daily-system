"""Ruta service — W4 read model de rutas y mutaciones administrativas.

Read model: listado paginado server-side con `cobrador_nombre` humano (join
con Usuario, sin N+1) y resumen ligero por estado. Sort/order allowlist —
cualquier valor fuera de la lista -> 422 (igual que creditos W3).

Reglas:
  - ADMINISTRADOR: tenant-wide (rutas:ver + rutas:crear + rutas:reasignar).
  - COBRADOR: SOLO su ruta activa; lista/resumen/detalle fuera de scope -> 404
    (no revelar existencia).
  - INVERSIONISTA: read-only (rutas:ver); los campos de cobrador no amplían
    PII por encima del contrato ya emitido por /api/creditos.

S4 (reasignación R1→R2):
  - R1 queda inactiva; R2 queda activa; una única ruta activa por cobrador
    (constraint uq_ruta_activa_cobrador).
  - version_asignacion del dispositivo del cobrador se incrementa -> JWT
    anterior queda inválido (la base manda sobre el claim).
  - Los eventos/operaciones previos conservan su provenance R1.
  - NO es "cambiar cobrador de la misma ruta": mutar cobrador_id sobre una ruta
    con historia financiera falsearía la provenance histórica (prohibido).

Conflictos de dominio -> 409 (nunca IntegrityError -> 500): los pre-checks
detectan el caso común y el catch de IntegrityError cubre la carrera (p. ej.
dos solicitudes concurrentes de alta de ruta activa para el mismo cobrador en
PostgreSQL).
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from src.models import AuditLog, Dispositivo, Negocio, Ruta, Usuario

SORT_ALLOWLIST = {"nombre", "creado_el", "version"}

ROLES_VER = ("ADMINISTRADOR", "INVERSIONISTA")


def _uuid_eq(column, val: str | UUID):
    """Comparar columna UUID con valor string o UUID."""
    if isinstance(val, str):
        return column == UUID(val)
    if isinstance(val, UUID):
        return column == val
    return column == val


def _nombre_cobrador(ruta: Ruta) -> str | None:
    cobrador = getattr(ruta, "cobrador", None)
    if cobrador is None:
        return None
    return cobrador.nombre or None


def _base_query(db: Session, negocio_id: UUID, role: str, route_id: UUID | None):
    q = (
        db.query(Ruta)
        .options(joinedload(Ruta.cobrador))
        .filter(_uuid_eq(Ruta.negocio_id, negocio_id))
    )
    if role == "COBRADOR":
        q = q.filter(_uuid_eq(Ruta.id, route_id), Ruta.activa == 1)
    return q


def _fila(ruta: Ruta) -> dict:
    return {
        "ruta_id": ruta.id,
        "negocio_id": ruta.negocio_id,
        "nombre": ruta.nombre,
        "activa": ruta.activa,
        "version": ruta.version,
        "creado_el": ruta.creado_el,
        "cobrador_id": ruta.cobrador_id,
        "cobrador_nombre": _nombre_cobrador(ruta),
    }


def listar_rutas(
    db: Session,
    negocio_id: UUID,
    role: str,
    route_id: UUID | None,
    search: str | None = None,
    activa: int | None = None,
    cobrador_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
    sort: str = "creado_el",
    order: str = "desc",
) -> dict:
    """Lista paginada del read model de rutas.

    - COBRADOR: solo su ruta (ignora filtros; fuera de scope = vacío).
    - cobrador_id como filtro: SOLO ADMINISTRADOR (el resto lo ignora).
    - q busca en nombre (no es PII de cliente).
    """
    if sort not in SORT_ALLOWLIST:
        raise HTTPException(status_code=422, detail=f"sort no permitido: {sort}")
    if order not in ("asc", "desc"):
        raise HTTPException(status_code=422, detail="order debe ser asc o desc")

    q = _base_query(db, negocio_id, role, route_id)

    if role != "COBRADOR":
        if search:
            term = f"%{search.strip().lower()}%"
            q = q.filter(func.lower(func.coalesce(Ruta.nombre, "")).like(term))
        if activa is not None:
            q = q.filter(Ruta.activa == activa)
        if cobrador_id is not None and role == "ADMINISTRADOR":
            q = q.filter(_uuid_eq(Ruta.cobrador_id, cobrador_id))

    total = q.count()
    rutas = q.all()
    filas = [_fila(r) for r in rutas]

    rev = order == "desc"
    filas.sort(key=lambda r: (r[sort] is None, r[sort]), reverse=rev)
    items = filas[offset:offset + limit]

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def resumen_rutas(
    db: Session,
    negocio_id: UUID,
    role: str,
    route_id: UUID | None,
) -> dict:
    """Conteos por estado, scoped por rol. COBRADOR: solo su ruta."""
    q = _base_query(db, negocio_id, role, route_id)
    rutas = q.all()
    activas = sum(1 for r in rutas if r.activa == 1)
    return {
        "total_rutas": len(rutas),
        "activas": activas,
        "inactivas": len(rutas) - activas,
    }


def obtener_ruta(
    db: Session,
    negocio_id: UUID,
    role: str,
    route_id: UUID | None,
    ruta_id: UUID,
) -> dict:
    """Detalle de una ruta. COBRADOR fuera de su ruta -> 404."""
    ruta = (
        db.query(Ruta)
        .options(joinedload(Ruta.cobrador))
        .filter(_uuid_eq(Ruta.id, ruta_id), _uuid_eq(Ruta.negocio_id, negocio_id))
        .first()
    )
    if not ruta:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    if role == "COBRADOR" and (ruta_id != route_id or ruta.activa != 1):
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    return {
        "id": ruta.id,
        "negocio_id": ruta.negocio_id,
        "nombre": ruta.nombre,
        "cobrador_id": ruta.cobrador_id,
        "cobrador_nombre": _nombre_cobrador(ruta),
        "activa": ruta.activa,
        "version": ruta.version,
        "creado_el": ruta.creado_el,
    }


def crear_ruta(
    db: Session,
    negocio_id: UUID,
    actor_id: UUID | None,
    data,
) -> dict:
    """Crear ruta (SOLO ADMINISTRADOR via rutas:crear).

    Validaciones de dominio:
      - cobrador debe existir, ser del mismo negocio, rol COBRADOR y activo (400).
      - nombre duplicado en el negocio -> 409.
      - cobrador ya tiene una ruta activa -> 409 (una única activa por cobrador).
    Auditoría append-only RUTA_CREADA (metadata técnica, sin PII innecesaria).
    """
    cobrador_id = data.cobrador_id

    if cobrador_id is not None:
        cobrador = db.query(Usuario).filter(
            _uuid_eq(Usuario.id, cobrador_id),
            _uuid_eq(Usuario.negocio_id, negocio_id),
        ).first()
        if not cobrador or cobrador.rol != "COBRADOR":
            raise HTTPException(
                status_code=400,
                detail="Cobrador no encontrado en este negocio o no tiene rol COBRADOR",
            )
        if cobrador.activo != 1:
            raise HTTPException(status_code=400, detail="El cobrador no está activo")

        activa_existente = db.query(Ruta).filter(
            _uuid_eq(Ruta.negocio_id, negocio_id),
            _uuid_eq(Ruta.cobrador_id, cobrador_id),
            Ruta.activa == 1,
        ).first()
        if activa_existente:
            raise HTTPException(
                status_code=409,
                detail=f"El cobrador ya tiene una ruta activa: '{activa_existente.nombre}'",
            )

    duplicada = db.query(Ruta).filter(
        _uuid_eq(Ruta.negocio_id, negocio_id),
        Ruta.nombre == data.nombre,
    ).first()
    if duplicada:
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe una ruta con nombre '{data.nombre}' en este negocio",
        )

    ruta = Ruta(
        negocio_id=negocio_id,
        nombre=data.nombre,
        cobrador_id=cobrador_id,
    )
    db.add(ruta)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Conflicto al crear la ruta: ya existe una ruta activa para este cobrador o el nombre está en uso",
        )
    db.refresh(ruta)

    _registrar_audit(
        db,
        negocio_id,
        actor_id,
        "RUTA_CREADA",
        ruta.id,
        {
            "nombre": ruta.nombre,
            "cobrador_id": str(ruta.cobrador_id) if ruta.cobrador_id else None,
        },
    )

    return {
        "id": ruta.id,
        "negocio_id": ruta.negocio_id,
        "nombre": ruta.nombre,
        "cobrador_id": ruta.cobrador_id,
        "cobrador_nombre": _nombre_cobrador(ruta),
        "activa": ruta.activa,
        "version": ruta.version,
        "creado_el": ruta.creado_el,
    }


def reasignar_ruta(
    db: Session,
    negocio_id: UUID,
    actor_id: UUID | None,
    ruta_id: UUID,
    data,
) -> dict:
    """S4 — Reasignación productiva R1→R2 (movida desde routes/ruta.py).

    Desactiva la ruta actual (R1), crea/activa R2 para el MISMO cobrador y
    hace bump de version_asignacion del dispositivo del cobrador (invalida el
    JWT anterior). Provenance de operaciones previas permanece en R1.

    La lógica NO cambia respecto al contrato S4 certificado: se traslada al
    service y se añade auditoría append-only RUTA_REASIGNADA.
    """
    negocio = db.query(Negocio).filter(_uuid_eq(Negocio.id, negocio_id)).first()
    if not negocio:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")

    # 1. Validar R1: debe existir, del mismo negocio, activa, con cobrador.
    ruta_actual = db.query(Ruta).filter(
        _uuid_eq(Ruta.id, ruta_id),
        _uuid_eq(Ruta.negocio_id, negocio_id),
        Ruta.activa == 1,
    ).first()
    if not ruta_actual:
        raise HTTPException(status_code=404, detail="Ruta activa no encontrada")
    if not ruta_actual.cobrador_id:
        raise HTTPException(status_code=400, detail="La ruta no tiene cobrador asignado")

    # 2. Validar cobrador: mismo negocio, activo, rol COBRADOR.
    cobrador = db.query(Usuario).filter(
        _uuid_eq(Usuario.id, ruta_actual.cobrador_id),
        _uuid_eq(Usuario.negocio_id, negocio_id),
        Usuario.rol == "COBRADOR",
        Usuario.activo == 1,
    ).first()
    if not cobrador:
        raise HTTPException(status_code=400, detail="Cobrador no encontrado en este negocio o no activo")

    cobrador_id_val = cobrador.id
    if not isinstance(cobrador_id_val, UUID):
        cobrador_id_val = UUID(cobrador_id_val)

    # 3. Validar nuevo nombre de ruta (R2).
    nuevo_nombre = data.nombre
    if not nuevo_nombre or len(nuevo_nombre) < 1 or len(nuevo_nombre) > 100:
        raise HTTPException(status_code=400, detail="nombre debe tener entre 1 y 100 caracteres")

    # 3a. Nombre no ocupado por otra ruta activa de otro cobrador.
    ruta_ocupada = db.query(Ruta).filter(
        _uuid_eq(Ruta.negocio_id, negocio_id),
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
    #    Constraint único: cobrador_id + activa == 1 → máx. una activa por cobrador.
    r2 = db.query(Ruta).filter(
        _uuid_eq(Ruta.cobrador_id, cobrador_id_val),
        _uuid_eq(Ruta.negocio_id, negocio_id),
        Ruta.activa == 1,
    ).first()
    if r2:
        r2.nombre = nuevo_nombre
        r2.version = (r2.version or 1) + 1
    else:
        r2 = Ruta(
            negocio_id=negocio_id,
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

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Conflicto al reasignar la ruta: el cobrador ya tiene una ruta activa",
        )

    _registrar_audit(
        db,
        negocio_id,
        actor_id,
        "RUTA_REASIGNADA",
        r2.id,
        {
            "ruta_anterior_id": str(ruta_actual.id),
            "ruta_anterior_nombre": ruta_actual.nombre,
            "ruta_nueva_id": str(r2.id),
            "ruta_nueva_nombre": r2.nombre,
            "cobrador_id": str(cobrador_id_val),
            "version_asignacion": nueva_version,
        },
    )

    return {
        "ruta_anterior_id": ruta_actual.id,
        "ruta_anterior_nombre": ruta_actual.nombre,
        "ruta_nueva_id": r2.id,
        "ruta_nueva_nombre": r2.nombre,
        "cobrador_id": cobrador_id_val,
        "cobrador_nombre": cobrador.nombre,
        "version_asignacion": nueva_version,
    }


def _registrar_audit(
    db: Session,
    negocio_id: UUID,
    actor_id: UUID | None,
    action: str,
    entity_id: UUID,
    metadata_col: dict,
) -> None:
    if actor_id is None:
        # Dev/test sin identidad de actor (query-param auth): no hay a quién
        # atribuir. En producción el JWT siempre trae sub (columna NOT NULL).
        return
    db.add(AuditLog(
        negocio_id=negocio_id,
        actor_id=actor_id,
        action=action,
        entity_type="RUTA",
        entity_id=entity_id,
        metadata_col=metadata_col,
    ))
    db.flush()
