import 'dart:convert';
import 'package:sqflite/sqflite.dart';
import '../database/database.dart';
import '../models/models.dart';

class SyncQueueService {
  // Estados S3
  static const String estadoPendiente = 'PENDIENTE_DE_SINCRONIZAR';
  static const String estadoEnviando = 'ENVIANDO';
  static const String estadoSincronizado = 'SINCRONIZADO';
  static const String estadoError = 'ERROR_REINTENTABLE';
  static const String estadoConflicto = 'CONFLICTO';

  static Future<void> crearTabla(Database db) async {
    await db.execute('''
      CREATE TABLE IF NOT EXISTS sync_queue (
        id TEXT PRIMARY KEY,
        tipo TEXT NOT NULL,
        entidad_id TEXT NOT NULL,
        datos TEXT NOT NULL,
        creado_el TEXT NOT NULL,
        estado TEXT DEFAULT 'PENDIENTE_DE_SINCRONIZAR'
      )
    ''');
  }

  /// Enqueue legacy (para compatibilidad con código existente).
  /// S3 usa enqueueCompleto() para payloads completos.
  static Future<void> enqueue(String tipo, String entidadId, Map<String, dynamic> datos) async {
    final db = await database;
    await db.execute('CREATE TABLE IF NOT EXISTS sync_queue (id TEXT PRIMARY KEY, tipo TEXT NOT NULL, entidad_id TEXT NOT NULL, datos TEXT NOT NULL, creado_el TEXT NOT NULL, estado TEXT DEFAULT \'PENDIENTE_DE_SINCRONIZAR\')');

    final now = DateTime.now().toIso8601String();
    await db.insert('sync_queue', {
      'id': uid(),
      'tipo': tipo,
      'entidad_id': entidadId,
      'datos': jsonEncode(datos),
      'creado_el': now,
      'estado': estadoPendiente,
      'idempotency_key': uid(),
      'intento': 0,
      'ultima_transicion': now,
    });
  }

  /// Enqueue S3 completo con todos los campos de procedencia.
  static Future<void> enqueueCompleto({
    required String tipo,
    required String entidadId,
    required Map<String, dynamic> datos,
    required String idempotencyKey,
    String? negocioId,
    String? rutaIdOrigen,
    String? cobradorIdOrigen,
    String? jornadaIdOrigen,
  }) async {
    final db = await database;
    final now = DateTime.now().toIso8601String();

    await db.insert('sync_queue', {
      'id': uid(),
      'tipo': tipo,
      'entidad_id': entidadId,
      'datos': jsonEncode(datos),
      'creado_el': now,
      'estado': estadoPendiente,
      'idempotency_key': idempotencyKey,
      'negocio_id': negocioId,
      'ruta_id_origen': rutaIdOrigen,
      'cobrador_id_origen': cobradorIdOrigen,
      'jornada_id_origen': jornadaIdOrigen,
      'intento': 0,
      'ultimo_error': null,
      'ultima_transicion': now,
    });
  }

  /// Transición a ENVIANDO — antes de enviar al servidor.
  static Future<void> marcarEnviando(String id) async {
    final db = await database;
    final nuevoIntento = await _incrementarIntento(db, id);
    await db.update('sync_queue', {
      'estado': estadoEnviando,
      'intento': nuevoIntento,
      'ultima_transicion': DateTime.now().toIso8601String(),
    }, where: 'id = ?', whereArgs: [id]);
  }

  /// Transición a ERROR_REINTENTABLE — después de fallo HTTP.
  static Future<void> marcarError(String id, String mensajeError) async {
    final db = await database;
    await db.update('sync_queue', {
      'estado': estadoError,
      'ultimo_error': mensajeError,
      'ultima_transicion': DateTime.now().toIso8601String(),
    }, where: 'id = ?', whereArgs: [id]);
  }

  /// Transición a CONFLICTO — error permanente no recuperable.
  static Future<void> marcarConflicto(String id, String motivo) async {
    final db = await database;
    await db.update('sync_queue', {
      'estado': estadoConflicto,
      'ultimo_error': motivo,
      'ultima_transicion': DateTime.now().toIso8601String(),
    }, where: 'id = ?', whereArgs: [id]);
  }

