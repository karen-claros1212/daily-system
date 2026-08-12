// ─── Push orchestrator S3 — outbox → servidor ──────────────────────────────
//
// Orquesta el envío de filas PENDIENTE_DE_SINCRONIZAR al servidor:
//   1. Recupera ENVIANDO abandonados (crash recovery, misma fila)
//   2. Ordena filas: dentro de misma jornada PAYMENT→REVERSAL→MOVIMIENTO→JORNADA
//   3. Verifica R1→R2: ruta_id_origen == ruta actual
//   4. Transición ENVIANDO → envía request → mapea respuesta HTTP
//   5. ACK: ENVIANDO → SINCRONIZADO
//   6. Network/5xx: ENVIANDO → ERROR_REINTENTABLE
//   7. 401: fila conserva payload/key/provenance → ERROR_REINTENTABLE
//   8. 409: clasifica por operación — mismatch → CONFLICTO, "ya cerrada" → retry
//
// Reutiliza: AuthHttpClient, DeviceAuthClient, AuthTokenStore (S0+S1).
// No crea segundo cliente HTTP ni refresh token.

import 'dart:convert';
import 'package:daily_system/auth/auth_http_client.dart';
import 'package:daily_system/auth/auth_token_store.dart';
import 'package:daily_system/auth/device_auth_client.dart';
import 'package:daily_system/database/database.dart';
import 'package:daily_system/models/models.dart';
import 'package:daily_system/services/sync_queue_service.dart';

/// Resultado de procesar una fila del outbox.
class PushResult {
  final String filaId;
  final String tipo;
  final PushStatus status;
  final String? detail;

  PushResult({
    required this.filaId,
    required this.tipo,
    required this.status,
    this.detail,
  });
}

enum PushStatus {
  sincronizado,  // ACK correcto
  conflicto,     // 409 mismatch, 400, 403, 404, 422
  reintentable,  // 5xx, network, timeout, 401
  skipRuta,      // R1→R2 mismatch
}

class PushOrchestrator {
  final AuthHttpClient http;
  final AuthTokenStore tokenStore;
  final DeviceAuthClient auth;
  final String? currentRutaId; // ruta operativa actual (del bootstrap)

  PushOrchestrator({
    required this.http,
    required this.tokenStore,
    required this.auth,
    this.currentRutaId,
  });

  /// Ejecuta el ciclo completo de push: recupera ENVIANDO abandonados,
  /// ordena pendientes, envía en lote.
  Future<List<PushResult>> ejecutarPush() async {
    final resultados = <PushResult>[];

    // 1. Recuperar ENVIANDO abandonados (crash recovery)
    final abandonados = await SyncQueueService.getEnviandoAbandonados();
    for (final fila in abandonados) {
      final resultado = await _recuperarEnviandoAbandonado(fila.id);
      resultados.add(resultado);
    }

    // 2. Obtener y ordenar pendientes
    final pendientes = await _ordenarPendientes();

    // 3. Obtener error reintentables e intercalar con dependencia
    final reintentables = await SyncQueueService.getErrorReintentables();
    final interleaved = _intercalarReintentables(pendientes, reintentables);

    // 4. Enviar en orden
    for (final fila in interleaved) {
      final resultado = await _enviarFila(fila);
      resultados.add(resultado);
    }

    return resultados;
  }

  /// Recupera fila ENVIANDO abandonada: retry con MISMA fila, mismo payload/key.
  /// NO INSERTAR nueva fila — actualizar la existente.
  Future<PushResult> _recuperarEnviandoAbandonado(String filaId) async {
    final fila = await SyncQueueService.getFilaCompleta(filaId);
    if (fila == null) {
      return PushResult(
        filaId: filaId,
        tipo: 'desconocido',
        status: PushStatus.reintentable,
        detail: 'fila ENVIANDO no encontrada',
      );
    }

    // Actualizar MISMA fila: cambiar estado a PENDIENTE, mantener datos/key
    final db = await database;
    await db.update('sync_queue', {
      'estado': SyncQueueService.estadoPendiente,
      'ultima_transicion': DateTime.now().toIso8601String(),
    }, where: 'id = ?', whereArgs: [filaId]);

    return PushResult(
      filaId: filaId,
      tipo: fila['tipo'] as String? ?? 'desconocido',
      status: PushStatus.reintentable,
      detail: 'recuperado de ENVIANDO abandonado (misma fila)',
    );
  }

