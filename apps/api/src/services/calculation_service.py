"""Servicios de cálculo financiero probados contra el documento maestro."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CalculoCredito:
    """Resultados del cálculo de un crédito."""
    total: int
    saldo: int
    cuotas_pagadas: int
    pico: int
    mora_legacy: int = 0


def calcular_credito(cuota: int, n_cuotas: int, abo: int) -> CalculoCredito:
    """
    Cálculo probado contra el documento maestro (Parte 4.1).

    total  = cuota × n
    saldo  = total − abo
    #_C    = abo ÷ cuota            (división entera)
    pico   = abo mód cuota

    Ejemplo del documento (fixtures):
        cuota=30, n=40, abo=260
        → total=1200, saldo=940, #_C=8, pico=20
    """
    total = cuota * n_cuotas
    saldo = total - abo
    cuotas_pagadas = abo // cuota
    pico = abo % cuota
    return CalculoCredito(
        total=total,
        saldo=saldo,
        cuotas_pagadas=cuotas_pagadas,
        pico=pico,
    )


def calcular_mora_legacy(fecha_reporte, inicia, cuotas_pagadas: int = 0) -> int:
    """
    Mora legacy: (fecha_reporte - 1 día - inicia).days - cuotas_pagadas.

    La ancla es la fecha del reporte menos un día, no el campo Ultimo.
    Cuenta días calendario corridos, sin excluir domingos ni festivos.
    Descuenta cuotas_pagadas como se define en el documento (Parte 4.1).
    """
    from datetime import timedelta
    ancla = fecha_reporte - timedelta(days=1)
    dias_corridos = (ancla - inicia).days
    mora = dias_corridos - cuotas_pagadas
    return max(mora, 0)


def calcular_caja(
    opening_base: int,
    opening_carry: int,
    recaudo_real: int,
    desembolsos: list[int],
    vales: list[int],
    gastos: list[int],
    ahorro: list[int],
    entregas: list[int] | None = None,
    recibidos: list[int] | None = None,
) -> dict:
    """
    Cadena de caja probada (Parte 4.3).

    Caso R4: 275 + 805 - 400 - 20 - 18 - 50 = 592

    La fórmula completa del documento incluye transferencias de salida
    (entregas) y transferencias de entrada (recibidos):
      base + carry + recaudo + recibidos - desembolsos - vales - gastos - ahorro - entregas
    """
    entregas = entregas or []
    recibidos = recibidos or []
    total_entradas = opening_base + opening_carry + recaudo_real + sum(recibidos)
    total_salidas = (
        sum(desembolsos) + sum(vales) + sum(gastos) + sum(ahorro) + sum(entregas)
    )
    esperado = total_entradas - total_salidas
    return {
        "opening_base": opening_base,
        "opening_carry": opening_carry,
        "recaudo_real": recaudo_real,
        "entregas": sum(entregas),
        "recibidos": sum(recibidos),
        "total_entradas": total_entradas,
        "total_salidas": total_salidas,
        "esperado": esperado,
    }


def calcular_renovacion(
    saldo_anterior: int,
    pago_efectivo: int,
    monto_nuevo: int,
    recargo_pct: int = 20,
) -> dict:
    """
    Renovación probada (Parte 4.4 + fixtures).

    saldo_anterior = pago_efectivo + saldo_refinanciado
    monto_final_con_recargo = monto_nuevo + (monto_nuevo * recargo_pct // 100)
    dinero_nuevo_entregado = monto_nuevo - saldo_refinanciado

    Fixture:
        saldo_anterior=2740, pago_efectivo=0
        saldo_refinanciado=2740, monto_nuevo=3000
        dinero_nuevo_entregado=260
    """
    saldo_refinanciado = saldo_anterior - pago_efectivo
    dinero_nuevo_entregado = monto_nuevo - saldo_refinanciado
    monto_final_con_recargo = monto_nuevo + (monto_nuevo * recargo_pct // 100)
    return {
        "saldo_anterior": saldo_anterior,
        "pago_efectivo": pago_efectivo,
        "saldo_refinanciado": saldo_refinanciado,
        "monto_nuevo": monto_nuevo,
        "monto_final_con_recargo": monto_final_con_recargo,
        "dinero_nuevo_entregado": dinero_nuevo_entregado,
    }
