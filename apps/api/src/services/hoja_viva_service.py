"""Hoja viva service — business logic separated from HTTP concerns."""

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models import Credito, CuotaProgramada, Pago

BOGOTA_TZ = timezone(timedelta(hours=-5))


def today_bogota() -> date:
    return datetime.now(BOGOTA_TZ).date()


def _uuid_eq(column, val):
    if isinstance(val, str):
        return column == UUID(val)
    return column == val


def resumen_creditos(
    db: Session,
    creditos: list[Credito],
    report_date: date | None = None,
) -> dict:
    """Resumen financiero por credito: saldo, cuotas_pagadas, pico, mora_legacy.

    Autoridad UNICA del calculo de saldo y mora_legacy: reutilizada por
    build_hoja_viva y por el detalle Cliente 360 del panel. Batch de pagos
    (SUM(PAYMENT) - SUM(REVERSAL)), sin N+1.
    """
    report_date = report_date or today_bogota()

    credito_ids = [c.id for c in creditos]

    # Batch: abono_neto = SUM(PAYMENT) - SUM(REVERSAL)
    pagos_agg = {}
    if credito_ids:
        rows = (
            db.query(
                Pago.credito_id,
                Pago.tipo,
                func.sum(Pago.monto).label("total"),
            )
            .filter(
                Pago.credito_id.in_(credito_ids),
                Pago.tipo.in_(["PAYMENT", "REVERSAL"]),
            )
            .group_by(Pago.credito_id, Pago.tipo)
            .all()
        )
        for credito_id, tipo, total in rows:
            if credito_id not in pagos_agg:
                pagos_agg[credito_id] = {"PAYMENT": 0, "REVERSAL": 0}
            pagos_agg[credito_id][tipo] = total

    resumen = {}
    for credito in creditos:
        cid = credito.id
        agg = pagos_agg.get(cid, {"PAYMENT": 0, "REVERSAL": 0})
        abono_neto = (agg["PAYMENT"] or 0) - (agg["REVERSAL"] or 0)

        saldo = credito.total - abono_neto
        cuotas_pagadas = abono_neto // credito.cuota if credito.cuota > 0 else 0
        pico = abono_neto % credito.cuota if credito.cuota > 0 else 0

        # mora_legacy
        if credito.fecha_inicio:
            mora_legacy = (report_date - credito.fecha_inicio).days - 1 - cuotas_pagadas
            mora_legacy = max(mora_legacy, 0)
        else:
            mora_legacy = 0

        resumen[cid] = {
            "abono_neto": abono_neto,
            "saldo": saldo,
            "cuotas_pagadas": cuotas_pagadas,
            "pico": pico,
            "mora_legacy": mora_legacy,
        }

    return resumen


def build_hoja_viva(
    db: Session,
    ruta_id: UUID,
    report_date: date | None = None,
) -> dict:
    report_date = report_date or today_bogota()

    creditos = (
        db.query(Credito)
        .filter(
            _uuid_eq(Credito.ruta_id, ruta_id),
            Credito.estado == "ACTIVO",
        )
        .all()
    )

    credito_ids = [c.id for c in creditos]

    resumen = resumen_creditos(db, creditos, report_date)

    # DC_LEGACY = Σ cuota de todos los créditos activos (sin filtrar periodicidad)
    dc_legacy = sum(c.cuota for c in creditos)

    # VENCE_HOY desde cuota_programada
    vence_hoy_monto = 0
    cuotas_que_vencen_hoy = 0
    if credito_ids:
        cuotas_hoy = (
            db.query(
                func.count(CuotaProgramada.id),
                func.sum(CuotaProgramada.monto),
            )
            .filter(
                CuotaProgramada.credito_id.in_(credito_ids),
                CuotaProgramada.fecha_vencimiento == report_date,
                CuotaProgramada.estado == "PENDIENTE",
            )
            .first()
        )
        if cuotas_hoy:
            cuotas_que_vencen_hoy = cuotas_hoy[0] or 0
            vence_hoy_monto = cuotas_hoy[1] or 0

    # Build per-credito rows
    clientes = []
    for credito in creditos:
        cid = credito.id
        fin = resumen[cid]
        abono_neto = fin["abono_neto"]
        saldo = fin["saldo"]
        cuotas_pagadas = fin["cuotas_pagadas"]
        pico = fin["pico"]
        mora_legacy = fin["mora_legacy"]

        # Semáforo: siempre GRIS hasta score_snapshot real
        semaforo = "GRIS"

        cliente_nombre = "Sin nombre"
        if credito.cliente:
            cliente_nombre = f"{credito.cliente.primer_apellido} {credito.cliente.nombres}".strip()

        clientes.append({
            "credito_id": credito.id,
            "cliente_nombre": cliente_nombre,
            "cuota": credito.cuota,
            "saldo": saldo,
            "mora_legacy": mora_legacy,
            "pico": pico,
            "cuotas_pagadas": cuotas_pagadas,
            "estado_credito": credito.estado,
            "semaforo": semaforo,
        })

    return {
        "clientes": clientes,
        "dc_legacy": dc_legacy,
        "vence_hoy_monto": vence_hoy_monto,
        "cuotas_que_vencen_hoy": cuotas_que_vencen_hoy,
    }
