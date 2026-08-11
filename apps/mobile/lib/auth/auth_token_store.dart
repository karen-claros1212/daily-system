// ─── Almacenamiento seguro de la sesión (JWT productivo) ──────────────────────
//
// La sesión (access token JWT + expira_el + dispositivo_id) se guarda como un
// ÚNICO envelope JSON bajo la clave `daily_session` en flutter_secure_storage
// (respaldado por AndroidKeyStore). Una sola write() garantiza atomicidad: el
// JWT nuevo nunca queda aparejado a metadata vieja/incompleta; la renovación
// sustituye el envelope completo en un único write. Prohibido por contrato
// usar SharedPreferences para el access token.
//
// Migración tolerante: si existen las 3 claves legadas del commit anterior
// (daily_access_token / _expira_el / _dispositivo_id), se leen como
// compatibilidad y se migran al envelope la primera vez.

import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'models.dart';

/// Puerta de entrada única al almacenamiento de la sesión.
class AuthTokenStore {
  /// Clave única del envelope serializado.
  static const String kSessionKey = 'daily_session';

  /// Claves legadas (solo para migración tolerante, no se escriben de nuevo).
  static const String kTokenKey = 'daily_access_token';
  static const String kExpiraElKey = 'daily_access_token_expira_el';
  static const String kDispositivoKey = 'daily_dispositivo_id';

  final FlutterSecureStorage _storage;

  AuthTokenStore({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  Map<String, dynamic> get _emptySession =>
      {'token': null, 'expira_el': null, 'dispositivo_id': null};

  /// Lee el envelope, migrando tolerante desde las claves legadas si aún no
  /// existe. Un envelope corrupto se invalida (borra la clave quedada pegada).
  Future<Map<String, dynamic>> _leerEnvelope() async {
    final raw = await _storage.read(key: kSessionKey);
    if (raw != null) {
      try {
        final decoded = jsonDecode(raw) as Map<String, dynamic>;
        return Map<String, dynamic>.from(decoded);
      } catch (_) {
        await _storage.delete(key: kSessionKey);
        return _emptySession;
      }
    }

    final token = await _storage.read(key: kTokenKey);
    final expiraEl = await _storage.read(key: kExpiraElKey);
    final dispositivoId = await _storage.read(key: kDispositivoKey);
    final migrado = {
      'token': token,
      'expira_el': expiraEl,
      'dispositivo_id': dispositivoId,
    };
    if (token != null || expiraEl != null || dispositivoId != null) {
      await _storage.write(key: kSessionKey, value: jsonEncode(migrado));
      await _storage.delete(key: kTokenKey);
      await _storage.delete(key: kExpiraElKey);
      await _storage.delete(key: kDispositivoKey);
    }
    return migrado;
  }

  Future<T?> _leerCampo<T>(String campo) async {
    final env = await _leerEnvelope();
    final v = env[campo];
    return v is T ? v : null;
  }

  /// Token JWT de sesión, o null si no hay sesión activa.
  Future<String?> leerToken() => _leerCampo<String>('token');

  /// expira_el (RFC3339) del token vigente, o null si no hay sesión.
  Future<String?> leerExpiraEl() => _leerCampo<String>('expira_el');

  /// Dispositivo autenticado, requerido para firmar la renovación.
  Future<String?> leerDispositivoId() => _leerCampo<String>('dispositivo_id');

  /// Persiste la sesión completa emitida por /api/auth/device/canjear en un
  /// único write() atómico (el JWT nuevo nunca se escribe si el canje falló).
  Future<void> guardarSesion(CanjearAuth canje) async {
    final env = {
      'token': canje.token,
      'expira_el': canje.expiraEl,
      'dispositivo_id': canje.dispositivoId,
    };
    await _storage.write(key: kSessionKey, value: jsonEncode(env));
  }

  /// Limpia la sesión (contrato: un 401 de auth/bootstrap termina la sesión).
  Future<void> borrarToken() async {
    await _storage.delete(key: kSessionKey);
  }
}
