// BLOQUE 5 — Paridad financiera backend–móvil (casos C-01 .. C-16).
//
// El backend es la autoridad financiera. Este archivo fija el resultado móvil
// sobre los servicios reales (HojaVivaService, CajaService, PagoService,
// JornadaService) y SQLite real, y lo compara contra los valores canónicos de
// la matriz: DAILY-SYSTEM-BLOQUE5-MATRIZ-PARIDAD.md
//
// Los valores esperados aquí son los del backend (autoridad). Antes de la
// corrección, los casos de hoja viva fallaban por las fórmulas divergentes
// (pico, cuotas_pagadas, mora_legacy, semáforo). Con las correcciones en
// hoja_viva_service.dart y jornada_service.dart, todo debe pasar.

import 'package:daily_system/database/database.dart';
import 'package:daily_system/services/caja_service.dart';
import 'package:daily_system/services/hoja_viva_service.dart';
import 'package:daily_system/services/jornada_service.dart';
import 'package:daily_system/services/movimiento_service.dart';
import 'package:daily_system/services/pago_service.dart';
import 'package:flutter_test/flutter_test.dart';

import 'helpers/fixture.dart';

const int _cuota = 5000;
const int _n = 40;
const int _total = _cuota * _n; // 200.000

// Fecha de reporte fija (igual que la suite backend) para mora determinista.
final DateTime _reporte = DateTime(2026, 8, 6);

Future<({String ruta, String negocio, String cobrador, String cliente})> _ids() async {
  final db = await database;
  final rutas = await db.query('ruta', where: 'activa = ?', whereArgs: [1], limit: 1);
  final negocios = await db.query('negocio', limit: 1);
  final cobradores =
      await db.query('usuario', where: 'rol = ?', whereArgs: ['COBRADOR'], limit: 1);
  final clientes = await db.query('cliente', limit: 1);
  return (
    ruta: rutas.first['id'] as String,
    negocio: negocios.first['id'] as String,
    cobrador: cobradores.first['id'] as String,
    cliente: clientes.first['id'] as String,
  );
}

Future<String> _crearCredito({
  required String rutaId,
  required String negocioId,
  required String clienteId,
  required int cuota,
  required int n,
  required String fechaInicio,
}) async {
  final db = await database;
  final id = 'b5-$cuota-$n-$fechaInicio-${DateTime.now().microsecondsSinceEpoch}';
  await db.insert('credito', {
    'id': id,
    'negocio_id': negocioId,
    'cliente_id': clienteId,
    'ruta_id': rutaId,
    'cuota': cuota,
    'n_cuotas': n,
    'monto': cuota * n - 20000,
    'total': cuota * n,
    'periodicidad': 'DIARIO',
    'fecha_inicio': fechaInicio,
    'estado': 'ACTIVO',
  });
  return id;
}

Future<Map<String, dynamic>> _filaHojaViva(String creditoId) async {
  final ids = await _ids();
  final clientes =
      await HojaVivaService.getHojaViva(ids.ruta, ids.negocio, reportDate: _reporte);
  return clientes.firstWhere((c) => c['credito_id'] == creditoId);
}

