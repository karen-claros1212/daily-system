// Validacion lexical vinculante de los campos firmados (perfil 13.3 y D7-H2):
// un valor no conforme produce payload no valido, ANTES de serializar.

import 'package:flutter_test/flutter_test.dart';
import 'package:daily_system/auth/jcs.dart';

const _validNonce = 'ZmljdGljaW9uZXN1ZXJ0ZTY0bGluZzMyYnl0ZWNzcHI';
final _validHash = 'a' * 64;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('buildPayloadActivacion (daily-v1) — rechaza valores no canonicos', () {
    void expectInvalid({String protocolVersion = 'daily-v1', String? environment,
        String? attemptId, String? nonce, String? publicKeyHash,
        String? expiresAt}) {
      expect(
        () => buildPayloadActivacion(
          protocolVersion: protocolVersion,
          environment: environment ?? 'development',
          attemptId: attemptId ?? '11111111-2222-4333-8444-555555555555',
          nonce: nonce ?? _validNonce,
          publicKeyHash: publicKeyHash ?? _validHash,
          expiresAt: expiresAt ?? '2026-08-08T12:00:00Z',
        ),
        throwsA(isA<JcsValidationException>()),
      );
    }

    test('protocol_version distinto de daily-v1', () {
      expectInvalid(protocolVersion: 'otro');
    });

    test('environment fuera del set valido', () {
      expectInvalid(environment: 'production-sandbox');
    });

    test('attempt_id no es UUID lowercase 8-4-4-4-12', () {
      for (final bad in [
        '11111111-2222-4333-8444-5555555555555',
        '11111111-2222-4333-8444-55555555555',
        'AAAAAAAa-2222-4333-8444-555555555555',
        'no-es-un-uuid',
        '',
      ]) {
        expectInvalid(attemptId: bad);
      }
    });

    test('nonce debe ser base64url sin padding de 43 caracteres', () {
      for (final bad in [
        'a' * 42,
        'a' * 44,
        'a+==' ,
        'a/==',
        '',
      ]) {
        expectInvalid(nonce: bad);
      }
    });

    test('public_key_hash debe ser hex lowercase de 64', () {
      for (final bad in ['A' * 64, 'a' * 63, 'a' * 65, '', 'gg']) {
        expectInvalid(publicKeyHash: bad);
      }
    });

    test('expires_at debe ser RFC 3339 en segundos Z', () {
      for (final bad in [
        '2026-08-08T12:00:00',
        '2026-08-08T12:00:00.000Z',
        '2026-08-08 12:00:00Z',
        '',
      ]) {
        expectInvalid(expiresAt: bad);
      }
    });
  });

  group('buildPayloadAuth (daily-auth-v1) — rechaza valores no canonicos', () {
    test('purpose distinto de issue_access_token', () {
      expect(
        () => buildPayloadAuth(
          purpose: 'revocar',
          environment: 'development',
          challengeId: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
          deviceId: '11111111-2222-4333-8444-555555555555',
          nonce: _validNonce,
          publicKeyHash: _validHash,
          expiresAt: '2026-08-08T12:00:00Z',
        ),
        throwsA(isA<JcsValidationException>()),
      );
    });

    test('challenge_id y device_id deben ser UUID lowercase', () {
      for (final bad in ['no-uuid', 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeeff']) {
        expect(
          () => buildPayloadAuth(
            purpose: 'issue_access_token',
            environment: 'development',
            challengeId: bad,
            deviceId: '11111111-2222-4333-8444-555555555555',
            nonce: _validNonce,
            publicKeyHash: _validHash,
            expiresAt: '2026-08-08T12:00:00Z',
          ),
          throwsA(isA<JcsValidationException>()),
        );
        expect(
          () => buildPayloadAuth(
            purpose: 'issue_access_token',
            environment: 'development',
            challengeId: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
            deviceId: bad,
            nonce: _validNonce,
            publicKeyHash: _validHash,
            expiresAt: '2026-08-08T12:00:00Z',
          ),
          throwsA(isA<JcsValidationException>()),
        );
      }
    });

    test('nonce, hash y expira_el heredan la validacion lexical', () {
      for (final bad in ['a' * 42, 'a' * 44, 'x+==']) {
        expect(
          () => buildPayloadAuth(
            purpose: 'issue_access_token',
            environment: 'development',
            challengeId: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
            deviceId: '11111111-2222-4333-8444-555555555555',
            nonce: bad,
            publicKeyHash: _validHash,
            expiresAt: '2026-08-08T12:00:00Z',
          ),
          throwsA(isA<JcsValidationException>()),
        );
      }
    });
  });

  group('base64UrlNoPad', () {
    test('codifica sin padding y con alphabet URL-safe', () {
      expect(base64UrlNoPad([0xfb, 0xff, 0xef]), '-__v');
      expect(base64UrlNoPad([0x00, 0x00, 0x00]), 'AAAA');
      expect(base64UrlNoPad([0xfb, 0xff]), '-_8');
      expect(base64UrlNoPad([0xff]), '_w');
      expect(base64UrlNoPad([0x3e, 0x00]), 'PgA');
    });
  });
}
