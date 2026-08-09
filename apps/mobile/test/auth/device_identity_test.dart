// Wrapper Dart del canal daily_system/device_identity (D7-02): verifica que
// envia el payload JCS en base64url sin padding, parsea las respuestas
// {firma}/{valida}/{spki} y normaliza errores nativos.

import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:daily_system/auth/device_identity.dart';
import 'package:daily_system/auth/jcs.dart' show base64UrlNoPad;

const _spkiFixture = 'MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE/abcdefghij0123456789';

/// Decodifica base64url sin padding (tolerante al '=' faltante).
List<int> _b64UrlDecode(String value) {
  var padded = value;
  while (padded.length % 4 != 0) {
    padded = '$padded=';
  }
  return base64Url.decode(padded);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late List<MethodCall> llamadas;

  void registrarCanal(Future<Object?> Function(MethodCall call) handler) {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(DeviceIdentity.channel, handler);
  }

  setUp(() {
    llamadas = [];
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(DeviceIdentity.channel, null);
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(DeviceIdentity.channel, null);
  });

  group('DeviceIdentity — canal productivo', () {
    test('generar devuelve el SPKI', () async {
      registrarCanal((call) async {
        llamadas.add(call);
        return {'spki': _spkiFixture};
      });

      final identity = DeviceIdentity();
      expect(await identity.generar(), _spkiFixture);
      expect(llamadas.single.method, 'generate');
    });

    test('getPublicKeySpki devuelve el SPKI', () async {
      registrarCanal((call) async {
        llamadas.add(call);
        return {'spki': _spkiFixture};
      });

      final identity = DeviceIdentity();
      expect(await identity.getPublicKeySpki(), _spkiFixture);
      expect(llamadas.single.method, 'getPublicKeySpki');
    });

    test('firmar envia el payload JCS en base64url sin padding', () async {
      final payload = utf8.encode('{"challenge_id":"x","purpose":"issue_access_token"}');
      registrarCanal((call) async {
        llamadas.add(call);
        final recibido = (call.arguments as Map)['payload'] as String;
        return {
          'firma': base64UrlNoPad(sha256.convert(_b64UrlDecode(recibido)).bytes),
        };
      });

      final identity = DeviceIdentity();
      final firma = await identity.firmar(payload);
      expect(firma, isNotEmpty);

      final signCall = llamadas.single;
      expect(signCall.method, 'sign');
      expect((signCall.arguments as Map)['payload'], base64UrlNoPad(payload));
      expect((signCall.arguments as Map)['payload'], isNot(contains('=')));
    });

    test('verificar parsea la respuesta booleana', () async {
      registrarCanal((call) async {
        return {'valida': true};
      });

      final identity = DeviceIdentity();
      expect(
        await identity.verificar(payload: utf8.encode('p'), firma: 'f'),
        isTrue,
      );
    });

    test('borrar e isPrivateKeyExportable parsean booleanos', () async {
      registrarCanal((call) async {
        return switch (call.method) {
          'delete' => {'borrado': true},
          'isPrivateKeyExportable' => {'exportable': false},
          _ => null,
        };
      });

      final identity = DeviceIdentity();
      expect(await identity.borrar(), isTrue);
      expect(await identity.isPrivateKeyExportable(), isFalse);
    });

    test('PlatformException nativo se normaliza', () async {
      registrarCanal((call) async {
        throw PlatformException(code: 'KEYSTORE_ERROR', message: 'no hay clave');
      });

      final identity = DeviceIdentity();
      await expectLater(
        identity.getPublicKeySpki(),
        throwsA(isA<DeviceIdentityException>()
            .having((e) => e.code, 'code', 'KEYSTORE_ERROR')
            .having((e) => e.message, 'message', 'no hay clave')),
      );
    });

    test('canal ausente reporta CANAL_NO_DISPONIBLE', () async {
      registrarCanal((call) async {
        throw MissingPluginException('no hay implementacion');
      });

      final identity = DeviceIdentity();
      await expectLater(
        identity.getPublicKeySpki(),
        throwsA(isA<DeviceIdentityException>()
            .having((e) => e.code, 'code', 'CANAL_NO_DISPONIBLE')),
      );
    });
  });
}
