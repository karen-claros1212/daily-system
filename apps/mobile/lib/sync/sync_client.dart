// ─── Cliente del sync offline (bloque offline sync, S2) ─────────────────────
//
// Orquesta la descarga del dataset de la ruta activa unica:
//   1. Si la sesion requiere renovacion (~5 min antes de expira_el) se
//      renueva con DeviceAuthClient.renovarSesion() ANTES de consumir el
//      recurso (S0 + S1 coordinados, sin esperar el 401).
//   2. GET /api/mobile/sync con el access token JWT.
//   3. Se refleja el dataset en el modelo local (SyncRepository, por dataset).
//   4. Un 401 de cualquier paso limpia la sesion (token) y se propaga.
//
// Reglas de contrato aplicadas aqui:
//   - El scope del dataset lo deriva el servidor (ruta activa unica del
//     cobrador); el movil no elige rutas ni pide por query params.
//   - El JWT nunca se reutiliza como credencial bootstrap y viceversa.
//   - Sin access token se lanza NoSessionException (sin tocar el token).

import '../auth/auth_http_client.dart';
import '../auth/auth_token_store.dart';
import '../auth/device_auth_client.dart';
import 'sync_models.dart';
import 'sync_repository.dart';

class SyncClient {
  final AuthHttpClient http;
  final AuthTokenStore tokenStore;
  final SyncRepository repository;
  final DeviceAuthClient auth;

  SyncClient({
    required this.http,
    required this.tokenStore,
    required this.repository,
    required this.auth,
  });

  /// Descarga y refleja el dataset de la ruta activa unica del cobrador.
  ///
  /// Devuelve el dataset descargado. Antes de llamar a la API renueva la
  /// sesion si esta por expirar. Un 401 limpia la sesion (borrarToken) y se
  /// propaga como AuthApiException.
  Future<SyncDataset> sincronizar() async {
    if (await auth.requiereRenovacion()) {
      await auth.renovarSesion();
    }

    final token = await tokenStore.leerToken();
    if (token == null || token.isEmpty) {
      throw const NoSessionException();
    }

    try {
      final json = await http.getJson('/api/mobile/sync', token: token);
      final dataset = SyncDataset.fromJson(json);
      await repository.importar(dataset);
      return dataset;
    } on AuthApiException catch (e) {
      if (e.es401) {
        await tokenStore.borrarToken();
      }
      rethrow;
    }
  }
}
