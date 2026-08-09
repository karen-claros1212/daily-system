// ─── Orquestador del flujo productivo de auth + bootstrap (bloque mobile) ───
//
// Flujo (contrato D7, bloque mobile):
//   1. activacion/canje  -> credencial_bootstrap temporal
//   2. desafio auth      -> firma daily-auth-v1 con AndroidKeyStore
//   3. canjear desafio   -> access token JWT (se guarda en secure storage)
//   4. bootstrap         -> identidad operativa (negocio, cobrador,
//                           dispositivo, version_asignacion, ruta unica,
//                           ruta_version)
//
// Reglas de contrato aplicadas aqui:
//   - La credencial bootstrap NUNCA se reutiliza como access token.
//   - El access token se guarda SOLO en secure storage (AuthTokenStore).
//   - La ruta unica sale del bootstrap del servidor; la app no elige rutas ni
//     descarga listas. Reasignacion R1->R2 = nuevo bootstrap del servidor.
//   - Un 401 de auth/bootstrap limpia la sesion (token) y se propaga.

import 'dart:convert';

import 'package:crypto/crypto.dart';

import 'auth_http_client.dart';
import 'auth_token_store.dart';
import 'device_identity.dart';
import 'jcs.dart';
import 'models.dart';

/// No hay sesion activa (no hay access token guardado).
class NoSessionException implements Exception {
  const NoSessionException();

  @override
  String toString() => 'NoSessionException: no hay access token de sesion';
}

/// Orquesta los pasos del flujo productivo sobre la identidad del dispositivo.
class DeviceAuthClient {
  final AuthHttpClient http;
  final DeviceIdentity identity;
  final AuthTokenStore tokenStore;

  DeviceAuthClient({
    required this.http,
    required this.identity,
    required this.tokenStore,
  });

  /// Paso 1: activa el dispositivo con un codigo de activacion. Devuelve la
  /// credencial bootstrap temporal (NUNCA se guarda como access token).
  Future<CanjearActivacion> activar({
    required String token,
    String? modelo,
    String? plataforma,
  }) async {
    final spki = await identity.generar();
    final desafio = DesafioActivacion.fromJson(await http.postJson(
      '/api/activaciones/desafio',
      body: {
        'token': token,
        'clave_publica': spki,
        'modelo': ?modelo,
        'plataforma': ?plataforma,
      },
    ));

    final firma = await _firmarActivacion(desafio, spki);
    return CanjearActivacion.fromJson(await http.postJson(
      '/api/activaciones/canjear',
      body: {'intento_id': desafio.intentoId, 'firma': firma},
    ));
  }

  /// Pasos 2-3: canjea una sesion productiva con la credencial bootstrap.
  /// Guarda el access token JWT en secure storage y lo devuelve.
  Future<CanjearAuth> canjearSesion(CanjearActivacion activacion) async {
    final spki = await identity.getPublicKeySpki();
    final desafio = DesafioAuth.fromJson(await http.postJson(
      '/api/auth/device/desafio',
      body: const {},
      token: activacion.credencialBootstrap,
    ));

    final firma = await _firmarAuth(desafio, activacion.dispositivoId, spki);
    final canje = CanjearAuth.fromJson(await http.postJson(
      '/api/auth/device/canjear',
      body: {'challenge_id': desafio.challengeId, 'firma': firma},
    ));
    await tokenStore.guardarToken(canje.token);
    return canje;
  }

  /// Paso 4: obtiene la identidad operativa con el access token. Un 401
  /// limpia la sesion (token) y se propaga; sin token lanza NoSessionException.
  Future<BootstrapIdentity> bootstrap() async {
    final token = await tokenStore.leerToken();
    if (token == null || token.isEmpty) {
      throw const NoSessionException();
    }
    try {
      return BootstrapIdentity.fromJson(
        await http.getJson('/api/mobile/bootstrap', token: token),
      );
    } on AuthApiException catch (e) {
      if (e.es401) {
        await tokenStore.borrarToken();
      }
      rethrow;
    }
  }

  /// Cierra la sesion: limpia el access token (no borra la identidad del
  /// AndroidKeyStore, que persiste entre sesiones).
  Future<void> cerrarSesion() => tokenStore.borrarToken();

  Future<String> _firmarActivacion(DesafioActivacion desafio, String spki) async {
    final payload = buildPayloadActivacion(
      protocolVersion: kProtocolVersionActivacion,
      environment: desafio.environment,
      attemptId: desafio.intentoId,
      nonce: desafio.nonce,
      publicKeyHash: _publicKeyHash(spki),
      expiresAt: desafio.expiraEl,
    );
    return identity.firmar(payload);
  }

  Future<String> _firmarAuth(DesafioAuth desafio, String dispositivoId, String spki) async {
    final payload = buildPayloadAuth(
      purpose: kPurposeIssueAccessToken,
      environment: desafio.environment,
      challengeId: desafio.challengeId,
      deviceId: dispositivoId,
      nonce: desafio.nonce,
      publicKeyHash: _publicKeyHash(spki),
      expiresAt: desafio.expiraEl,
    );
    return identity.firmar(payload);
  }

  /// SHA-256 del SPKI (DER X.509) en hex lowercase, como exige el contrato.
  /// Tolera base64 sin padding (el canal puede omitir el '=' final).
  static String _publicKeyHash(String spkiBase64) {
    var padded = spkiBase64;
    while (padded.length % 4 != 0) {
      padded = '$padded=';
    }
    return sha256.convert(base64Decode(padded)).toString();
  }
}
