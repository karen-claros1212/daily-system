from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from uuid import UUID
from datetime import date, datetime, timezone

from src.database import get_db
from src.models import Credito, Ruta, Pago, CuotaProgramada
from src.schemas import HojaVivaCliente, HojaVivaResponse
from src.auth.deps import get_request_context
from src.auth.context import RequestContext


def _uuid_eq(column, val: str | UUID):
    if isinstance(val, str):
        return column == UUID(val)
    return column == val


router = APIRouter(tags=["hoja-viva"])


@router.get(
    "/api/rutas/{ruta_id}/hoja-viva",
    response_model=HojaVivaResponse,
)
def obtener_hoja_viva(
    ruta_id: UUID,
    fecha: date | None = None,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    ruta = db.query(Ruta).filter(_uuid_eq(Ruta.id, ruta_id)).first()
    if not ruta:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")

    if not ctx.has_negocio(ruta.negocio_id):
        raise HTTPException(status_code=403, detail="Ruta no pertenece a tu negocio")

    if ctx.is_cobrador() and not ctx.has_route(ruta_id):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta ruta")

    report_date = fecha or date.today()

    creditos = (
        db.query(Credito)
        .filter(
            _uuid_eq(Credito.ruta_id, ruta_id),
            Credito.estado == "ACTIVO",
        )
        .all()
    )

    # DC_LEGACY = Σ cuota de todos los créditos activos (el valor de la cuota diaria)
    dc_legacy = sum(c.cuota for c in creditos if c.periodicidad == "DIARIO")

    # VENCE_HOY = count of cuotas_programadas cuyo vencimiento cae hoy
    credito_ids = [c.id for c in creditos]
    vence_hoy = 0
    if credito_ids:
        vence_hoy = (
            db.query(func.count(CuotaProgramada.id))
            .filter(
                CuotaProgramada.credito_id.in_(credito_ids),
                CuotaProgramada.fecha_vencimiento == report_date,
                CuotaProgramada.estado == "PENDIENTE",
            )
            .scalar() or 0
        )

    clientes = []
    for credito in creditos:
        total_pagado = (
            db.query(func.sum(Pago.monto))
            .filter(
                _uuid_eq(Pago.credito_id, credito.id),
                Pago.tipo == "PAYMENT",
            )
            .scalar() or 0
        )

        saldo = credito.total - total_pagado
        cuotas_pagadas = total_pagado // credito.cuota if credito.cuota > 0 else 0
        pico = total_pagado % credito.cuota if credito.cuota > 0 else 0

        # mora_legacy = (fecha_reporte - 1 día - fecha_inicio).days - cuotas_pagadas
        if credito.fecha_inicio:
            mora_legacy = (report_date - credito.fecha_inicio).days - 1 - cuotas_pagadas
            if mora_legacy < 0:
                mora_legacy = 0
        else:
            mora_legacy = 0

        # Semáforo basado en atraso real, no en version del crédito
        semaforo = "GRIS"
        if credito.version >= 1:
            if saldo <= 0:
                semaforo = "VERDE"
            elif mora_legacy > 30:
                semaforo = "ROJO"
            elif mora_legacy > 7:
                semaforo = "AMARILLO"
            else:
                semaforo = "VERDE"

        clientes.append(HojaVivaCliente(
            credito_id=credito.id,
            cliente_nombre=_cliente_nombre(credito),
            cuota=credito.cuota,
            saldo=saldo,
            mora_legacy=mora_legacy,
            pico=pico,
            cuotas_pagadas=cuotas_pagadas,
            estado_credito=credito.estado,
            semaforo=semaforo,
        ))

    return HojaVivaResponse(
        ruta_id=ruta_id,
        ruta_nombre=ruta.nombre,
        fecha=report_date,
        clientes=clientes,
        vence_hoy=vence_hoy,
        dc_legacy=dc_legacy,
        efectivo_esperado=0,
    )


def _cliente_nombre(credito):
    if credito.cliente:
        return f"{credito.cliente.primer_apellido} {credito.cliente.nombres}".strip()
    return "Sin nombre"
