// SyncClient (offline sync, S2) contra un HttpServer local + SQLite real (FFI).
//
// Cubre las reglas del contrato:
//   - sin token -> NoSessionException (sin tocar secure storage)
//   - GET /api/mobile/sync con el JWT vigente -> dataset reflejado en local
//   - si la sesion requiere renovacion se renueva ANTES de consumir el recurso
//   - un 401 del sync limpia la sesion (token) y se propaga

import 'dart:convert';
import 'dart:io';

import 'package:daily_system/auth/auth_http_client.dart';
import 'package:daily_system/auth/auth_token_store.dart';
import 'package:daily_system/auth/device_auth_client.dart';
import 'package:daily_system/auth/device_identity.dart';
import 'package:daily_system/auth/models.dart';
import 'package:daily_system/database/database.dart';
import 'package:daily_system/sync/sync_client.dart';
import 'package:daily_system/sync/sync_repository.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/fixture.dart';

const _spkiFixture =
    'MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEfltvZ5mRj+BFLYfEwxbexXeSeLrs9MFCBxCbx2i6ub9vfaAmyFj1frXaYdE2oKA/iQh6PhnCaMsWfxXmwA+V6g==';

class _RealHttpOverrides extends HttpOverrides {
  @override
  HttpClient createHttpClient(SecurityContext? context) {
    final client = super.createHttpClient(context);
    client.connectionTimeout = const Duration(seconds: 15);
    return client;
  }
}

const _jwtSesion = 'jwt-de-sesion-productiva';
const _jwtRenovado = 'jwt-de-sesion-renovada';

const _desafioAuth = {
  'challenge_id': 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
  'nonce': 'ZmljdGljaW9uZXN1ZXJ0ZTY0bGluZzMyYnl0ZWNzcHI',
  'expira_el': '2026-08-08T12:10:00Z',
  'environment': 'development',
};

