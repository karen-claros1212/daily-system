// AuthTokenStore: la sesión (access token JWT + expira_el + dispositivo_id)
// se guarda como UN ÚNICO envelope JSON bajo `daily_session` en secure storage
// (respaldado por AndroidKeyStore). Verifica atomicidad (una sola write),
// migración tolerante desde las claves legadas, envelope corrupto e invalidación.

import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:daily_system/auth/auth_token_store.dart';
import 'package:daily_system/auth/models.dart';

const _canje = CanjearAuth(
  token: 'jwt-de-sesion',
  negocioId: 'negocio-1',
  usuarioId: 'usuario-1',
  dispositivoId: 'dispositivo-1',
  versionAsignacion: 3,
  expiraEl: '2026-08-08T13:00:00Z',
);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
  });

  group('AuthTokenStore — secure storage', () {
    test('sin sesion el token es null', () async {
      final store = AuthTokenStore();
      expect(await store.leerToken(), isNull);
      expect(await store.leerExpiraEl(), isNull);
      expect(await store.leerDispositivoId(), isNull);
    });

    test('guardarSesion persiste token + expira_el + dispositivo en un unico '
        'envelope atomico', () async {
      final store = AuthTokenStore();
      await store.guardarSesion(_canje);

      expect(await store.leerToken(), 'jwt-de-sesion');
      expect(await store.leerExpiraEl(), '2026-08-08T13:00:00Z');
      expect(await store.leerDispositivoId(), 'dispositivo-1');

      final all = await const FlutterSecureStorage().readAll();
      expect(all[AuthTokenStore.kSessionKey], isNotNull);
      expect(all[AuthTokenStore.kTokenKey], isNull);
      expect(all[AuthTokenStore.kExpiraElKey], isNull);
      expect(all[AuthTokenStore.kDispositivoKey], isNull);
      expect(jsonDecode(all[AuthTokenStore.kSessionKey]!)['token'],
          'jwt-de-sesion');
    });

    test('borrarToken limpia la sesion completa', () async {
      final store = AuthTokenStore();
      await store.guardarSesion(_canje);
      await store.borrarToken();
      expect(await store.leerToken(), isNull);
      expect(await store.leerExpiraEl(), isNull);
      expect(await store.leerDispositivoId(), isNull);
      final all = await const FlutterSecureStorage().readAll();
      expect(all[AuthTokenStore.kSessionKey], isNull);
    });

    test('el token no queda en SharedPreferences', () async {
      SharedPreferences.setMockInitialValues({});
      await AuthTokenStore().guardarSesion(_canje);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString(AuthTokenStore.kTokenKey), isNull);
      expect(prefs.getKeys(), isEmpty);
    });

    test('renovacion sustituye el envelope completo en un write', () async {
      final store = AuthTokenStore();
      await store.guardarSesion(_canje);
      await store.guardarSesion(const CanjearAuth(
        token: 'jwt-renovado',
        negocioId: 'negocio-1',
        usuarioId: 'usuario-1',
        dispositivoId: 'dispositivo-1',
        versionAsignacion: 3,
        expiraEl: '2026-08-08T14:00:00Z',
      ));

      expect(await store.leerToken(), 'jwt-renovado');
      expect(await store.leerExpiraEl(), '2026-08-08T14:00:00Z');
      final all = await const FlutterSecureStorage().readAll();
      // Una sola clave: el envelope. La metadata vieja no queda aislada.
      expect(all.keys, contains(AuthTokenStore.kSessionKey));
      expect(all.keys, isNot(contains(AuthTokenStore.kTokenKey)));
    });

    test('envelope corrupto -> sesion invalida (null)', () async {
      FlutterSecureStorage.setMockInitialValues({
        AuthTokenStore.kSessionKey: 'no-es-json-valid',
      });
      final store = AuthTokenStore();
      expect(await store.leerToken(), isNull);
      expect(await store.leerExpiraEl(), isNull);
      expect(await store.leerDispositivoId(), isNull);
      final all = await const FlutterSecureStorage().readAll();
      expect(all[AuthTokenStore.kSessionKey], isNull);
    });

    test('migracion tolerante desde claves legadas al envelope', () async {
      FlutterSecureStorage.setMockInitialValues({
        AuthTokenStore.kTokenKey: 'jwt-legado',
        AuthTokenStore.kExpiraElKey: '2026-08-08T13:00:00Z',
        AuthTokenStore.kDispositivoKey: 'disp-legado',
      });
      final store = AuthTokenStore();

      expect(await store.leerToken(), 'jwt-legado');
      expect(await store.leerExpiraEl(), '2026-08-08T13:00:00Z');
      expect(await store.leerDispositivoId(), 'disp-legado');

      final all = await const FlutterSecureStorage().readAll();
      expect(all[AuthTokenStore.kSessionKey], isNotNull);
      expect(all[AuthTokenStore.kTokenKey], isNull);
      expect(all[AuthTokenStore.kExpiraElKey], isNull);
      expect(all[AuthTokenStore.kDispositivoKey], isNull);
    });
  });
}
