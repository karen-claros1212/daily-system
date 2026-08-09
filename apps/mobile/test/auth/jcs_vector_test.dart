// Vector obligatorio del contrato (seccion 13.4): la salida JCS de este
// modulo debe coincidir byte a byte con la producida por el backend.
// Vectores generados con src/services/jcs.py y src/services/auth_jcs.py.

import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:daily_system/auth/jcs.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('jcsCanonicalize — perfil de activacion (daily-v1)', () {
    test('coincide byte a byte con el backend', () {
      final bytes = buildPayloadActivacion(
        protocolVersion: 'daily-v1',
        environment: 'development',
        attemptId: '11111111-2222-4333-8444-555555555555',
        nonce: 'ZmljdGljaW9uZXN1ZXJ0ZTY0bGluZzMyYnl0ZWNzcHI',
        publicKeyHash: 'a' * 64,
        expiresAt: '2026-08-08T12:00:00Z',
      );

      expect(utf8.decode(bytes), '{"attempt_id":"11111111-2222-4333-8444-'
          '555555555555","environment":"development","expires_at":"2026-08-08T'
          '12:00:00Z","nonce":"ZmljdGljaW9uZXN1ZXJ0ZTY0bGluZzMyYnl0ZWNzcHI",'
          '"protocol_version":"daily-v1","public_key_hash":"'
          'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}');

      expect(bytes.length, 286);
      expect(
        sha256.convert(bytes).toString(),
        'ebef9d20fc3f1fcf0df181a5a151441cebc55a1cf8a7b086ad0ee46eb8af32bb',
      );
    });
  });

  group('jcsCanonicalize — perfil de auth (daily-auth-v1)', () {
    test('coincide byte a byte con el backend', () {
      final bytes = buildPayloadAuth(
        purpose: 'issue_access_token',
        environment: 'development',
        challengeId: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
        deviceId: '11111111-2222-4333-8444-555555555555',
        nonce: 'ZmljdGljaW9uZXN1ZXJ0ZTY0bGluZzMyYnl0ZWNzcHI',
        publicKeyHash: 'a' * 64,
        expiresAt: '2026-08-08T12:00:00Z',
      );

      expect(utf8.decode(bytes), '{"challenge_id":"aaaaaaaa-bbbb-4ccc-8ddd-'
          'eeeeeeeeeeee","device_id":"11111111-2222-4333-8444-555555555555",'
          '"environment":"development","expires_at":"2026-08-08T12:00:00Z",'
          '"nonce":"ZmljdGljaW9uZXN1ZXJ0ZTY0bGluZzMyYnl0ZWNzcHI",'
          '"protocol_version":"daily-auth-v1","public_key_hash":"'
          'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
          '"purpose":"issue_access_token"}');

      expect(bytes.length, 375);
      expect(
        sha256.convert(bytes).toString(),
        '01c297128819bcf15f540e8a2cd739292409785cf67f536cdfbbe18e3d58952f',
      );
    });
  });

  group('jcsCanonicalize — canonicidad (RFC 8785)', () {
    test('escapa control y comillas como json.dumps(ensure_ascii=False)', () {
      expect(
        utf8.decode(jcsCanonicalize({'a': 'x\n"y\\z'})),
        r'{"a":"x\n\"y\\z"}',
      );
    });

    test('escapa caracteres de control no abreviables con \\u00XX lowercase', () {
      expect(utf8.decode(jcsCanonicalize({'a': 'a\u0001b'})), r'{"a":"a\u0001b"}');
    });

    test('emite no-ASCII literal (UTF-8, sin ensure_ascii)', () {
      expect(utf8.decode(jcsCanonicalize({'clave': 'ñ'})), '{"clave":"ñ"}');
    });

    test('ordena claves por code points UTF-16', () {
      expect(utf8.decode(jcsCanonicalize({'Z': 1, 'a': 2, 'b': 3})), '{"Z":1,"a":2,"b":3}');
    });

    test('serializa bool y null como literales JSON', () {
      expect(
        utf8.decode(jcsCanonicalize({'b': true, 'a': null, 'c': 0})),
        '{"a":null,"b":true,"c":0}',
      );
    });

    test('dict vacio y -0', () {
      expect(utf8.decode(jcsCanonicalize({})), '{}');
      expect(utf8.decode(jcsCanonicalize({'n': -0})), '{"n":0}');
    });

    test('rechaza tipos fuera del perfil del contrato', () {
      expect(() => jcsCanonicalize(1.5), throwsArgumentError);
      expect(() => jcsCanonicalize(['a']), throwsArgumentError);
      expect(() => jcsCanonicalize({'n': 1.5}), throwsArgumentError);
    });
  });
}