const _syncDataset = {
  'negocio_id': '44444444-5555-4666-8777-888888888888',
  'cobrador_id': '55555555-6666-4777-8888-999999999999',
  'ruta_id': '77777777-8888-4999-8aaa-bbbbbbbbbbbb',
  'ruta_version': 2,
  'clientes': [
    {
      'id': 'cl1',
      'negocio_id': '44444444-5555-4666-8777-888888888888',
      'primer_apellido': 'Perez',
      'nombres': 'Ana',
      'tipo_documento': 'CC',
      'documento_normalizado': '1234567890',
      'telefono_1': '3001234567',
      'barrio': 'Centro',
      'ocupacion': 'Independiente',
      'identity_status': 'PROVISIONAL',
    },
  ],
  'creditos': [
    {
      'id': 'cr1',
      'negocio_id': '44444444-5555-4666-8777-888888888888',
      'cliente_id': 'cl1',
      'ruta_id': '77777777-8888-4999-8aaa-bbbbbbbbbbbb',
      'cuota': 5000,
      'n_cuotas': 10,
      'monto': 5000,
      'total': 50000,
      'periodicidad': 'DIARIO',
      'fecha_inicio': '2026-08-01',
      'estado': 'ACTIVO',
    },
  ],
  'cuotas': [
    {
      'id': 'cu1',
      'credito_id': 'cr1',
      'numero': 1,
      'fecha_vencimiento': '2026-08-02',
      'monto': 5000,
      'estado': 'PENDIENTE',
    },
  ],
  'jornadas': [
    {
      'id': 'j1',
      'negocio_id': '44444444-5555-4666-8777-888888888888',
      'ruta_id': '77777777-8888-4999-8aaa-bbbbbbbbbbbb',
      'fecha': '2026-08-08',
      'estado': 'CLOSED_SYNCED',
      'opening_base': 50000,
      'opening_carry': 0,
      'esperado': 5000,
      'contado': 5000,
      'diferencia': 0,
      'sobrante_manana': 0,
    },
  ],
  'pagos': [
    {
      'id': 'p1',
      'negocio_id': '44444444-5555-4666-8777-888888888888',
      'credito_id': 'cr1',
      'jornada_id': 'j1',
      'tipo': 'PAYMENT',
      'monto': 5000,
      'clave_idempotencia': 'sync-pago-1',
      'recibido_el_servidor': '2026-08-08T18:00:00Z',
    },
  ],
  'movimientos': [
    {
      'id': 'm1',
      'negocio_id': '44444444-5555-4666-8777-888888888888',
      'jornada_id': 'j1',
      'tipo': 'GASOLINA',
      'naturaleza': 'GASTO',
      'monto': 12000,
      'nota': 'Combustible',
    },
  ],
};

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  initTestDatabase();

  late HttpServer server;
  late String baseUrl;
  final headersSync = <String, String>{};
  final headersDesafio = <String, String>{};

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
    // ignore: unawaited_futures
    server.listen((request) async {
      final path = request.uri.path;
      final method = request.method;

      if (method == 'POST' && path == '/api/auth/device/desafio') {
        final auth = request.headers.value(HttpHeaders.authorizationHeader) ?? '';
        headersDesafio['desafio'] = auth;
        await responder(request, 200, _desafioAuth);
        return;
      }

      if (method == 'POST' && path == '/api/auth/device/canjear') {
        final body = jsonDecode(await utf8.decoder.bind(request).join());
        if (body['challenge_id'] != _desafioAuth['challenge_id'] ||
            body['firma'] != 'firma-ejemplo') {
          await responder(request, 400, {'detail': 'FIRMA_INVALIDA'});
          return;
        }
        await responder(request, 200, {
          'token': _jwtRenovado,
          'negocio_id': '44444444-5555-4666-8777-888888888888',
          'usuario_id': '55555555-6666-4777-8888-999999999999',
          'dispositivo_id': '33333333-4444-4555-8666-777777777777',
          'version_asignacion': 3,
          'expira_el': '2026-08-08T14:00:00Z',
        });
        return;
      }

      if (method == 'GET' && path == '/api/mobile/sync') {
        final auth = request.headers.value(HttpHeaders.authorizationHeader) ?? '';
        headersSync['sync'] = auth;
        if (auth != 'Bearer $_jwtSesion' && auth != 'Bearer $_jwtRenovado') {
          await responder(request, 401, {'detail': 'AUTH_REQUERIDA'});
          return;
        }
        await responder(request, 200, _syncDataset);
        return;
      }

      await responder(request, 404, {'detail': 'NO_ENCONTRADO'});
    });
  }

  Future<SyncClient> buildClient() async {
    await clearDatabase();
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(DeviceIdentity.channel, (call) async {
      switch (call.method) {
        case 'generate':
        case 'getPublicKeySpki':
          return {'spki': _spkiFixture};
        case 'sign':
          return {'firma': 'firma-ejemplo'};
        default:
          return null;
      }
    });

    return SyncClient(
      http: AuthHttpClient(baseUrl: baseUrl),
      tokenStore: AuthTokenStore(),
      repository: SyncRepository(await database),
      auth: DeviceAuthClient(
        http: AuthHttpClient(baseUrl: baseUrl),
        identity: DeviceIdentity(),
        tokenStore: AuthTokenStore(),
      ),
    );
  }

  CanjearAuth sesion(String token, {String? expiraEl}) {
    return CanjearAuth(
      token: token,
      negocioId: '44444444-5555-4666-8777-888888888888',
      usuarioId: '55555555-6666-4777-8888-999999999999',
      dispositivoId: '33333333-4444-4555-8666-777777777777',
      versionAsignacion: 3,
      expiraEl: expiraEl ?? '2030-08-08T23:59:00Z',
    );
  }

  setUp(() async {
    headersSync.clear();
    headersDesafio.clear();
    FlutterSecureStorage.setMockInitialValues({});
    HttpOverrides.global = _RealHttpOverrides();
    await startServer();
  });

  tearDown(() async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(DeviceIdentity.channel, null);
    HttpOverrides.global = null;
    await server.close(force: true);
  });

  group('SyncClient — sincronizar', () {
    test('sin access token lanza NoSessionException', () async {
      final client = await buildClient();

      await expectLater(
        client.sincronizar(),
        throwsA(isA<NoSessionException>()),
      );
    });

    test('con JWT vigente descarga y refleja el dataset en el modelo local',
        () async {
      final client = await buildClient();
      await AuthTokenStore().guardarSesion(sesion(_jwtSesion));

      final dataset = await client.sincronizar();

      expect(dataset.rutaVersion, 2);
      expect(dataset.clientes, hasLength(1));
      expect(dataset.jornadas.single.estado, 'CLOSED_SYNCED');
      expect(headersSync['sync'], 'Bearer $_jwtSesion');

      final db = await database;
      expect(await db.query('cliente', where: 'id = ?', whereArgs: ['cl1']),
          hasLength(1));
      expect(await db.query('jornada', where: 'id = ?', whereArgs: ['j1']),
          hasLength(1));
      expect(await db.query('pago', where: 'id = ?', whereArgs: ['p1']),
          hasLength(1));
      expect(await db.query('movimiento', where: 'id = ?', whereArgs: ['m1']),
          hasLength(1));
    });

    test('renueva la sesion antes del sync cuando expira ~5 min', () async {
      final client = await buildClient();
      await AuthTokenStore().guardarSesion(sesion(
        _jwtSesion,
        expiraEl: '2026-08-08T12:01:00Z',
      ));

      final dataset = await client.sincronizar();

      expect(dataset.clientes, hasLength(1));
      final store = AuthTokenStore();
      expect(await store.leerToken(), _jwtRenovado);
      expect(headersDesafio['desafio'], 'Bearer $_jwtSesion');
      expect(headersSync['sync'], 'Bearer $_jwtRenovado');
    });

    test('401 del sync limpia la sesion (token) y se propaga', () async {
      final client = await buildClient();
      await AuthTokenStore().guardarSesion(sesion('jwt-revocado'));

      await expectLater(
        client.sincronizar(),
        throwsA(isA<AuthApiException>()
            .having((e) => e.es401, 'es401', isTrue)),
      );
      expect(await AuthTokenStore().leerToken(), isNull);
    });
  });
}
