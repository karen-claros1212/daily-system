"""Renewal service — full renewal transaction."""

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from src.models import Credito, Renovacion, Pago
from src.services.calculation_service import calcular_renovacion
from src.services.schedule_service import generate_schedule


def renew_credito(
    db: Session,
    credito_id: UUID,
    pago_efectivo: int,
    nueva_cuota: int,
    nuevas_n_cuotas: int,
    nuevo_monto: int,
    nueva_periodicidad: str = "DIARIO",
    fecha_inicio: date | None = None,
    recargo_pct: int = 20,
) -> dict:
    old = db.query(Credito).filter(Credito.id == credito_id).first()
    if not old:
        raise ValueError("Crédito no encontrado")

    # Net saldo from payments
    pagos = (
        db.query(Pago)
        .filter(Pago.credito_id == credito_id)
        .all()
    )
    total_pagado = sum(
        p.monto for p in pagos if p.tipo == "PAYMENT"
    ) - sum(
        p.monto for p in pagos if p.tipo == "REVERSAL"
    )
    saldo_anterior = old.total - total_pagado

    calc = calcular_renovacion(
        saldo_anterior=saldo_anterior,
        pago_efectivo=pago_efectivo,
        monto_nuevo=nuevo_monto,
        recargo_pct=recargo_pct,
    )

    nuevo_total = nueva_cuota * nuevas_n_cuotas

    # Create new credito
    new = Credito(
        id=uuid4(),
        negocio_id=old.negocio_id,
        cliente_id=old.cliente_id,
        ruta_id=old.ruta_id,
        origination_type="RENEWAL",
        cuota=nueva_cuota,
        n_cuotas=nuevas_n_cuotas,
        monto=nuevo_monto,
        total=nuevo_total,
        periodicidad=nueva_periodicidad,
        fecha_inicio=fecha_inicio or date.today(),
        estado="ACTIVO",
        credito_anterior_id=old.id,
    )
    db.add(new)
    db.flush()

    # Mark old as RENOVADO
    old.estado = "REFINANCIADO"

    # Register renewal event
    ren = Renovacion(
        id=uuid4(),
        negocio_id=old.negocio_id,
        credito_viejo_id=old.id,
        credito_nuevo_id=new.id,
        saldo_anterior=calc["saldo_anterior"],
        pago_efectivo=calc["pago_efectivo"],
        saldo_refinanciado=calc["saldo_refinanciado"],
        monto_nuevo=calc["monto_nuevo"],
        dinero_nuevo_entregado=calc["dinero_nuevo_entregado"],
    )
    db.add(ren)

    # Generate schedule for new credito
    cuotas = generate_schedule(db, new)

    db.flush()
    return {
        "credito_viejo_id": old.id,
        "credito_nuevo_id": new.id,
        "renovacion": calc,
        "cuotas_generadas": len(cuotas),
        "total_contractual": nuevo_total,
    }