void main() {
  setUpAll(() {
    initTestDatabase();
  });

  setUp(() async {
    await clearDatabase();
  });

  group('C-01..C-05 Matriz de pagos (hoja viva móvil)', () {
    Future<void> verificar({
      required int abono,
      required int esperadoCuotas,
      required int esperadoPico,
      required int esperadoSaldo,
    }) async {
      final ids = await _ids();
      final creditoId = await _crearCredito(
        rutaId: ids.ruta,
        negocioId: ids.negocio,
        clienteId: ids.cliente,
        cuota: _cuota,
        n: _n,
        fechaInicio: '2026-07-01',
      );
      final jornada = await JornadaService.abrirJornada(
          ids.ruta, ids.cobrador, ids.negocio, 0);
      await PagoService.registrarPago(creditoId, jornada.id, ids.cobrador, ids.negocio,
          abono, 'abono', 'b5-pago-$abono');

      final fila = await _filaHojaViva(creditoId);
      expect(fila['total'], _total, reason: 'total = cuota × n');
      expect(fila['saldo'], esperadoSaldo, reason: 'saldo = total − abono');
      expect(fila['cuotas_pagadas'], esperadoCuotas, reason: '#_C = abono ÷ cuota');
      expect(fila['pico'], esperadoPico, reason: 'pico = abono mód cuota');
    }

    test('C-01 pago exacto de una cuota (5.000 → 1, pico 0)', () async {
      await verificar(abono: 5000, esperadoCuotas: 1, esperadoPico: 0, esperadoSaldo: 195000);
    });

    test('C-02 pago parcial menor que una cuota (1.500 → 0, pico 1.500)', () async {
      await verificar(abono: 1500, esperadoCuotas: 0, esperadoPico: 1500, esperadoSaldo: 198500);
    });

    test('C-03 pago de varias cuotas exactas (10.000 → 2, pico 0)', () async {
      await verificar(abono: 10000, esperadoCuotas: 2, esperadoPico: 0, esperadoSaldo: 190000);
    });

    test('C-04 pago superior con pico (12.000 → 2, pico 2.000)', () async {
      await verificar(abono: 12000, esperadoCuotas: 2, esperadoPico: 2000, esperadoSaldo: 188000);
    });

    test('C-05 pago total del crédito (200.000 → 40, pico 0)', () async {
      await verificar(abono: 200000, esperadoCuotas: 40, esperadoPico: 0, esperadoSaldo: 0);
    });
  });

  group('C-06/C-07 Reversos (neto = Σ PAYMENT − Σ REVERSAL)', () {
    Future<void> verificar({
      required int pago1,
      required int pago2,
      required bool reversar,
      required int esperadoCuotas,
      required int esperadoPico,
      required int esperadoSaldo,
    }) async {
      final ids = await _ids();
      final creditoId = await _crearCredito(
        rutaId: ids.ruta,
        negocioId: ids.negocio,
        clienteId: ids.cliente,
        cuota: _cuota,
        n: _n,
        fechaInicio: '2026-07-01',
      );
      final jornada = await JornadaService.abrirJornada(
          ids.ruta, ids.cobrador, ids.negocio, 0);
      final p1 = await PagoService.registrarPago(creditoId, jornada.id, ids.cobrador,
          ids.negocio, pago1, 'pago1', 'b5-r-$pago1');
      if (pago2 > 0) {
        await PagoService.registrarPago(creditoId, jornada.id, ids.cobrador,
            ids.negocio, pago2, 'pago2', 'b5-r2-$pago2');
      }
      if (reversar) {
        await PagoService.reversarPago(p1.id, jornada.id, ids.cobrador, ids.negocio, 'test');
      }

      final fila = await _filaHojaViva(creditoId);
      expect(fila['saldo'], esperadoSaldo, reason: 'saldo = total − abono_neto');
      expect(fila['cuotas_pagadas'], esperadoCuotas, reason: '#_C = abono_neto ÷ cuota');
      expect(fila['pico'], esperadoPico, reason: 'pico = abono_neto mód cuota');
    }

    test('C-06 reverso parcial documentado → no representable, el reverso es total', () async {
      // La matriz clasifica C-06 como REGLA NO DEFINIDA: ninguna plataforma
      // soporta reverso parcial (el REVERSAL copia el monto del pago original).
      // Lo representable es reversar el pago completo de 10.000 → abono_neto 0.
      await verificar(
          pago1: 10000,
          pago2: 0,
          reversar: true,
          esperadoCuotas: 0,
          esperadoPico: 0,
          esperadoSaldo: 200000);
    });

    test('C-07 reverso total (pago 5.000, reverso 5.000 → 0)', () async {
      await verificar(
          pago1: 5000,
          pago2: 0,
          reversar: true,
          esperadoCuotas: 0,
          esperadoPico: 0,
          esperadoSaldo: 200000);
    });
  });

  group('C-08 Mora legacy', () {
    test('15 días sin abono → mora = 14', () async {
      final ids = await _ids();
      final creditoId = await _crearCredito(
        rutaId: ids.ruta,
        negocioId: ids.negocio,
        clienteId: ids.cliente,
        cuota: _cuota,
        n: _n,
        fechaInicio: '2026-07-22', // _reporte − 15
      );

      final fila = await _filaHojaViva(creditoId);
      expect(fila['mora_legacy'], 14);
    });

    test('descuenta cuotas pagadas (15 días, 2 cuotas → mora 12)', () async {
      final ids = await _ids();
      final creditoId = await _crearCredito(
        rutaId: ids.ruta,
        negocioId: ids.negocio,
        clienteId: ids.cliente,
        cuota: _cuota,
        n: _n,
        fechaInicio: '2026-07-22',
      );
      final jornada = await JornadaService.abrirJornada(
          ids.ruta, ids.cobrador, ids.negocio, 0);
      await PagoService.registrarPago(creditoId, jornada.id, ids.cobrador, ids.negocio,
          10000, 'abono', 'b5-mora-2c');

      final fila = await _filaHojaViva(creditoId);
      expect(fila['cuotas_pagadas'], 2);
      expect(fila['mora_legacy'], 12);
    });

    test('nunca negativa (inicio _reporte − 1 → mora 0)', () async {
      final ids = await _ids();
      final creditoId = await _crearCredito(
        rutaId: ids.ruta,
        negocioId: ids.negocio,
        clienteId: ids.cliente,
        cuota: _cuota,
        n: _n,
        fechaInicio: '2026-08-05',
      );

      final fila = await _filaHojaViva(creditoId);
      expect(fila['mora_legacy'], 0);
    });
  });

  group('C-14 Semáforo', () {
    test('sin score real → siempre GRIS', () async {
      final ids = await _ids();
      final creditoId = await _crearCredito(
        rutaId: ids.ruta,
        negocioId: ids.negocio,
        clienteId: ids.cliente,
        cuota: _cuota,
        n: _n,
        fechaInicio: '2026-07-22',
      );
      final jornada = await JornadaService.abrirJornada(
          ids.ruta, ids.cobrador, ids.negocio, 0);
      await PagoService.registrarPago(creditoId, jornada.id, ids.cobrador, ids.negocio,
          5000, 'abono', 'b5-sem-pago');

      final fila = await _filaHojaViva(creditoId);
      expect(fila['semaforo'], 'GRIS');
    });
  });

  group('C-10 Cadena de caja (flujos físicos)', () {
    test('base + recaudo − reversos + recibidos − gastos − ahorro − vales − entregas − desembolsos = 98.000',
        () async {
      final ids = await _ids();
      final creditoId = await _crearCredito(
        rutaId: ids.ruta,
        negocioId: ids.negocio,
        clienteId: ids.cliente,
        cuota: _cuota,
        n: _n,
        fechaInicio: '2026-07-01',
      );
      final jornada =
          await JornadaService.abrirJornada(ids.ruta, ids.cobrador, ids.negocio, 100000);

      final pago1 = await PagoService.registrarPago(creditoId, jornada.id, ids.cobrador,
          ids.negocio, 50000, 'pago1', 'b5-c10-p1');
      await PagoService.registrarPago(creditoId, jornada.id, ids.cobrador, ids.negocio,
          20000, 'pago2', 'b5-c10-p2');
      await PagoService.reversarPago(
          pago1.id, jornada.id, ids.cobrador, ids.negocio, 'test');

      for (final (tipo, monto) in [
        ('GASOLINA', 15000),
        ('AHORRO', 5000),
        ('VALE', 3000),
        ('ENTREGA', 2000),
        ('RECIBIDO', 4000),
        ('DESEMBOLSO', 1000),
      ]) {
        await MovimientoService.registrarMovimiento(
          jornadaId: jornada.id,
          tipo: tipo,
          monto: monto,
          nota: 'b5',
          cobradorId: ids.cobrador,
          negocioId: ids.negocio,
        );
      }

      final caja = await CajaService.calcularCaja(jornada.id);
      expect(caja.openingBase, 100000);
      expect(caja.openingCarry, 0);
      expect(caja.recaudoReal, 70000, reason: 'Σ PAYMENT bruto');
      expect(caja.reversales, 50000, reason: 'Σ REVERSAL ligado a la jornada');
      expect(caja.gastos, 15000);
      expect(caja.ahorro, 5000);
      expect(caja.vales, 3000);
      expect(caja.entregas, 2000);
      expect(caja.recibidos, 4000);
      expect(caja.desembolsos, 1000);
      expect(caja.efectivoEsperado, 98000);
    });
  });

  group('C-11/C-12 Cierre con diferencia y carry', () {
    test('cierre contado 120.000 sobre esperado 118.000 → diferencia 2.000 y carry al siguiente día',
        () async {
      final ids = await _ids();

      final jornadaD = await JornadaService.abrirJornada(
          ids.ruta, ids.cobrador, ids.negocio, 118000,
          fecha: '2026-08-06');
      final cierre = await JornadaService.cerrarJornada(
          jornadaD.id, 120000, 'Sobrante menor');

      expect(cierre.efectivoEsperado, 118000);
      expect(cierre.contado, 120000);
      expect(cierre.diferencia, 2000);

      // opening_carry(D+1) = sobrante_manana(D) = contado = 120.000
      final jornadaD1 = await JornadaService.abrirJornada(
          ids.ruta, ids.cobrador, ids.negocio, 0,
          fecha: '2026-08-07');
      expect(jornadaD1.openingCarry, 120000);
    });

    test('sin jornada previa cerrada → carry cero', () async {
      final ids = await _ids();
      final jornada = await JornadaService.abrirJornada(
          ids.ruta, ids.cobrador, ids.negocio, 0,
          fecha: '2026-08-07');
      expect(jornada.openingCarry, 0);
    });
  });
}
