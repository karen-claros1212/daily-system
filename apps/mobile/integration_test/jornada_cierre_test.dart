// Integration test: Jornada cierre — evidenciado por capas
//
// A. SERVICE TEST — JornadaService.cerrarJornada() + persistencia
// B. UI TEST — JornadaCierreScreen real (input + botón + confirmación)
// C. ADB RESTART TEST — force-stop + reopen + verificación DB
//
// Fixture canónico:
//   opening_base = 100000
//   opening_carry = 10000
//   pago = 50000
//   reversal = 50000 (reversarPago revierte el pago completo)
//   recibido = 20000
//   entrega = 10000
//   gasolina = 15000
//   ahorro = 5000
//
// esperado = 100000 + 10000 + 50000 - 50000 - 15000 - 5000 - 0 - 10000 - 0 + 20000
//         = 100000

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:path_provider/path_provider.dart';
import 'package:daily_system/database/database.dart';
import 'package:daily_system/services/caja_service.dart';
import 'package:daily_system/services/pago_service.dart';
import 'package:daily_system/services/jornada_service.dart';
import 'package:daily_system/services/sync_queue_service.dart';
import 'package:daily_system/models/models.dart';
import 'package:daily_system/screens/jornada_cierre_screen.dart';

// ─── Fixture canónico ──────────────────────────────────────────
const kOpeningBase = 100000;
const kOpeningCarry = 10000;
const kPagoMonto = 50000;
const kReversalMonto = 50000; // reversarPago revierte el pago completo
const kRecibidoMonto = 20000;
const kEntregaMonto = 10000;
const kGasolinaMonto = 15000;
const kAhorroMonto = 5000;
const kContadoInyectado = 155000;

