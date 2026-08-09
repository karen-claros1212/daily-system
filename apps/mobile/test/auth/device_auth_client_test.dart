// Flujo completo del orquestador (DeviceAuthClient) contra un HttpServer local.
//
// Cubre los criterios del contrato del bloque mobile:
//   - la credencial bootstrap se obtiene del canje de activacion y NUNCA se
//     reutiliza como access token (el servidor responde 401 y la sesion se
//     limpia)
//   - el access token se firma con el perfil daily-auth-v1 exacto y se guarda
//     en secure storage
//   - bootstrap con JWT devuelve SOLO la identidad operativa con la ruta
//     unica asignada (sin listas de rutas ni selector)
//   - un 401 de bootstrap limpia la sesion (token)

import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:daily_system/auth/auth_http_client.dart';
import 'package:daily_system/auth/auth_token_store.dart';
import 'package:daily_system/auth/device_auth_client.dart';
import 'package:daily_system/auth/device_identity.dart';
import 'package:daily_system/auth/jcs.dart';
import 'package:daily_system/auth/models.dart';

const _spkiFixture =
    'MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEfltvZ5mRj+BFLYfEwxbexXeSeLrs9MFCBxCbx2i6ub9vfaAmyFj1frXaYdE2oKA/iQh6PhnCaMsWfxXmwA+V6g==';

/// Restaura el HttpClient real: TestWidgetsFlutterBinding reemplaza
/// HttpOverrides.global por un mock que responde 400 a todo request.
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
const _credencialBootstrap = 'bootstrap-credencial-1';

const _desafioActivacion = {
  'intento_id': '22222222-3333-4444-8555-666666666666',
  'nonce': 'ZmljdGljaW9uZXN1ZXJ0ZTY0bGluZzMyYnl0ZWNzcHI',
  'expira_el': '2026-08-08T12:00:00Z',
  'environment': 'development',
};

const _canjearActivacion = {
  'dispositivo_id': '33333333-4444-4555-8666-777777777777',
  'negocio_id': '44444444-5555-4666-8777-888888888888',
  'cobrador_id': '55555555-6666-4777-8888-999999999999',
  'credencial_bootstrap': _credencialBootstrap,
  'expira_el': '2026-08-08T12:05:00Z',
  'idempotente': false,
};

const _desafioAuth = {
  'challenge_id': 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
  'nonce': 'ZmljdGljaW9uZXN1ZXJ0ZTY0bGluZzMyYnl0ZWNzcHI',
  'expira_el': '2026-08-08T12:10:00Z',
  'environment': 'development',
};

