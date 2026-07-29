"""Tests for financial calculations."""

import pytest
from src.services.calculation_service import (
    calcular_credito,
    calcular_caja,
    calcular_renovacion,
)


class TestCalcularCredito:
    """Tests for the core credit calculation (Part 4.1 of master doc)."""

    def test_legacy_basic(self):
        """Fixture from master doc: cuota=30, n=40, abo=260."""
        result = calcular_credito(cuota=30, n_cuotas=40, abo=260)

        assert result.total == 1200
        assert result.saldo == 940
        assert result.cuotas_pagadas == 8
        assert result.pico == 20

    def test_zero_abono(self):
        """No abono: saldo = total."""
        result = calcular_credito(cuota=30000, n_cuotas=40, abo=0)

        assert result.total == 1200000
        assert result.saldo == 1200000
        assert result.cuotas_pagadas == 0
        assert result.pico == 0

    def test_full_payment(self):
        """Pago completo: saldo = 0."""
        result = calcular_credito(cuota=30000, n_cuotas=40, abo=1200000)

        assert result.total == 1200000
        assert result.saldo == 0
        assert result.cuotas_pagadas == 40
        assert result.pico == 0

    def test_rounding_cobra_residuo(self):
        """El redondeo cobra el residuo: 50 × 29 = 1450."""
        result = calcular_credito(cuota=50, n_cuotas=29, abo=0)

        assert result.total == 1450
        assert result.saldo == 1450

    def test_asymmetric_ratio(self):
        """Ratio 1.40 (no siempre es 1.20)."""
        # Monto = 100000, ratio 1.40 → total = 140000
        # cuota × n = 140000
        result = calcular_credito(cuota=35000, n_cuotas=4, abo=0)

        assert result.total == 140000
        assert result.saldo == 140000

    def test_partial_abono_multiple(self):
        """Abono parcial que no cubre cuota completa."""
        result = calcular_credito(cuota=30000, n_cuotas=40, abo=15000)

        assert result.total == 1200000
        assert result.saldo == 1185000
        assert result.cuotas_pagadas == 0  # 15000 // 30000 = 0
        assert result.pico == 15000

    def test_large_amounts(self):
        """Montos grandes de COP."""
        result = calcular_credito(cuota=500000, n_cuotas=60, abo=2500000)

        assert result.total == 30000000
        assert result.saldo == 27500000
        assert result.cuotas_pagadas == 5
        assert result.pico == 0

    def test_single_payment(self):
        """Cuota única."""
        result = calcular_credito(cuota=1000000, n_cuotas=1, abo=1000000)

        assert result.total == 1000000
        assert result.saldo == 0
        assert result.cuotas_pagadas == 1
        assert result.pico == 0


class TestCalcularCaja:
    """Tests for cash chain calculation (Part 4.3 of master doc)."""

    def test_r4_case(self):
        """Caso R4: 275 + 805 - 400 - 20 - 18 - 50 = 592."""
        result = calcular_caja(
            opening_base=275,
            opening_carry=805,
            recaudo_real=0,  # no se suma al esperado en este contexto
            desembolsos=[400],
            vales=[0],
            gastos=[20, 18],
            ahorro=[50],
        )

        assert result["esperado"] == 592
        assert result["opening_base"] == 275
        assert result["opening_carry"] == 805

    def test_empty_day(self):
        """Día sin movimientos."""
        result = calcular_caja(
            opening_base=100000,
            opening_carry=0,
            recaudo_real=0,
            desembolsos=[],
            vales=[],
            gastos=[],
            ahorro=[],
        )

        assert result["esperado"] == 100000

    def test_with_collection(self):
        """Día con recaudo."""
        result = calcular_caja(
            opening_base=500000,
            opening_carry=100000,
            recaudo_real=2000000,
            desembolsos=[300000],
            vales=[50000],
            gastos=[25000],
            ahorro=[100000],
        )

        # 500000 + 100000 + 2000000 - 300000 - 50000 - 25000 - 100000 = 2125000
        assert result["esperado"] == 2125000


class TestCalcularRenovacion:
    """Tests for renewal calculation (Part 4.4 + fixtures)."""

    def test_fixture_renovacion(self):
        """Fixture: saldo_anterior=2740, pago_efectivo=0, monto_nuevo=3000."""
        result = calcular_renovacion(
            saldo_anterior=2740,
            pago_efectivo=0,
            monto_nuevo=3000,
            recargo_pct=20,
        )

        assert result["saldo_anterior"] == 2740
        assert result["pago_efectivo"] == 0
        assert result["saldo_refinanciado"] == 2740
        assert result["monto_nuevo"] == 3000
        assert result["dinero_nuevo_entregado"] == 260

    def test_partial_cash_payment(self):
        """Renovación con pago en efectivo parcial."""
        result = calcular_renovacion(
            saldo_anterior=5000,
            pago_efectivo=1000,
            monto_nuevo=6000,
        )

        assert result["saldo_refinanciado"] == 4000
        assert result["dinero_nuevo_entregado"] == 2000

    def test_full_cash_payment(self):
        """Renovación con todo en efectivo."""
        result = calcular_renovacion(
            saldo_anterior=3000,
            pago_efectivo=3000,
            monto_nuevo=3000,
        )

        assert result["saldo_refinanciado"] == 0
        assert result["dinero_nuevo_entregado"] == 3000

    def test_invariant(self):
        """saldo_anterior = pago_efectivo + saldo_refinanciado."""
        result = calcular_renovacion(
            saldo_anterior=10000,
            pago_efectivo=3000,
            monto_nuevo=12000,
        )

        assert result["saldo_anterior"] == result["pago_efectivo"] + result["saldo_refinanciado"]