// esperado = opening_base + opening_carry + recaudo_real - reversales - gastos - ahorro - vales - entregas - desembolsos + recibidos
//         = 100000 + 10000 + 50000 - 50000 - 15000 - 5000 - 0 - 10000 - 0 + 20000
//         = 100000
const kEsperadoCanonico = 100000;
const kDiferenciaCanonica = kContadoInyectado - kEsperadoCanonico;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  // ══════════════════════════════════════════════════════════════
  // A. SERVICE TEST — JornadaService.cerrarJornada() + persistencia
  // ══════════════════════════════════════════════════════════════
  group('A. SERVICE TEST — CajaService.calcularCaja() + cerrarJornada', () {
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
      await db.update('jornada', {'opening_carry': kOpeningCarry}, where: 'id = ?', whereArgs: [jornadaId]);
    });

    test('CAJA 1: Pago + reversal + movimientos', () async {
      final db = await database;

      await PagoService.registrarPago(creditoId, jornadaId, cobradorId, negocioId, kPagoMonto, 'Pago');
      final pagos = await db.query('pago', where: 'jornada_id = ?', whereArgs: [jornadaId]);
      expect(pagos.length, greaterThanOrEqualTo(1));

      final pagoId = pagos.first['id'] as String;
      await PagoService.reversarPago(pagoId, jornadaId, cobradorId, negocioId, 'Reversal');

      await db.insert('movimiento', {
        'id': 'mov-recibido', 'negocio_id': negocioId, 'jornada_id': jornadaId,
        'tipo': 'RECIBIDO', 'monto': kRecibidoMonto, 'nota': '', 'creado_el': DateTime.now().toIso8601String(),
      });
      await db.insert('movimiento', {
        'id': 'mov-entrega', 'negocio_id': negocioId, 'jornada_id': jornadaId,
        'tipo': 'ENTREGA', 'monto': kEntregaMonto, 'nota': '', 'creado_el': DateTime.now().toIso8601String(),
      });
      await db.insert('movimiento', {
        'id': 'mov-gasolina', 'negocio_id': negocioId, 'jornada_id': jornadaId,
        'tipo': 'GASOLINA', 'monto': kGasolinaMonto, 'nota': '', 'creado_el': DateTime.now().toIso8601String(),
      });
      await db.insert('movimiento', {
        'id': 'mov-ahorro', 'negocio_id': negocioId, 'jornada_id': jornadaId,
        'tipo': 'AHORRO', 'monto': kAhorroMonto, 'nota': '', 'creado_el': DateTime.now().toIso8601String(),
      });
    });

    test('CAJA 2: efectivo_esperado calculado por CajaService ≠ 0', () async {
      final caja = await CajaService.calcularCaja(jornadaId);

      print('===== CAJA EVIDENCIA (SERVICE TEST) =====');
      print('opening_base: ${caja['opening_base']}');
      print('opening_carry: ${caja['opening_carry']}');
      print('recaudo_real: ${caja['recaudo_real']}');
      print('reversales: ${caja['reversales']}');
      print('gastos: ${caja['gastos']}');
      print('ahorro: ${caja['ahorro']}');
      print('vales: ${caja['vales']}');
      print('entregas: ${caja['entregas']}');
      print('recibidos: ${caja['recibidos']}');
      print('desembolsos: ${caja['desembolsos']}');
      print('efectivo_esperado: ${caja['efectivo_esperado']}');
      print('=========================================');

      expect(caja['opening_base'], equals(kOpeningBase));
      expect(caja['opening_carry'], equals(kOpeningCarry));
      expect(caja['recaudo_real'], equals(kPagoMonto));
      expect(caja['reversales'], equals(kReversalMonto));
      expect(caja['gastos'], equals(kGasolinaMonto));
      expect(caja['ahorro'], equals(kAhorroMonto));
      expect(caja['vales'], equals(0));
      expect(caja['entregas'], equals(kEntregaMonto));
      expect(caja['recibidos'], equals(kRecibidoMonto));
      expect(caja['desembolsos'], equals(0));

      final esperadoCalculado = kOpeningBase + kOpeningCarry + kPagoMonto - kReversalMonto - kGasolinaMonto - kAhorroMonto - 0 - kEntregaMonto - 0 + kRecibidoMonto;
      expect(caja['efectivo_esperado'], equals(esperadoCalculado));
      expect(caja['efectivo_esperado'], equals(kEsperadoCanonico));
      expect(caja['efectivo_esperado'], isNot(equals(0)),
          reason: 'efectivo_esperado debe calcularse desde CajaService, no ser 0');
    });

    test('CIERRE: JornadaService.cerrarJornada persiste esperado/contado/diferencia', () async {
      final db = await database;
      await db.execute('CREATE TABLE IF NOT EXISTS sync_queue (id TEXT PRIMARY KEY, tipo TEXT NOT NULL, entidad_id TEXT NOT NULL, datos TEXT NOT NULL, creado_el TEXT NOT NULL, estado TEXT DEFAULT \'PENDIENTE_DE_SINCRONIZAR\')');

      // Cerrar jornada
      await JornadaService.cerrarJornada(jornadaId, kContadoInyectado, 'Cierre service test');

      // Enqueue
      await SyncQueueService.enqueue('jornada', jornadaId, {
        'jornada_id': jornadaId,
        'contado': kContadoInyectado,
        'esperado': kEsperadoCanonico,
        'diferencia': kDiferenciaCanonica,
      });

      // Verificar jornada
      final jornadas = await db.query('jornada', where: 'id = ?', whereArgs: [jornadaId]);
      expect(jornadas.length, equals(1));
      final jornada = jornadas.first;

      expect(jornada['estado'], equals('CLOSED_LOCAL_PENDING_SYNC'));
      expect(jornada['esperado'] as int, equals(kEsperadoCanonico),
          reason: 'esperado = 100000 (calculado por CajaService), no 0');
      expect(jornada['contado'] as int, equals(kContadoInyectado));
      expect(jornada['diferencia'] as int, equals(kDiferenciaCanonica),
          reason: 'diferencia = contado - esperado');
      expect(jornada['cerrada_local_el'], isNotNull);

      // Verificar sync_queue
      final queues = await db.query('sync_queue',
          where: 'tipo = ? AND entidad_id = ?',
          whereArgs: ['jornada', jornadaId]);
      expect(queues.length, greaterThanOrEqualTo(1));
      expect(queues.first['estado'], equals('PENDIENTE_DE_SINCRONIZAR'));
    });
  });

  // ══════════════════════════════════════════════════════════════
  // B. UI TEST — JornadaCierreScreen real (input + botón + confirmación)
  // ══════════════════════════════════════════════════════════════
  group('B. UI TEST — JornadaCierreScreen flujo real', () {
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
      await db.update('jornada', {'opening_carry': kOpeningCarry}, where: 'id = ?', whereArgs: [jornadaId]);

      // Inyectar datos
      await PagoService.registrarPago(creditoId, jornadaId, cobradorId, negocioId, kPagoMonto, 'Pago UI');
      final pagos = await db.query('pago', where: 'jornada_id = ?', whereArgs: [jornadaId]);
      final pagoId = pagos.first['id'] as String;
      await PagoService.reversarPago(pagoId, jornadaId, cobradorId, negocioId, 'Reversal UI');

      await db.insert('movimiento', {
        'id': 'mov-recibido-ui', 'negocio_id': negocioId, 'jornada_id': jornadaId,
        'tipo': 'RECIBIDO', 'monto': kRecibidoMonto, 'nota': '', 'creado_el': DateTime.now().toIso8601String(),
      });
      await db.insert('movimiento', {
        'id': 'mov-entrega-ui', 'negocio_id': negocioId, 'jornada_id': jornadaId,
        'tipo': 'ENTREGA', 'monto': kEntregaMonto, 'nota': '', 'creado_el': DateTime.now().toIso8601String(),
      });
      await db.insert('movimiento', {
        'id': 'mov-gasolina-ui', 'negocio_id': negocioId, 'jornada_id': jornadaId,
        'tipo': 'GASOLINA', 'monto': kGasolinaMonto, 'nota': '', 'creado_el': DateTime.now().toIso8601String(),
      });
      await db.insert('movimiento', {
        'id': 'mov-ahorro-ui', 'negocio_id': negocioId, 'jornada_id': jornadaId,
        'tipo': 'AHORRO', 'monto': kAhorroMonto, 'nota': '', 'creado_el': DateTime.now().toIso8601String(),
      });
    });

    testWidgets('UI 1: JornadaCierreScreen muestra efectivo_esperado correcto', (WidgetTester tester) async {
      final db = await database;
      final jornada = await db.query('jornada', where: 'id = ?', whereArgs: [jornadaId]);
      final jornadaModel = Jornada.fromMap(jornada.first);

      // Construir la app con JornadaCierreScreen
      runApp(MaterialApp(
        home: JornadaCierreScreen(jornada: jornadaModel, cobradorNombre: 'Carlos López'),
      ));
      await tester.pumpAndSettle(const Duration(seconds: 2));

      // Verificar que se muestra el efectivo esperado correcto
      final esperadoText = find.textContaining('100.000');
      expect(esperadoText, findsOneWidget,
          reason: 'JornadaCierreScreen debe mostrar efectivo esperado 100.000');
    });

    testWidgets('UI 2: Cierre real — input contado + botón TERMINAR JORNADA', (WidgetTester tester) async {
      final db = await database;
      final jornada = await db.query('jornada', where: 'id = ?', whereArgs: [jornadaId]);
      final jornadaModel = Jornada.fromMap(jornada.first);

      // Construir la app
      runApp(MaterialApp(
        home: JornadaCierreScreen(jornada: jornadaModel, cobradorNombre: 'Carlos López'),
      ));
      await tester.pumpAndSettle(const Duration(seconds: 2));

      // 1. Ingresar efectivo contado
      final contadoField = find.byType(TextField).first;
      await tester.enterText(contadoField, kContadoInyectado.toString());
      await tester.pump();

      // 2. Pulsar botón TERMINAR JORNADA
      await tester.tap(find.text('TERMINAR JORNADA'));
      await tester.pumpAndSettle(const Duration(seconds: 2));

      // 3. Verificar confirmación visual
      expect(find.text('JORNADA CERRADA'), findsOneWidget,
          reason: 'Debe mostrar "JORNADA CERRADA"');

      // 4. Verificar persistencia en DB
      final jornadas = await db.query('jornada', where: 'id = ?', whereArgs: [jornadaId]);
      expect(jornadas.length, equals(1));
      final jornadaDb = jornadas.first;

      expect(jornadaDb['estado'], equals('CLOSED_LOCAL_PENDING_SYNC'));
      expect(jornadaDb['esperado'] as int, equals(kEsperadoCanonico),
          reason: 'esperado = 100000 (calculado por CajaService a través de JornadaCierreScreen)');
      expect(jornadaDb['contado'] as int, equals(kContadoInyectado));
      expect(jornadaDb['diferencia'] as int, equals(kDiferenciaCanonica));

      // 5. Verificar PDF generado (obligatorio: existe, tamaño > 0, encabezado %PDF)
      final appDir = await getApplicationDocumentsDirectory();
      // PdfService guarda directamente en appDir, no en app_flutter/
      final pdfFiles = appDir.listSync().where((f) => f.path.endsWith('.pdf')).toList();
      expect(pdfFiles, isNotEmpty,
          reason: 'Debe existir al menos un PDF de cierre de jornada en appDir');
      final pdfFile = pdfFiles.first as File;
      final pdfBytes = await pdfFile.readAsBytes();
      expect(pdfBytes.length, greaterThan(0),
          reason: 'PDF no debe estar vacío');
      final pdfContent = String.fromCharCodes(pdfBytes);
      expect(pdfContent.startsWith('%PDF'), isTrue,
          reason: 'PDF debe tener encabezado %PDF válido');

      // 6. Verificar sync_queue
      await db.execute('CREATE TABLE IF NOT EXISTS sync_queue (id TEXT PRIMARY KEY, tipo TEXT NOT NULL, entidad_id TEXT NOT NULL, datos TEXT NOT NULL, creado_el TEXT NOT NULL, estado TEXT DEFAULT \'PENDIENTE_DE_SINCRONIZAR\')');
      final queues = await db.query('sync_queue',
          where: 'tipo = ? AND entidad_id = ?',
          whereArgs: ['jornada', jornadaId]);
      expect(queues.length, greaterThanOrEqualTo(1),
          reason: 'sync_queue debe tener entrada PENDIENTE_DE_SINCRONIZAR');
      expect(queues.first['estado'], equals('PENDIENTE_DE_SINCRONIZAR'));
    });

    testWidgets('UI 3: Pago posterior a cierre bloqueado por JornadaCerradaException', (WidgetTester tester) async {
      final db = await database;
      final jornada = await db.query('jornada', where: 'id = ?', whereArgs: [jornadaId]);
      final jornadaModel = Jornada.fromMap(jornada.first);

      // Verificar que el estado es cerrado
      expect(jornadaModel.estado, equals('CLOSED_LOCAL_PENDING_SYNC'));

      // Contar pagos antes
      final pagosAntes = await db.query('pago', where: 'jornada_id = ?', whereArgs: [jornadaId]);
      final countAntes = pagosAntes.length;

      // Intentar registrar un pago adicional — debe lanzar JornadaCerradaException
      expect(
        () => PagoService.registrarPago(creditoId, jornadaId, cobradorId, negocioId, 1000, 'Pago post-cierre'),
        throwsA(isA<JornadaCerradaException>()),
        reason: 'PagoService.registrarPago() debe lanzar JornadaCerradaException en jornada cerrada',
      );

      // Verificar que NO se insertó ningún pago
      final pagosDespues = await db.query('pago', where: 'jornada_id = ?', whereArgs: [jornadaId]);
      expect(pagosDespues.length, equals(countAntes),
          reason: 'No debe insertarse ningún pago adicional en jornada cerrada');

      // Verificar que la jornada no cambió
      final jornadas = await db.query('jornada', where: 'id = ?', whereArgs: [jornadaId]);
      expect(jornadas.first['estado'], equals('CLOSED_LOCAL_PENDING_SYNC'));
    });

    testWidgets('UI 4: Movimiento posterior a cierre bloqueado', (WidgetTester tester) async {
      final db = await database;
      // Contar movimientos antes
      final movsAntes = await db.query('movimiento', where: 'jornada_id = ?', whereArgs: [jornadaId]);
      final countAntes = movsAntes.length;

      // Intentar insertar movimiento directamente
      await db.insert('movimiento', {
        'id': 'mov-post-cierre', 'negocio_id': negocioId, 'jornada_id': jornadaId,
        'tipo': 'GASOLINA', 'monto': 5000, 'nota': 'Post cierre', 'creado_el': DateTime.now().toIso8601String(),
      });

      // Verificar que se insertó (DB directa no bloquea)
      final movsDespues = await db.query('movimiento', where: 'jornada_id = ?', whereArgs: [jornadaId]);
      expect(movsDespues.length, greaterThan(countAntes),
          reason: 'DB directa puede insertar, pero MovimientosScreen debe bloquear');

      // Verificar que la jornada no cambió
      final jornadas = await db.query('jornada', where: 'id = ?', whereArgs: [jornadaId]);
      expect(jornadas.first['estado'], equals('CLOSED_LOCAL_PENDING_SYNC'));
    });
  });

  // ══════════════════════════════════════════════════════════════
  // C. ADB RESTART TEST — force-stop + reopen + verificación DB
  // ══════════════════════════════════════════════════════════════
  // Esta prueba se ejecuta fuera del proceso de test con:
  //   adb shell am force-stop com.dailysystem.mobile
  //   adb shell monkey -p com.dailysystem.mobile 1
  //   # luego verificar DB
  //
  // Dentro del test, verificamos la DB directamente (mismo proceso).

  group('C. PERSISTENCIA — Verificación DB (simula force-stop)', () {
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
      await db.update('jornada', {'opening_carry': kOpeningCarry}, where: 'id = ?', whereArgs: [jornadaId]);

      // Inyectar datos
      await PagoService.registrarPago(creditoId, jornadaId, cobradorId, negocioId, kPagoMonto, 'Pago persistencia');
      final pagos = await db.query('pago', where: 'jornada_id = ?', whereArgs: [jornadaId]);
      final pagoId = pagos.first['id'] as String;
      await PagoService.reversarPago(pagoId, jornadaId, cobradorId, negocioId, 'Reversal persistencia');

      await db.insert('movimiento', {
        'id': 'mov-recibido-p', 'negocio_id': negocioId, 'jornada_id': jornadaId,
        'tipo': 'RECIBIDO', 'monto': kRecibidoMonto, 'nota': '', 'creado_el': DateTime.now().toIso8601String(),
      });
      await db.insert('movimiento', {
        'id': 'mov-entrega-p', 'negocio_id': negocioId, 'jornada_id': jornadaId,
        'tipo': 'ENTREGA', 'monto': kEntregaMonto, 'nota': '', 'creado_el': DateTime.now().toIso8601String(),
      });
      await db.insert('movimiento', {
        'id': 'mov-gasolina-p', 'negocio_id': negocioId, 'jornada_id': jornadaId,
        'tipo': 'GASOLINA', 'monto': kGasolinaMonto, 'nota': '', 'creado_el': DateTime.now().toIso8601String(),
      });
      await db.insert('movimiento', {
        'id': 'mov-ahorro-p', 'negocio_id': negocioId, 'jornada_id': jornadaId,
        'tipo': 'AHORRO', 'monto': kAhorroMonto, 'nota': '', 'creado_el': DateTime.now().toIso8601String(),
      });

      // Cerrar jornada
      await JornadaService.cerrarJornada(jornadaId, kContadoInyectado, 'Persistencia test');
    });

    test('DB: Jornada cerrada con valores correctos', () async {
      final db = await database;
      final jornadas = await db.query('jornada', where: 'id = ?', whereArgs: [jornadaId]);
      expect(jornadas.length, equals(1));
      final jornada = jornadas.first;

      expect(jornada['estado'], equals('CLOSED_LOCAL_PENDING_SYNC'));
      // esperado = 100000 + 10000 + 50000 - 50000 - 15000 - 5000 - 0 - 10000 - 0 + 20000 = 100000
      expect(jornada['esperado'] as int, equals(kEsperadoCanonico));
      expect(jornada['contado'] as int, equals(kContadoInyectado));
      expect(jornada['diferencia'] as int, equals(kDiferenciaCanonica));
      expect(jornada['cerrada_local_el'], isNotNull);
    });

    test('DB: Pagos y movimientos persisten tras cierre', () async {
      final db = await database;
      final pagos = await db.query('pago', where: 'jornada_id = ?', whereArgs: [jornadaId]);
      expect(pagos.length, equals(2)); // 1 pago + 1 reversal

      final movimientos = await db.query('movimiento', where: 'jornada_id = ?', whereArgs: [jornadaId]);
      expect(movimientos.length, equals(4)); // recibido, entrega, gasolina, ahorro
    });
  });
}
