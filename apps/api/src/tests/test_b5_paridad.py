"""BLOQUE 5 — Paridad financiera backend–móvil.

El backend es la autoridad financiera. Este archivo fija el resultado backend
(canónico) para cada caso de la matriz de paridad, usando las funciones puras
del documento maestro y los servicios reales (hoja viva, caja, jornada).

Referencia: DAILY-SYSTEM-BLOQUE5-MATRIZ-PARIDAD.md (casos C-01 .. C-16).
"""

from datetime import date, timedelta
from uuid import uuid4

import pytest

from src.auth.context import RequestContext
from src.models import (
    Credito,
    CuotaProgramada,
    Jornada,
    MovimientoCaja,
    Pago,
)
from src.services.caja_service import calcular_cadena_caja
from src.services.calculation_service import (
    calcular_caja,
    calcular_credito,
    calcular_mora_legacy,
    calcular_renovacion,
)
from src.services.hoja_viva_service import build_hoja_viva
from src.services.jornada_service import (
    cerrar_jornada,
    get_carry_for_date,
    open_jornada,
)
from src.services.payment_service import (
    register_payment,
    reverse_payment,
)

CUOTA = 5000
N = 40
TOTAL = CUOTA * N  # 200_000


def _admin_ctx(negocio_id, user_id=None):
    return RequestContext(
        user_id=user_id or uuid4(),
        negocio_id=negocio_id,
        role="ADMINISTRADOR",
        route_id=None,
        device_id=None,
    )


class TestParidadMatrizCredito:
    """C-01..C-07 — matriz de pagos: total, saldo, cuotas_pagadas, pico."""

    @pytest.mark.parametrize(
        "monto_abono, esperado_total, esperado_saldo, esperado_cuotas, esperado_pico",
        [
            # C-01 pago exacto de una cuota
            (5_000, TOTAL, 195_000, 1, 0),
            # C-02 pago parcial menor que una cuota
            (1_500, TOTAL, 198_500, 0, 1_500),
            # C-03 pago de varias cuotas exactas
            (10_000, TOTAL, 190_000, 2, 0),
            # C-04 pago superior a una cuota con pico
            (12_000, TOTAL, 188_000, 2, 2_000),
            # C-05 pago total del crédito
            (200_000, TOTAL, 0, 40, 0),
            # C-06 reverso parcial (pago 10.000 - reverso 5.000 = 5.000)
            (5_000, TOTAL, 195_000, 1, 0),
            # C-07 reverso total (pago 5.000 - reverso 5.000 = 0)
            (0, TOTAL, 200_000, 0, 0),
        ],
    )
    def test_matriz_credito(
        self,
        monto_abono,
        esperado_total,
        esperado_saldo,
        esperado_cuotas,
        esperado_pico,
    ):
        result = calcular_credito(cuota=CUOTA, n_cuotas=N, abo=monto_abono)

        assert result.total == esperado_total
        assert result.saldo == esperado_saldo
        assert result.cuotas_pagadas == esperado_cuotas
        assert result.pico == esperado_pico


class TestParidadMoraLegacy:
    """C-08/C-09 — mora legacy: (reporte - 1 día - inicio).days - #_C, mínimo 0."""

    def test_mora_15_dias_sin_abono(self):
        """C-08: 15 días corridos sin abono → mora = 15 - 1 - 0 = 14."""
        fecha_reporte = date(2026, 8, 6)
        fecha_inicio = fecha_reporte - timedelta(days=15)

        mora = calcular_mora_legacy(fecha_reporte, fecha_inicio, cuotas_pagadas=0)

        assert mora == 14

    def test_mora_descuenta_cuotas_pagadas(self):
        """Un pago de 2 cuotas descuenta 2 días de mora."""
        fecha_reporte = date(2026, 8, 6)
        fecha_inicio = fecha_reporte - timedelta(days=15)

        mora = calcular_mora_legacy(fecha_reporte, fecha_inicio, cuotas_pagadas=2)

        assert mora == 12

    def test_mora_cero_si_negativa(self):
        """Nunca negativa (se topa en cero)."""
        fecha_reporte = date(2026, 8, 6)
        fecha_inicio = fecha_reporte - timedelta(days=1)

        mora = calcular_mora_legacy(fecha_reporte, fecha_inicio, cuotas_pagadas=0)

        assert mora == 0


