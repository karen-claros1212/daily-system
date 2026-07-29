"""Caja service — calcular caja via flujos físicos.

Cadena de caja:
  opening_base + opening_carry + recaudo_real
    - desembolsos - vales - gastos - ahorro
  = efectivo_esperado

Caso R4 (6 julio): 275 + 805 - 400 - 20 - 18 - 50 = 592
"""

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models import MovimientoCaja, Pago, Renovacion


def calcular_cadena_caja(
    db: Session,
    jornada_id: UUID,
) -> dict:
    """Calculate caja via physical flows for a jornada.

    Returns dict with:
      opening_base, opening_carry
      recaudo_real (SUM of PAYMENT montos for this jornada)
      desembolsos (SUM of DESEMBOLSO movimientos)
      vales (SUM of VALE movimientos)
      gastos (SUM of GASOLINA + OFICINA movimientos)
      ahorro (SUM of AHORRO movimientos)
      entregas (SUM of ENTREGA movimientos)
      otros_entrada (SUM of RECIBIDO movimientos)
      efectivo_esperado
      movimientos_count
      pagos_count
      renovaciones_count
    """
    from src.models import Jornada as JornadaModel
    from src.services.jornada_service import _uuid_eq

    jornada_data = (
        db.query(JornadaModel)
        .filter(_uuid_eq(JornadaModel.id, jornada_id))
        .first()
    )
    if not jornada_data:
        return {
            "opening_base": 0,
            "opening_carry": 0,
            "recaudo_real": 0,
            "desembolsos": 0,
            "vales": 0,
            "gastos": 0,
            "ahorro": 0,
            "entregas": 0,
            "otros_entrada": 0,
            "efectivo_esperado": 0,
            "movimientos_count": 0,
            "pagos_count": 0,
            "renovaciones_count": 0,
        }

    opening_base = jornada_data.opening_base
    opening_carry = jornada_data.opening_carry

    # SUM of PAYMENT montos for this jornada
    pagos_agg = (
        db.query(
            func.sum(Pago.monto).label("total"),
            func.count(Pago.id).label("count"),
        )
        .filter(
            Pago.jornada_id == jornada_id,
            Pago.tipo == "PAYMENT",
        )
        .first()
    )
    recaudo_real = pagos_agg[0] or 0 if pagos_agg else 0
    pagos_count = pagos_agg[1] or 0 if pagos_agg else 0

    # SUM of movements by type
    movimientos = (
        db.query(
            MovimientoCaja.tipo,
            func.sum(MovimientoCaja.monto).label("total"),
        )
        .filter(MovimientoCaja.jornada_id == jornada_id)
        .group_by(MovimientoCaja.tipo)
        .all()
    )

    desembolsos = 0
    vales = 0
    gastos = 0
    ahorro = 0
    entregas = 0
    otros_entrada = 0

    for tipo, total in movimientos:
        if tipo == "DESEMBOLSO":
            desembolsos = total or 0
        elif tipo == "VALE":
            vales = total or 0
        elif tipo == "GASOLINA" or tipo == "OFICINA":
            gastos = (gastos or 0) + (total or 0)
        elif tipo == "AHORRO":
            ahorro = total or 0
        elif tipo == "ENTREGA":
            entregas = total or 0
        elif tipo == "RECIBIDO":
            otros_entrada = total or 0

    movimientos_count = (
        db.query(func.count(MovimientoCaja.id))
        .filter(MovimientoCaja.jornada_id == jornada_id)
        .scalar()
    ) or 0

    # Renovaciones: suma de dinero_nuevo_entregado
    renovaciones_total = (
        db.query(func.count(Renovacion.id))
        .join(
            MovimientoCaja,
            MovimientoCaja.renovacion_id == Renovacion.id,
        )
        .filter(MovimientoCaja.jornada_id == jornada_id)
        .scalar()
    ) or 0

    # efectivo_esperado = base + carry + recaudo - desembolsos - vales - gastos - ahorro
    efectivo_esperado = (
        opening_base
        + opening_carry
        + recaudo_real
        + otros_entrada
        - desembolsos
        - vales
        - gastos
        - ahorro
    )

    return {
        "opening_base": opening_base,
        "opening_carry": opening_carry,
        "recaudo_real": recaudo_real,
        "desembolsos": desembolsos,
        "vales": vales,
        "gastos": gastos,
        "ahorro": ahorro,
        "entregas": entregas,
        "otros_entrada": otros_entrada,
        "efectivo_esperado": efectivo_esperado,
        "movimientos_count": movimientos_count,
        "pagos_count": pagos_count,
        "renovaciones_count": renovaciones_total,
    }


def calcular_caja_fixture(
    opening_base: int,
    opening_carry: int,
    recaudo_real: int,
    desembolsos: int,
    vales: int,
    gastos: int,
    ahorro: int,
) -> dict:
    """Calculate caja from explicit values (for testing).

    Caso R4: 275 + 805 - 400 - 20 - 18 - 50 = 592
    """
    efectivo_esperado = (
        opening_base
        + opening_carry
        + recaudo_real
        - desembolsos
        - vales
        - gastos
        - ahorro
    )
    return {
        "opening_base": opening_base,
        "opening_carry": opening_carry,
        "recaudo_real": recaudo_real,
        "desembolsos": desembolsos,
        "vales": vales,
        "gastos": gastos,
        "ahorro": ahorro,
        "efectivo_esperado": efectivo_esperado,
    }
