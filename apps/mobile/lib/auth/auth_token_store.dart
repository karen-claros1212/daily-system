// ─── Almacenamiento seguro de la sesion (JWT productivo) ─────────────────────
//
// El token de sesion se guarda SOLO en secure storage respaldado por
// AndroidKeyStore (flutter_secure_storage). Prohibido por contrato usar
// SharedPreferences para el access token.
//
// La sesion tambien conserva expira_el (RFC3339) y el dispositivo_id: son los
// datos que permiten RENOVAR la sesion (~5 min antes de expirar) reutilizando
// los mismos endpoints /api/auth/device/desafio + /canjear sin refresh token
// y sin una segunda arquitectura de auth.

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'models.dart';

/// Puerta de entrada unica al almacenamiento de la sesion.
class AuthTokenStore {
  static const String kTokenKey = 'daily_access_token';
  static const String kExpiraElKey = 'daily_access_token_expira_el';
  static const String kDispositivoKey = 'daily_dispositivo_id';

  final FlutterSecureStorage _storage;

  AuthTokenStore({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  /// Token JWT de sesion, o null si no hay sesion activa.
  Future<String?> leerToken() => _storage.read(key: kTokenKey);

  /// expira_el (RFC3339) del token vigente, o null si no hay sesion.
  Future<String?> leerExpiraEl() => _storage.read(key: kExpiraElKey);

  /// Dispositivo autenticado, requerido para firmar la renovacion.
  Future<String?> leerDispositivoId() => _storage.read(key: kDispositivoKey);

  /// Persiste la sesion completa emitida por /api/auth/device/canjear:
  /// token + expira_el + dispositivo_id. Solo se llama con un canje EXITOSO
  /// (el JWT nuevo nunca se escribe si el canje fallo).
  Future<void> guardarSesion(CanjearAuth canje) async {
    await _storage.write(key: kTokenKey, value: canje.token);
    await _storage.write(key: kExpiraElKey, value: canje.expiraEl);
    await _storage.write(key: kDispositivoKey, value: canje.dispositivoId);
  }

  /// Limpia la sesion (contrato: un 401 de auth/bootstrap termina la sesion).
  Future<void> borrarToken() async {
    await _storage.delete(key: kTokenKey);
    await _storage.delete(key: kExpiraElKey);
    await _storage.delete(key: kDispositivoKey);
  }
}