class TestParidadHojaVivaIntegracion:
    """C-08, C-14, C-15 — build_hoja_viva real: mora_legacy, semáforo, dc_legacy, vence_hoy."""

    def _crear_credito(self, db_session, negocio_id, ruta_id, cliente_id, **kwargs):
        defaults = dict(
            id=uuid4(),
            negocio_id=negocio_id,
            cliente_id=cliente_id,
            ruta_id=ruta_id,
            origination_type="NEW",
            cuota=CUOTA,
            n_cuotas=N,
            monto=180_000,
            total=TOTAL,
            periodicidad="DIARIO",
            fecha_inicio=kwargs.pop("fecha_inicio", date(2026, 8, 6)),
            estado="ACTIVO",
        )
        defaults.update(kwargs)
        c = Credito(**defaults)
        db_session.add(c)
        db_session.commit()
        db_session.refresh(c)
        return c

    def test_hoja_viva_semforo_gris_y_agregados(
        self, db_session, negocio_id, ruta_id, cliente_id
    ):
        """C-14 (semáforo GRIS) y C-15 (dc_legacy) con 3 créditos ACTIVOS."""
        for cuota, n in [(5000, 40), (3000, 30), (7000, 50)]:
            self._crear_credito(
                db_session,
                negocio_id,
                ruta_id,
                cliente_id,
                cuota=cuota,
                n_cuotas=n,
                total=cuota * n,
            )

        result = build_hoja_viva(db_session, ruta_id, report_date=date(2026, 8, 6))

        assert result["dc_legacy"] == 5000 + 3000 + 7000
        assert result["vence_hoy_monto"] == 0
        assert result["cuotas_que_vencen_hoy"] == 0
        saldos_esperados = {200_000, 90_000, 350_000}
        for cliente in result["clientes"]:
            assert cliente["semaforo"] == "GRIS"
            assert cliente["cuotas_pagadas"] == 0
            assert cliente["pico"] == 0
            assert cliente["saldo"] in saldos_esperados

    def test_mora_legacy_en_hoja_viva(
        self, db_session, negocio_id, ruta_id, cliente_id
    ):
        """C-08: 15 días sin abono → fila con mora_legacy = 14."""
        fecha_reporte = date(2026, 8, 6)
        fecha_inicio = fecha_reporte - timedelta(days=15)
        self._crear_credito(
            db_session, negocio_id, ruta_id, cliente_id, fecha_inicio=fecha_inicio
        )

        result = build_hoja_viva(db_session, ruta_id, report_date=fecha_reporte)

        assert len(result["clientes"]) == 1
        assert result["clientes"][0]["mora_legacy"] == 14

    def test_vence_hoy_desde_cuota_programada(
        self, db_session, negocio_id, ruta_id, cliente_id
    ):
        """C-09: cuota PENDIENTE con vencimiento = reporte cuenta en vence_hoy."""
        fecha_reporte = date(2026, 8, 6)
        fecha_inicio = fecha_reporte - timedelta(days=10)
        credito = self._crear_credito(
            db_session, negocio_id, ruta_id, cliente_id, fecha_inicio=fecha_inicio
        )

        for numero, venc, estado in [
            (1, fecha_reporte - timedelta(days=2), "PENDIENTE"),
            (2, fecha_reporte - timedelta(days=1), "PENDIENTE"),
            (3, fecha_reporte, "PENDIENTE"),
        ]:
            db_session.add(
                CuotaProgramada(
                    id=uuid4(),
                    negocio_id=negocio_id,
                    credito_id=credito.id,
                    numero=numero,
                    fecha_vencimiento=venc,
                    monto=CUOTA,
                    estado=estado,
                )
            )
        db_session.commit()

        result = build_hoja_viva(db_session, ruta_id, report_date=fecha_reporte)

        assert result["cuotas_que_vencen_hoy"] == 1
        assert result["vence_hoy_monto"] == CUOTA
        assert result["clientes"][0]["mora_legacy"] == 9


