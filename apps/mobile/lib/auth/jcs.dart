// ─── JCS (RFC 8785) canonicalization — perfiles daily-v1 y daily-auth-v1 ───
//
// Replica byte a byte del motor del backend (apps/api/src/services/jcs.py y
// auth_jcs.py):
//   - daily-v1      : canje de activacion (payload firmado de 6 campos)
//   - daily-auth-v1 : desafio/canje del token productivo (payload de 8 campos)
//   - Canonizacion segun RFC 8785: claves ordenadas por code points (unidades
//     UTF-16), strings segun json.dumps(ensure_ascii=False), sin floats.
//
// El vector de prueba (test/auth/jcs_vector_test.dart) compara la salida
// byte a byte contra la producida por el backend: este modulo debe producir
// exactamente esos bytes.

import 'dart:convert';
import 'dart:typed_data';

/// Perfil de activacion (daily-v1) — canje de codigo de activacion.
const String kProtocolVersionActivacion = 'daily-v1';

/// Perfil de auth (daily-auth-v1) — desafio/canje del token productivo.
const String kProtocolVersionAuth = 'daily-auth-v1';

/// Unico proposito admitido por el perfil daily-auth-v1.
const String kPurposeIssueAccessToken = 'issue_access_token';

const List<String> kEnvironmentsValidos = ['development', 'staging', 'production'];

/// Orden lexical vinculante de los campos firmados por perfil.
const List<String> kSignedFieldsActivacion = [
  'attempt_id',
  'environment',
  'expires_at',
  'nonce',
  'protocol_version',
  'public_key_hash',
];

const List<String> kSignedFieldsAuth = [
  'challenge_id',
  'device_id',
  'environment',
  'expires_at',
  'nonce',
  'protocol_version',
  'public_key_hash',
  'purpose',
];

final RegExp _reUuidLower = RegExp(
  r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
);
final RegExp _reNonceBase64Url = RegExp(r'^[A-Za-z0-9_-]{43}$');
final RegExp _reHex64 = RegExp(r'^[0-9a-f]{64}$');
final RegExp _reRfc3339Seconds = RegExp(
  r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$',
);

/// Error de validacion lexical de un campo firmado (equivale al ValueError
/// del backend): el payload solo es valido si cada valor conforma su forma
/// canonica antes de serializar.
class JcsValidationException implements Exception {
  final String message;
  JcsValidationException(this.message);

  @override
  String toString() => 'JcsValidationException: $message';
}

String _validarUuidLowercase(String value, String field) {
  if (!_reUuidLower.hasMatch(value)) {
    throw JcsValidationException('$field debe ser un UUID lowercase (8-4-4-4-12)');
  }
  return value;
}

String _validarNonce(String value) {
  if (!_reNonceBase64Url.hasMatch(value)) {
    throw JcsValidationException(
      'nonce debe ser base64url sin padding de 43 caracteres (32 bytes)',
    );
  }
  return value;
}

String _validarPublicKeyHash(String value) {
  if (!_reHex64.hasMatch(value)) {
    throw JcsValidationException(
      'public_key_hash debe ser hex lowercase de 64 caracteres (SHA-256)',
    );
  }
  return value;
}

String _validarRfc3339Seconds(String value) {
  if (!_reRfc3339Seconds.hasMatch(value)) {
    throw JcsValidationException(
      'expires_at debe ser RFC 3339 en segundos (YYYY-MM-DDTHH:MM:SSZ)',
    );
  }
  return value;
}

/// JSON string literal per RFC 8785 (UTF-8 literal, sin ensure_ascii).
///
/// Replica json.dumps(value, ensure_ascii=False): escapa los caracteres de
/// control con la forma corta cuando existe (\b \t \n \f \r) y \u00XX en el
/// resto (hex lowercase de 4 digitos), mas \u0022 y \u005C. Todo lo demas
/// (incluido no-ASCII) se emite literal.
String _stringify(String value) {
  final buf = StringBuffer('"');
  for (final rune in value.runes) {
    if (rune == 0x22) {
      buf.write(r'\"');
    } else if (rune == 0x5C) {
      buf.write(r'\\');
    } else if (rune == 0x08) {
      buf.write(r'\b');
    } else if (rune == 0x09) {
      buf.write(r'\t');
    } else if (rune == 0x0A) {
      buf.write(r'\n');
    } else if (rune == 0x0C) {
      buf.write(r'\f');
    } else if (rune == 0x0D) {
      buf.write(r'\r');
    } else if (rune <= 0x1F) {
      buf.write(r'\u00');
      buf.write(rune.toRadixString(16).padLeft(2, '0'));
    } else {
      buf.writeCharCode(rune);
    }
  }
  buf.write('"');
  return buf.toString();
}

