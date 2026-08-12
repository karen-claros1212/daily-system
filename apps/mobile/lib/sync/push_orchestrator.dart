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
  final String? currentCobradorId; // cobrador actual para S4 reasignación

  PushOrchestrator({
    required this.http,
    required this.tokenStore,
    required this.auth,
    this.currentRutaId,
    this.currentCobradorId,
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
    if (tipo == 'pago') {
      // Distinguir PAYMENT de REVERSAL dentro del mismo tipo 'pago'
      final datosTipo = datos['tipo'] as String?;
      if (datosTipo == 'REVERSAL') return 1;
      return 0; // PAYMENT
    }
    if (tipo == 'movimiento') return 2;
    if (tipo == 'jornada_cierre') return 3;
    return 1; // reversal por defecto
  }

  /// Intercala ERROR_REINTENTABLE con PENDIENTE respetando dependencias.
  /// Todos los reintentables se ordenan por prioridad dentro de su jornada:
  /// PAYMENT(0) → REVERSAL(1) → MOVIMIENTO(2) → JORNADA_CIERRE(3).
  /// Esto garantiza que un PAYMENT en retry nunca quede después de una
  /// JORNADA_CIERRE de la misma jornada (defecto 3).
  List<SyncQueueItem> _intercalarReintentables(
    List<SyncQueueItem> pendientes,
    List<SyncQueueItem> reintentables,
  ) {
    if (reintentables.isEmpty) return pendientes;
    final combinados = <SyncQueueItem>[...pendientes, ...reintentables];
    combinados.sort(_compararOrdenPush);
    return combinados;
  }

  /// Comparador para ordenar filas de push: jornada → prioridad tipo → creado_el.
  int _compararOrdenPush(SyncQueueItem a, SyncQueueItem b) {
    final jornadaA = a.jornadaIdOrigen ?? '';
    final jornadaB = b.jornadaIdOrigen ?? '';
    if (jornadaA != jornadaB) return jornadaA.compareTo(jornadaB);
    final prioA = _prioridadTipoDependiente(a.tipo, a.datos);
    final prioB = _prioridadTipoDependiente(b.tipo, b.datos);
    if (prioA != prioB) return prioA.compareTo(prioB);
    return a.creadoEl.compareTo(b.creadoEl);
  }

  /// Verifica si hay filas financieras (pago/movimiento) de la jornada
  /// que aún no están sincronizadas (PENDIENTE/ENVIANDO/ERROR_REINTENTABLE).
  Future<bool> _tieneDependenciasPendientes(String jornadaId) async {
    final db = await database;
    final resultados = await db.query(
      'sync_queue',
      columns: ['id'],
      where: "jornada_id_origen = ? AND tipo IN ('pago', 'movimiento') AND estado IN (?, ?, ?)",
      whereArgs: [
        jornadaId,
        SyncQueueService.estadoPendiente,
        SyncQueueService.estadoEnviando,
        SyncQueueService.estadoError,
      ],
      limit: 1,
    );
    return resultados.isNotEmpty;
  }

  /// Verifica si hay filas financieras (pago/movimiento) de la jornada
  /// en estado CONFLICTO (no se reintentarán).
  Future<bool> _tieneDependenciaConflicto(String jornadaId) async {
    final db = await database;
    final resultados = await db.query(
      'sync_queue',
      columns: ['id'],
      where: "jornada_id_origen = ? AND tipo IN ('pago', 'movimiento') AND estado = ?",
      whereArgs: [jornadaId, SyncQueueService.estadoConflicto],
      limit: 1,
    );
    return resultados.isNotEmpty;
  }

  /// Envía una fila individual al servidor.
  Future<PushResult> _enviarFila(SyncQueueItem fila) async {
    final filaId = fila.id;
    final tipo = fila.tipo;
    final datos = fila.datos;
    final idempotencyKey = fila.idempotencyKey;
    final rutaOrigen = fila.rutaIdOrigen;

    // 1. Verificar R1→R2 con provenance PERSISTIDA en la fila.
    // S4: ruta_id_origen es inmutable — un evento nacido en R1 nunca se
    // envía bajo R2 aunque el cobrador sea el mismo.
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
  /// Wait state: si PAYMENT está PENDIENTE/ENVIANDO/ERROR → skip (0 HTTP,
  /// recoverable). Solo CONFLICTO → bloquear permanentemente.
  Future<PushResult> _enviarReversal(String filaId, Map<String, dynamic> datos, String token, String idempotencyKey) async {
    final localPagoId = datos['reversal_of_payment_id'];

    // Resolver server ID del PAYMENT original:
    // 1. Si tiene sync_queue → usar server_entity_id / estado
    // 2. Si no tiene sync_queue pero tiene recibido_el_servidor →
    //    PAYMENT descargado del servidor (pull): local id == server id
    // 3. Si no tiene sync_queue ni recibido_el_servidor →
    //    PAYMENT local roto/sin outbox → CONFLICTO
    String serverPagoId = localPagoId;
    final db = await database;
    final queueRow = await db.query('sync_queue',
        columns: ['server_entity_id', 'estado'],
        where: 'entidad_id = ? AND tipo = ?',
        whereArgs: [localPagoId, 'pago'],
        limit: 1);

    final svrId = queueRow.isNotEmpty
        ? queueRow.first['server_entity_id'] as String?
        : null;
    final paymentEstado = queueRow.isNotEmpty
        ? queueRow.first['estado'] as String?
        : null;

    if (svrId != null && svrId.isNotEmpty) {
      // PAYMENT SINCRONIZADO → usar server ID
      serverPagoId = svrId;
    } else if (queueRow.isEmpty) {
      // No hay fila en sync_queue: verificar si es PAYMENT del servidor
      final pagoRow = await db.query('pago',
          columns: ['recibido_el_servidor'],
          where: 'id = ?',
          whereArgs: [localPagoId],
          limit: 1);
      if (pagoRow.isNotEmpty) {
        final recibido = pagoRow.first['recibido_el_servidor'] as String?;
        if (recibido != null && recibido.isNotEmpty) {
          // PAYMENT descargado del servidor: local id == server id
          serverPagoId = localPagoId;
        } else {
          // PAYMENT local sin outbox y sin ACK → CONFLICTO
          await SyncQueueService.marcarConflicto(
            filaId,
            'PAYMENT original no encontrado: $localPagoId',
          );
          return PushResult(
            filaId: filaId,
            tipo: 'REVERSAL',
            status: PushStatus.conflicto,
            detail: 'PAYMENT original no encontrado',
          );
        }
      } else {
        // No existe en pago → CONFLICTO
        await SyncQueueService.marcarConflicto(
          filaId,
          'PAYMENT original no encontrado: $localPagoId',
        );
        return PushResult(
          filaId: filaId,
          tipo: 'REVERSAL',
          status: PushStatus.conflicto,
          detail: 'PAYMENT original no encontrado',
        );
      }
    } else {
      // Hay fila en sync_queue pero sin server_entity_id: verificar estado
      switch (paymentEstado) {
        case 'PENDIENTE_DE_SINCRONIZAR':
        case 'ENVIANDO':
        case 'ERROR_REINTENTABLE':
          // Wait state: 0 HTTP, recoverable en próximo ciclo.
          // Marcar ERROR_REINTENTABLE explícitamente para que el
          // siguiente ciclo la intercale después del PAYMENT.
          await SyncQueueService.marcarError(
            filaId,
            'PAYMENT pendiente: $localPagoId (esperando ACK)',
          );
          return PushResult(
            filaId: filaId,
            tipo: 'REVERSAL',
            status: PushStatus.reintentable,
            detail: 'PAYMENT pendiente: $localPagoId (esperando ACK)',
          );
        case 'CONFLICTO':
          // PAYMENT CONFLICTO → bloquear REVERSAL permanentemente
          await SyncQueueService.marcarConflicto(
            filaId,
            'PAYMENT original CONFLICTO: $localPagoId',
          );
          return PushResult(
            filaId: filaId,
            tipo: 'REVERSAL',
            status: PushStatus.conflicto,
            detail: 'PAYMENT original CONFLICTO',
          );
        default:
          // SINCRONIZADO sin server_entity_id: verificar procedencia
          final pagoRow = await db.query('pago',
              columns: ['recibido_el_servidor'],
              where: 'id = ?',
              whereArgs: [localPagoId],
              limit: 1);
          if (pagoRow.isNotEmpty) {
            final recibido = pagoRow.first['recibido_el_servidor'] as String?;
            if (recibido != null && recibido.isNotEmpty) {
              // PAYMENT del servidor: local id == server id
              serverPagoId = localPagoId;
            } else {
              // PAYMENT local SINCRONIZADO sin server_entity_id → CONFLICTO
              await SyncQueueService.marcarConflicto(
                filaId,
                'PAYMENT SINCRONIZADO sin server ID: $localPagoId',
              );
              return PushResult(
                filaId: filaId,
                tipo: 'REVERSAL',
                status: PushStatus.conflicto,
                detail: 'PAYMENT SINCRONIZADO sin server ID',
              );
            }
          } else {
            await SyncQueueService.marcarConflicto(
              filaId,
              'PAYMENT SINCRONIZADO sin server ID: $localPagoId',
            );
            return PushResult(
              filaId: filaId,
              tipo: 'REVERSAL',
              status: PushStatus.conflicto,
              detail: 'PAYMENT SINCRONIZADO sin server ID',
            );
          }
      }
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
  /// S3: antes de enviar, verificar que todas las filas financieras de la
  /// jornada (PAYMENT/REVERSAL/MOVIMIENTO) estén SINCRONIZADAS.
  Future<PushResult> _enviarJornadaCierre(String filaId, Map<String, dynamic> datos, String token, String idempotencyKey) async {
    final jornadaId = datos['jornada_id'] ?? datos['entidad_id'];

    // Guardia de dependencias: no cerrar mientras haya filas financieras
    // de la misma jornada pendientes, en retry o en conflicto.
    if (await _tieneDependenciaConflicto(jornadaId)) {
      // Dependencia CONFLICTO: no se reintenta, jornada queda CONFLICTO.
      await SyncQueueService.marcarConflicto(
        filaId,
        'dependencia financiera en conflicto: $jornadaId',
      );
      return PushResult(
        filaId: filaId,
        tipo: 'JORNADA_CIERRE',
        status: PushStatus.conflicto,
        detail: 'dependencia financiera en conflicto: $jornadaId',
      );
    }
    if (await _tieneDependenciasPendientes(jornadaId)) {
      // Dependencia PENDIENTE/ENVIANDO/ERROR_REINTENTABLE: se reintenta.
      await SyncQueueService.marcarError(
        filaId,
        'jornada espera dependencias: $jornadaId',
      );
      return PushResult(
        filaId: filaId,
        tipo: 'JORNADA_CIERRE',
        status: PushStatus.reintentable,
        detail: 'jornada espera dependencias: $jornadaId',
      );
    }

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
        final synced = await _marcarJornadaSincronizada(filaId, serverJornadaId, jornadaId, syncResp: syncResp);
        if (!synced) {
          return PushResult(
            filaId: filaId,
            tipo: 'JORNADA_CIERRE',
            status: PushStatus.conflicto,
            detail: 'jornada sincronizada pero respuesta inválida',
          );
        }
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
    final synced = await _marcarJornadaSincronizada(filaId, serverJornadaId, jornadaId, syncResp: syncResp);
    if (!synced) {
      return PushResult(
        filaId: filaId,
        tipo: 'JORNADA_CIERRE',
        status: PushStatus.conflicto,
        detail: 'jornada sincronizada pero respuesta inválida',
      );
    }
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
  /// Returns true si éxito, false si respuesta inválida (sync_queue queda ENVIANDO).
  Future<bool> _marcarJornadaSincronizada(
    String filaId,
    String? serverJornadaId,
    String jornadaId, {
    Map<String, dynamic>? syncResp,
  }) async {
    String? invalidReason;

    // S3: validar respuesta del servidor antes de marcar como synced
    if (syncResp != null) {
      final snapshotValido = syncResp['snapshot_valido'] as Object?;
      final estadoDevuelto = syncResp['estado'] as String?;
      final jornadaIdDevuelto = syncResp['jornada_id'] as String?;

      // snapshot_valido debe ser true
      if (snapshotValido != true) {
        invalidReason = 'snapshot_no_valido';
      }
      // jornada_id debe coincidir
      else if (jornadaIdDevuelto != null && jornadaIdDevuelto != jornadaId) {
        invalidReason = 'jornada_id_mismatch';
      }
      // estado devuelto debe ser CLOSED_SYNCED o compatible
      else if (estadoDevuelto != null &&
          estadoDevuelto != 'CLOSED_SYNCED' &&
          estadoDevuelto != 'CLOSED') {
        invalidReason = 'estado_no_compatible';
      }
    }

    if (invalidReason != null) {
      // No actualizar jornada (queda CLOSED_LOCAL_PENDING_SYNC)
      // Marcar sync_queue como CONFLICTO (no ENVIANDO)
      final db = await database;
      await db.update('sync_queue', {
        'estado': SyncQueueService.estadoConflicto,
        'ultimo_error': invalidReason,
        'ultima_transicion': DateTime.now().toIso8601String(),
      }, where: 'id = ?', whereArgs: [filaId]);
      return false;
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
    return true;
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
