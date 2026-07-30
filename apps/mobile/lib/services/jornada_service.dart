import 'package:sqflite/sqflite.dart';
import 'package:intl/intl.dart';
import '../database/database.dart';
import '../models/models.dart';

class JornadaService {
  static Future<Jornada> abrirJornada(String rutaId, String cobradorId, String negocioId, int openingBase) async {
    final db = await database;
    final fecha = DateFormat('yyyy-MM-dd').format(DateTime.now());

    // Check for existing open jornada
    final existing = await db.query('jornada', where: 'fecha = ? AND estado = ? AND ruta_id = ?',
        whereArgs: [fecha, 'OPEN', rutaId]);
    if (existing.isNotEmpty) {
      throw Exception('Ya existe una jornada abierta para esta ruta hoy');
    }

    final jornada = Jornada(
      id: uid(),
      negocioId: negocioId,
      rutaId: rutaId,
      cobradorId: cobradorId,
      fecha: fecha,
      estado: 'OPEN',
      openingBase: openingBase,
    );

    await db.insert('jornada', jornada.toMap());
    return jornada;
  }

  static Future<Jornada?> getJornadaAbierta(String rutaId) async {
    final db = await database;
    final fecha = DateFormat('yyyy-MM-dd').format(DateTime.now());
    final results = await db.query('jornada', where: 'fecha = ? AND estado = ? AND ruta_id = ?',
        whereArgs: [fecha, 'OPEN', rutaId]);
    if (results.isEmpty) return null;
    return Jornada.fromMap(results.first);
  }

  static Future<Jornada> cerrarJornada(String jornadaId, int contado, String diferenciaMotivo) async {
    final db = await database;
    final jornadaMap = await db.query('jornada', limit: 1, where: 'id = ?', whereArgs: [jornadaId]);
    if (jornadaMap.isEmpty) throw Exception('Jornada no encontrada');

    final jornada = Jornada.fromMap(jornadaMap.first);
    final esperado = jornada.efectivoEsperado;
    final diferencia = contado - esperado;

    await db.update('jornada', {
      'estado': 'CLOSED_LOCAL_PENDING_SYNC',
      'contado': contado,
      'esperado': esperado,
      'diferencia': diferencia,
      'diferencia_motivo': diferenciaMotivo,
      'cerrada_local_el': DateTime.now().toIso8601String(),
    }, where: 'id = ?', whereArgs: [jornadaId]);

    jornada.estado = 'CLOSED_LOCAL_PENDING_SYNC';
    jornada.contado = contado;
    jornada.diferencia = diferencia;
    jornada.diferenciaMotivo = diferenciaMotivo;
    jornada.cerradaLocalEl = DateTime.now().toIso8601String();
    return jornada;
  }

  static Future<List<Jornada>> getJornadasHistorial(String rutaId) async {
    final db = await database;
    final results = await db.query('jornada',
        where: 'ruta_id = ?',
        whereArgs: [rutaId],
        orderBy: 'fecha DESC');
    return results.map((m) => Jornada.fromMap(m)).toList();
  }
}