const _bootstrap = {
  'negocio_id': '44444444-5555-4666-8777-888888888888',
  'negocio_nombre': 'Negocio Demo',
  'cobrador_id': '55555555-6666-4777-8888-999999999999',
  'cobrador_nombre': 'Cobrador Uno',
  'dispositivo_id': '33333333-4444-4555-8666-777777777777',
  'version_asignacion': 3,
  'ruta_id': '77777777-8888-4999-8aaa-bbbbbbbbbbbb',
  'ruta_nombre': 'Ruta Norte',
  'ruta_version': 2,
  'rol': 'COBRADOR',
};

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late HttpServer server;
  late String baseUrl;
  final ultimosHeaders = <String, String>{};
  final payloadsFirmados = <Uint8List>[];
  var renovando = false;

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

      if (method == 'POST' && path == '/api/activaciones/desafio') {
        final body = jsonDecode(await utf8.decoder.bind(request).join());
        if (body['token'] != 'codigo-de-activacion') {
          await responder(request, 401, {'detail': 'TOKEN_INVALIDO'});
          return;
        }
        if (body['clave_publica'] != _spkiFixture) {
          await responder(request, 400, {'detail': 'CLAVE_PUBLICA_INVALIDA'});
          return;
        }
        await responder(request, 200, _desafioActivacion);
        return;
      }

      if (method == 'POST' && path == '/api/activaciones/canjear') {
        final body = jsonDecode(await utf8.decoder.bind(request).join());
        if (body['intento_id'] != _desafioActivacion['intento_id'] ||
            body['firma'] != 'firma-ejemplo') {
          await responder(request, 400, {'detail': 'FIRMA_INVALIDA'});
          return;
        }
        await responder(request, 200, _canjearActivacion);
        return;
      }

      if (method == 'POST' && path == '/api/auth/device/desafio') {
        final auth = request.headers.value(HttpHeaders.authorizationHeader) ?? '';
        ultimosHeaders['desafio-auth'] = auth;
        if (auth != 'Bearer $_credencialBootstrap' &&
            auth != 'Bearer $_jwtSesion') {
          await responder(request, 401, {'detail': 'CREDENCIAL_INVALIDA'});
          return;
        }
        renovando = auth == 'Bearer $_jwtSesion';
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
          'token': renovando ? _jwtRenovado : _jwtSesion,
          'negocio_id': '44444444-5555-4666-8777-888888888888',
          'usuario_id': '66666666-7777-4888-8999-000000000000',
          'dispositivo_id': '33333333-4444-4555-8666-777777777777',
          'version_asignacion': 3,
          'expira_el': renovando
              ? '2026-08-08T14:00:00Z'
              : '2026-08-08T13:00:00Z',
        });
        return;
      }

      if (method == 'GET' && path == '/api/mobile/bootstrap') {
        final auth = request.headers.value(HttpHeaders.authorizationHeader) ?? '';
        ultimosHeaders['bootstrap'] = auth;
        if (auth != 'Bearer $_jwtSesion' && auth != 'Bearer $_jwtRenovado') {
          await responder(request, 401, {'detail': 'AUTH_REQUERIDA'});
          return;
        }
        await responder(request, 200, _bootstrap);
        return;
      }

      await responder(request, 404, {'detail': 'NO_ENCONTRADO'});
    });
  }

  DeviceAuthClient buildClient() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(DeviceIdentity.channel, (call) async {
      switch (call.method) {
        case 'generate':
        case 'getPublicKeySpki':
          return {'spki': _spkiFixture};
        case 'sign':
          final recibido = (call.arguments as Map)['payload'] as String;
          var padded = recibido;
          while (padded.length % 4 != 0) {
            padded = '$padded=';
          }
          payloadsFirmados.add(base64Url.decode(padded));
          return {'firma': 'firma-ejemplo'};
        default:
          return null;
      }
    });

    return DeviceAuthClient(
      http: AuthHttpClient(baseUrl: baseUrl),
      identity: DeviceIdentity(),
      tokenStore: AuthTokenStore(),
    );
  }

  setUp(() async {
    payloadsFirmados.clear();
    ultimosHeaders.clear();
    renovando = false;
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

  group('DeviceAuthClient — activacion', () {
    test('desafio -> firma daily-v1 -> canje: devuelve credencial bootstrap',
        () async {
      final client = buildClient();

      final resultado = await client.activar(token: 'codigo-de-activacion');

      expect(resultado, isA<CanjearActivacion>());
      expect(resultado.credencialBootstrap, _credencialBootstrap);
      expect(resultado.dispositivoId, _canjearActivacion['dispositivo_id']);
      expect(resultado.idempotente, isFalse);

      final payloadFirmado = payloadsFirmados.single;
      expect(payloadFirmado, buildPayloadActivacion(
        protocolVersion: 'daily-v1',
        environment: 'development',
        attemptId: _desafioActivacion['intento_id'] as String,
        nonce: _desafioActivacion['nonce'] as String,
        publicKeyHash: _publicKeyHash(_spkiFixture),
        expiresAt: _desafioActivacion['expira_el'] as String,
      ));
    });

    test('activacion con token invalido propaga 401', () async {
      final client = buildClient();
      await expectLater(
        client.activar(token: 'token-malo'),
        throwsA(isA<AuthApiException>()
            .having((e) => e.statusCode, 'statusCode', 401)),
      );
    });
  });

  group('DeviceAuthClient — canje de sesion', () {
    test('firma daily-auth-v1 exacta y guarda el access token', () async {
      final client = buildClient();
      final activacion = CanjearActivacion.fromJson(_canjearActivacion);

      final canje = await client.canjearSesion(activacion);

      expect(canje.token, _jwtSesion);
      expect(canje.versionAsignacion, 3);
      expect(ultimosHeaders['desafio-auth'], 'Bearer $_credencialBootstrap');
      expect(await AuthTokenStore().leerToken(), _jwtSesion);

      final payloadFirmado = payloadsFirmados.single;
      expect(payloadFirmado, buildPayloadAuth(
        purpose: 'issue_access_token',
        environment: 'development',
        challengeId: _desafioAuth['challenge_id'] as String,
        deviceId: _canjearActivacion['dispositivo_id'] as String,
        nonce: _desafioAuth['nonce'] as String,
        publicKeyHash: _publicKeyHash(_spkiFixture),
        expiresAt: _desafioAuth['expira_el'] as String,
      ));
    });

    test('credential bootstrap invalida propaga 401 y no guarda token', () async {
      final activacion = CanjearActivacion.fromJson(_canjearActivacion)
          .copyWithCredencial('bootstrap-invalida');
      final client = buildClient();

      await expectLater(
        client.canjearSesion(activacion),
        throwsA(isA<AuthApiException>()
            .having((e) => e.statusCode, 'statusCode', 401)),
      );
      expect(await AuthTokenStore().leerToken(), isNull);
    });
  });

  group('DeviceAuthClient — bootstrap', () {
    test('con JWT devuelve la identidad operativa con la ruta unica asignada',
        () async {
      final client = buildClient();
      await AuthTokenStore().guardarSesion(_sesion(_jwtSesion));

      final identidad = await client.bootstrap();

      expect(identidad, isA<BootstrapIdentity>());
      expect(identidad.negocioId, _bootstrap['negocio_id']);
      expect(identidad.negocioNombre, 'Negocio Demo');
      expect(identidad.cobradorNombre, 'Cobrador Uno');
      expect(identidad.dispositivoId, _bootstrap['dispositivo_id']);
      expect(identidad.versionAsignacion, 3);
      expect(identidad.rutaId, _bootstrap['ruta_id']);
      expect(identidad.rutaNombre, 'Ruta Norte');
      expect(identidad.rutaVersion, 2);
      expect(identidad.rol, 'COBRADOR');
      expect(ultimosHeaders['bootstrap'], 'Bearer $_jwtSesion');
    });

    test('credencial bootstrap usada como access token -> 401 y limpia sesion',
        () async {
      final client = buildClient();
      await AuthTokenStore().guardarSesion(_sesion(_credencialBootstrap));

      await expectLater(
        client.bootstrap(),
        throwsA(isA<AuthApiException>()
            .having((e) => e.es401, 'es401', isTrue)),
      );
      expect(await AuthTokenStore().leerToken(), isNull);
    });

    test('401 limpia la sesion (token) y se propaga', () async {
      final client = buildClient();
      await AuthTokenStore().guardarSesion(_sesion('jwt-expirado-o-revocado'));

      await expectLater(
        client.bootstrap(),
        throwsA(isA<AuthApiException>()
            .having((e) => e.es401, 'es401', isTrue)),
      );
      expect(await AuthTokenStore().leerToken(), isNull);
    });

    test('sin access token lanza NoSessionException', () async {
      final client = buildClient();
      await expectLater(
        client.bootstrap(),
        throwsA(isA<NoSessionException>()),
      );
    });
  });

  group('DeviceAuthClient — renovacion de sesion (S0)', () {
    test('renueva con el JWT vigente y persiste el token nuevo atomicamente',
        () async {
      final client = buildClient();
      await AuthTokenStore().guardarSesion(_sesion(_jwtSesion));

      final renovado = await client.renovarSesion();

      expect(renovado.token, _jwtRenovado);
      expect(ultimosHeaders['desafio-auth'], 'Bearer $_jwtSesion');
      final store = AuthTokenStore();
      expect(await store.leerToken(), _jwtRenovado);
      expect(await store.leerExpiraEl(), '2026-08-08T14:00:00Z');
      expect(await store.leerDispositivoId(), '33333333-4444-4555-8666-777777777777');

      final payloadFirmado = payloadsFirmados.single;
      expect(payloadFirmado, buildPayloadAuth(
        purpose: 'issue_access_token',
        environment: 'development',
        challengeId: _desafioAuth['challenge_id'] as String,
        deviceId: '33333333-4444-4555-8666-777777777777',
        nonce: _desafioAuth['nonce'] as String,
        publicKeyHash: _publicKeyHash(_spkiFixture),
        expiresAt: _desafioAuth['expira_el'] as String,
      ));
    });

    test('sin access token lanza NoSessionException', () async {
      final client = buildClient();
      await expectLater(
        client.renovarSesion(),
        throwsA(isA<NoSessionException>()),
      );
    });

    test('un 401 de renovacion limpia la sesion (token) y se propaga',
        () async {
      final client = buildClient();
      await AuthTokenStore().guardarSesion(_sesion('jwt-expirado-o-revocado'));

      await expectLater(
        client.renovarSesion(),
        throwsA(isA<AuthApiException>()
            .having((e) => e.es401, 'es401', isTrue)),
      );
      final store = AuthTokenStore();
      expect(await store.leerToken(), isNull);
      expect(await store.leerExpiraEl(), isNull);
      expect(await store.leerDispositivoId(), isNull);
    });

    test('el token renovado se usa en el siguiente bootstrap', () async {
      final client = buildClient();
      await AuthTokenStore().guardarSesion(_sesion(_jwtSesion));
      await client.renovarSesion();

      final identidad = await client.bootstrap();

      expect(ultimosHeaders['bootstrap'], 'Bearer $_jwtRenovado');
      expect(identidad.rutaId, _bootstrap['ruta_id']);
    });
  });

  group('DeviceAuthClient — cierre de sesion', () {
    test('cerrarSesion borra el access token', () async {
      final client = buildClient();
      await AuthTokenStore().guardarSesion(_sesion(_jwtSesion));
      await client.cerrarSesion();
      expect(await AuthTokenStore().leerToken(), isNull);
    });
  });
}

String _publicKeyHash(String spkiBase64) {
  return sha256.convert(base64Decode(spkiBase64)).toString();
}

CanjearAuth _sesion(String token) {
  return CanjearAuth(
    token: token,
    negocioId: '44444444-5555-4666-8777-888888888888',
    usuarioId: '66666666-7777-4888-8999-000000000000',
    dispositivoId: '33333333-4444-4555-8666-777777777777',
    versionAsignacion: 3,
    expiraEl: '2026-08-08T13:00:00Z',
  );
}

extension on CanjearActivacion {
  CanjearActivacion copyWithCredencial(String credencial) {
    return CanjearActivacion(
      dispositivoId: dispositivoId,
      negocioId: negocioId,
      cobradorId: cobradorId,
      credencialBootstrap: credencial,
      expiraEl: expiraEl,
      idempotente: idempotente,
    );
  }
}
