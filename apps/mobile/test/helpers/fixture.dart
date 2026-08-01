// ─── Test Fixture — real SQLite (FFI) + seeded data + open jornada ─
// Widget tests use sqflite_common_ffi so the real `database` singleton
// runs against a real SQLite file. Every test gets a fresh seeded DB
// with an open jornada, a registered payment and a gasto, plus the
// SharedPreferences values a real login would set.

import 'dart:io';

import 'package:daily_system/database/database.dart';
import 'package:daily_system/models/models.dart';
import 'package:daily_system/services/jornada_service.dart';
import 'package:daily_system/services/movimiento_service.dart';
import 'package:daily_system/services/pago_service.dart';
import 'package:path/path.dart' as p;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

const int kFixtureOpeningBase = 100000;
const int kFixturePagoMonto = 50000;
const int kFixtureGastoMonto = 15000;

class Fixture {
  final String cobradorId;
  final String cobradorNombre;
  final String negocioId;
  final String rutaId;
  final String rutaNombre;
  final String creditoId;
  final Jornada jornada;

  const Fixture({
    required this.cobradorId,
    required this.cobradorNombre,
    required this.negocioId,
    required this.rutaId,
    required this.rutaNombre,
    required this.creditoId,
    required this.jornada,
  });
}

/// Must be called before any use of `database` in the test process.
void initTestDatabase() {
  sqfliteFfiInit();
  databaseFactory = databaseFactoryFfiNoIsolate;
  databaseFactory.setDatabasesPath(
    p.join(Directory.systemTemp.createTempSync('daily_system_test').path,
        'databases'),
  );
}

/// Rebuilds the seeded DB and returns a fixture with a real open jornada,
/// one registered payment and one gasto. Also seeds SharedPreferences with
/// the session a login would produce.
Future<Fixture> crearFixture() async {
  await clearDatabase();

  final db = await database;

  final cobradores =
      await db.query('usuario', where: 'rol = ?', whereArgs: ['COBRADOR']);
  final cobradorId = Usuario.fromMap(cobradores.first).id;
  final cobradorNombre = cobradores.first['nombre'] as String;

  final negocios = await db.query('negocio', limit: 1);
  final negocioId = negocios.first['id'] as String;

  final rutas = await db.query('ruta', where: 'activa = ?', whereArgs: [1]);
  final rutaId = rutas.first['id'] as String;
  final rutaNombre = rutas.first['nombre'] as String;

  final creditos = await db.query('credito', limit: 1);
  final creditoId = creditos.first['id'] as String;

  final jornada = await JornadaService.abrirJornada(
      rutaId, cobradorId, negocioId, kFixtureOpeningBase);

  await PagoService.registrarPago(creditoId, jornada.id, cobradorId, negocioId,
      kFixturePagoMonto, 'Abono de prueba', 'fixture-pago-1');

  await MovimientoService.registrarMovimiento(
    jornadaId: jornada.id,
    tipo: 'GASOLINA',
    monto: kFixtureGastoMonto,
    nota: 'Combustible',
    cobradorId: cobradorId,
    negocioId: negocioId,
  );

  SharedPreferences.setMockInitialValues({
    'cobrador_id': cobradorId,
    'cobrador_nombre': cobradorNombre,
    'negocio_id': negocioId,
    'ruta_id': rutaId,
    'ruta_nombre': rutaNombre,
  });

  return Fixture(
    cobradorId: cobradorId,
    cobradorNombre: cobradorNombre,
    negocioId: negocioId,
    rutaId: rutaId,
    rutaNombre: rutaNombre,
    creditoId: creditoId,
    jornada: jornada,
  );
}
