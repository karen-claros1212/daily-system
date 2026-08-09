// AuthTokenStore: el access token JWT se guarda SOLO en secure storage
// (respaldado por AndroidKeyStore). Verifica guardar/leer/borrar y que el
// token nunca quede en SharedPreferences (el almacenamiento es aislado).

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:daily_system/auth/auth_token_store.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
  });

  group('AuthTokenStore — secure storage', () {
    test('sin sesion el token es null', () async {
      final store = AuthTokenStore();
      expect(await store.leerToken(), isNull);
    });

    test('guarda y lee el access token', () async {
      final store = AuthTokenStore();
      await store.guardarToken('jwt-de-sesion');
      expect(await store.leerToken(), 'jwt-de-sesion');
    });

    test('borrarToken limpia la sesion', () async {
      final store = AuthTokenStore();
      await store.guardarToken('jwt-de-sesion');
      await store.borrarToken();
      expect(await store.leerToken(), isNull);
    });

    test('el token no queda en SharedPreferences', () async {
      SharedPreferences.setMockInitialValues({});
      await AuthTokenStore().guardarToken('jwt-secreto');
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString(AuthTokenStore.kTokenKey), isNull);
      expect(prefs.getKeys(), isEmpty);
    });

    test('se guarda bajo la clave daily_access_token', () async {
      await AuthTokenStore().guardarToken('jwt');
      final storage = const FlutterSecureStorage();
      final all = await storage.readAll();
      expect(all[AuthTokenStore.kTokenKey], 'jwt');
    });
  });
}
