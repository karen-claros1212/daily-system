// ─── Almacenamiento seguro del access token (JWT productivo) ────────────────
//
// El token de sesion se guarda SOLO en secure storage respaldado por
// AndroidKeyStore (flutter_secure_storage). Prohibido por contrato usar
// SharedPreferences para el access token.

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Puerta de entrada unica al almacenamiento del access token.
class AuthTokenStore {
  static const String kTokenKey = 'daily_access_token';

  final FlutterSecureStorage _storage;

  AuthTokenStore({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  /// Token JWT de sesion, o null si no hay sesion activa.
  Future<String?> leerToken() => _storage.read(key: kTokenKey);

  /// Persiste el token JWT emitido por /api/auth/device/canjear.
  Future<void> guardarToken(String token) =>
      _storage.write(key: kTokenKey, value: token);

  /// Limpia la sesion (contrato: un 401 de auth/bootstrap termina la sesion).
  Future<void> borrarToken() => _storage.delete(key: kTokenKey);
}
