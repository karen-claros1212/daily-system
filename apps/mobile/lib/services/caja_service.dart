import 'package:sqflite/sqflite.dart';
import '../database/database.dart';

class CajaService {
  static Future<Map<String, dynamic>> calcularCaja(String jornadaId) async {
    final db = await database;

    // Opening base
    final jornadas = await db.query('jornada', limit: 1, where: 'id = ?', whereArgs: [jornadaId]);
    final openingBase = jornadas.isEmpty ? 0 : (jornadas.first['opening_base'] as int? ?? 0);
    final openingCarry = jornadas.isEmpty ? 0 : (jornadas.first['opening_carry'] as int? ?? 0);

    // Payments (PAYMENT)
    final pagosResult = await db.query('pago',
        columns: ['SUM(monto)'],
        where: 'jornada_id = ? AND tipo = ?',
        whereArgs: [jornadaId, 'PAYMENT']);
    final recaudoReal = (pagosResult.first['SUM(monto)'] as int?) ?? 0;

    // Reversals (REVERSAL)
    final reversalesResult = await db.query('pago',
        columns: ['SUM(monto)'],
        where: 'jornada_id = ? AND tipo = ?',
        whereArgs: [jornadaId, 'REVERSAL']);
    final totalReversales = (reversalesResult.first['SUM(monto)'] as int?) ?? 0;

    // Movimientos by type
    final gastosResult = await db.query('movimiento',
        columns: ['SUM(monto)'],
        where: 'jornada_id = ? AND tipo IN (?, ?)',
        whereArgs: [jornadaId, 'GASOLINA', 'OFICINA']);
    final gastos = (gastosResult.first['SUM(monto)'] as int?) ?? 0;

    final ahorroResult = await db.query('movimiento',
        columns: ['SUM(monto)'],
        where: 'jornada_id = ? AND tipo = ?',
        whereArgs: [jornadaId, 'AHORRO']);
    final ahorro = (ahorroResult.first['SUM(monto)'] as int?) ?? 0;

    final valesResult = await db.query('movimiento',
        columns: ['SUM(monto)'],
        where: 'jornada_id = ? AND tipo = ?',
        whereArgs: [jornadaId, 'VALE']);
    final vales = (valesResult.first['SUM(monto)'] as int?) ?? 0;

    final entregasResult = await db.query('movimiento',
        columns: ['SUM(monto)'],
        where: 'jornada_id = ? AND tipo = ?',
        whereArgs: [jornadaId, 'ENTREGA']);
    final entregas = (entregasResult.first['SUM(monto)'] as int?) ?? 0;

    final recibidosResult = await db.query('movimiento',
        columns: ['SUM(monto)'],
        where: 'jornada_id = ? AND tipo = ?',
        whereArgs: [jornadaId, 'RECIBIDO']);
    final recibidos = (recibidosResult.first['SUM(monto)'] as int?) ?? 0;

    final desembolsosResult = await db.query('movimiento',
        columns: ['SUM(monto)'],
        where: 'jornada_id = ? AND tipo = ?',
        whereArgs: [jornadaId, 'DESEMBOLSO']);
    final desembolsos = (desembolsosResult.first['SUM(monto)'] as int?) ?? 0;

    // Efectivo esperado = opening_base + opening_carry + recaudo_real - reversales - gastos - ahorro - vales - entregas - desembolsos + recibidos
    final efectivoEsperado = openingBase + openingCarry + recaudoReal - totalReversales - gastos - ahorro - vales - entregas - desembolsos + recibidos;

    // Count items
    final pagosCount = await _count(db, 'pago', jornadaId, 'PAYMENT');
    final reversalesCount = await _count(db, 'pago', jornadaId, 'REVERSAL');
    final movimientosCount = await _countMovimientos(db, jornadaId);

    return {
      'opening_base': openingBase,
      'opening_carry': openingCarry,
      'recaudo_real': recaudoReal,
      'reversales': totalReversales,
      'gastos': gastos,
      'ahorro': ahorro,
      'vales': vales,
      'entregas': entregas,
      'recibidos': recibidos,
      'desembolsos': desembolsos,
      'efectivo_esperado': efectivoEsperado,
      'pagos_count': pagosCount,
      'reversales_count': reversalesCount,
      'movimientos_count': movimientosCount,
    };
  }

  static Future<int> _count(Database db, String table, String jornadaId, String tipo) async {
    final results = await db.query(table,
        columns: ['COUNT(*)'],
        where: 'jornada_id = ? AND tipo = ?',
        whereArgs: [jornadaId, tipo]);
    return results.first['COUNT(*)'] as int;
  }

  static Future<int> _countMovimientos(Database db, String jornadaId) async {
    final results = await db.query('movimiento',
        columns: ['COUNT(*)'],
        where: 'jornada_id = ?',
        whereArgs: [jornadaId]);
    return results.first['COUNT(*)'] as int;
  }
}
