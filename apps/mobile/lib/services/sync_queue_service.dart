import 'package:sqflite/sqflite.dart';
import '../database/database.dart';
import '../models/models.dart';

class SyncQueueService {
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

  static Future<void> enqueue(String tipo, String entidadId, Map<String, dynamic> datos) async {
    final db = await database;
    await db.execute('CREATE TABLE IF NOT EXISTS sync_queue (id TEXT PRIMARY KEY, tipo TEXT NOT NULL, entidad_id TEXT NOT NULL, datos TEXT NOT NULL, creado_el TEXT NOT NULL, estado TEXT DEFAULT \'PENDIENTE_DE_SINCRONIZAR\')');

    await db.insert('sync_queue', {
      'id': uid(),
      'tipo': tipo,
      'entidad_id': entidadId,
      'datos': datos.toString(),
      'creado_el': DateTime.now().toIso8601String(),
      'estado': 'PENDIENTE_DE_SINCRONIZAR',
    });
  }

  static Future<List<SyncQueueItem>> getPendientes() async {
    final db = await database;
    final results = await db.query('sync_queue',
        where: 'estado = ?',
        whereArgs: ['PENDIENTE_DE_SINCRONIZAR'],
        orderBy: 'creado_el ASC');
    return results.map((m) => SyncQueueItem.fromMap(m)).toList();
  }

  static Future<int> getPendienteCount() async {
    final db = await database;
    final results = await db.query('sync_queue',
        columns: ['COUNT(*)'],
        where: 'estado = ?',
        whereArgs: ['PENDIENTE_DE_SINCRONIZAR']);
    return results.first['COUNT(*)'] as int;
  }

  static Future<void> marcarSincronizado(String id) async {
    final db = await database;
    await db.update('sync_queue',
        {'estado': 'SINCRONIZADO'},
        where: 'id = ?',
        whereArgs: [id]);
  }

  static Future<void> limpiarSincronizados() async {
    final db = await database;
    await db.delete('sync_queue', where: 'estado = ?', whereArgs: ['SINCRONIZADO']);
  }
}