  /// Ordena filas con dependencia explícita:
  /// - Dentro de misma jornada: PAYMENT → REVERSAL → MOVIMIENTO → JORNADA_CIERRE
  /// - Entre jornadas: orden por creado_el (cronológico)
  Future<List<SyncQueueItem>> _ordenarPendientes() async {
    final pendientes = await SyncQueueService.getPendientes();

    pendientes.sort((a, b) {
      // 1. Agrupar por jornada_id_origen
      final jornadaA = a.jornadaIdOrigen ?? '';
      final jornadaB = b.jornadaIdOrigen ?? '';

      // 2. Diferente jornada → orden cronológico
      if (jornadaA != jornadaB) {
        return jornadaA.compareTo(jornadaB);
      }

      // 3. Misma jornada → prioridad de tipo (PAYMENT primero, JORNADA_CIERRE ultimo)
      final prioA = _prioridadTipoDependiente(a.tipo, a.datos);
      final prioB = _prioridadTipoDependiente(b.tipo, b.datos);
      if (prioA != prioB) return prioA.compareTo(prioB);

      // 4. Mismo tipo → orden por creado_el
      return a.creadoEl.compareTo(b.creadoEl);
    });

    return pendientes;
  }

  /// Prioridad de tipo dependiente del contexto:
  /// - PAYMENT = 0 (siempre primero)
  /// - REVERSAL = 1 (depende de PAYMENT de misma jornada)
  /// - MOVIMIENTO = 2
  /// - JORNADA_CIERRE = 3 (siempre ultimo)
  int _prioridadTipoDependiente(String tipo, Map<String, dynamic> datos) {
    switch (tipo) {
      case 'pago':
        return 0;
      case 'movimiento':
        return 2;
      case 'jornada_cierre':
        return 3;
      default:
        return 1; // reversal
    }
  }

  /// Intercala ERROR_REINTENTABLE con PENDIENTE respetando dependencias.
  /// Un REVERSAL ERROR_REINTENTABLE se inserta después de cualquier PAYMENT
  /// en la misma jornada (tanto PENDIENTE como ERROR_REINTENTABLE).
  List<SyncQueueItem> _intercalarReintentables(
    List<SyncQueueItem> pendientes,
    List<SyncQueueItem> reintentables,
  ) {
    if (reintentables.isEmpty) return pendientes;

    // Separar reintentables por tipo
    final revReintentables = reintentables.where((i) => i.tipo == 'pago' && i.datos['tipo'] == 'REVERSAL').toList();
    final otrosReintentables = reintentables.where((i) => !(i.tipo == 'pago' && i.datos['tipo'] == 'REVERSAL')).toList();

    // Para cada jornada, encontrar el índice del último PAYMENT (pendiente o reintentable)
    final resultado = List<SyncQueueItem>.from(pendientes);

    for (final rev in revReintentables) {
      final jornadaId = rev.datos['jornada_id'] as String?;
      if (jornadaId == null) {
        resultado.add(rev);
        continue;
      }

      // Buscar el último PAYMENT de esta jornada en resultado
      int ultimoPagoIdx = -1;
      for (int i = 0; i < resultado.length; i++) {
        final item = resultado[i];
        if (item.tipo == 'pago' && item.datos['tipo'] == 'PAYMENT' && item.datos['jornada_id'] == jornadaId) {
          ultimoPagoIdx = i;
        }
      }

      if (ultimoPagoIdx >= 0) {
        // Insertar después del último PAYMENT
        resultado.insert(ultimoPagoIdx + 1, rev);
      } else {
        // Sin pagos en la jornada, añadir al final
        resultado.add(rev);
      }
    }

    // Añadir otros reintentables (no REVERSAL) al final
    resultado.addAll(otrosReintentables);

    return resultado;
  }

