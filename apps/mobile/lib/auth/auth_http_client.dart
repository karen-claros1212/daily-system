// ─── Unico cliente HTTP del flujo productivo (bloque mobile auth) ───────────
//
// Un solo `http.Client` compartido por todo el flujo de auth/bootstrap.
// Traduce respuestas HTTP a excepciones de dominio:
//   - 401 -> AuthApiException (la sesion queda invalida: quien la usa debe
//     limpiar el token y finalizar la sesion)
//   - 400/403/404/422 -> AuthApiException (error de validacion/permiso)
//   - fallos de red/JSON -> AuthNetworkException

import 'dart:convert';

import 'package:http/http.dart' as http;

/// Error de API con status y detail del backend.
class AuthApiException implements Exception {
  final int statusCode;
  final String detail;

  const AuthApiException(this.statusCode, this.detail);

  bool get es401 => statusCode == 401;

  @override
  String toString() => 'AuthApiException($statusCode): $detail';
}

/// Falla de red, timeout o respuesta no parseable.
class AuthNetworkException implements Exception {
  final String message;

  const AuthNetworkException(this.message);

  @override
  String toString() => 'AuthNetworkException: $message';
}

/// Cliente unico y tipado para los endpoints del flujo productivo.
class AuthHttpClient {
  final String baseUrl;
  final http.Client _client;
  final Duration timeout;

  AuthHttpClient({
    required this.baseUrl,
    http.Client? client,
    this.timeout = const Duration(seconds: 15),
  }) : _client = client ?? http.Client();

  /// POST JSON con bearer opcional. Devuelve el cuerpo JSON decodificado.
  Future<Map<String, dynamic>> postJson(
    String path, {
    required Map<String, dynamic> body,
    String? token,
  }) async {
    final headers = <String, String>{
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
    if (token != null) {
      headers['Authorization'] = 'Bearer $token';
    }
    return _parse(_send(() => _client.post(
          _url(path),
          headers: headers,
          body: jsonEncode(body),
        )));
  }

  /// GET con bearer opcional. Devuelve el cuerpo JSON decodificado.
  Future<Map<String, dynamic>> getJson(String path, {String? token}) async {
    final headers = <String, String>{'Accept': 'application/json'};
    if (token != null) {
      headers['Authorization'] = 'Bearer $token';
    }
    return _parse(_send(() => _client.get(_url(path), headers: headers)));
  }

  Uri _url(String path) => Uri.parse('$baseUrl$path');

  Future<http.Response> _send(Future<http.Response> Function() request) async {
    try {
      return await request().timeout(timeout);
    } on Exception catch (e) {
      throw AuthNetworkException('fallo de red hacia $baseUrl: $e');
    }
  }

  Future<Map<String, dynamic>> _parse(Future<http.Response> pending) async {
    final response = await pending;
    final status = response.statusCode;
    final detail = _extractDetail(response);

    if (status >= 200 && status < 300) {
      if (response.body.isEmpty) return const {};
      try {
        final decoded = jsonDecode(response.body);
        if (decoded is Map<String, dynamic>) return decoded;
        throw const AuthNetworkException('respuesta JSON no es un objeto');
      } on FormatException {
        throw const AuthNetworkException('respuesta no es JSON valido');
      }
    }
    throw AuthApiException(status, detail);
  }

  static String _extractDetail(http.Response response) {
    if (response.body.isEmpty) return '';
    try {
      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic> && decoded['detail'] is String) {
        return decoded['detail'] as String;
      }
    } on FormatException {
      // cuerpo no JSON: se usa el status como detalle.
    }
    return response.body;
  }
}
