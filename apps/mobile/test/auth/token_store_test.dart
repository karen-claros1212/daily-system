// AuthTokenStore: la sesion (access token JWT + expira_el + dispositivo_id)
// se guarda SOLO en secure storage (respaldado por AndroidKeyStore). Verifica
// guardar/leer/borrar de la sesion completa y que nunca quede en
// SharedPreferences (el almacenamiento es aislado).

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

    test('guardarSesion persiste token + expira_el + dispositivo', () async {
      final store = AuthTokenStore();
      await store.guardarSesion(_canje);
      expect(await store.leerToken(), 'jwt-de-sesion');
      expect(await store.leerExpiraEl(), '2026-08-08T13:00:00Z');
      expect(await store.leerDispositivoId(), 'dispositivo-1');
    });

    test('borrarToken limpia la sesion completa', () async {
      final store = AuthTokenStore();
      await store.guardarSesion(_canje);
      await store.borrarToken();
      expect(await store.leerToken(), isNull);
      expect(await store.leerExpiraEl(), isNull);
      expect(await store.leerDispositivoId(), isNull);
    });

    test('el token no queda en SharedPreferences', () async {
      SharedPreferences.setMockInitialValues({});
      await AuthTokenStore().guardarSesion(_canje);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString(AuthTokenStore.kTokenKey), isNull);
      expect(prefs.getKeys(), isEmpty);
    });

    test('la sesion queda bajo las claves daily_* en secure storage',
        () async {
      await AuthTokenStore().guardarSesion(_canje);
      final storage = const FlutterSecureStorage();
      final all = await storage.readAll();
      expect(all[AuthTokenStore.kTokenKey], 'jwt-de-sesion');
      expect(all[AuthTokenStore.kExpiraElKey], '2026-08-08T13:00:00Z');
      expect(all[AuthTokenStore.kDispositivoKey], 'dispositivo-1');
    });
  });
}