/// Canonicaliza `obj` al subconjunto permitido por el contrato.
///
/// Soporta dict (claves string), strings, ints, bools y null. Los ints se
/// serializan sin ceros a la izquierda (-0 -> 0). Cualquier otro tipo se
/// rechaza (el contrato prohibe floats y numeros no enteros firmados).
Uint8List jcsCanonicalize(Object? obj) {
  return utf8.encode(_canonicalizeToString(obj));
}

String _canonicalizeToString(Object? obj) {
  if (obj is Map) {
    if (obj.isEmpty) return '{}';
    final parts = StringBuffer('{');
    final keys = obj.keys.map((k) => k.toString()).toList()
      ..sort((a, b) => _compareUtf16CodeUnits(a, b));
    for (final key in keys) {
      parts.write(_stringify(key));
      parts.write(':');
      parts.write(_canonicalizeToString(obj[key]));
      parts.write(',');
    }
    final s = parts.toString();
    return '${s.substring(0, s.length - 1)}}';
  }
  if (obj is String) return _stringify(obj);
  if (obj is bool) return obj ? 'true' : 'false';
  if (obj == null) return 'null';
  if (obj is int) return obj == 0 ? '0' : obj.toString();
  throw ArgumentError(
    'Tipo no canonicalizable por el perfil del contrato: ${obj.runtimeType}',
  );
}

/// Ordena por code points (unidades de codigo UTF-16), como
/// Python sorted(..., key=lambda k: k.encode('utf-16-be')).
int _compareUtf16CodeUnits(String a, String b) {
  final ua = a.codeUnits;
  final ub = b.codeUnits;
  final n = ua.length < ub.length ? ua.length : ub.length;
  for (var i = 0; i < n; i++) {
    if (ua[i] != ub[i]) return ua[i] < ub[i] ? -1 : 1;
  }
  if (ua.length == ub.length) return 0;
  return ua.length < ub.length ? -1 : 1;
}

/// Construye los bytes JCS exactos del payload firmado de activacion
/// (perfil daily-v1). Valida la representacion lexical vinculante ANTES de
/// serializar: un valor no conforme produce payload no valido.
Uint8List buildPayloadActivacion({
  required String protocolVersion,
  required String environment,
  required String attemptId,
  required String nonce,
  required String publicKeyHash,
  required String expiresAt,
}) {
  if (protocolVersion != kProtocolVersionActivacion) {
    throw JcsValidationException("protocol_version debe ser 'daily-v1'");
  }
  if (!kEnvironmentsValidos.contains(environment)) {
    throw JcsValidationException('environment invalido: $environment');
  }
  _validarUuidLowercase(attemptId, 'attempt_id');
  _validarNonce(nonce);
  _validarPublicKeyHash(publicKeyHash);
  _validarRfc3339Seconds(expiresAt);

  return jcsCanonicalize({
    'protocol_version': protocolVersion,
    'environment': environment,
    'attempt_id': attemptId,
    'nonce': nonce,
    'public_key_hash': publicKeyHash,
    'expires_at': expiresAt,
  });
}

/// Construye los bytes JCS exactos del payload firmado de auth
/// (perfil daily-auth-v1). Valida la representacion lexical vinculante ANTES
/// de serializar: un valor no conforme produce payload no valido.
Uint8List buildPayloadAuth({
  required String purpose,
  required String environment,
  required String challengeId,
  required String deviceId,
  required String nonce,
  required String publicKeyHash,
  required String expiresAt,
}) {
  if (purpose != kPurposeIssueAccessToken) {
    throw JcsValidationException('purpose invalido: $purpose');
  }
  if (!kEnvironmentsValidos.contains(environment)) {
    throw JcsValidationException('environment invalido: $environment');
  }
  _validarUuidLowercase(challengeId, 'challenge_id');
  _validarUuidLowercase(deviceId, 'device_id');
  _validarNonce(nonce);
  _validarPublicKeyHash(publicKeyHash);
  _validarRfc3339Seconds(expiresAt);

  return jcsCanonicalize({
    'protocol_version': kProtocolVersionAuth,
    'purpose': purpose,
    'environment': environment,
    'challenge_id': challengeId,
    'device_id': deviceId,
    'nonce': nonce,
    'public_key_hash': publicKeyHash,
    'expires_at': expiresAt,
  });
}

/// Codifica bytes a base64url sin padding (usado por el canal nativo y por
/// la firma en la API).
String base64UrlNoPad(List<int> bytes) {
  return base64UrlEncode(bytes).replaceAll('=', '');
}
