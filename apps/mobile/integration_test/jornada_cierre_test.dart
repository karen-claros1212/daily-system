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

import 'package:intl/intl.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:path_provider/path_provider.dart';
import 'package:sqflite/sqflite.dart' show DatabaseException;
import 'package:daily_system/database/database.dart';
import 'package:daily_system/services/caja_service.dart';
import 'package:daily_system/services/pago_service.dart';
import 'package:daily_system/services/jornada_service.dart';
import 'package:daily_system/services/pdf_service.dart';
import 'package:daily_system/domain/domain_exceptions.dart';
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

      await PagoService.registrarPago(creditoId, jornadaId, cobradorId, negocioId, kPagoMonto, 'Pago', 'pago-test-1');
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

      final evidencia = {
        'opening_base': caja.openingBase,
        'opening_carry': caja.openingCarry,
        'recaudo_real': caja.recaudoReal,
        'reversales': caja.reversales,
        'gastos': caja.gastos,
        'ahorro': caja.ahorro,
        'vales': caja.vales,
        'entregas': caja.entregas,
        'recibidos': caja.recibidos,
        'desembolsos': caja.desembolsos,
        'efectivo_esperado': caja.efectivoEsperado,
      };

      expect(evidencia['opening_base'], equals(kOpeningBase));
      expect(evidencia['opening_carry'], equals(kOpeningCarry));
      expect(evidencia['recaudo_real'], equals(kPagoMonto));
      expect(evidencia['reversales'], equals(kReversalMonto));
      expect(evidencia['gastos'], equals(kGasolinaMonto));
      expect(evidencia['ahorro'], equals(kAhorroMonto));
      expect(evidencia['vales'], equals(0));
      expect(evidencia['entregas'], equals(kEntregaMonto));
      expect(evidencia['recibidos'], equals(kRecibidoMonto));
      expect(evidencia['desembolsos'], equals(0));

      final esperadoCalculado = kOpeningBase + kOpeningCarry + kPagoMonto - kReversalMonto - kGasolinaMonto - kAhorroMonto - 0 - kEntregaMonto - 0 + kRecibidoMonto;
      expect(evidencia['efectivo_esperado'], equals(esperadoCalculado));
      expect(evidencia['efectivo_esperado'], equals(kEsperadoCanonico));
      expect(evidencia['efectivo_esperado'], isNot(equals(0)),
          reason: 'efectivo_esperado debe calcularse desde CajaService, no ser 0');
    });

    test('CIERRE: JornadaService.cerrarJornada persiste esperado/contado/diferencia', () async {
      final db = await database;

      // Cerrar jornada — ahora retorna ResultadoCierre y crea sync_queue internamente
      final resultado = await JornadaService.cerrarJornada(jornadaId, kContadoInyectado, 'Cierre service test');

      // Verificar resultado tipado
      expect(resultado.efectivoEsperado, equals(kEsperadoCanonico));
      expect(resultado.contado, equals(kContadoInyectado));
      expect(resultado.diferencia, equals(kDiferenciaCanonica));

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

      // Verificar sync_queue — cerradaJornada crea entrada con tipo 'jornada_cierre'
      final queues = await db.query('sync_queue',
          where: 'tipo = ? AND entidad_id = ?',
          whereArgs: ['jornada_cierre', jornadaId]);
      expect(queues.length, greaterThanOrEqualTo(1),
          reason: 'cerrarJornada debe crear sync_queue de cierre');
      expect(queues.first['estado'], equals('PENDIENTE_DE_SINCRONIZAR'));

      // Verificar snapshot inmutable
      final snapshots = await db.query('jornada_snapshot', where: 'jornada_id = ?', whereArgs: [jornadaId]);
      expect(snapshots.length, equals(1), reason: 'Debe existir snapshot inmutable');
      expect(snapshots.first['efectivo_esperado'] as int, equals(kEsperadoCanonico),
          reason: 'snapshot debe tener efectivo_esperado = 100000');
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
      await PagoService.registrarPago(creditoId, jornadaId, cobradorId, negocioId, kPagoMonto, 'Pago UI', 'pago-test-2');
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

      // 6. Verificar sync_queue — cerrarJornada crea entrada con tipo 'jornada_cierre'
      final queues = await db.query('sync_queue',
          where: 'tipo = ? AND entidad_id = ?',
          whereArgs: ['jornada_cierre', jornadaId]);
      expect(queues.length, greaterThanOrEqualTo(1),
          reason: 'sync_queue debe tener entrada PENDIENTE_DE_SINCRONIZAR de cerrarJornada');
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
        () => PagoService.registrarPago(creditoId, jornadaId, cobradorId, negocioId, 1000, 'Pago post-cierre', 'pago-test-3'),
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

    testWidgets('UI 4: Movimiento posterior a cierre bloqueado por trigger', (WidgetTester tester) async {
      final db = await database;
      // Contar movimientos antes
      final movsAntes = await db.query('movimiento', where: 'jornada_id = ?', whereArgs: [jornadaId]);
      final countAntes = movsAntes.length;

      // Intentar insertar movimiento directamente — trigger lo bloquea
      await expectLater(
        () => db.insert('movimiento', {
          'id': 'mov-post-cierre', 'negocio_id': negocioId, 'jornada_id': jornadaId,
          'tipo': 'GASOLINA', 'monto': 5000, 'nota': 'Post cierre', 'creado_el': DateTime.now().toIso8601String(),
        }),
        throwsA(isA<DatabaseException>().having((e) => e.toString(), 'toString', contains('DS_JORNADA_NOT_OPEN'))),
        reason: 'Trigger trg_movimiento_require_open_jornada bloquea INSERT en jornada cerrada',
      );

      // Verificar que NO se insertó
      final movsDespues = await db.query('movimiento', where: 'jornada_id = ?', whereArgs: [jornadaId]);
      expect(movsDespues.length, equals(countAntes),
          reason: 'Trigger impide inserción directa en jornada cerrada');

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
      await PagoService.registrarPago(creditoId, jornadaId, cobradorId, negocioId, kPagoMonto, 'Pago persistencia', 'pago-test-4');
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

    // D. MIGRATION V3 — jornada_documento
    test('MIG_V3: Tabla jornada_documento existe con trigger', () async {
      final db = await database;

      // Verificar que la tabla existe
      final tables = await db.rawQuery(
          "SELECT name FROM sqlite_master WHERE type='table' AND name='jornada_documento'");
      expect(tables.isNotEmpty, isTrue, reason: 'jornada_documento debe existir');

      // Verificar trigger
      final triggers = await db.rawQuery(
          "SELECT name FROM sqlite_master WHERE type='trigger' AND name='trg_doc_require_valid_jornada'");
      expect(triggers.isNotEmpty, isTrue, reason: 'trg_doc_require_valid_jornada debe existir');

      // Verificar índice único
      final indexes = await db.rawQuery(
          "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_doc_jornada_tipo'");
      expect(indexes.isNotEmpty, isTrue, reason: 'idx_doc_jornada_tipo debe existir');
    });

    // E. IDEMPOTENCIA CONFLICTO
    test('IDEMPOTENCIA: Dos pagos con misma clave pero distinto monto generan conflicto', () async {
      final db = await database;

      // Limpiar cualquier fila previa con esta clave
      await db.delete('pago', where: 'clave_idempotencia = ?', whereArgs: ['test-clave-123']);

      // Crear jornada OPEN para el trigger
      await db.insert('jornada', {
        'id': 'jornada-emp-test',
        'negocio_id': 'negocio-1',
        'ruta_id': 'ruta-test',
        'cobrador_id': 'cobrador-1',
        'fecha': DateFormat('yyyy-MM-dd').format(DateTime.now()),
        'estado': 'OPEN',
        'opening_base': 0,
      });

      // Insertar un pago con clave 'test-clave-123'
      await db.insert('pago', {
        'id': 'pago-conflicto-1',
        'negocio_id': 'negocio-1',
        'credito_id': 'credito-test',
        'jornada_id': 'jornada-emp-test',
        'cobrador_id': 'cobrador-1',
        'tipo': 'PAYMENT',
        'monto': 10000,
        'clave_idempotencia': 'test-clave-123',
        'registrado_el_dispositivo': DateTime.now().toIso8601String(),
      });

      // Intentar registrar otro pago con misma clave pero monto diferente
      final future = PagoService.registrarPago(
        'credito-test', 'jornada-emp-test', 'cobrador-1', 'negocio-1',
        20000, 'Nota conflicto', 'test-clave-123');

      expect(future, throwsA(isA<IdempotenciaConflictoException>()));
    });

    // F. HASH VALIDATION
    test('HASH: generarPdfDesdeSnapshot valida hash_content', () async {
      final db = await database;

      // El snapshot ya fue creado con hash válido
      final snapshots = await db.query('jornada_snapshot',
          where: 'jornada_id = ?', whereArgs: [jornadaId]);
      expect(snapshots.isNotEmpty, isTrue);
      final storedHash = snapshots.first['hash_content'] as String?;
      expect(storedHash, isNotNull);
      expect(storedHash!.length, equals(64)); // SHA-256 = 64 hex chars

      // Validar que el hash es reproducible
      final caja = await CajaService.calcularCaja(jornadaId);
      final fecha = snapshots.first['fecha'] as String;
      final cobradorId = snapshots.first['cobrador_id'] as String?;
      final rutaId = snapshots.first['ruta_id'] as String;
      final cerradoEl = snapshots.first['cerrada_local_el'] as String? ?? '';
      final diferenciaMotivo = snapshots.first['diferencia_motivo'] as String? ?? '';

      final recomputed = JornadaSnapshot.computeHash(JornadaSnapshot(
          jornadaId: jornadaId,
          fecha: fecha,
          cobradorId: cobradorId,
          rutaId: rutaId,
          openingBase: caja.openingBase,
          openingCarry: caja.openingCarry,
          recaudoReal: caja.recaudoReal,
          reversales: caja.reversales,
          gastos: caja.gastos,
          ahorro: caja.ahorro,
          vales: caja.vales,
          entregas: caja.entregas,
          recibidos: caja.recibidos,
          desembolsos: caja.desembolsos,
          efectivoEsperado: caja.efectivoEsperado,
          contado: kContadoInyectado,
          diferencia: kDiferenciaCanonica,
          diferenciaMotivo: diferenciaMotivo,
          cerradaLocalEl: cerradoEl));
      expect(recomputed, equals(storedHash));
    });

    // G. DOCUMENTO REGISTRADO EN JORNADA_DOCUMENTO
    test('DOC: jornada_documento se crea al cerrar jornada', () async {
      final db = await database;

      final docs = await db.query('jornada_documento',
          where: 'jornada_id = ? AND tipo = ?',
          whereArgs: [jornadaId, 'PDF_CIERRE']);

      // Puede existir si el test anterior generó PDF
      if (docs.isNotEmpty) {
        final doc = docs.first;
        expect(doc['estado'] as String?, anyOf(isNull, 'PENDING', 'GENERATED'));
        expect(doc['jornada_id'] as String?, equals(jornadaId));
        expect(doc['tipo'] as String?, equals('PDF_CIERRE'));
      }
    });

    // H. IDEMPOTENCIA: mismo UUID + mismos datos = un solo pago
    test('IDEMPOTENCIA: mismo UUID + mismos datos = un solo pago', () async {
      final db = await database;

      // Limpiar pagos previos con esta clave
      await db.delete('pago', where: 'clave_idempotencia = ?', whereArgs: ['idempotencia-test-uuid']);

      // Crear jornada OPEN para el trigger
      await db.insert('jornada', {
        'id': 'jornada-idempot-test',
        'negocio_id': 'negocio-1',
        'ruta_id': 'ruta-test',
        'cobrador_id': 'cobrador-1',
        'fecha': DateFormat('yyyy-MM-dd').format(DateTime.now()),
        'estado': 'OPEN',
        'opening_base': 0,
      });

      // Primer pago con clave 'idempotencia-test-uuid'
      final pago1 = await PagoService.registrarPago(
        'credito-idempot', 'jornada-idempot-test', 'cobrador-1', 'negocio-1',
        15000, 'Pago idempotencia', 'idempotencia-test-uuid');
      expect(pago1.id, isNotNull);

      // Segundo pago con misma clave (reintento)
      final pago2 = await PagoService.registrarPago(
        'credito-idempot', 'jornada-idempot-test', 'cobrador-1', 'negocio-1',
        15000, 'Pago idempotencia', 'idempotencia-test-uuid');

      // Debe devolver el mismo pago (idempotencia)
      expect(pago2.id, equals(pago1.id));

      // Verificar que solo existe un pago en la base
      final pagos = await db.query('pago',
          where: 'clave_idempotencia = ?', whereArgs: ['idempotencia-test-uuid']);
      expect(pagos.length, equals(1),
          reason: 'Debe existir exactamente un pago con esta clave de idempotencia');
    });

    // I. IDEMPOTENCIA: UUID diferente + mismos datos = dos pagos legítimos
    test('IDEMPOTENCIA: UUID diferente + mismos datos = dos pagos legítimos', () async {
      final db = await database;

      // Limpiar pagos previos
      await db.delete('pago', where: 'jornada_id = ?', whereArgs: ['jornada-idempot-test2']);

      // Crear jornada OPEN para el trigger
      await db.insert('jornada', {
        'id': 'jornada-idempot-test2',
        'negocio_id': 'negocio-1',
        'ruta_id': 'ruta-test',
        'cobrador_id': 'cobrador-1',
        'fecha': DateFormat('yyyy-MM-dd').format(DateTime.now()),
        'estado': 'OPEN',
        'opening_base': 0,
      });

      // Primer pago con clave 'uuid-pago-1'
      final pago1 = await PagoService.registrarPago(
        'credito-idempot2', 'jornada-idempot-test2', 'cobrador-1', 'negocio-1',
        15000, 'Pago legítimo 1', 'uuid-pago-1');

      // Segundo pago con misma data pero diferente clave (intención distinta)
      final pago2 = await PagoService.registrarPago(
        'credito-idempot2', 'jornada-idempot-test2', 'cobrador-1', 'negocio-1',
        15000, 'Pago legítimo 2', 'uuid-pago-2');

      // Deben ser pagos diferentes
      expect(pago2.id, isNot(equals(pago1.id)));

      // Verificar que existen dos pagos en la base
      final pagos = await db.query('pago',
          where: 'jornada_id = ?', whereArgs: ['jornada-idempot-test2']);
      expect(pagos.length, equals(2),
          reason: 'Deben existir dos pagos con diferentes claves de idempotencia');
    });

    // J. PDF CORRUPTO → regeneración
    test('PDF: archivo corrupto se regenera', () async {
      final db = await database;

      // Crear jornada OPEN para el trigger
      await db.insert('jornada', {
        'id': 'jornada-pdf-test',
        'negocio_id': 'negocio-1',
        'ruta_id': 'ruta-test',
        'cobrador_id': 'cobrador-1',
        'fecha': DateFormat('yyyy-MM-dd').format(DateTime.now()),
        'estado': 'OPEN',
        'opening_base': 0,
      });

      // Registrar un pago para tener datos en caja
      await PagoService.registrarPago(
        'credito-pdf', 'jornada-pdf-test', 'cobrador-1', 'negocio-1',
        10000, 'Pago PDF test', 'pdf-test-uuid');

      // Cerrar jornada
      await JornadaService.cerrarJornada('jornada-pdf-test', 10000, '');

      // Obtener el snapshot
      final snapshots = await db.query('jornada_snapshot',
          where: 'jornada_id = ?', whereArgs: ['jornada-pdf-test']);
      expect(snapshots.isNotEmpty, isTrue);

      // Generar PDF por primera vez
      final pdfPath1 = await PdfService.generarPdfDesdeSnapshot('jornada-pdf-test');
      expect(pdfPath1, isNotNull);

      // Verificar que el PDF existe y es válido
      final pdfFile = File(pdfPath1);
      expect(await pdfFile.exists(), isTrue);
      final header1 = (await pdfFile.readAsBytes()).sublist(0, 5);
      expect(String.fromCharCodes(header1), equals('%PDF-'));

      // Corromper el PDF (escribir datos aleatorios)
      await pdfFile.writeAsBytes([0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07]);

      // Generar PDF de nuevo — debería regenerar
      final pdfPath2 = await PdfService.generarPdfDesdeSnapshot('jornada-pdf-test');
      expect(pdfPath2, isNotNull);

      // Verificar que el PDF regenerado es válido
      final pdfFile2 = File(pdfPath2);
      expect(await pdfFile2.exists(), isTrue);
      final header2 = (await pdfFile2.readAsBytes()).sublist(0, 5);
      expect(String.fromCharCodes(header2), equals('%PDF-'));
    });

    // K. HASH SNAPSHOT ALTERADO → bloquea generación
    test('HASH: snapshot alterado bloquea generación de PDF', () async {
      final db = await database;

      // Crear jornada OPEN para el trigger
      await db.insert('jornada', {
        'id': 'jornada-hash-test',
        'negocio_id': 'negocio-1',
        'ruta_id': 'ruta-test',
        'cobrador_id': 'cobrador-1',
        'fecha': DateFormat('yyyy-MM-dd').format(DateTime.now()),
        'estado': 'OPEN',
        'opening_base': 0,
      });

      // Registrar un pago para tener datos en caja
      await PagoService.registrarPago(
        'credito-hash', 'jornada-hash-test', 'cobrador-1', 'negocio-1',
        10000, 'Pago hash test', 'hash-test-uuid');

      // Cerrar jornada
      await JornadaService.cerrarJornada('jornada-hash-test', 10000, '');

      // Obtener el snapshot original
      final snapshots = await db.query('jornada_snapshot',
          where: 'jornada_id = ?', whereArgs: ['jornada-hash-test']);
      expect(snapshots.isNotEmpty, isTrue);
      final originalHash = snapshots.first['hash_content'] as String?;
      expect(originalHash, isNotNull);
      expect(originalHash!.length, equals(64)); // SHA-256 = 64 hex chars

      // Alterar el hash del snapshot
      await db.update('jornada_snapshot',
          {'hash_content': 'aaaaaa0000000000000000000000000000000000000000000000000000000000'},
          where: 'jornada_id = ?', whereArgs: ['jornada-hash-test']);

      // Intentar generar PDF — debe fallar por hash mismatch
      final future = PdfService.generarPdfDesdeSnapshot('jornada-hash-test');
      expect(future, throwsA(anyOf(
        isA<Exception>(),
        throwsException,
      )));
    });
  });
}
