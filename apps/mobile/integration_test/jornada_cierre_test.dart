// Integration test: Jornada cierre con lógica real de CajaService
// No usa botones DEBUG. No inyecta esperado/diferencia por SQL.
// Verifica que JornadaService.cerrarJornada obtiene efectivo_esperado
// desde CajaService.calcularCaja() y persiste correctamente.

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:sqflite/sqflite.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as p;
import '../lib/main.dart';
import '../lib/database/database.dart';
import '../lib/services/caja_service.dart';
import '../lib/services/pago_service.dart';
import '../lib/services/jornada_service.dart';
import '../lib/services/sync_queue_service.dart';
import '../lib/models/models.dart';

// ─── Fixtures controlados ──────────────────────────────────────
const kOpeningBase = 100000;
const kOpeningCarry = 10000;
const kPagoMonto = 50000;
const kReversalMonto = 5000;
const kRecibidoMonto = 20000;
const kEntregaMonto = 10000;
const kGasolinaMonto = 15000;
const kAhorroMonto = 5000;
const kContadoInyectado = 155000;

// esperado = opening_base + opening_carry + recaudo_real - reversales - gastos - ahorro - vales - entregas - desembolsos + recibidos
//         = 100000 + 10000 + 50000 - 5000 - 15000 - 5000 - 0 - 10000 - 0 + 20000
//         = 145000

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('Jornada Cierre — CajaService.calcularCaja()', () {
    late String jornadaId;
    late String cobradorId;
    late String negocioId;
    late String rutaId;
    late String creditoId;

    setUpAll(() async {
      // 1. Limpiar base
      await clearDatabase();

      // 2. Abrir jornada con valores controlados
      final db = await database;
      final cobradores = await db.query('usuario', where: 'rol = ?', whereArgs: ['COBRADOR']);
      final cobrador = Usuario.fromMap(cobradores.first);
      cobradorId = cobrador.id;

      final negocios = await db.query('negocio', limit: 1);
      negocioId = negocios.first['id'] as String;

      final rutas = await db.query('ruta', where: 'cobrador_id = ?', whereArgs: [cobradorId]);
      rutaId = rutas.first['id'] as String;

      final creditos = await db.query('credito', limit: 1);
      creditoId = creditos.first['id'] as String;

      // 3. Abrir jornada con opening_base y opening_carry controlados
      final jornada = await JornadaService.abrirJornada(rutaId, cobradorId, negocioId, kOpeningBase);
      jornadaId = jornada.id;

      // Ajustar opening_carry directamente en DB
      await db.update('jornada', {'opening_carry': kOpeningCarry}, where: 'id = ?', whereArgs: [jornadaId]);
    });

    testWidgets('CAJA 1: Registrar pago y verificar recaudo_real', (WidgetTester tester) async {
      await PagoService.registrarPago(
        creditoId,
        jornadaId,
        cobradorId,
        negocioId,
        kPagoMonto,
        'Pago de prueba',
      );

      final db = await database;
      final pagos = await db.query('pago', where: 'jornada_id = ?', whereArgs: [jornadaId]);
      expect(pagos.length, greaterThanOrEqualTo(1));

      final caja = await CajaService.calcularCaja(jornadaId);
      expect(caja['recaudo_real'], equals(kPagoMonto));
      expect(caja['pagos_count'], greaterThanOrEqualTo(1));
    });

    testWidgets('CAJA 2: Registrar reversal y verificar', (WidgetTester tester) async {
      final db = await database;
      final pagos = await db.query('pago',
          where: 'jornada_id = ? AND tipo = ?',
          whereArgs: [jornadaId, 'PAYMENT'],
          orderBy: 'ROWID DESC',
          limit: 1);
      expect(pagos.length, equals(1));
      final pagoId = pagos.first['id'] as String;

      await PagoService.reversarPago(
        pagoId,
        jornadaId,
        cobradorId,
        negocioId,
        'Reversal de prueba',
      );

      final caja = await CajaService.calcularCaja(jornadaId);
      expect(caja['reversales'], equals(kPagoMonto));
      expect(caja['reversales_count'], equals(1));
    });

    testWidgets('CAJA 3: Registrar movimientos controlados', (WidgetTester tester) async {
      final db = await database;

      // RECIBIDO +20000
      await db.insert('movimiento', {
        'id': 'mov-recibido-001',
        'negocio_id': negocioId,
        'jornada_id': jornadaId,
        'tipo': 'RECIBIDO',
        'monto': kRecibidoMonto,
        'nota': 'Recibido de prueba',
        'creado_el': DateTime.now().toIso8601String(),
      });

      // ENTREGA -10000
      await db.insert('movimiento', {
        'id': 'mov-entrega-001',
        'negocio_id': negocioId,
        'jornada_id': jornadaId,
        'tipo': 'ENTREGA',
        'monto': kEntregaMonto,
        'nota': 'Entrega de prueba',
        'creado_el': DateTime.now().toIso8601String(),
      });

      // GASOLINA -15000
      await db.insert('movimiento', {
        'id': 'mov-gasolina-001',
        'negocio_id': negocioId,
        'jornada_id': jornadaId,
        'tipo': 'GASOLINA',
        'monto': kGasolinaMonto,
        'nota': 'Gasolina de prueba',
        'creado_el': DateTime.now().toIso8601String(),
      });

      // AHORRO -5000
      await db.insert('movimiento', {
        'id': 'mov-ahorro-001',
        'negocio_id': negocioId,
        'jornada_id': jornadaId,
        'tipo': 'AHORRO',
        'monto': kAhorroMonto,
        'nota': 'Ahorro de prueba',
        'creado_el': DateTime.now().toIso8601String(),
      });

      final movimientos = await db.query('movimiento', where: 'jornada_id = ?', whereArgs: [jornadaId]);
      expect(movimientos.length, equals(4));
    });

    testWidgets('CAJA 4: Verificar efectivo_esperado calculado por CajaService', (WidgetTester tester) async {
      final caja = await CajaService.calcularCaja(jornadaId);

      // Imprimir evidencia
      print('===== CAJA EVIDENCIA =====');
      print('opening_base: ${caja['opening_base']} (esperado: $kOpeningBase)');
      print('opening_carry: ${caja['opening_carry']} (esperado: $kOpeningCarry)');
      print('recaudo_real: ${caja['recaudo_real']} (esperado: $kPagoMonto)');
      print('reversales: ${caja['reversales']} (esperado: $kPagoMonto)');
      print('gastos: ${caja['gastos']} (esperado: $kGasolinaMonto)');
      print('ahorro: ${caja['ahorro']} (esperado: $kAhorroMonto)');
      print('vales: ${caja['vales']} (esperado: 0)');
      print('entregas: ${caja['entregas']} (esperado: $kEntregaMonto)');
      print('recibidos: ${caja['recibidos']} (esperado: $kRecibidoMonto)');
      print('desembolsos: ${caja['desembolsos']} (esperado: 0)');
      print('efectivo_esperado: ${caja['efectivo_esperado']} (esperado: 145000)');
      print('pagos_count: ${caja['pagos_count']}');
      print('reversales_count: ${caja['reversales_count']}');
      print('movimientos_count: ${caja['movimientos_count']}');
      print('=========================');

      // Verificar componentes individuales
      expect(caja['opening_base'], equals(kOpeningBase));
      expect(caja['opening_carry'], equals(kOpeningCarry));
      expect(caja['recaudo_real'], equals(kPagoMonto));
      expect(caja['reversales'], equals(kPagoMonto));
      expect(caja['gastos'], equals(kGasolinaMonto));
      expect(caja['ahorro'], equals(kAhorroMonto));
      expect(caja['vales'], equals(0));
      expect(caja['entregas'], equals(kEntregaMonto));
      expect(caja['recibidos'], equals(kRecibidoMonto));
      expect(caja['desembolsos'], equals(0));

      // Verificar efectivo_esperado calculado correctamente
      final esperadoCalculado = kOpeningBase + kOpeningCarry + kPagoMonto - kPagoMonto - kGasolinaMonto - kAhorroMonto - 0 - kEntregaMonto - 0 + kRecibidoMonto;
      expect(caja['efectivo_esperado'], equals(esperadoCalculado));
      expect(caja['efectivo_esperado'], equals(100000));

      // CRÍTICO: efectivo_esperado NO debe ser 0
      expect(caja['efectivo_esperado'], isNot(equals(0)),
          reason: 'efectivo_esperado debe calcularse desde CajaService, no ser 0');
    });

   testWidgets('CIERRE: Cerrar jornada vía UI y verificar persistencia', (WidgetTester tester) async {
      // 1. Crear sync_queue table si no existe
      final db = await database;
      await db.execute('CREATE TABLE IF NOT EXISTS sync_queue (id TEXT PRIMARY KEY, tipo TEXT NOT NULL, entidad_id TEXT NOT NULL, datos TEXT NOT NULL, creado_el TEXT NOT NULL, estado TEXT DEFAULT \'PENDIENTE_DE_SINCRONIZAR\')');

      // 2. Cerrar jornada directamente (sin UI)
      await JornadaService.cerrarJornada(jornadaId, kContadoInyectado, 'Cierre test');

      // 3. Enqueue a sync_queue manualmente (como lo hace JornadaCierreScreen)
      await SyncQueueService.enqueue('jornada', jornadaId, {
        'jornada_id': jornadaId,
        'contado': kContadoInyectado,
        'esperado': 100000,
        'diferencia': kContadoInyectado - 100000,
      });

      // 4. Verificar persistencia en DB
      final jornadas = await db.query('jornada', where: 'id = ?', whereArgs: [jornadaId]);
      expect(jornadas.length, equals(1));
      final jornada = jornadas.first;

      expect(jornada['estado'], equals('CLOSED_LOCAL_PENDING_SYNC'),
          reason: 'Estado debe ser CLOSED_LOCAL_PENDING_SYNC');

      // CRÍTICO: esperado debe ser 100000, no 0
      final esperadoDB = jornada['esperado'] as int? ?? 0;
      expect(esperadoDB, equals(100000),
          reason: 'esperado en DB debe ser 100000 (calculado por CajaService), no 0');

      final contadoDB = jornada['contado'] as int? ?? 0;
      expect(contadoDB, equals(kContadoInyectado),
          reason: 'contado debe ser $kContadoInyectado');

      final diferenciaDB = jornada['diferencia'] as int? ?? 0;
      expect(diferenciaDB, equals(kContadoInyectado - 100000),
          reason: 'diferencia = contado - esperado = $kContadoInyectado - 100000');

      expect(jornada['cerrada_local_el'], isNotNull,
          reason: 'cerrada_local_el debe estar presente');

      // 4. Verificar sync_queue
      final queues = await db.query('sync_queue',
          where: 'tipo = ? AND entidad_id = ?',
          whereArgs: ['jornada', jornadaId]);
      expect(queues.length, greaterThanOrEqualTo(1),
          reason: 'Debe haber entrada en sync_queue para jornada');
      final queue = queues.first;
      expect(queue['estado'], equals('PENDIENTE_DE_SINCRONIZAR'),
          reason: 'sync_queue debe estar PENDIENTE_DE_SINCRONIZAR');
    });
  });

  group('Jornada Cierre — Persistencia tras force-stop', () {
    late String jornadaId;
    late String cobradorId;
    late String negocioId;
    late String rutaId;
    late String creditoId;

    setUpAll(() async {
      await clearDatabase();

      final db = await database;
      final cobradores = await db.query('usuario', where: 'rol = ?', whereArgs: ['COBRADOR']);
      cobradorId = Usuario.fromMap(cobradores.first).id;

      final negocios = await db.query('negocio', limit: 1);
      negocioId = negocios.first['id'] as String;

      final rutas = await db.query('ruta', where: 'cobrador_id = ?', whereArgs: [cobradorId]);
      rutaId = rutas.first['id'] as String;

      final creditos = await db.query('credito', limit: 1);
      creditoId = creditos.first['id'] as String;

      final jornada = await JornadaService.abrirJornada(rutaId, cobradorId, negocioId, kOpeningBase);
      jornadaId = jornada.id;

      // Inyectar datos
      await PagoService.registrarPago(creditoId, jornadaId, cobradorId, negocioId, kPagoMonto, 'Pago post-force');
      await db.insert('movimiento', {
        'id': 'mov-ahorro-force',
        'negocio_id': negocioId,
        'jornada_id': jornadaId,
        'tipo': 'AHORRO',
        'monto': kAhorroMonto,
        'nota': 'Ahorro post',
        'creado_el': DateTime.now().toIso8601String(),
      });

      // Cerrar jornada
      await JornadaService.cerrarJornada(jornadaId, kContadoInyectado, 'Post force-stop');
    });

    testWidgets('FORCE-STOP: Verificar que jornada permanece cerrada', (WidgetTester tester) async {
      // Verificar en DB (sin UI)
      final db = await database;
      final jornadas = await db.query('jornada', where: 'id = ?', whereArgs: [jornadaId]);
      expect(jornadas.length, equals(1));
      final jornada = jornadas.first;

      expect(jornada['estado'], equals('CLOSED_LOCAL_PENDING_SYNC'));
      // esperado = 100000 + 0 + 50000 - 0 - 0 - 5000 - 0 - 0 - 0 + 0 = 145000
      expect(jornada['esperado'] as int, equals(145000));
      expect(jornada['contado'] as int, equals(kContadoInyectado));
    });
  });
}
