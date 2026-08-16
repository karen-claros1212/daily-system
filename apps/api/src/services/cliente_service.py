"""Cliente service — business logic del panel Cliente 360 (W2).

Autoridad de saldo/mora delegada a hoja_viva_service.resumen_creditos (misma
fuente que la hoja viva): el panel NO duplica calculo financiero.

Contrato:
  - listar_clientes: búsqueda/filtros/paginación; COBRADOR scoped a su ruta
    via Credito (aislamiento derivado, sin ruta_id en Cliente).
  - obtener_cliente_360: detalle con creditos + saldo/mora + pagos recientes.
  - crear/editar: SOLO clientes:gestionar (ADMINISTRADOR); identidad
    (tipo_documento/documento_normalizado/identity_status) no se edita por
    panel; documento duplicado del negocio -> POSSIBLE_DUPLICATE.
  - Auditoría append-only: CLIENTE_CREADO / CLIENTE_EDITADO.
"""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from src.models import AuditLog, Cliente, Credito, Pago, Ruta, Usuario
from src.schemas import ClienteUpdate
from src.services.hoja_viva_service import resumen_creditos


def _uuid_eq(column, val):
    if isinstance(val, str):
        return column == UUID(val)
    return column == val


def _like_term(s: str) -> str:
    """Escapa caracteres comodín de LIKE: el termino es un literal del usuario."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _base_query(db: Session, negocio_id: UUID, role: str, route_id: UUID | None):
    q = db.query(Cliente).filter(_uuid_eq(Cliente.negocio_id, negocio_id))
    if role == "COBRADOR":
        q = q.join(
            Credito,
            _uuid_eq(Credito.cliente_id, Cliente.id),
        ).filter(
            _uuid_eq(Credito.ruta_id, route_id),
        ).distinct()
    return q


def listar_clientes(
    db: Session,
    negocio_id: UUID,
    role: str,
    route_id: UUID | None,
    search: str | None = None,
    tipo_documento: str | None = None,
    identity_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Lista paginada de clientes del negocio (scoped a ruta para COBRADOR)."""
    q = _base_query(db, negocio_id, role, route_id)

    if search:
        term = f"%{_like_term(search.strip())}%"
        q = q.filter(
            or_(
                Cliente.primer_apellido.ilike(term, escape="\\"),
                Cliente.segundo_apellido.ilike(term, escape="\\"),
                Cliente.nombres.ilike(term, escape="\\"),
                Cliente.documento_normalizado.ilike(term, escape="\\"),
            )
        )
    if tipo_documento:
        q = q.filter(Cliente.tipo_documento == tipo_documento)
    if identity_status:
        q = q.filter(Cliente.identity_status == identity_status)

    total = q.count()

    clientes = (
        q.order_by(Cliente.creado_el.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    # Conteo batch de creditos activos por cliente (sin N+1).
    credito_ids = [c.id for c in clientes]
    counts = {}
    if credito_ids:
        rows = (
            db.query(Credito.cliente_id, func.count(Credito.id))
            .filter(
                Credito.cliente_id.in_(credito_ids),
                Credito.estado == "ACTIVO",
            )
            .group_by(Credito.cliente_id)
            .all()
        )
        counts = {cliente_id: n for cliente_id, n in rows}

    items = []
    for c in clientes:
        items.append({
            "id": c.id,
            "tipo_documento": c.tipo_documento,
            "documento_normalizado": c.documento_normalizado,
            "identity_status": c.identity_status,
            "primer_apellido": c.primer_apellido,
            "segundo_apellido": c.segundo_apellido,
            "nombres": c.nombres,
            "telefono_1": c.telefono_1,
            "ciudad": c.ciudad,
            "creditos_activos": counts.get(c.id, 0),
            "creado_el": c.creado_el,
        })

    return {"items": items, "total": total, "limit": limit, "offset": offset}


def obtener_cliente_360(
    db: Session,
    negocio_id: UUID,
    cliente_id: UUID,
    role: str,
    route_id: UUID | None,
    limite_pagos: int = 10,
) -> dict:
    """Cliente 360: datos + creditos (saldo/mora) + pagos recientes + saldo_total.

    COBRADOR: 404 si el cliente no tiene credito en su ruta (no revela
    existencia de clientes de otras rutas).
    """
    q = db.query(Cliente).filter(
        _uuid_eq(Cliente.id, cliente_id),
        _uuid_eq(Cliente.negocio_id, negocio_id),
    )
    if role == "COBRADOR":
        q = q.join(
            Credito,
            _uuid_eq(Credito.cliente_id, Cliente.id),
        ).filter(
            _uuid_eq(Credito.ruta_id, route_id),
        )
    cliente = q.first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    creditos = db.query(Credito).filter(
        _uuid_eq(Credito.cliente_id, cliente.id)
    ).all()
    if role == "COBRADOR":
        creditos = [c for c in creditos if _uuid_eq(c.ruta_id, route_id)]

    resumen = resumen_creditos(db, creditos)

    # Batch rutas + cobradores (sin N+1).
    ruta_ids = {c.ruta_id for c in creditos}
    rutas = db.query(Ruta).filter(Ruta.id.in_(ruta_ids)).all() if ruta_ids else []
    ruta_map = {r.id: r for r in rutas}
    cobrador_ids = {r.cobrador_id for r in rutas if r.cobrador_id}
    cobradores = (
        db.query(Usuario).filter(Usuario.id.in_(cobrador_ids)).all()
        if cobrador_ids else []
    )
    cobrador_map = {u.id: u for u in cobradores}

    credito_list = []
    for c in creditos:
        fin = resumen.get(c.id, {
            "saldo": c.total,
            "mora_legacy": 0,
            "pico": 0,
            "cuotas_pagadas": 0,
        })
        ruta = ruta_map.get(c.ruta_id)
        cobrador = cobrador_map.get(ruta.cobrador_id) if ruta else None
        credito_list.append({
            "id": c.id,
            "estado": c.estado,
            "cuota": c.cuota,
            "n_cuotas": c.n_cuotas,
            "monto": c.monto,
            "total": c.total,
            "periodicidad": c.periodicidad,
            "fecha_inicio": c.fecha_inicio,
            "saldo": fin["saldo"],
            "mora_legacy": fin["mora_legacy"],
            "pico": fin["pico"],
            "cuotas_pagadas": fin["cuotas_pagadas"],
            "ruta_id": c.ruta_id,
            "ruta_nombre": ruta.nombre if ruta else "Sin ruta",
            "cobrador_nombre": cobrador.nombre if cobrador else None,
        })

    saldo_total = sum(
        fin["saldo"] for c, fin in (
            (c, resumen.get(c.id, {"saldo": c.total})) for c in creditos
        ) if c.estado == "ACTIVO"
    )

    credito_ids = [c.id for c in creditos]
    pagos = []
    if credito_ids:
        pagos = (
            db.query(Pago)
            .filter(Pago.credito_id.in_(credito_ids))
            .order_by(Pago.recibido_el_servidor.desc())
            .limit(limite_pagos)
            .all()
        )

    return {
        "id": cliente.id,
        "negocio_id": cliente.negocio_id,
        "tipo_documento": cliente.tipo_documento,
        "documento_normalizado": cliente.documento_normalizado,
        "identity_status": cliente.identity_status,
        "primer_apellido": cliente.primer_apellido,
        "segundo_apellido": cliente.segundo_apellido,
        "nombres": cliente.nombres,
        "telefono_1": cliente.telefono_1,
        "telefono_2": cliente.telefono_2,
        "direccion": cliente.direccion,
        "barrio": cliente.barrio,
        "ciudad": cliente.ciudad,
        "ocupacion": cliente.ocupacion,
        "creado_el": cliente.creado_el,
        "creditos": credito_list,
        "pagos_recientes": [
            {
                "id": p.id,
                "credito_id": p.credito_id,
                "tipo": p.tipo,
                "monto": p.monto,
                "nota": p.nota,
                "recibido_el_servidor": p.recibido_el_servidor,
            }
            for p in pagos
        ],
        "saldo_total": saldo_total,
    }


def _registrar_audit(
    db: Session,
    negocio_id: UUID,
    actor_id: UUID,
    action: str,
    entity_id: UUID,
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
        action=action,
        entity_type="CLIENTE",
        entity_id=entity_id,
        metadata_col=metadata_col,
    ))
    db.flush()


def crear_cliente(
    db: Session,
    negocio_id: UUID,
    actor_id: UUID,
    data,
) -> Cliente:
    """Crear cliente (PROVISIONAL). Duplicado de documento -> POSSIBLE_DUPLICATE."""
    doc = data.documento_normalizado
    identity_status = "PROVISIONAL"
    if doc:
        existente = db.query(Cliente).filter(
            _uuid_eq(Cliente.negocio_id, negocio_id),
            Cliente.documento_normalizado == doc,
        ).first()
        if existente:
            identity_status = "POSSIBLE_DUPLICATE"

    cliente = Cliente(
        negocio_id=negocio_id,
        primer_apellido=data.primer_apellido,
        segundo_apellido=data.segundo_apellido,
        nombres=data.nombres,
        tipo_documento=data.tipo_documento,
        documento_normalizado=doc,
        telefono_1=data.telefono_1,
        telefono_2=data.telefono_2,
        direccion=data.direccion,
        barrio=data.barrio,
        ciudad=data.ciudad,
        ocupacion=data.ocupacion,
        identity_status=identity_status,
    )
    db.add(cliente)
    db.flush()

    _registrar_audit(
        db,
        negocio_id,
        actor_id,
        "CLIENTE_CREADO",
        cliente.id,
        {"identity_status": identity_status},
    )
    db.refresh(cliente)
    return cliente


def editar_cliente(
    db: Session,
    negocio_id: UUID,
    cliente: Cliente,
    actor_id: UUID,
    data: ClienteUpdate,
) -> Cliente:
    """Editar campos editables del panel. Sin cambios -> no-op sin audit."""
    cambios = {}

    if data.primer_apellido is not None:
        if not data.primer_apellido:
            raise HTTPException(status_code=400, detail="primer_apellido no puede ser solo espacios")
        cliente.primer_apellido = data.primer_apellido
        cambios["primer_apellido"] = data.primer_apellido
    if data.segundo_apellido is not None:
        cliente.segundo_apellido = data.segundo_apellido or None
        cambios["segundo_apellido"] = cliente.segundo_apellido
    if data.nombres is not None:
        if not data.nombres:
            raise HTTPException(status_code=400, detail="nombres no puede ser solo espacios")
        cliente.nombres = data.nombres
        cambios["nombres"] = data.nombres
    if data.telefono_1 is not None:
        cliente.telefono_1 = data.telefono_1 or None
        cambios["telefono_1"] = cliente.telefono_1
    if data.telefono_2 is not None:
        cliente.telefono_2 = data.telefono_2 or None
        cambios["telefono_2"] = cliente.telefono_2
    if data.direccion is not None:
        cliente.direccion = data.direccion or None
        cambios["direccion"] = cliente.direccion
    if data.barrio is not None:
        cliente.barrio = data.barrio or None
        cambios["barrio"] = cliente.barrio
    if data.ciudad is not None:
        cliente.ciudad = data.ciudad or None
        cambios["ciudad"] = cliente.ciudad
    if data.ocupacion is not None:
        cliente.ocupacion = data.ocupacion or None
        cambios["ocupacion"] = cliente.ocupacion

    if not cambios:
        return cliente

    db.flush()
    _registrar_audit(
        db,
        negocio_id,
        actor_id,
        "CLIENTE_EDITADO",
        cliente.id,
        {"campos": sorted(cambios.keys())},
    )
    db.refresh(cliente)
    return cliente
