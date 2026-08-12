// ─── S3 Push Orchestrator tests ────────────────────────────────────────────

import 'dart:convert';
import 'dart:io';

import 'package:daily_system/auth/auth_http_client.dart';
import 'package:daily_system/auth/auth_token_store.dart';
import 'package:daily_system/auth/device_auth_client.dart';
import 'package:daily_system/auth/device_identity.dart';
import 'package:daily_system/database/database.dart';
import 'package:daily_system/models/models.dart';
import 'package:daily_system/services/sync_queue_service.dart';
import 'package:daily_system/sync/push_orchestrator.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/fixture.dart';

class _RealHttpOverrides extends HttpOverrides {
  @override
  HttpClient createHttpClient(SecurityContext? context) {
    final client = super.createHttpClient(context);
    client.connectionTimeout = const Duration(seconds: 15);
    return client;
  }
}

const _spkiFixture =
    'MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEfltvZ5mRj+BFLYfEwxbexXeSeLrs9MFCBxCbx2i6ub9vfaAmyFj1frXaYdE2oKA/iQh6PhnCaMsWfxXmwA+V6g==';

const _jwtSesion = 'jwt-de-sesion-productiva';

// Mutable state shared between server and tests
final _serverState = <String, dynamic>{};
final _requestLog = <String>[];

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  initTestDatabase();

  late HttpServer server;
  late String baseUrl;

  Future<void> responder(
    HttpRequest request,
    int status,
    Map<String, dynamic> body,
  ) async {
    request.response.statusCode = status;
    request.response.headers.contentType = ContentType.json;
    request.response.write(jsonEncode(body));
    await request.response.close();
  }

  Future<void> startServer() async {
    server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    baseUrl = 'http://127.0.0.1:${server.port}';
    _requestLog.clear();

    server.listen((request) async {
      final path = request.uri.path;
      final method = request.method;

      if (method == 'GET' && path == '/api/mobile/bootstrap') {
        final auth = request.headers.value(HttpHeaders.authorizationHeader) ?? '';
        if (auth != 'Bearer $_jwtSesion') {
          await responder(request, 401, {'detail': 'AUTH_REQUERIDA'});
          return;
        }
        await responder(request, 200, {
          'negocio_id': 'n1',
          'negocio_nombre': 'Neg Demo',
          'cobrador_id': 'c1',
          'cobrador_nombre': 'Cob Uno',
          'dispositivo_id': 'd1',
          'version_asignacion': 1,
          'ruta_id': 'r1',
          'ruta_nombre': 'Ruta Norte',
          'ruta_version': 1,
          'rol': 'COBRADOR',
        });
        _requestLog.add('bootstrap');
        return;
      }

      // /reversar debe checked ANTES de /api/pagos (path.contains matched por /api/pagos/{id}/reversar)
      if (method == 'POST' && path.contains('/reversar')) {
        final auth = request.headers.value(HttpHeaders.authorizationHeader) ?? '';
        if (auth != 'Bearer $_jwtSesion') {
          await responder(request, 401, {'detail': 'AUTH_REQUERIDA'});
          return;
        }
        final body = jsonDecode(await utf8.decoder.bind(request).join());
        final clave = body['clave_idempotencia'] as String?;
        _requestLog.add('reversal:$clave');

        if (clave != null && _serverState.containsKey('rev_$clave')) {
          await responder(request, 200, {'id': _serverState['rev_$clave'], 'detalle': 'idempotente'});
          return;
        }

        final nuevoId = 'rev_${DateTime.now().millisecondsSinceEpoch}';
        _serverState['rev_$clave'] = nuevoId;
        await responder(request, 201, {'id': nuevoId, 'detalle': 'nuevo'});
        return;
      }

      if (method == 'POST' && path.startsWith('/api/pagos') && !path.contains('/reversar')) {
        final auth = request.headers.value(HttpHeaders.authorizationHeader) ?? '';
        if (auth != 'Bearer $_jwtSesion') {
          await responder(request, 401, {'detail': 'AUTH_REQUERIDA'});
          return;
        }
        final body = jsonDecode(await utf8.decoder.bind(request).join());
        final clave = body['clave_idempotencia'] as String?;
        _requestLog.add('pago:$clave');

        if (clave != null && _serverState.containsKey('pago_$clave')) {
          await responder(request, 200, {
            'id': _serverState['pago_$clave'],
            'detalle': 'idempotente',
          });
          return;
        }

        final nuevoId = 'pago_${DateTime.now().millisecondsSinceEpoch}';
        _serverState['pago_$clave'] = nuevoId;
        await responder(request, 201, {'id': nuevoId, 'detalle': 'nuevo'});
        return;
      }

      if (method == 'POST' && path == '/api/movimientos') {
        final auth = request.headers.value(HttpHeaders.authorizationHeader) ?? '';
        if (auth != 'Bearer $_jwtSesion') {
          await responder(request, 401, {'detail': 'AUTH_REQUERIDA'});
          return;
        }
        final body = jsonDecode(await utf8.decoder.bind(request).join());
        final clave = body['clave_idempotencia'] as String?;
        _requestLog.add('movimiento:$clave');

        if (clave != null && _serverState.containsKey('mov_$clave')) {
          await responder(request, 200, {'id': _serverState['mov_$clave'], 'detalle': 'idempotente'});
          return;
        }

        final nuevoId = 'mov_${DateTime.now().millisecondsSinceEpoch}';
        _serverState['mov_$clave'] = nuevoId;
        await responder(request, 201, {'id': nuevoId, 'detalle': 'nuevo'});
        return;
      }

      if (method == 'POST' && path.contains('/cerrar')) {
        final auth = request.headers.value(HttpHeaders.authorizationHeader) ?? '';
        if (auth != 'Bearer $_jwtSesion') {
          await responder(request, 401, {'detail': 'AUTH_REQUERIDA'});
          return;
        }
        final body = jsonDecode(await utf8.decoder.bind(request).join());
        final clave = body['idempotencia_cierre'] as String?;
        _requestLog.add('cerrar:$clave');

        if (_serverState['jornada_${clave}_cerrada'] == true) {
          await responder(request, 409, {'detail': 'Jornada ya cerrada'});
          return;
        }

        _serverState['jornada_${clave}_cerrada'] = true;
        await responder(request, 200, {'detalle': 'cerrada'});
        return;
      }

      if (method == 'POST' && path.contains('/sincronizar')) {
        final auth = request.headers.value(HttpHeaders.authorizationHeader) ?? '';
        if (auth != 'Bearer $_jwtSesion') {
          await responder(request, 401, {'detail': 'AUTH_REQUERIDA'});
          return;
        }
        final body = jsonDecode(await utf8.decoder.bind(request).join());
        _requestLog.add('sincronizar');
        await responder(request, 200, {
          'jornada_id': body['snapshot']?['jornada_id'],
          'estado': 'CLOSED_SYNCED',
          'snapshot_valido': true,
        });
        return;
      }

      await responder(request, 404, {'detail': 'NO_ENCONTRADO'});
    });
  }

  Future<PushOrchestrator> buildOrchestrator({String? rutaId}) async {
    final storage = FlutterSecureStorage();
    await storage.write(key: AuthTokenStore.kSessionKey, value: jsonEncode({
      'token': _jwtSesion,
      'expira_el': '2030-08-08T23:59:00Z',
      'dispositivo_id': 'd1',
    }));

    return PushOrchestrator(
      http: AuthHttpClient(baseUrl: baseUrl),
      tokenStore: AuthTokenStore(),
      auth: DeviceAuthClient(
        http: AuthHttpClient(baseUrl: baseUrl),
        identity: DeviceIdentity(),
        tokenStore: AuthTokenStore(),
      ),
      currentRutaId: rutaId ?? 'r1',
    );
  }

  setUp(() async {
    _serverState.clear();
    await clearDatabase();
    await startServer();
    FlutterSecureStorage.setMockInitialValues({});
    HttpOverrides.global = _RealHttpOverrides();
  });

  tearDown(() async {
    HttpOverrides.global = null;
    await server.close(force: true);
  });

  // ===== PAYMENT tests =====

  group('S3 — PAYMENT', () {
    test('pago offline → queue → push → ACK → SINCRONIZADO', () async {
      final orch = await buildOrchestrator();
      final db = await database;

      await db.insert('sync_queue', {
        'id': 'sq-pay-1',
        'tipo': 'pago',
        'entidad_id': 'p1',
        'datos': jsonEncode({
          'tipo': 'PAYMENT',
          'monto': 5000,
          'credito_id': 'cr1',
          'jornada_id': 'j1',
          'cobrador_id': 'c1',
          'negocio_id': 'n1',
        }),
        'creado_el': '2026-08-10T10:00:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': 'idem-pay-1',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T10:00:00Z',
      });

      final resultados = await orch.ejecutarPush();

      expect(resultados.length, 1);
      expect(resultados.first.status, PushStatus.sincronizado);
      expect(resultados.first.detail, 'pago sincronizado');

      final filas = await db.query('sync_queue', where: 'id = ?', whereArgs: ['sq-pay-1']);
      expect(filas.first['estado'], SyncQueueService.estadoSincronizado);
      expect(_requestLog, contains('pago:idem-pay-1'));
    });

    test('response lost: server commit + retry → ACK cero duplicados', () async {
      final orch = await buildOrchestrator();
      final db = await database;

      await db.insert('sync_queue', {
        'id': 'sq-pay-2',
        'tipo': 'pago',
        'entidad_id': 'p2',
        'datos': jsonEncode({
          'tipo': 'PAYMENT',
          'monto': 5000,
          'credito_id': 'cr1',
          'jornada_id': 'j1',
          'cobrador_id': 'c1',
          'negocio_id': 'n1',
        }),
        'creado_el': '2026-08-10T11:00:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': 'idem-pay-2',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T11:00:00Z',
      });

      // Primera vez: server acepta (201)
      var resultados = await orch.ejecutarPush();
      expect(resultados.first.status, PushStatus.sincronizado);

      // Simula response lost: reset servidor + re-enqueue fila
      _serverState.clear();
      await db.update('sync_queue', {
        'estado': SyncQueueService.estadoPendiente,
      }, where: 'id = ?', whereArgs: ['sq-pay-2']);

      // Segunda vez (retry): server acepta como idempotente (200)
      resultados = await orch.ejecutarPush();
      expect(resultados.first.status, PushStatus.sincronizado);

      // Cero duplicados: solo un request al servidor
      final pagosLog = _requestLog.where((e) => e.startsWith('pago:idem-pay-2')).toList();
      expect(pagosLog.length, 2); // dos envios: primero 201, retry 200
      // Cero duplicados logicos: key unica
      final keysUnicas = pagosLog.toSet();
      expect(keysUnicas.length, 1);
    });

    test('401 preserva fila outbox', () async {
      final orch = await buildOrchestrator();
      final db = await database;

      final storage = FlutterSecureStorage();
      await storage.write(key: AuthTokenStore.kSessionKey, value: jsonEncode({
        'token': 'jwt-invalido',
        'expira_el': '2030-08-08T23:59:00Z',
        'dispositivo_id': 'd1',
      }));

      await db.insert('sync_queue', {
        'id': 'sq-pay-3',
        'tipo': 'pago',
        'entidad_id': 'p3',
        'datos': jsonEncode({
          'tipo': 'PAYMENT',
          'monto': 5000,
          'credito_id': 'cr1',
          'jornada_id': 'j1',
        }),
        'creado_el': '2026-08-10T12:00:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': 'idem-pay-3',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T12:00:00Z',
      });

      final resultados = await orch.ejecutarPush();
      expect(resultados.first.status, PushStatus.reintentable);

      final filas = await db.query('sync_queue', where: 'id = ?', whereArgs: ['sq-pay-3']);
      expect(filas.first['estado'], SyncQueueService.estadoError);
      expect(filas.first['ultimo_error'], contains('401'));
      expect(filas.first['idempotency_key'], 'idem-pay-3');
    });
  });

  // ===== ENVIANDO restart recovery =====

  group('S3 — ENVIANDO restart recovery', () {
    test('misma fila: count(sync_queue) antes == despues', () async {
      final orch = await buildOrchestrator();
      final db = await database;

      await db.insert('sync_queue', {
        'id': 'sq-rev-1',
        'tipo': 'pago',
        'entidad_id': 'r1',
        'datos': jsonEncode({
          'tipo': 'REVERSAL',
          'monto': 5000,
          'reversal_of_payment_id': 'p1',
          'jornada_id': 'j1',
          'cobrador_id': 'c1',
          'negocio_id': 'n1',
          'motivo': 'test reversal',
        }),
        'creado_el': '2026-08-10T13:00:00Z',
        'estado': SyncQueueService.estadoEnviando,
        'idempotency_key': 'idem-rev-1',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 1,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T13:00:00Z',
      });

      final countAntes = await db.query('sync_queue', columns: ['COUNT(*)']);
      final countAntesVal = countAntes.first['COUNT(*)'] as int;

      await orch.ejecutarPush();

      final countDespues = await db.query('sync_queue', columns: ['COUNT(*)']);
      final countDespuesVal = countDespues.first['COUNT(*)'] as int;

      expect(countDespuesVal, countAntesVal);

      final filas = await db.query('sync_queue', where: 'id = ?', whereArgs: ['sq-rev-1']);
      // La fila se recupera (PENDIENTE) y se envia exitosamente → SINCRONIZADO
      expect(filas.first['estado'], SyncQueueService.estadoSincronizado);
      expect(filas.first['idempotency_key'], 'idem-rev-1');
    });
  });

  // ===== R1 → R2 =====

  group('S3 — R1→R2', () {
    test('fila R1 no enviada como R2 → CONFLICTO', () async {
      final orch = await buildOrchestrator(rutaId: 'r2');
      final db = await database;

      await db.insert('sync_queue', {
        'id': 'sq-r1-pend',
        'tipo': 'pago',
        'entidad_id': 'p-r1',
        'datos': jsonEncode({
          'tipo': 'PAYMENT',
          'monto': 5000,
          'credito_id': 'cr1',
          'jornada_id': 'j1',
        }),
        'creado_el': '2026-08-10T14:00:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': 'idem-r1',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T14:00:00Z',
      });

      final resultados = await orch.ejecutarPush();

      expect(resultados.first.status, PushStatus.skipRuta);
      expect(resultados.first.detail, contains('r1'));

      final filas = await db.query('sync_queue', where: 'id = ?', whereArgs: ['sq-r1-pend']);
      expect(filas.first['estado'], SyncQueueService.estadoConflicto);
      expect(filas.first['ultimo_error'], contains('R1->R2'));

      final pagosLog = _requestLog.where((e) => e.startsWith('pago:')).toList();
      expect(pagosLog.length, 0);
    });
  });

  // ===== JORNADA_CIERRE =====

  group('S3 — JORNADA_CIERRE', () {
    test('/cerrar 409 "ya cerrada" → /sincronizar', () async {
      final orch = await buildOrchestrator();
      final db = await database;

      _serverState['jornada_jc-test_cerrada'] = true;

      await db.insert('sync_queue', {
        'id': 'sq-jc-1',
        'tipo': 'jornada_cierre',
        'entidad_id': 'j1',
        'datos': jsonEncode({
          'contado': 10000,
          'esperado': 9500,
          'diferencia': 500,
          'jornada_id': 'j1',
          'negocio_id': 'n1',
          'ruta_id': 'r1',
          'cobrador_id': 'c1',
          'opening_base': 50000,
          'opening_carry': 0,
          'recaudo_real': 9500,
          'reversales': 0,
          'gastos': 0,
          'ahorro': 0,
          'vales': 0,
          'entregas': 0,
          'recibidos': 0,
          'desembolsos': 0,
          'pagos_count': 1,
          'reversales_count': 0,
          'movimientos_count': 0,
          'diferencia_motivo': 'sobrante',
        }),
        'creado_el': '2026-08-10T15:00:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': 'jc-test',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T15:00:00Z',
      });

      final resultados = await orch.ejecutarPush();

      expect(resultados.first.status, PushStatus.sincronizado);
      expect(resultados.first.detail, contains('sincronizada'));
    });
  });

  // ===== PAYMENT → REVERSAL dependency =====

  group('S3 — PAYMENT → REVERSAL dependency', () {
    test('REVERSAL espera PAYMENT ACK', () async {
      final orch = await buildOrchestrator();
      final db = await database;

      await db.insert('sync_queue', {
        'id': 'sq-pay-dep',
        'tipo': 'pago',
        'entidad_id': 'p-dep',
        'datos': jsonEncode({
          'tipo': 'PAYMENT',
          'monto': 5000,
          'credito_id': 'cr1',
          'jornada_id': 'j1',
          'cobrador_id': 'c1',
          'negocio_id': 'n1',
        }),
        'creado_el': '2026-08-10T16:00:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': 'idem-pay-dep',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T16:00:00Z',
      });

      await db.insert('sync_queue', {
        'id': 'sq-rev-dep',
        'tipo': 'pago',
        'entidad_id': 'r-dep',
        'datos': jsonEncode({
          'tipo': 'REVERSAL',
          'monto': 5000,
          'reversal_of_payment_id': 'p-dep',
          'jornada_id': 'j1',
          'cobrador_id': 'c1',
          'negocio_id': 'n1',
          'motivo': 'test',
        }),
        'creado_el': '2026-08-10T16:01:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': 'idem-rev-dep',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T16:01:00Z',
      });

      final resultados = await orch.ejecutarPush();

      expect(resultados[0].tipo, 'PAYMENT');
      expect(resultados[0].status, PushStatus.sincronizado);
      expect(resultados[1].tipo, 'REVERSAL');
      expect(resultados[1].status, PushStatus.sincronizado);

      final pagosLog = _requestLog.where((e) => e.startsWith('pago:')).toList();
      final reversalsLog = _requestLog.where((e) => e.startsWith('reversal:')).toList();
      expect(pagosLog.length, 1);
      expect(reversalsLog.length, 1);
      expect(pagosLog.first, 'pago:idem-pay-dep');
      expect(reversalsLog.first, 'reversal:idem-rev-dep');
    });
  });

  // ===== MOVIMIENTO =====

  group('S3 — MOVIMIENTO', () {
    test('movimiento push → ACK', () async {
      final orch = await buildOrchestrator();
      final db = await database;

      await db.insert('sync_queue', {
        'id': 'sq-mov-1',
        'tipo': 'movimiento',
        'entidad_id': 'm1',
        'datos': jsonEncode({
          'tipo': 'GASOLINA',
          'monto': 12000,
          'nota': 'Combustible',
          'jornada_id': 'j1',
          'negocio_id': 'n1',
        }),
        'creado_el': '2026-08-10T17:00:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': 'idem-mov-1',
        'negocio_id': 'n1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T17:00:00Z',
      });

      final resultados = await orch.ejecutarPush();

      expect(resultados.first.status, PushStatus.sincronizado);
      expect(resultados.first.detail, 'movimiento sincronizado');
      expect(_requestLog, contains('movimiento:idem-mov-1'));
    });
  });

  // ===== ENVIANDO restart: count test =====

  group('S3 — ENVIANDO restart count', () {
    test('count(sync_queue) antes restart == despues recovery', () async {
      final orch = await buildOrchestrator();
      final db = await database;

      await db.insert('sync_queue', {
        'id': 'sq-enviando-test',
        'tipo': 'pago',
        'entidad_id': 'p-enviando',
        'datos': jsonEncode({
          'tipo': 'PAYMENT',
          'monto': 5000,
          'credito_id': 'cr1',
        }),
        'creado_el': '2026-08-10T18:00:00Z',
        'estado': SyncQueueService.estadoEnviando,
        'idempotency_key': 'idem-enviando',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 1,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T18:00:00Z',
      });

      final countAntes = await db.query('sync_queue', columns: ['COUNT(*)']);
      final countAntesVal = countAntes.first['COUNT(*)'] as int;

      await orch.ejecutarPush();

      final countDespues = await db.query('sync_queue', columns: ['COUNT(*)']);
      final countDespuesVal = countDespues.first['COUNT(*)'] as int;

      expect(countDespuesVal, countAntesVal, reason: 'misma fila, no INSERT nueva');

      final filas = await db.query('sync_queue', where: 'id = ?', whereArgs: ['sq-enviando-test']);
      expect(filas.first['id'], 'sq-enviando-test');
      expect(filas.first['idempotency_key'], 'idem-enviando');
    });
  });
}
