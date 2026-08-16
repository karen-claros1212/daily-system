"""Credito service — W3 read model de cartera y mutaciones.

Read model: reutiliza `hoja_viva_service.resumen_creditos`, la autoridad
UNICA de saldo/mora/pico/cuotas_pagadas compartida con Cliente360 y la hoja
viva. Prohibido duplicar formulas financieras aqui o en el frontend.

Reglas W3:
  - ADMINISTRADOR: tenant-wide (creditos:ver + creditos:gestionar).
  - COBRADOR: solo su ruta activa; detalle/lista fuera de scope -> 404
    (no revelar existencia).
  - INVERSIONISTA: read-only, PII minimizada (cliente_nombre/cliente_id en
    None), nunca Cliente360; solo agregados vía resumen.
"""

from datetime import date
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from src.models import AuditLog, Cliente, Credito, Ruta
from src.services.hoja_viva_service import resumen_creditos
from src.services.schedule_service import generate_schedule

ROLES_CON_PII_CLIENTE = ("ADMINISTRADOR", "COBRADOR")

SORT_ALLOWLIST = {
    "fecha_inicio",
    "monto",
    "total",
    "cuota",
    "periodicidad",
    "estado",
    "saldo",
}

PERIODICIDAD_LABEL = {"DIARIO": "Diaria", "SEMANAL": "Semanal", "QUINCENAL": "Quincenal", "UNICA": "Única"}
ESTADO_LABEL = {"ACTIVO": "Activo", "PAGADO": "Pagado", "REFINANCIADO": "Refinanciado", "CANCELADO": "Cancelado"}


def _nombre_cliente(cliente: Cliente | None) -> str | None:
    if not cliente:
        return None
    nombre = " ".join(
        x for x in (cliente.nombres, cliente.primer_apellido, cliente.segundo_apellido) if x
    ).strip()
    return nombre or None


def _escope_base(db: Session, negocio_id: UUID, role: str, route_id: UUID | None):
    q = db.query(Credito).filter(Credito.negocio_id == negocio_id)
    q = q.options(
        joinedload(Credito.cliente),
        joinedload(Credito.ruta).joinedload(Ruta.cobrador),
    )
    if role == "COBRADOR":
        q = q.filter(Credito.ruta_id == route_id)
    return q


def _validar_scope_ruta(role: str, route_id: UUID | None, credito: Credito) -> None:
    """COBRADOR: fuera de su ruta -> 404 (no revelar existencia)."""
    if role == "COBRADOR" and credito.ruta_id != route_id:
        raise HTTPException(status_code=404, detail="Crédito no encontrado")


def _enriquecer(db: Session, creditos: list[Credito], role: str) -> list[dict]:
    """Construye las filas del read model con financiero (resumen batch)."""
    resumen = resumen_creditos(db, creditos)
    mostrar_pii = role in ROLES_CON_PII_CLIENTE
    filas = []
    for c in creditos:
        fin = resumen[c.id]
        filas.append({
            "id": c.id,
            "cliente_id": c.cliente_id if mostrar_pii else None,
            "cliente_nombre": _nombre_cliente(c.cliente) if mostrar_pii else None,
            "ruta_id": c.ruta_id,
            "ruta_nombre": c.ruta.nombre if c.ruta else "",
            "cobrador_nombre": c.ruta.cobrador.nombre if (c.ruta and c.ruta.cobrador) else None,
            "estado": c.estado,
            "cuota": c.cuota,
            "n_cuotas": c.n_cuotas,
            "monto": c.monto,
            "total": c.total,
            "periodicidad": c.periodicidad,
            "fecha_inicio": c.fecha_inicio,
            "saldo": fin["saldo"],
            "mora": fin["mora_legacy"],
            "pico": fin["pico"],
            "cuotas_pagadas": fin["cuotas_pagadas"],
            "creado_el": c.creado_el,
        })
    return filas