  /// Envía una fila individual al servidor.
  Future<PushResult> _enviarFila(SyncQueueItem fila) async {
    final filaId = fila.id;
    final tipo = fila.tipo;
    final datos = fila.datos;
    final idempotencyKey = fila.idempotencyKey;
    final rutaOrigen = fila.rutaIdOrigen;

    // 1. Verificar R1→R2 con provenance PERSISTIDA en la fila
    if (currentRutaId != null && rutaOrigen != null) {
      if (rutaOrigen != currentRutaId) {
        await SyncQueueService.marcarConflicto(
          filaId,
          'R1->R2 mismatch: ruta_origen=$rutaOrigen != actual=$currentRutaId',
        );
        return PushResult(
          filaId: filaId,
          tipo: tipo,
          status: PushStatus.skipRuta,
          detail: 'ruta origen $rutaOrigen != actual $currentRutaId',
        );
      }
    }

    // 2. Transición ENVIANDO
    await SyncQueueService.marcarEnviando(filaId);

    // 3. Obtener token
    String? token;
    try {
      token = await tokenStore.leerToken();
    } catch (_) {}

    if (token == null || token.isEmpty) {
      await SyncQueueService.marcarError(filaId, 'no hay token de sesion');
      return PushResult(
        filaId: filaId,
        tipo: tipo,
        status: PushStatus.reintentable,
        detail: 'sin token',
      );
    }

    // 4. Enviar según tipo
    try {
      final datosTipo = datos['tipo'] as String?;
      switch (tipo) {
        case 'pago':
          if (datosTipo == 'REVERSAL') {
            return await _enviarReversal(filaId, datos, token, idempotencyKey ?? '');
          }
          return await _enviarPago(filaId, datos, token, idempotencyKey ?? '', fila.entidadId);
        case 'movimiento':
          return await _enviarMovimiento(filaId, datos, token, idempotencyKey ?? '');
        case 'jornada_cierre':
          return await _enviarJornadaCierre(filaId, datos, token, idempotencyKey ?? '');
        default:
          await SyncQueueService.marcarConflicto(filaId, 'tipo desconocido: $tipo');
          return PushResult(
            filaId: filaId,
            tipo: tipo,
            status: PushStatus.conflicto,
            detail: 'tipo desconocido',
          );
      }
    } on AuthApiException catch (e) {
      return await _mapearHttpResponse(filaId, tipo, e.statusCode, e.detail);
    } on AuthNetworkException catch (e) {
      await SyncQueueService.marcarError(filaId, e.message);
      return PushResult(
        filaId: filaId,
        tipo: tipo,
        status: PushStatus.reintentable,
        detail: e.message,
      );
    } catch (e) {
      await SyncQueueService.marcarError(filaId, e.toString());
      return PushResult(
        filaId: filaId,
        tipo: tipo,
        status: PushStatus.reintentable,
        detail: e.toString(),
      );
    }
  }

  /// Enviar PAYMENT a POST /api/pagos.
  /// 200 = ACK (idempotente o nuevo). 409 = mismatch → CONFLICTO.
  Future<PushResult> _enviarPago(String filaId, Map<String, dynamic> datos, String token, String idempotencyKey, String? entidadId) async {
    final body = {
      'credito_id': datos['credito_id'],
      'jornada_id': datos['jornada_id'],
      'monto': datos['monto'],
      'clave_idempotencia': idempotencyKey,
      'nota': datos['nota'],
    };

    final response = await http.postJson('/api/pagos', body: body, token: token);

    // ACK: ENVIANDO → SINCRONIZADO + mapping durable
    final serverId = response['id'] as String?;
    await SyncQueueService.marcarSincronizado(filaId, serverEntityId: serverId);

    // S2: guardar server ID en pago para que REVERSAL lo referencie
    if (entidadId != null && serverId != null) {
      final db = await database;
      await db.update('pago', {
        'server_entity_id': serverId,
        'recibido_el_servidor': DateTime.now().toIso8601String(),
      }, where: 'id = ?', whereArgs: [entidadId]);
    }

    return PushResult(
      filaId: filaId,
      tipo: 'PAYMENT',
      status: PushStatus.sincronizado,
      detail: 'pago sincronizado',
    );
  }

