from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, String
from uuid import UUID
from datetime import date

from src.database import get_db
from src.models import Credito, Ruta, Pago
from src.schemas import (
    HojaVivaCliente,
    HojaVivaResponse,
)


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
    db: Session = Depends(get_db),
):
    """
    Hoja viva de una ruta.

    Devuelve todas las filas del cobrador con:
    - cliente nombre
    - cuota
    - saldo (total - abo acumulado)
    - mora_legacy
    - pico
    - cuotas_pagadas
    - estado del crédito
    - semáforo de riesgo

    La hoja viva se calcula sobre los datos más recientes del servidor.
    """
    ruta = db.query(Ruta).filter(_uuid_eq(Ruta.id, ruta_id)).first()
    if not ruta:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")

    # Obtener créditos activos de esta ruta
    creditos = (
        db.query(Credito)
        .filter(
            _uuid_eq(Credito.ruta_id, ruta_id),
            Credito.estado == "ACTIVO",
        )
        .all()
    )

    clientes = []
    for credito in creditos:
        # Calcular abo acumulado desde pagos
        pagos = (
            db.query(func.sum(Pago.monto))
            .filter(
                Pago.credito_id == credito.id,
                Pago.tipo == "PAYMENT",
            )
            .scalar() or 0
        )

        total = credito.cuota * credito.n_cuotas
        saldo = total - pagos
        cuotas_pagadas = pagos // credito.cuota if credito.cuota > 0 else 0
        pico = pagos % credito.cuota if credito.cuota > 0 else 0

        # Semáforo básico basado en atraso
        semaforo = "GRIS"
        if credito.version >= 2:
            semaforo = "VERDE"

        clientes.append(HojaVivaCliente(
            credito_id=credito.id,
            cliente_nombre=f"{credito.cliente.primer_apellido} {credito.cliente.nombres}".strip(),
            cuota=credito.cuota,
            saldo=saldo,
            mora_legacy=0,
            pico=pico,
            cuotas_pagadas=cuotas_pagadas,
            estado_credito=credito.estado,
            semaforo=semaforo,
        ))

    # DC Legacy (PROMEDIO) = suma de todas las cuotas activas
    dc_legacy = sum(c.cuota * c.n_cuotas for c in creditos)

    # Vence hoy: créditos con cuota vencida hoy
    # Simplificado para M0: contamos créditos activos
    vence_hoy = len(creditos)

    return HojaVivaResponse(
        ruta_id=ruta_id,
        ruta_nombre=ruta.nombre,
        fecha=fecha or date.today(),
        clientes=clientes,
        vence_hoy=vence_hoy,
        dc_legacy=dc_legacy,
        efectivo_esperado=0,
    )
