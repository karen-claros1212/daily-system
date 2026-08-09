// ─── Wrapper Dart del canal nativo de identidad (D7-02) ─────────────────────
//
// Expone el MethodChannel `daily_system/device_identity` registrado en
// MainActivity.kt. Reutiliza el motor AndroidKeyStore existente (EC P-256,
// SHA256withECDSA, clave privada no exportable); NO es una segunda
// implementacion de identidad.

import 'package:flutter/services.dart';

import 'jcs.dart' show base64UrlNoPad;

/// Error del canal nativo (PlatformException), normalizado.
class DeviceIdentityException implements Exception {
  final String code;
  final String message;

  const DeviceIdentityException(this.code, this.message);

  @override
  String toString() => 'DeviceIdentityException($code): $message';
}

/// Acceso al canal productivo de identidad del dispositivo.
class DeviceIdentity {
  static const MethodChannel channel = MethodChannel('daily_system/device_identity');

  /// Genera (o recupera) el par EC P-256 en AndroidKeyStore y devuelve el
  /// SPKI (X.509, base64) de la clave publica. La privada nunca se exporta.
  Future<String> generar() async {
    final res = await _invoke('generate');
    return res['spki'] as String;
  }

  /// SPKI de la clave publica actual (sin generarla si no existe).
  Future<String> getPublicKeySpki() async {
    final res = await _invoke('getPublicKeySpki');
    return res['spki'] as String;
  }

  /// Firma los bytes exactos del payload JCS (SHA256withECDSA) y devuelve la
  /// firma en base64url sin padding.
  Future<String> firmar(List<int> payload) async {
    final res = await _invoke('sign', {'payload': base64UrlNoPad(payload)});
    return res['firma'] as String;
  }

  /// Verifica una firma contra el payload (usado por tests y auditoria).
  Future<bool> verificar({required List<int> payload, required String firma}) async {
    final res = await _invoke('verify', {
      'payload': base64UrlNoPad(payload),
      'firma': firma,
    });
    return res['valida'] as bool;
  }

  /// Borra el alias de identidad del AndroidKeyStore.
  Future<bool> borrar() async {
    final res = await _invoke('delete');
    return res['borrado'] as bool;
  }

  /// True si el alias firmo correctamente un payload (auditoria de uso).
  Future<bool> isPrivateKeyExportable() async {
    final res = await _invoke('isPrivateKeyExportable');
    return res['exportable'] as bool;
  }

  Future<Map<String, dynamic>> _invoke(String method, [Map<String, dynamic>? args]) async {
    try {
      final raw = await channel.invokeMethod<Map<Object?, Object?>>(method, args);
      if (raw == null) {
        throw DeviceIdentityException('RESULTADO_NULO', 'el canal no respondio $method');
      }
      return raw.cast<String, dynamic>();
    } on PlatformException catch (e) {
      throw DeviceIdentityException(e.code, e.message ?? 'error nativo en $method');
    } on MissingPluginException {
      throw DeviceIdentityException(
        'CANAL_NO_DISPONIBLE',
        'el canal daily_system/device_identity no esta registrado',
      );
    }
  }
}
