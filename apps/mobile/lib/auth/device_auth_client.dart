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
// Mantenimiento de sesion (S0 — bloque offline sync):
//   - renovarSesion() reutiliza los MISMOS endpoints /api/auth/device/desafio
//     + /canjear con el JWT vigente como credencial (sin refresh token y sin
//     una segunda arquitectura de auth).
//   - Se renueva ~5 min antes de expira_el (guardado en AuthTokenStore).
//   - El JWT nuevo se persiste de forma atomica con guardarSesion().
//   - Un 401 de renovacion limpia la sesion (token) y se propaga.
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
    final canje = await _desafiarYCanjear(
      credencial: activacion.credencialBootstrap,
      dispositivoId: activacion.dispositivoId,
    );
    await tokenStore.guardarSesion(canje);
    return canje;
  }

  /// S0: renueva la sesion vigente ~5 min antes de expira_el.
  ///
  /// Reutiliza los MISMOS endpoints /api/auth/device/desafio + /canjear con el
  /// JWT vigente como credencial (sin refresh token). El JWT nuevo se persiste
  /// de forma atomica solo tras un canje exitoso. Sin access token lanza
  /// NoSessionException; un 401 limpia la sesion y se propaga.
  Future<CanjearAuth> renovarSesion() async {
    final token = await tokenStore.leerToken();
    if (token == null || token.isEmpty) {
      throw const NoSessionException();
    }
    final dispositivoId = await tokenStore.leerDispositivoId();
    if (dispositivoId == null || dispositivoId.isEmpty) {
      throw const NoSessionException();
    }
    try {
      final canje = await _desafiarYCanjear(
        credencial: token,
        dispositivoId: dispositivoId,
      );
      await tokenStore.guardarSesion(canje);
      return canje;
    } on AuthApiException catch (e) {
      if (e.es401) {
        await tokenStore.borrarToken();
      }
      rethrow;
    }
  }

  /// Indica si la sesion requiere renovacion: no hay sesion o expira dentro
  /// de [margen] (por defecto 5 minutos). Ignora un expira_el corrupto
  /// tratandolo como "renovar ya".
  Future<bool> requiereRenovacion({
    Duration margen = const Duration(minutes: 5),
  }) async {
    final token = await tokenStore.leerToken();
    if (token == null || token.isEmpty) return true;
    final expiraEl = await tokenStore.leerExpiraEl();
    if (expiraEl == null || expiraEl.isEmpty) return true;
    final expira = DateTime.tryParse(expiraEl);
    if (expira == null) return true;
    return expira.difference(DateTime.now().toUtc()) <= margen;
  }

  Future<CanjearAuth> _desafiarYCanjear({
    required String credencial,
    required String dispositivoId,
  }) async {
    final spki = await identity.getPublicKeySpki();
    final desafio = DesafioAuth.fromJson(await http.postJson(
      '/api/auth/device/desafio',
      body: const {},
      token: credencial,
    ));

    final firma = await _firmarAuth(desafio, dispositivoId, spki);
    return CanjearAuth.fromJson(await http.postJson(
      '/api/auth/device/canjear',
      body: {'challenge_id': desafio.challengeId, 'firma': firma},
    ));
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
