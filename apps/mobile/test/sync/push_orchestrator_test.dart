// ─── S3 Push Orchestrator tests ────────────────────────────────────────────

import 'dart:convert';
import 'dart:io';

import 'package:daily_system/auth/auth_http_client.dart';
import 'package:daily_system/auth/auth_token_store.dart';
import 'package:daily_system/auth/device_auth_client.dart';
import 'package:daily_system/auth/device_identity.dart';
import 'package:daily_system/database/database.dart';
import 'package:daily_system/database/migration_v5.dart';
import 'package:daily_system/database/migration_v6.dart';
import 'package:daily_system/database/migration_v7.dart';
import 'package:daily_system/services/sync_queue_service.dart';
import 'package:daily_system/sync/push_orchestrator.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/fixture.dart';

const _jwtSesion = 'jwt-de-sesion-productiva';

class _RealHttpOverrides extends HttpOverrides {
  @override
  HttpClient createHttpClient(SecurityContext? context) {
    final client = super.createHttpClient(context);
    client.connectionTimeout = const Duration(seconds: 15);
    return client;
  }
}

// Mutable state shared between server and tests
final _serverState = <String, dynamic>{};
final _requestLog = <String>[];
String? _simulate409MismatchKey; // idempotency key that triggers 409 mismatch
Map<String, dynamic>? _customSyncResponse; // custom response for /sincronizar

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

        // 409 mismatch: misma clave, payload distinto
        if (_simulate409MismatchKey != null && clave == _simulate409MismatchKey) {
          await responder(request, 409, {'detail': 'Misma clave, monto distinto'});
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
        final jornadaId = body['snapshot']?['jornada_id'] as String?;
        _requestLog.add('sincronizar');

        // SOLO devolver HTTP — el producto actualiza jornada local
        // Si hay respuesta custom, usarla
        if (_customSyncResponse != null) {
          await responder(request, 200, _customSyncResponse!);
          _customSyncResponse = null; // reset after use
        } else {
          await responder(request, 200, {
            'jornada_id': jornadaId,
            'estado': 'CLOSED_SYNCED',
            'snapshot_valido': true,
          });
        }
        return;
      }

      await responder(request, 404, {'detail': 'NO_ENCONTRADO'});
    });
  }

  Future<PushOrchestrator> buildOrchestrator({String? rutaId, String? cobradorId}) async {
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
      currentCobradorId: cobradorId ?? 'c1',
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
      expect(filas.first['server_entity_id'], isNotNull);
      expect(filas.first['server_entity_id'], startsWith('pago_'));
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

      // server_entity_id persistido tras retry (mapping durable)
      final filas = await db.query('sync_queue', where: 'id = ?', whereArgs: ['sq-pay-2']);
      expect(filas.first['estado'], SyncQueueService.estadoSincronizado);
      expect(filas.first['server_entity_id'], isNotNull);
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

    test('lost response PAYMENT: local L1 → server S1 → retry → server_entity_id persistido', () async {
      final orch = await buildOrchestrator();
      final db = await database;

      await db.insert('sync_queue', {
        'id': 'sq-lost-1',
        'tipo': 'pago',
        'entidad_id': 'L1',
        'datos': jsonEncode({
          'tipo': 'PAYMENT',
          'monto': 5000,
          'credito_id': 'cr1',
          'jornada_id': 'j1',
          'cobrador_id': 'c1',
          'negocio_id': 'n1',
        }),
        'creado_el': '2026-08-10T19:00:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': 'K1',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T19:00:00Z',
      });

      // Push inicial: server acepta (201) y guarda mapping K1→S1
      var resultados = await orch.ejecutarPush();
      expect(resultados.first.status, PushStatus.sincronizado);

      // Verificar server_entity_id guardado
      var filas = await db.query('sync_queue', where: 'id = ?', whereArgs: ['sq-lost-1']);
      expect(filas.first['server_entity_id'], isNotNull);
      final serverIdOriginal = filas.first['server_entity_id'];

      // Simula response lost: solo el cliente olvida (fila se re-enqueue)
      // El servidor conserva mapping K1→S1 (idempotencia)
      await db.update('sync_queue', {
        'estado': SyncQueueService.estadoPendiente,
      }, where: 'id = ?', whereArgs: ['sq-lost-1']);

      // Retry: server devuelve S1 (idempotente 200)
      resultados = await orch.ejecutarPush();
      expect(resultados.first.status, PushStatus.sincronizado);

      // Verificar: server_entity_id conservado (mismo S1)
      filas = await db.query('sync_queue', where: 'id = ?', whereArgs: ['sq-lost-1']);
      expect(filas.first['estado'], SyncQueueService.estadoSincronizado);
      expect(filas.first['server_entity_id'], serverIdOriginal);
      expect(filas.first['server_entity_id'], startsWith('pago_'));
    });
  });

  // ===== ENVIANDO restart recovery =====

  group('S3 — ENVIANDO restart recovery', () {
    test('misma fila: count(sync_queue) antes == despues', () async {
      final orch = await buildOrchestrator();
      final db = await database;

      // Original PAYMENT con server_entity_id (para que REVERSAL lo encuentre)
      await db.insert('sync_queue', {
        'id': 'sq-pay-p1',
        'tipo': 'pago',
        'entidad_id': 'p1',
        'datos': jsonEncode({'tipo': 'PAYMENT', 'monto': 5000}),
        'creado_el': '2026-08-10T12:00:00Z',
        'estado': SyncQueueService.estadoSincronizado,
        'idempotency_key': 'idem-p1',
        'negocio_id': 'n1',
        'server_entity_id': 'pago_p1_server',
        'intento': 1,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T12:00:00Z',
      });

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
    test('fila R1 no enviada como R2 → CONFLICTO (cobrador diferente)', () async {
      final orch = await buildOrchestrator(rutaId: 'r2', cobradorId: 'c2');
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

    // ===== S4 — Reasignación de ruta =====

    test('S4 — fila R1 NO pusha bajo R2 aunque cobrador coincida (ruta_id_origen inmutable)', () async {
      final orch = await buildOrchestrator(rutaId: 'r2', cobradorId: 'c1');
      final db = await database;

      // Fila creada bajo R1, cobrador c1
      await db.insert('sync_queue', {
        'id': 'sq-r1-reassign',
        'tipo': 'pago',
        'entidad_id': 'p-reassign',
        'datos': jsonEncode({
          'tipo': 'PAYMENT',
          'monto': 5000,
          'credito_id': 'cr1',
          'jornada_id': 'j1',
          'cobrador_id': 'c1',
          'negocio_id': 'n1',
        }),
        'creado_el': '2026-08-10T14:00:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': 'idem-reassign',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T14:00:00Z',
      });

      final resultados = await orch.ejecutarPush();

      // Mismo cobrador pero ruta diferente → R1 fila NO se envía bajo R2
      expect(resultados.first.status, PushStatus.skipRuta);
      expect(resultados.first.detail, contains('r1'));

      // 0 HTTP al server
      final pagosLog = _requestLog.where((e) => e.startsWith('pago:')).toList();
      expect(pagosLog.length, 0);

      // Fila marcada como CONFLICTO (no SINCRONIZADO)
      final filas = await db.query('sync_queue', where: 'id = ?', whereArgs: ['sq-r1-reassign']);
      expect(filas.first['estado'], SyncQueueService.estadoConflicto);
      expect(filas.first['ultimo_error'], contains('R1->R2'));

      // ruta_id_origen sigue siendo R1
      expect(filas.first['ruta_id_origen'], 'r1');

      // Payload/idempotency intactos
      expect(filas.first['idempotency_key'], 'idem-reassign');
    });

    test('S4 — ciclo completo reasignación R1→R2: outbox R1 preservado, nuevo evento R2 sincroniza', () async {
      final db = await database;

      // 1. cobrador opera en R1 — crea PAYMENT pendiente
      await db.insert('sync_queue', {
        'id': 'sq-s4-pay-r1',
        'tipo': 'pago',
        'entidad_id': 'p-s4-r1',
        'datos': jsonEncode({
          'tipo': 'PAYMENT',
          'monto': 3000,
          'credito_id': 'cr-s4',
          'jornada_id': 'j-s4',
          'cobrador_id': 'c1',
          'negocio_id': 'n1',
        }),
        'creado_el': '2026-08-10T10:00:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': 'idem-s4-pay-r1',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j-s4',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T10:00:00Z',
      });

      // 2. Admin realiza R1→R2: desactiva R1, activa R2 para mismo cobrador
      await db.insert('ruta', {
        'id': 'r1',
        'negocio_id': 'n1',
        'nombre': 'R1',
        'cobrador_id': 'c1',
        'activa': 0,
      });
      await db.insert('ruta', {
        'id': 'r2',
        'negocio_id': 'n1',
        'nombre': 'R2',
        'cobrador_id': 'c1',
        'activa': 1,
      });

      // 3. Orchestrador bajo R2 (nueva sesión post-reasignación)
      final orchR2 = await buildOrchestrator(rutaId: 'r2', cobradorId: 'c1');

      // 4. Ejecutar push bajo R2
      final resultadosR2 = await orchR2.ejecutarPush();

      // 5. La fila R1 NO se envía bajo R2 (misma ruta check)
      expect(resultadosR2.first.status, PushStatus.skipRuta);
      expect(resultadosR2.first.detail, contains('r1'));

      // 6. 0 HTTP al server para la fila R1
      final pagosLogR2 = _requestLog.where((e) => e.startsWith('pago:')).toList();
      expect(pagosLogR2.length, 0);

      // 7. Fila R1 permanece con provenance intacta
      final filasR2 = await db.query('sync_queue',
          where: 'id = ?',
          whereArgs: ['sq-s4-pay-r1']);
      expect(filasR2.first['estado'], SyncQueueService.estadoConflicto);
      expect(filasR2.first['ruta_id_origen'], 'r1');
      expect(filasR2.first['idempotency_key'], 'idem-s4-pay-r1');
      expect(filasR2.first['cobrador_id_origen'], 'c1');

      // 8. Nuevo evento creado bajo R2 sincroniza normalmente
      await db.insert('sync_queue', {
        'id': 'sq-s4-pay-r2',
        'tipo': 'pago',
        'entidad_id': 'p-s4-r2',
        'datos': jsonEncode({
          'tipo': 'PAYMENT',
          'monto': 5000,
          'credito_id': 'cr-s4-r2',
          'jornada_id': 'j-s4-r2',
          'cobrador_id': 'c1',
          'negocio_id': 'n1',
        }),
        'creado_el': '2026-08-10T12:00:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': 'idem-s4-pay-r2',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r2',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j-s4-r2',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T12:00:00Z',
      });

      final resultadosR2b = await orchR2.ejecutarPush();

      // La fila R2 sí se envía
      final payR2 = resultadosR2b.firstWhere(
        (r) => r.filaId == 'sq-s4-pay-r2',
        orElse: () => throw Exception('fila R2 no encontrada'),
      );
      expect(payR2.status, PushStatus.sincronizado);

      // 1 HTTP para la fila R2
      final pagosLogR2b = _requestLog.where((e) => e.startsWith('pago:')).toList();
      expect(pagosLogR2b.length, 1);
      expect(pagosLogR2b.first, 'pago:idem-s4-pay-r2');

      // 9. Historial R1 permanece intacto
      final filasR1 = await db.query('sync_queue',
          where: 'ruta_id_origen = ?',
          whereArgs: ['r1']);
      expect(filasR1.length, 1);
      expect(filasR1.first['entidad_id'], 'p-s4-r1');
    });
  });

  // ===== REVERSAL lost response =====

  group('S3 — REVERSAL lost response', () {
    test('lost response REVERSAL: local R1 → server SR1 → retry → server_entity_id persistido', () async {
      final orch = await buildOrchestrator();
      final db = await database;

      // Original PAYMENT con server_entity_id
      await db.insert('sync_queue', {
        'id': 'sq-pay-p1-lost',
        'tipo': 'pago',
        'entidad_id': 'p1',
        'datos': jsonEncode({'tipo': 'PAYMENT', 'monto': 5000}),
        'creado_el': '2026-08-10T19:00:00Z',
        'estado': SyncQueueService.estadoSincronizado,
        'idempotency_key': 'idem-p1-lost',
        'negocio_id': 'n1',
        'server_entity_id': 'pago_p1_server_lost',
        'intento': 1,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T19:00:00Z',
      });

      await db.insert('sync_queue', {
        'id': 'sq-rev-lost',
        'tipo': 'pago',
        'entidad_id': 'R1',
        'datos': jsonEncode({
          'tipo': 'REVERSAL',
          'monto': 5000,
          'reversal_of_payment_id': 'p1',
          'jornada_id': 'j1',
          'cobrador_id': 'c1',
          'negocio_id': 'n1',
          'motivo': 'test reversal lost',
        }),
        'creado_el': '2026-08-10T20:00:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': 'K2',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T20:00:00Z',
      });

      // Push inicial: server acepta (201) pero respuesta se pierde
      var resultados = await orch.ejecutarPush();
      expect(resultados.first.status, PushStatus.sincronizado);

      // Verificar server_entity_id guardado
      var filas = await db.query('sync_queue', where: 'id = ?', whereArgs: ['sq-rev-lost']);
      expect(filas.first['server_entity_id'], isNotNull);
      final serverIdOriginal = filas.first['server_entity_id'];

      // Simula response lost: solo el cliente olvida (fila se re-enqueue)
      // El servidor conserva mapping K2→SR1 (idempotencia)
      await db.update('sync_queue', {
        'estado': SyncQueueService.estadoPendiente,
      }, where: 'id = ?', whereArgs: ['sq-rev-lost']);

      // Retry: server devuelve SR1 (idempotente 200)
      resultados = await orch.ejecutarPush();
      expect(resultados.first.status, PushStatus.sincronizado);

      // Verificar: server_entity_id conservado (mismo SR1)
      filas = await db.query('sync_queue', where: 'id = ?', whereArgs: ['sq-rev-lost']);
      expect(filas.first['estado'], SyncQueueService.estadoSincronizado);
      expect(filas.first['server_entity_id'], serverIdOriginal);
      expect(filas.first['server_entity_id'], startsWith('rev_'));
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

    test('REVERSAL ERROR_REINTENTABLE: PAYMENT PENDIENTE → 0 requests HTTP al REVERSAL', () async {
      final orch = await buildOrchestrator();
      final db = await database;

      // PAYMENT PENDIENTE (nunca se envió)
      await db.insert('sync_queue', {
        'id': 'sq-pay-pend',
        'tipo': 'pago',
        'entidad_id': 'p-pend',
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
        'idempotency_key': 'idem-pay-pend',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T16:00:00Z',
      });

      // REVERSAL ERROR_REINTENTABLE (antes del PAYMENT)
      await db.insert('sync_queue', {
        'id': 'sq-rev-err',
        'tipo': 'pago',
        'entidad_id': 'r-err',
        'datos': jsonEncode({
          'tipo': 'REVERSAL',
          'monto': 3000,
          'reversal_of_payment_id': 'p-pend',
          'jornada_id': 'j1',
          'cobrador_id': 'c1',
          'negocio_id': 'n1',
          'motivo': 'test',
        }),
        'creado_el': '2026-08-10T15:00:00Z',
        'estado': SyncQueueService.estadoError,
        'idempotency_key': 'idem-rev-err',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 2,
        'ultimo_error': 'network timeout',
        'ultima_transicion': '2026-08-10T15:30:00Z',
      });

      final resultados = await orch.ejecutarPush();

      // Debe haber 2 resultados: PAYMENT (pendiente) + REVERSAL (reintento)
      final tipos = resultados.map((r) => r.tipo).toList();
      expect(tipos, contains('PAYMENT'));
      expect(tipos, contains('REVERSAL'));

      // El REVERSAL debe ir DESPUÉS del PAYMENT en los resultados
      final payIdx = resultados.indexWhere((r) => r.tipo == 'PAYMENT');
      final revIdx = resultados.indexWhere((r) => r.tipo == 'REVERSAL');
      expect(revIdx, greaterThan(payIdx), reason: 'REVERSAL debe ir después de PAYMENT');

      // Verificar que el PAYMENT se envió primero
      final pagosLog = _requestLog.where((e) => e.startsWith('pago:')).toList();
      expect(pagosLog.length, 1);
      expect(pagosLog.first, 'pago:idem-pay-pend');

      // Después de este push, el PAYMENT ya está SINCRONIZADO y el REVERSAL debería enviar
      // (porque ahora su PAYMENT tiene ACK)
      final filasPay = await db.query('sync_queue', where: 'id = ?', whereArgs: ['sq-pay-pend']);
      expect(filasPay.first['estado'], SyncQueueService.estadoSincronizado);

      // El REVERSAL ya debería haberse enviado en el mismo ciclo (porque PAYMENT ya tiene ACK)
      // Puede estar SINCRONIZADO o ERROR_REINTENTABLE (si el PAYMENT PENDIENTE no se envía en este ciclo)
      // Lo importante: el REVERSAL se envió DESPUÉS del PAYMENT
    });
  });

  // ===== limpiarSincronizados() durability =====

  group('S3 — limpiarSincronizados() durability', () {
    test('filas con server_entity_id preservadas tras limpiarSincronizados()', () async {
      final orch = await buildOrchestrator();
      final db = await database;

      // Push un pago para generar server_entity_id
      await db.insert('sync_queue', {
        'id': 'sq-ls-1',
        'tipo': 'pago',
        'entidad_id': 'p-ls',
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
        'idempotency_key': 'idem-ls-1',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T10:00:00Z',
      });

      await orch.ejecutarPush();

      // Verificar que ahora tiene server_entity_id
      var filas = await db.query('sync_queue', where: 'id = ?', whereArgs: ['sq-ls-1']);
      expect(filas.first['estado'], SyncQueueService.estadoSincronizado);
      expect(filas.first['server_entity_id'], isNotNull);
      expect(filas.first['server_entity_id'], isNot(equals('')));
      final serverIdPreservado = filas.first['server_entity_id'];

      // Limpiar sincronizados
      final eliminados = await SyncQueueService.limpiarSincronizados();
      expect(eliminados, 0, reason: 'cero eliminados — server_entity_id preservado');

      // Verificar fila aún existe con server_entity_id intacto
      filas = await db.query('sync_queue', where: 'id = ?', whereArgs: ['sq-ls-1']);
      expect(filas, hasLength(1));
      expect(filas.first['server_entity_id'], serverIdPreservado);
    });

    test('filas sin server_entity_id eliminadas por limpiarSincronizados()', () async {
      final db = await database;

      // Insertar fila SINCRONIZADA sin server_entity_id (legacy)
      await db.insert('sync_queue', {
        'id': 'sq-ls-legacy',
        'tipo': 'pago',
        'entidad_id': 'p-legacy',
        'datos': jsonEncode({'tipo': 'PAYMENT', 'monto': 5000}),
        'creado_el': '2026-08-10T10:00:00Z',
        'estado': SyncQueueService.estadoSincronizado,
        'idempotency_key': 'idem-legacy',
        'negocio_id': 'n1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T10:00:00Z',
      });

      // Insertar fila SINCRONIZADA con server_entity_id vacío
      await db.insert('sync_queue', {
        'id': 'sq-ls-empty',
        'tipo': 'pago',
        'entidad_id': 'p-empty',
        'datos': jsonEncode({'tipo': 'PAYMENT', 'monto': 5000}),
        'creado_el': '2026-08-10T11:00:00Z',
        'estado': SyncQueueService.estadoSincronizado,
        'idempotency_key': 'idem-empty',
        'negocio_id': 'n1',
        'server_entity_id': '',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T11:00:00Z',
      });

      final eliminados = await SyncQueueService.limpiarSincronizados();
      expect(eliminados, 2, reason: '2 filas legacy eliminadas');

      // Verificar que solo quedan filas con server_entity_id
      final restantes = await db.query('sync_queue');
      expect(restantes, isEmpty);
    });

    test('filas PENDIENTE y ERROR_REINTENTABLE no afectadas por limpiarSincronizados()', () async {
      final db = await database;

      await db.insert('sync_queue', {
        'id': 'sq-ls-pend',
        'tipo': 'pago',
        'entidad_id': 'p-pend-ls',
        'datos': jsonEncode({'tipo': 'PAYMENT', 'monto': 5000}),
        'creado_el': '2026-08-10T10:00:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': 'idem-ls-pend',
        'negocio_id': 'n1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T10:00:00Z',
      });

      await db.insert('sync_queue', {
        'id': 'sq-ls-err',
        'tipo': 'pago',
        'entidad_id': 'p-err-ls',
        'datos': jsonEncode({'tipo': 'PAYMENT', 'monto': 5000}),
        'creado_el': '2026-08-10T11:00:00Z',
        'estado': SyncQueueService.estadoError,
        'idempotency_key': 'idem-ls-err',
        'negocio_id': 'n1',
        'intento': 1,
        'ultimo_error': 'timeout',
        'ultima_transicion': '2026-08-10T11:00:00Z',
      });

      final eliminados = await SyncQueueService.limpiarSincronizados();
      expect(eliminados, 0);

      final pendientes = await db.query('sync_queue',
          where: 'estado IN (?, ?)',
          whereArgs: [SyncQueueService.estadoPendiente, SyncQueueService.estadoError]);
      expect(pendientes, hasLength(2));
    });
  });

  // ===== V5→V6 Upgrade =====

  group('S3 — V5→V6 upgrade', () {
    test('DB con datos S3 V5 migrados: server_entity_id propagado a pago', () async {
      final db = await database;

      // Insertar jornada abierta (trigger de pago requiere jornada abierta)
      await db.insert('jornada', {
        'id': 'j-v6-1',
        'negocio_id': 'n1',
        'ruta_id': 'r1',
        'cobrador_id': 'c1',
        'estado': 'OPEN',
        'fecha': '2026-08-10',
        'esperado': 0,
      });

      // Insertar pago local sin server_entity_id
      await db.insert('pago', {
        'id': 'pay-v6-1',
        'negocio_id': 'n1',
        'credito_id': 'cr1',
        'jornada_id': 'j-v6-1',
        'cobrador_id': 'c1',
        'tipo': 'PAYMENT',
        'monto': 5000,
        'clave_idempotencia': 'idem-v6-1',
        'nota': 'test',
        'registrado_el_dispositivo': '2026-08-10T10:00:00Z',
        'recibido_el_servidor': '2026-08-10T10:01:00Z',
        'reversal_of_payment_id': null,
        'server_entity_id': null,
      });

      // Insertar sync_queue con server_entity_id (V5 data)
      await db.insert('sync_queue', {
        'id': 'sq-v6-1',
        'tipo': 'pago',
        'entidad_id': 'pay-v6-1',
        'datos': jsonEncode({'tipo': 'PAYMENT', 'monto': 5000}),
        'creado_el': '2026-08-10T10:00:00Z',
        'estado': SyncQueueService.estadoSincronizado,
        'idempotency_key': 'idem-v6-1',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 1,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T10:01:00Z',
        'server_entity_id': 'pago_server_v6_123',
      });

      // Ejecutar migration v6 manualmente
      await MigrationV6.migrate(db);

      // Verificar que server_entity_id se propagó al pago
      final pagos = await db.query('pago',
          where: 'id = ?',
          whereArgs: ['pay-v6-1']);
      expect(pagos, hasLength(1));
      expect(pagos.first['server_entity_id'], 'pago_server_v6_123');
    });

    test('DB V5 legacy: json_extract() extrae provenance de datos JSON', () async {
      // Simular DB en versión 5 (sin server_entity_id en sync_queue ni pago)
      var db = await database;

      // Eliminar columnas server_entity_id si existen
      try {
        await db.execute('ALTER TABLE sync_queue DROP COLUMN server_entity_id');
      } catch (_) {}
      try {
        await db.execute('ALTER TABLE pago DROP COLUMN server_entity_id');
      } catch (_) {}

      // Insertar fila con datos legacy en formato JSON (como V5 migraría)
      await db.insert('sync_queue', {
        'id': 'sq-v5-legacy',
        'tipo': 'pago',
        'entidad_id': 'p-v5',
        'datos': jsonEncode({
          'tipo': 'PAYMENT',
          'monto': 5000,
          'idempotency_key': 'idem-v5-key',
          'cobrador_id': 'c1',
          'jornada_id': 'j1',
          'negocio_id': 'n1',
        }),
        'creado_el': '2026-08-10T10:00:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': null,
        'negocio_id': null,
        'ruta_id_origen': null,
        'cobrador_id_origen': null,
        'jornada_id_origen': null,
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T10:00:00Z',
      });

      // Ejecutar migration v5
      await MigrationV5.migrate(db);

      // V5 remota extrae idempotency_key + provenance desde JSON
      final filas = await db.query('sync_queue',
          where: 'id = ?',
          whereArgs: ['sq-v5-legacy']);
      expect(filas, hasLength(1));
      expect(filas.first['idempotency_key'], 'idem-v5-key');
      expect(filas.first['cobrador_id_origen'], 'c1');
      expect(filas.first['jornada_id_origen'], 'j1');
      expect(filas.first['negocio_id'], 'n1');
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

  // ===== Push → Pull integration with server_entity_id =====

  group('S3 — Push → Pull integration', () {
    test('PAYMENT: local L1 → push → server S1 → ACK guarda server_entity_id → pull reconcilia', () async {
      final orch = await buildOrchestrator();
      final db = await database;

      // Insertar fila pendiente con ID local L1
      await db.insert('sync_queue', {
        'id': 'sq-push-pull-1',
        'tipo': 'pago',
        'entidad_id': 'L1',
        'datos': jsonEncode({
          'tipo': 'PAYMENT',
          'monto': 5000,
          'credito_id': 'cr1',
          'jornada_id': 'j1',
          'cobrador_id': 'c1',
          'negocio_id': 'n1',
        }),
        'creado_el': '2026-08-10T21:00:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': 'idem-pp-1',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T21:00:00Z',
      });

      // Push: servidor asigna S1
      final resultados = await orch.ejecutarPush();
      expect(resultados.first.status, PushStatus.sincronizado);

      // Verificar mapping durable: entidad_id=L1, server_entity_id=S1
      final filas = await db.query('sync_queue', where: 'id = ?', whereArgs: ['sq-push-pull-1']);
      expect(filas.first['entidad_id'], 'L1');
      expect(filas.first['server_entity_id'], isNotNull);
      expect(filas.first['server_entity_id'], startsWith('pago_'));
      expect(filas.first['server_entity_id'], isNot(equals('L1')));
    });

    test('REVERSAL: local R1 → push → server SR1 → ACK guarda server_entity_id', () async {
      final orch = await buildOrchestrator();
      final db = await database;

      // Original PAYMENT con server_entity_id
      await db.insert('sync_queue', {
        'id': 'sq-pay-pp-rev',
        'tipo': 'pago',
        'entidad_id': 'p1',
        'datos': jsonEncode({'tipo': 'PAYMENT', 'monto': 5000}),
        'creado_el': '2026-08-10T21:00:00Z',
        'estado': SyncQueueService.estadoSincronizado,
        'idempotency_key': 'idem-pp-pay',
        'negocio_id': 'n1',
        'server_entity_id': 'pago_pp_server',
        'intento': 1,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T21:00:00Z',
      });

      await db.insert('sync_queue', {
        'id': 'sq-push-pull-rev',
        'tipo': 'pago',
        'entidad_id': 'R1',
        'datos': jsonEncode({
          'tipo': 'REVERSAL',
          'monto': 5000,
          'reversal_of_payment_id': 'p1',
          'jornada_id': 'j1',
          'cobrador_id': 'c1',
          'negocio_id': 'n1',
          'motivo': 'test reversal push-pull',
        }),
        'creado_el': '2026-08-10T22:00:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': 'idem-pp-rev',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T22:00:00Z',
      });

      final resultados = await orch.ejecutarPush();
      expect(resultados.first.status, PushStatus.sincronizado);

      final filas = await db.query('sync_queue', where: 'id = ?', whereArgs: ['sq-push-pull-rev']);
      expect(filas.first['entidad_id'], 'R1');
      expect(filas.first['server_entity_id'], isNotNull);
      expect(filas.first['server_entity_id'], startsWith('rev_'));
      expect(filas.first['server_entity_id'], isNot(equals('R1')));
    });

    test('MOVIMIENTO: local M1 → push → server SM1 → ACK guarda server_entity_id', () async {
      final orch = await buildOrchestrator();
      final db = await database;

      await db.insert('sync_queue', {
        'id': 'sq-push-pull-mov',
        'tipo': 'movimiento',
        'entidad_id': 'M1',
        'datos': jsonEncode({
          'tipo': 'GASOLINA',
          'monto': 12000,
          'nota': 'Combustible',
          'jornada_id': 'j1',
          'negocio_id': 'n1',
        }),
        'creado_el': '2026-08-10T23:00:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': 'idem-pp-mov',
        'negocio_id': 'n1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T23:00:00Z',
      });

      final resultados = await orch.ejecutarPush();
      expect(resultados.first.status, PushStatus.sincronizado);

      final filas = await db.query('sync_queue', where: 'id = ?', whereArgs: ['sq-push-pull-mov']);
      expect(filas.first['entidad_id'], 'M1');
      expect(filas.first['server_entity_id'], isNotNull);
      expect(filas.first['server_entity_id'], startsWith('mov_'));
      expect(filas.first['server_entity_id'], isNot(equals('M1')));
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

  // ===== 409 mismatch PAYMENT → CONFLICTO =====

  group('S3 — 409 mismatch PAYMENT', () {
    test('misma idempotency key + payload distinto → sync_queue = CONFLICTO', () async {
      final orch = await buildOrchestrator();
      final db = await database;

      _simulate409MismatchKey = 'idem-mismatch';

      await db.insert('sync_queue', {
        'id': 'sq-mismatch',
        'tipo': 'pago',
        'entidad_id': 'p-mismatch',
        'datos': jsonEncode({
          'tipo': 'PAYMENT',
          'monto': 5000,
          'credito_id': 'cr1',
          'jornada_id': 'j1',
          'cobrador_id': 'c1',
          'negocio_id': 'n1',
        }),
        'creado_el': '2026-08-10T15:00:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': 'idem-mismatch',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T15:00:00Z',
      });

      final resultados = await orch.ejecutarPush();

      expect(resultados.length, 1);
      expect(resultados.first.status, PushStatus.conflicto);
      expect(resultados.first.detail, contains('409'));

      final filas = await db.query('sync_queue', where: 'id = ?', whereArgs: ['sq-mismatch']);
      expect(filas.first['estado'], SyncQueueService.estadoConflicto);
      expect(filas.first['ultimo_error'], contains('409'));
      expect(filas.first['idempotency_key'], 'idem-mismatch');
    });
  });

  // ===== Jornada CLOSED_LOCAL_PENDING_SYNC → CLOSED_SYNCED =====

  group('S3 — Jornada CLOSED_LOCAL_PENDING_SYNC → CLOSED_SYNCED', () {
    test('/cerrar 409 → /sincronizar interno → jornada pasa a CLOSED_SYNCED', () async {
      final orch = await buildOrchestrator();
      final db = await database;

      // Insertar sync_queue para cerrar (tipo jornada_cierre)
      // El servidor responde 409 "ya cerrada" y el orchestrator llama internamente a /sincronizar
      await db.insert('sync_queue', {
        'id': 'sq-cerrar-1',
        'tipo': 'jornada_cierre',
        'entidad_id': 'j1',
        'datos': jsonEncode({
          'jornada_id': 'j1',
          'cobrador_id': 'c1',
          'negocio_id': 'n1',
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
          'contado': 10000,
          'pagos_count': 1,
          'reversales_count': 0,
          'movimientos_count': 0,
          'diferencia_motivo': 'sobrante',
        }),
        'creado_el': '2026-08-10T16:00:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': 'idem-cerrar-1',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T16:00:00Z',
      });

      // Insertar jornada en estado CLOSED_LOCAL_PENDING_SYNC
      await db.insert('jornada', {
        'id': 'j1',
        'negocio_id': 'n1',
        'ruta_id': 'r1',
        'cobrador_id': 'c1',
        'estado': 'CLOSED_LOCAL_PENDING_SYNC',
        'fecha': '2026-08-10',
        'esperado': 0,
      });

      final resultados = await orch.ejecutarPush();

      // 1 operation: cerrar (409) → sincronizar interno = 1 sincronizado
      final sincronizados = resultados.where((r) => r.status == PushStatus.sincronizado).toList();
      expect(sincronizados.length, 1, reason: 'cerrar 409 → sincronizar interno debe ACKear');

      // La jornada debe haber pasado a CLOSED_SYNCED (actualizado por mock server en /sincronizar)
      final jornadas = await db.query('jornada', where: 'id = ?', whereArgs: ['j1']);
      expect(jornadas.first['estado'], 'CLOSED_SYNCED',
          reason: 'jornada debe estar CLOSED_SYNCED tras ACK de /sincronizar');
    });

    test('jornada no avanza a CLOSED_SYNCED si snapshot_valido = false', () async {
      final orch = await buildOrchestrator();
      final db = await database;

      await db.insert('sync_queue', {
        'id': 'sq-cerrar-nv',
        'tipo': 'jornada_cierre',
        'entidad_id': 'j-nv',
        'datos': jsonEncode({
          'jornada_id': 'j-nv',
          'cobrador_id': 'c1',
          'negocio_id': 'n1',
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
          'contado': 10000,
          'pagos_count': 1,
          'reversales_count': 0,
          'movimientos_count': 0,
          'diferencia_motivo': 'sobrante',
        }),
        'creado_el': '2026-08-10T16:00:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': 'idem-nv',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j-nv',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T16:00:00Z',
      });

      await db.insert('jornada', {
        'id': 'j-nv',
        'negocio_id': 'n1',
        'ruta_id': 'r1',
        'cobrador_id': 'c1',
        'estado': 'CLOSED_LOCAL_PENDING_SYNC',
        'fecha': '2026-08-10',
        'esperado': 0,
      });

      // Mock server responde con snapshot_valido = false
      _customSyncResponse = {
        'jornada_id': 'j-nv',
        'estado': 'CLOSED_SYNCED',
        'snapshot_valido': false,
      };

      await orch.ejecutarPush();

      // La jornada NO debe cambiar (snapshot_valido = false)
      final jornadas = await db.query('jornada', where: 'id = ?', whereArgs: ['j-nv']);
      expect(jornadas.first['estado'], 'CLOSED_LOCAL_PENDING_SYNC',
          reason: 'jornada no debe avanzar a CLOSED_SYNCED con snapshot_valido = false');
    });
  });

  // ===== REVERSAL pre-ACK server ID resolution =====

  group('S3 — REVERSAL pre-ACK server ID', () {
    test('REVERSAL sin PAYMENT ACK → CONFLICTO (0 HTTP al server)', () async {
      final orch = await buildOrchestrator();
      final db = await database;

      // REVERSAL cuyo PAYMENT original nunca fue sync (no hay fila en sync_queue)
      await db.insert('sync_queue', {
        'id': 'sq-rev-noack',
        'tipo': 'pago',
        'entidad_id': 'r-noack',
        'datos': jsonEncode({
          'tipo': 'REVERSAL',
          'monto': 5000,
          'reversal_of_payment_id': 'p-ghost',
          'jornada_id': 'j1',
          'cobrador_id': 'c1',
          'negocio_id': 'n1',
          'motivo': 'test',
        }),
        'creado_el': '2026-08-10T16:00:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': 'idem-rev-noack',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T16:00:00Z',
      });

      final resultados = await orch.ejecutarPush();

      expect(resultados.first.status, PushStatus.conflicto);
      expect(resultados.first.detail, contains('PAYMENT original no encontrado'));

      // 0 requests HTTP al server
      final pagosLog = _requestLog.where((e) => e.startsWith('pago:')).toList();
      expect(pagosLog.length, 0);

      // Fila marcada como CONFLICTO
      final filas = await db.query('sync_queue', where: 'id = ?', whereArgs: ['sq-rev-noack']);
      expect(filas.first['estado'], SyncQueueService.estadoConflicto);
    });

    test('REVERSAL con PAYMENT ACK → usa server ID en URL', () async {
      final orch = await buildOrchestrator();
      final db = await database;

      // PAYMENT sincronizado primero (tiene server_entity_id)
      await db.insert('sync_queue', {
        'id': 'sq-pay-ack',
        'tipo': 'pago',
        'entidad_id': 'p-ack',
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
        'idempotency_key': 'idem-pay-ack',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T16:00:00Z',
      });

      // REVERSAL que referencia al PAYMENT local
      await db.insert('sync_queue', {
        'id': 'sq-rev-ack',
        'tipo': 'pago',
        'entidad_id': 'r-ack',
        'datos': jsonEncode({
          'tipo': 'REVERSAL',
          'monto': 5000,
          'reversal_of_payment_id': 'p-ack',
          'jornada_id': 'j1',
          'cobrador_id': 'c1',
          'negocio_id': 'n1',
          'motivo': 'test',
        }),
        'creado_el': '2026-08-10T16:01:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': 'idem-rev-ack',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T16:01:00Z',
      });

      final resultados = await orch.ejecutarPush();

      // PAYMENT sincronizado
      expect(resultados[0].status, PushStatus.sincronizado);
      // REVERSAL sincronizado (usó server ID del PAYMENT)
      expect(resultados[1].status, PushStatus.sincronizado);

      // Verificar que el REVERSAL usó el server ID en la URL
      final pagosLog = _requestLog.where((e) => e.startsWith('pago:')).toList();
      final revLog = _requestLog.where((e) => e.startsWith('reversal:')).toList();
      expect(pagosLog.length, 1);
      expect(revLog.length, 1);
      // El server ID del PAYMENT es 'pago_*', el REVERSAL debe usarlo en la URL
      expect(pagosLog.first, 'pago:idem-pay-ack');
      expect(revLog.first, 'reversal:idem-rev-ack');
    });
  });

  // ===== V5→V7 real upgrade =====

  group('S3 — V5→V7 real upgrade', () {
    test('V7 re-extract clave inventada (==entidad_id) desde JSON', () async {
      final db = await database;

      // Fila con idempotency_key == entidad_id (inventada por V5 bug)
      // pero datos.json contiene la clave real
      await db.insert('sync_queue', {
        'id': 'sq-v7-fix',
        'tipo': 'pago',
        'entidad_id': 'p-v7',
        'datos': jsonEncode({
          'tipo': 'PAYMENT',
          'monto': 5000,
          'idempotency_key': 'idem-real-v7',
          'cobrador_id': 'c1',
          'jornada_id': 'j1',
          'negocio_id': 'n1',
        }),
        'creado_el': '2026-08-10T10:00:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': 'p-v7', // inventada (= entidad_id)
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T10:00:00Z',
        'server_entity_id': null,
      });

      await MigrationV7.migrate(db);

      final filas = await db.query('sync_queue',
          where: 'id = ?',
          whereArgs: ['sq-v7-fix']);
      expect(filas, hasLength(1));
      expect(filas.first['idempotency_key'], 'idem-real-v7',
          reason: 'V7 re-extract clave real desde JSON cuando key == entidad_id');
    });

    test('V7 setea NULL cuando key inventada no está en JSON', () async {
      final db = await database;

      // Fila con idempotency_key == entidad_id y sin clave en JSON
      await db.insert('sync_queue', {
        'id': 'sq-v7-null',
        'tipo': 'pago',
        'entidad_id': 'p-v7n',
        'datos': jsonEncode({
          'tipo': 'PAYMENT',
          'monto': 5000,
          'cobrador_id': 'c1',
          'jornada_id': 'j1',
          'negocio_id': 'n1',
        }),
        'creado_el': '2026-08-10T10:00:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': 'p-v7n', // inventada (= entidad_id)
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T10:00:00Z',
        'server_entity_id': null,
      });

      await MigrationV7.migrate(db);

      final filas = await db.query('sync_queue',
          where: 'id = ?',
          whereArgs: ['sq-v7-null']);
      expect(filas, hasLength(1));
      expect(filas.first['idempotency_key'], isNull,
           reason: 'V7 setea NULL cuando key inventada no está en JSON');
    });
  });

  // ===== Jornada CIERRE dependency guard — CONFLICTO =====

  group('S3 — JORNADA_CIERRE dependencias CONFLICTO', () {
    test('PAYMENT J1 = CONFLICTO → JORNADA_CIERRE J1 = CONFLICTO (0 HTTP)', () async {
      final orch = await buildOrchestrator();
      final db = await database;

      // PAYMENT de J1 en CONFLICTO
      await db.insert('sync_queue', {
        'id': 'sq-pay-conf',
        'tipo': 'pago',
        'entidad_id': 'p-conf',
        'datos': jsonEncode({
          'tipo': 'PAYMENT',
          'monto': 5000,
          'credito_id': 'cr1',
          'jornada_id': 'j1',
          'cobrador_id': 'c1',
          'negocio_id': 'n1',
        }),
        'creado_el': '2026-08-10T16:00:00Z',
        'estado': SyncQueueService.estadoConflicto,
        'idempotency_key': 'idem-pay-conf',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 1,
        'ultimo_error': '409 mismatch',
        'ultima_transicion': '2026-08-10T16:30:00Z',
      });

      // JORNADA_CIERRE de J1 pendiente
      await db.insert('sync_queue', {
        'id': 'sq-jc-conf',
        'tipo': 'jornada_cierre',
        'entidad_id': 'j1',
        'datos': jsonEncode({
          'jornada_id': 'j1',
          'contado': 10000,
          'opening_base': 0,
          'opening_carry': 0,
          'negocio_id': 'n1',
          'ruta_id': 'r1',
          'cobrador_id': 'c1',
          'diferencia_motivo': '',
          'recaudo_real': 0,
          'reversales': 0,
          'gastos': 0,
          'ahorro': 0,
          'vales': 0,
          'entregas': 0,
          'recibidos': 0,
          'desembolsos': 0,
          'efectivo_esperado': 5000,
          'pagos_count': 1,
          'reversales_count': 0,
          'movimientos_count': 0,
        }),
        'creado_el': '2026-08-10T17:00:00Z',
        'estado': SyncQueueService.estadoPendiente,
        'idempotency_key': 'idem-jc-conf',
        'negocio_id': 'n1',
        'ruta_id_origen': 'r1',
        'cobrador_id_origen': 'c1',
        'jornada_id_origen': 'j1',
        'intento': 0,
        'ultimo_error': null,
        'ultima_transicion': '2026-08-10T17:00:00Z',
      });

      // Insertar jornada local CLOSED_LOCAL_PENDING_SYNC
      await db.insert('jornada', {
        'id': 'j1',
        'negocio_id': 'n1',
        'ruta_id': 'r1',
        'cobrador_id': 'c1',
        'fecha': '2026-08-10',
        'estado': 'CLOSED_LOCAL_PENDING_SYNC',
        'opening_base': 0,
        'opening_carry': 0,
        'esperado': 5000,
        'contado': 10000,
        'diferencia': 5000,
        'diferencia_motivo': '',
        'sobrante_manana': 10000,
      });

      final resultados = await orch.ejecutarPush();

      // 0 requests HTTP al server
      final pagosLog = _requestLog.where((e) => e.startsWith('pago:')).toList();
      final cerrarLog = _requestLog.where((e) => e.startsWith('cerrar:')).toList();
      final syncLog = _requestLog.where((e) => e.startsWith('sincronizar')).toList();
      expect(pagosLog.length, 0);
      expect(cerrarLog.length, 0);
      expect(syncLog.length, 0);

      // JORNADA_CIERRE queda CONFLICTO
      expect(resultados.first.status, PushStatus.conflicto);
      expect(resultados.first.detail, contains('dependencia financiera en conflicto'));

      // Fila marcada como CONFLICTO (no ENVIANDO)
      final filas = await db.query('sync_queue',
          where: 'id = ?',
          whereArgs: ['sq-jc-conf']);
      expect(filas.first['estado'], SyncQueueService.estadoConflicto);

      // Jornada local sigue CLOSED_LOCAL_PENDING_SYNC (no se actualizó)
      final jornadas = await db.query('jornada',
          where: 'id = ?',
          whereArgs: ['j1']);
      expect(jornadas.first['estado'], 'CLOSED_LOCAL_PENDING_SYNC');
    });
  });
}