  /// Enviar REVERSAL a POST /api/pagos/{pago_id}/reversar.
  /// 200 = ACK (idempotente o nuevo). 409 = mismatch → CONFLICTO.
  ///
  /// S2: antes de enviar, resolver server_entity_id del PAYMENT original.
  /// Si el PAYMENT aún no tiene ACK, bloquear el REVERSAL (0 HTTP) hasta que
  /// el PAYMENT se sincronicé.
  Future<PushResult> _enviarReversal(String filaId, Map<String, dynamic> datos, String token, String idempotencyKey) async {
    final localPagoId = datos['reversal_of_payment_id'];

    // Resolver server ID del PAYMENT original:
    // 1. Si ya tiene server_entity_id en sync_queue, usar ese
    // 2. Si no existe fila en sync_queue, bloquear (PAYMENT nunca sync)
    String serverPagoId = localPagoId;
    final db = await database;
    final queueRow = await db.query('sync_queue',
        columns: ['server_entity_id'],
        where: 'entidad_id = ? AND tipo = ?',
        whereArgs: [localPagoId, 'pago'],
        limit: 1);
    if (queueRow.isEmpty) {
      // PAYMENT nunca sincronizado: bloquear REVERSAL
      await SyncQueueService.marcarConflicto(
        filaId,
        'PAYMENT original sin ACK: $localPagoId',
      );
      return PushResult(
        filaId: filaId,
        tipo: 'REVERSAL',
        status: PushStatus.conflicto,
        detail: 'PAYMENT original sin ACK',
      );
    }
    final svrId = queueRow.first['server_entity_id'] as String?;
    if (svrId != null && svrId.isNotEmpty) {
      serverPagoId = svrId;
    } else {
      // PAYMENT en sync_queue pero sin server_entity_id aún: bloquear
      await SyncQueueService.marcarConflicto(
        filaId,
        'PAYMENT original sin ACK: $localPagoId',
      );
      return PushResult(
        filaId: filaId,
        tipo: 'REVERSAL',
        status: PushStatus.conflicto,
        detail: 'PAYMENT original sin ACK',
      );
    }

    final body = {
      'motivo': datos['motivo'],
      'clave_idempotencia': idempotencyKey,
    };

    final response = await http.postJson('/api/pagos/$serverPagoId/reversar', body: body, token: token);

    // ACK: ENVIANDO → SINCRONIZADO + mapping durable
    final serverId = response['id'] as String?;
    await SyncQueueService.marcarSincronizado(filaId, serverEntityId: serverId);
    return PushResult(
      filaId: filaId,
      tipo: 'REVERSAL',
      status: PushStatus.sincronizado,
      detail: 'reversal sincronizado',
    );
  }

  /// Enviar MOVIMIENTO a POST /api/movimientos.
  /// 200 = ACK (idempotente o nuevo). 409 = mismatch → CONFLICTO.
  Future<PushResult> _enviarMovimiento(String filaId, Map<String, dynamic> datos, String token, String idempotencyKey) async {
    final body = {
      'jornada_id': datos['jornada_id'],
      'tipo': datos['tipo'],
      'monto': datos['monto'],
      'nota': datos['nota'],
      'clave_idempotencia': idempotencyKey,
    };

    final response = await http.postJson('/api/movimientos', body: body, token: token);

    // ACK: ENVIANDO → SINCRONIZADO + mapping durable
    final serverId = response['id'] as String?;
    await SyncQueueService.marcarSincronizado(filaId, serverEntityId: serverId);
    return PushResult(
      filaId: filaId,
      tipo: 'MOVIMIENTO',
      status: PushStatus.sincronizado,
      detail: 'movimiento sincronizado',
    );
  }