class TestParidadCaja:
    """C-10 — cadena de caja con todos los flujos físicos."""

    def test_flujos_fisicos_completos(self):
        """Backend: base + carry + recaudo_neto + recibidos - gastos - ahorro - vales - entregas - desembolsos."""
        result = calcular_caja(
            opening_base=100_000,
            opening_carry=0,
            recaudo_real=40_000,  # recaudo neto de reversos (recaudo bruto - reversos)
            desembolsos=[1_000],
            vales=[3_000],
            gastos=[15_000],
            ahorro=[5_000],
            entregas=[2_000],
            recibidos=[4_000],
        )

        assert result["esperado"] == 118_000

    def test_calcular_cadena_caja_integracion(
        self, db_session, negocio_id, ruta_id, cliente_id
    ):
        """C-10 integrado: jornada + pagos + reverso + movimientos → 98.000.

        El reverso es TOTAL (único soportado en ambas plataformas) y queda
        ligado a la jornada del pago original: recaudo = 20.000 neto.
        """
        ctx = _admin_ctx(negocio_id)
        jornada = open_jornada(
            db_session,
            ruta_id,
            negocio_id,
            fecha=date(2026, 8, 6),
            opening_base=100_000,
            ctx=ctx,
        )
        credito = Credito(
            id=uuid4(),
            negocio_id=negocio_id,
            cliente_id=cliente_id,
            ruta_id=ruta_id,
            origination_type="NEW",
            cuota=CUOTA,
            n_cuotas=N,
            monto=180_000,
            total=TOTAL,
            periodicidad="DIARIO",
            fecha_inicio=date(2026, 8, 6),
            estado="ACTIVO",
        )
        db_session.add(credito)
        db_session.commit()
        db_session.refresh(credito)

        pago1 = register_payment(
            db_session,
            {
                "credito_id": credito.id,
                "jornada_id": jornada.id,
                "monto": 50_000,
                "clave_idempotencia": "c10-pago-1",
            },
            ctx,
        )
        register_payment(
            db_session,
            {
                "credito_id": credito.id,
                "jornada_id": jornada.id,
                "monto": 20_000,
                "clave_idempotencia": "c10-pago-2",
            },
            ctx,
        )
        reverse_payment(
            db_session,
            pago1.id,
            {"motivo": "test"},
            ctx,
        )
        for tipo, monto in [
            ("GASOLINA", 15_000),
            ("AHORRO", 5_000),
            ("VALE", 3_000),
            ("ENTREGA", 2_000),
            ("RECIBIDO", 4_000),
            ("DESEMBOLSO", 1_000),
        ]:
            db_session.add(
                MovimientoCaja(
                    id=uuid4(),
                    negocio_id=negocio_id,
                    jornada_id=jornada.id,
                    tipo=tipo,
                    naturaleza="GASTO" if tipo == "GASOLINA" else None,
                    monto=monto,
                    clave_idempotencia=f"c10-mov-{tipo}",
                )
            )
        db_session.commit()

        caja = calcular_cadena_caja(db_session, jornada.id)

        assert caja["recaudo_real"] == 20_000
        assert caja["gastos"] == 15_000
        assert caja["ahorro"] == 5_000
        assert caja["vales"] == 3_000
        assert caja["entregas"] == 2_000
        assert caja["otros_entrada"] == 4_000
        assert caja["desembolsos"] == 1_000
        assert caja["efectivo_esperado"] == 98_000


class TestParidadCierreYCarry:
    """C-11/C-12 — cierre con diferencia y carry de la siguiente jornada."""

    def test_cierre_diferencia_y_carry(self, db_session, negocio_id, ruta_id):
        """D cierre contado 120.000 → sobrante_manana 120.000; D+1 opening_carry 120.000."""
        ctx = _admin_ctx(negocio_id)
        fecha_d = date(2026, 8, 6)
        jornada_d = open_jornada(
            db_session,
            ruta_id,
            negocio_id,
            fecha=fecha_d,
            opening_base=118_000,
            ctx=ctx,
        )

        cierre = cerrar_jornada(
            db_session,
            jornada_d.id,
            {
                "efectivo_contado": 120_000,
                "motivo": "Sobrante menor",
                "version": 1,
            },
            ctx,
        )

        assert cierre["diferencia"] == 2_000
        assert cierre["sobrante_manana"] == 120_000

        fecha_d1 = fecha_d + timedelta(days=1)
        jornada_d1 = open_jornada(
            db_session,
            ruta_id,
            negocio_id,
            fecha=fecha_d1,
            opening_base=0,
            ctx=ctx,
        )

        assert jornada_d1.opening_carry == 120_000
        assert get_carry_for_date(db_session, negocio_id, ruta_id, fecha_d1) == 120_000

    def test_sin_jornada_previa_carry_cero(self, db_session, negocio_id, ruta_id):
        """Sin jornada anterior, el carry es cero."""
        fecha = date(2026, 8, 6)
        carry = get_carry_for_date(db_session, negocio_id, ruta_id, fecha)

        assert carry == 0


class TestParidadRenovacion:
    """C-13 — renovación: dinero nuevo entregado y recargo."""

    def test_fixture_documento(self):
        """Fixture maestro: saldo 2740, pago 0, monto nuevo 3000 → 260."""
        result = calcular_renovacion(
            saldo_anterior=2_740,
            pago_efectivo=0,
            monto_nuevo=3_000,
            recargo_pct=20,
        )

        assert result["saldo_refinanciado"] == 2_740
        assert result["dinero_nuevo_entregado"] == 260
        assert result["monto_final_con_recargo"] == 3_600