def listar_creditos(
    db: Session,
    negocio_id: UUID,
    role: str,
    route_id: UUID | None,
    search: str | None = None,
    estado: str | None = None,
    ruta_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
    sort: str = "fecha_inicio",
    order: str = "desc",
) -> dict:
    """Lista paginada del read model. Busqueda q solo aplica con PII de
    cliente (ADMINISTRADOR/COBRADOR); para INVERSIONISTA se ignora."""
    if sort not in SORT_ALLOWLIST:
        raise HTTPException(status_code=422, detail=f"sort no permitido: {sort}")
    if order not in ("asc", "desc"):
        raise HTTPException(status_code=422, detail="order debe ser asc o desc")

    q = _escope_base(db, negocio_id, role, route_id)

    if estado:
        q = q.filter(Credito.estado == estado)

    if ruta_id is not None:
        if role == "COBRADOR":
            if ruta_id != route_id:
                raise HTTPException(status_code=404, detail="Créditos no encontrados")
        else:
            q = q.filter(Credito.ruta_id == ruta_id)

    if search and role in ROLES_CON_PII_CLIENTE:
        q = q.outerjoin(Cliente, Credito.cliente_id == Cliente.id)
        term = f"%{search.strip().lower()}%"
        q = q.filter(or_(
            func.lower(func.coalesce(Cliente.primer_apellido, "")).like(term),
            func.lower(func.coalesce(Cliente.segundo_apellido, "")).like(term),
            func.lower(func.coalesce(Cliente.nombres, "")).like(term),
        ))

    total = q.count()

    creditos = q.all()
    filas = _enriquecer(db, creditos, role)

    rev = order == "desc"
    filas.sort(
        key=lambda r: (r[sort] is None, r[sort]),
        reverse=rev,
    )
    items = filas[offset:offset + limit]

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def obtener_credito_detalle(
    db: Session,
    negocio_id: UUID,
    credito_id: UUID,
    role: str,
    route_id: UUID | None,
) -> dict:
    """Detalle W3: credito + financiero + nombres humanos segun rol.
    COBRADOR fuera de ruta -> 404. INVERSIONISTA PII minimizada."""
    credito = (
        db.query(Credito)
        .options(
            joinedload(Credito.cliente),
            joinedload(Credito.ruta).joinedload(Ruta.cobrador),
        )
        .filter(
            Credito.id == credito_id,
            Credito.negocio_id == negocio_id,
        )
        .first()
    )
    if not credito:
        raise HTTPException(status_code=404, detail="Crédito no encontrado")
    _validar_scope_ruta(role, route_id, credito)

    fila = _enriquecer(db, [credito], role)[0]
    fila["negocio_id"] = negocio_id
    return fila


def resumen_cartera(
    db: Session,
    negocio_id: UUID,
    role: str,
    route_id: UUID | None,
) -> dict:
    """Agregados de cartera scoped por rol (autoridad del resumen superior
    de /creditos). Cartera = creditos ACTIVOS; saldo de resumen_creditos."""
    q = _escope_base(db, negocio_id, role, route_id)
    creditos = q.all()

    resumen = resumen_creditos(db, creditos)
    activos = [c for c in creditos if c.estado == "ACTIVO"]

    return {
        "total_creditos": len(creditos),
        "activos": len(activos),
        "saldo_total_cartera": sum(resumen[c.id]["saldo"] for c in activos),
        "en_mora": sum(1 for c in activos if resumen[c.id]["mora_legacy"] > 0),
    }


def crear_credito(
    db: Session,
    negocio_id: UUID,
    actor_id: UUID | None,
    data,
) -> Credito:
    """Crear credito (SOLO ADMINISTRADOR via creditos:gestionar). Mantiene
    los invariantes contractuales existentes: total = cuota * n_cuotas y
    schedule auto-generado. Auditoria append-only CREDITO_CREADO."""
    total = data.cuota * data.n_cuotas

    credito = Credito(
        negocio_id=negocio_id,
        cliente_id=data.cliente_id,
        ruta_id=data.ruta_id,
        origination_type="NEW",
        cuota=data.cuota,
        n_cuotas=data.n_cuotas,
        monto=data.monto,
        total=total,
        periodicidad=data.periodicidad or "DIARIO",
        fecha_inicio=data.fecha_inicio,
        estado="ACTIVO",
    )
    db.add(credito)
    db.flush()

    generate_schedule(db, credito)

    _registrar_audit(
        db,
        negocio_id,
        actor_id,
        credito.id,
        {
            "cliente_id": str(data.cliente_id),
            "ruta_id": str(data.ruta_id),
            "monto": data.monto,
            "total": total,
            "n_cuotas": data.n_cuotas,
            "periodicidad": credito.periodicidad,
        },
    )

    db.refresh(credito)
    return credito


def _registrar_audit(
    db: Session,
    negocio_id: UUID,
    actor_id: UUID | None,
    credito_id: UUID,
    metadata_col: dict,
) -> None:
    if actor_id is None:
        # Stub de dev/test sin identidad de actor: no hay a quien atribuir.
        # En produccion el JWT siempre trae sub, asi que toda mutacion ADMIN
        # queda auditada (columna NOT NULL).
        return
    db.add(AuditLog(
        negocio_id=negocio_id,
        actor_id=actor_id,
        action="CREDITO_CREADO",
        entity_type="CREDITO",
        entity_id=credito_id,
        metadata_col=metadata_col,
    ))
    db.flush()