  /// Enviar JORNADA_CIERRE: POST /cerrar + POST /sincronizar.
  /// 409 "ya cerrada" → probar /sincronizar.
  /// 409 "Misma clave" → CONFLICTO (mismatch).
  Future<PushResult> _enviarJornadaCierre(String filaId, Map<String, dynamic> datos, String token, String idempotencyKey) async {
    final jornadaId = datos['jornada_id'] ?? datos['entidad_id'];

    // Paso 1: POST /cerrar
    final cierreBody = {
      'efectivo_contado': datos['contado'],
      'idempotencia_cierre': idempotencyKey,
      'motivo': datos['diferencia_motivo'] ?? '',
    };

    String? serverJornadaId;

    try {
      final cerrarResp = await http.postJson('/api/jornadas/$jornadaId/cerrar', body: cierreBody, token: token);
      serverJornadaId = cerrarResp['id'] as String? ?? cerrarResp['jornada_id'] as String?;
    } on AuthApiException catch (e) {
      // 409 "ya cerrada" → probar /sincronizar directo
      if (e.statusCode == 409 && e.detail.contains('cerrada')) {
        // Intentar /sincronizar con snapshot almacenado
        final snapshotBody = _construirSnapshot(datos, jornadaId);
        final snapshotHash = _canonicalJsonHash(snapshotBody);

        final syncResp = await http.postJson('/api/jornadas/$jornadaId/sincronizar',
          body: {
            'snapshot': snapshotBody,
            'snapshot_hash': snapshotHash,
          },
          token: token,
        );

        serverJornadaId = syncResp['jornada_id'] as String?;
        await _marcarJornadaSincronizada(filaId, serverJornadaId, jornadaId, syncResp: syncResp);
        return PushResult(
          filaId: filaId,
          tipo: 'JORNADA_CIERRE',
          status: PushStatus.sincronizado,
          detail: 'jornada sincronizada (cerrar 409 → sincronizar)',
        );
      }
      // 409 "Misma clave" → CONFLICTO (mismatch)
      if (e.statusCode == 409) {
        await SyncQueueService.marcarConflicto(filaId, '409 cerrar: ${e.detail}');
        return PushResult(
          filaId: filaId,
          tipo: 'JORNADA_CIERRE',
          status: PushStatus.conflicto,
          detail: '409 cerrar: ${e.detail}',
        );
      }
      rethrow;
    }

    // Paso 2: POST /sincronizar con snapshot
    final snapshotBody = _construirSnapshot(datos, jornadaId);
    final snapshotHash = _canonicalJsonHash(snapshotBody);

    final syncResp = await http.postJson('/api/jornadas/$jornadaId/sincronizar',
      body: {
        'snapshot': snapshotBody,
        'snapshot_hash': snapshotHash,
      },
      token: token,
    );

    serverJornadaId = serverJornadaId ?? syncResp['jornada_id'] as String?;
    await _marcarJornadaSincronizada(filaId, serverJornadaId, jornadaId, syncResp: syncResp);
    return PushResult(
      filaId: filaId,
      tipo: 'JORNADA_CIERRE',
      status: PushStatus.sincronizado,
      detail: 'jornada sincronizada',
    );
  }

  /// Actualiza jornada local → CLOSED_SYNCED + sync_queue → SINCRONIZADO
  /// en una sola transacción SQLite.
  /// Valida snapshot_valido == true y jornada_id coincide antes de actualizar.
  Future<void> _marcarJornadaSincronizada(
    String filaId,
    String? serverJornadaId,
    String jornadaId, {
    Map<String, dynamic>? syncResp,
  }) async {
    // S3: validar respuesta del servidor antes de marcar como synced
    if (syncResp != null) {
      final snapshotValido = syncResp['snapshot_valido'] as Object?;
      final estadoDevuelto = syncResp['estado'] as String?;
      final jornadaIdDevuelto = syncResp['jornada_id'] as String?;

      // snapshot_valido debe ser true
      if (snapshotValido != true) {
        return; // no actualizar jornada si snapshot no es válido
      }

      // jornada_id debe coincidir
      if (jornadaIdDevuelto != null && jornadaIdDevuelto != jornadaId) {
        return; // no actualizar si jornada_id no coincide
      }

      // estado devuelto debe ser CLOSED_SYNCED o compatible
      if (estadoDevuelto != null &&
          estadoDevuelto != 'CLOSED_SYNCED' &&
          estadoDevuelto != 'CLOSED') {
        return; // no actualizar si estado no es compatible
      }
    }

    final db = await database;
    await db.transaction((txn) async {
      // Actualizar jornada local
      await txn.update('jornada', {
        'estado': 'CLOSED_SYNCED',
        'sincronizada_el': DateTime.now().toIso8601String(),
      }, where: 'id = ?', whereArgs: [jornadaId]);

      // Actualizar sync_queue
      await txn.update('sync_queue', {
        'estado': SyncQueueService.estadoSincronizado,
        'server_entity_id': serverJornadaId,
        'ultima_transicion': DateTime.now().toIso8601String(),
      }, where: 'id = ?', whereArgs: [filaId]);
    });
  }