  /// Transición a SINCRONIZADO — ACK correcto del servidor.
  static Future<void> marcarSincronizado(String id) async {
    final db = await database;
    await db.update('sync_queue', {
      'estado': estadoSincronizado,
      'ultima_transicion': DateTime.now().toIso8601String(),
    }, where: 'id = ?', whereArgs: [id]);
  }

  /// Recuperar fila ENVIANDO abandonada — reinicio tras crash.
  static Future<List<SyncQueueItem>> getEnviandoAbandonados() async {
    final db = await database;
    final results = await db.query('sync_queue',
        where: 'estado = ?',
        whereArgs: [estadoEnviando],
        orderBy: 'creado_el ASC');
    return results.map((m) => SyncQueueItem.fromMap(m)).toList();
  }

  /// Recuperar fila ERROR_REINTENTABLE — lista para retry.
  static Future<List<SyncQueueItem>> getErrorReintentables() async {
    final db = await database;
    final results = await db.query('sync_queue',
        where: 'estado = ?',
        whereArgs: [estadoError],
        orderBy: 'creado_el ASC');
    return results.map((m) => SyncQueueItem.fromMap(m)).toList();
  }

  /// Obtener todas las filas pendientes para push orchestrator.
  static Future<List<SyncQueueItem>> getPendientes() async {
    final db = await database;
    final results = await db.query('sync_queue',
        where: 'estado = ?',
        whereArgs: [estadoPendiente],
        orderBy: 'creado_el ASC');
    return results.map((m) => SyncQueueItem.fromMap(m)).toList();
  }

  static Future<int> getPendienteCount() async {
    final db = await database;
    final results = await db.query('sync_queue',
        columns: ['COUNT(*)'],
        where: 'estado = ?',
        whereArgs: [estadoPendiente]);
    return results.first['COUNT(*)'] as int;
  }

  static Future<int> limpiarSincronizados() async {
    final db = await database;
    return await db.delete('sync_queue', where: 'estado = ?', whereArgs: [estadoSincronizado]);
  }

  /// Obtener fila completa por id — para el push orchestrator.
  static Future<Map<String, dynamic>?> getFilaCompleta(String id) async {
    final db = await database;
    final results = await db.query('sync_queue',
        columns: null,
        where: 'id = ?',
        whereArgs: [id],
        limit: 1);
    if (results.isEmpty) return null;
    return results.first;
  }

  /// Actualizar solo la columna datos — para retry con payload corregido.
  static Future<void> actualizarDatos(String id, Map<String, dynamic> nuevosDatos) async {
    final db = await database;
    await db.update('sync_queue', {
      'datos': jsonEncode(nuevosDatos),
      'estado': estadoPendiente,
      'ultima_transicion': DateTime.now().toIso8601String(),
    }, where: 'id = ?', whereArgs: [id]);
  }

  /// Obtener ruta_id_origen de una fila — para verificar R1→R2.
  static Future<String?> getRutaOrigen(String id) async {
    final db = await database;
    final results = await db.query('sync_queue',
        columns: ['ruta_id_origen'],
        where: 'id = ?',
        whereArgs: [id],
        limit: 1);
    if (results.isEmpty) return null;
    return results.first['ruta_id_origen'] as String?;
  }

  /// Obtener idempotency_key de una fila — para retry idéntico.
  static Future<String?> getIdempotencyKey(String id) async {
    final db = await database;
    final results = await db.query('sync_queue',
        columns: ['idempotency_key'],
        where: 'id = ?',
        whereArgs: [id],
        limit: 1);
    if (results.isEmpty) return null;
    return results.first['idempotency_key'] as String?;
  }

  /// Helper: incrementar contador de intentos.
  static Future<int> _incrementarIntento(Database db, String id) async {
    final results = await db.query('sync_queue',
        columns: ['intento'],
        where: 'id = ?',
        whereArgs: [id],
        limit: 1);
    if (results.isEmpty) return 1;
    final actual = results.first['intento'] as int? ?? 0;
    return actual + 1;
  }
}