  Map<String, dynamic> _construirSnapshot(Map<String, dynamic> datos, String jornadaId) {
    return {
      'jornada_id': jornadaId,
      'negocio_id': datos['negocio_id'],
      'ruta_id': datos['ruta_id'],
      'cobrador_id': datos['cobrador_id'],
      'opening_base': datos['opening_base'],
      'opening_carry': datos['opening_carry'],
      'recaudo_real': datos['recaudo_real'],
      'reversales': datos['reversales'],
      'gastos': datos['gastos'],
      'ahorro': datos['ahorro'],
      'vales': datos['vales'],
      'entregas': datos['entregas'],
      'recibidos': datos['recibidos'],
      'desembolsos': datos['desembolsos'],
      'efectivo_esperado': datos['efectivo_esperado'],
      'efectivo_contado': datos['contado'],
      'diferencia': datos['diferencia'],
      'diferencia_motivo': datos['diferencia_motivo'],
      'pagos_count': datos['pagos_count'],
      'reversales_count': datos['reversales_count'],
      'movimientos_count': datos['movimientos_count'],
      'version': 1,
    };
  }

  /// Mapea HTTP status → outbox state.
  ///
  /// 409 por operación:
  /// - PAYMENT: 409 mismatch → CONFLICTO (idempotente replay devuelve 200)
  /// - REVERSAL: 409 mismatch → CONFLICTO (idempotente replay devuelve 200)
  /// - MOVIMIENTO: 409 mismatch → CONFLICTO (idempotente replay devuelve 200)
  /// - JORNADA /cerrar: 409 "ya cerrada" → try /sincronizar (manejado en _enviarJornadaCierre)
  /// - JORNADA /sincronizar: 400 mismatch → CONFLICTO
  Future<PushResult> _mapearHttpResponse(String filaId, String tipo, int statusCode, String detail) async {
    switch (statusCode) {
      case 401:
        // 401: fila conserva payload/key/provenance → ERROR_REINTENTABLE
        await SyncQueueService.marcarError(filaId, '401 sesion revocada: $detail');
        return PushResult(
          filaId: filaId,
          tipo: tipo,
          status: PushStatus.reintentable,
          detail: '401 sesion revocada',
        );

      case 409:
        // 409: mismatch → CONFLICTO (idempotente replay ya se manejó con 200)
        await SyncQueueService.marcarConflicto(filaId, '409 $detail');
        return PushResult(
          filaId: filaId,
          tipo: tipo,
          status: PushStatus.conflicto,
          detail: '409 $detail',
        );

      case 400:
      case 403:
      case 404:
      case 422:
        // 4xx permanentes: CONFLICTO
        await SyncQueueService.marcarConflicto(filaId, '$statusCode $detail');
        return PushResult(
          filaId: filaId,
          tipo: tipo,
          status: PushStatus.conflicto,
          detail: '$statusCode $detail',
        );

      default:
        // 5xx y otros: ERROR_REINTENTABLE
        await SyncQueueService.marcarError(filaId, '$statusCode $detail');
        return PushResult(
          filaId: filaId,
          tipo: tipo,
          status: PushStatus.reintentable,
          detail: '$statusCode $detail',
        );
    }
  }

  /// SHA-256 hash de canonical JSON (sorted keys).
  String _canonicalJsonHash(Map<String, dynamic> obj) {
    final canonical = jsonEncode(obj);
    // Simplificado: usar length como hash provisional (reemplazar con crypto.sha256)
    return canonical.length.toString();
  }
}
