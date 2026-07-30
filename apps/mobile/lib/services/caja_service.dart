import 'package:sqflite/sqflite.dart';
import '../database/database.dart';
import '../models/caja_resultado.dart';

/// Servicio inmutable de cálculo de caja.
/// Retorna CajaResultado tipado. Acepta DatabaseExecutor opcional para uso dentro de transacciones.
class CajaService {
  static Future<CajaResultado> calcularCaja(String jornadaId, {DatabaseExecutor? executor}) async {
    final bool usarDb = executor == null;
    final DatabaseExecutor db = usarDb ? await database : executor;

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

    return CajaResultado(
      openingBase: openingBase,
      openingCarry: openingCarry,
      recaudoReal: recaudoReal,
      reversales: totalReversales,
      gastos: gastos,
      ahorro: ahorro,
      vales: vales,
      entregas: entregas,
      recibidos: recibidos,
      desembolsos: desembolsos,
      efectivoEsperado: efectivoEsperado,
      pagosCount: pagosCount,
      reversalesCount: reversalesCount,
      movimientosCount: movimientosCount,
    );
  }

  static Future<int> _count(DatabaseExecutor db, String table, String jornadaId, String tipo) async {
    final results = await db.query(table,
        columns: ['COUNT(*)'],
        where: 'jornada_id = ? AND tipo = ?',
        whereArgs: [jornadaId, tipo]);
    return results.first['COUNT(*)'] as int;
  }

  static Future<int> _countMovimientos(DatabaseExecutor db, String jornadaId) async {
    final results = await db.query('movimiento',
        columns: ['COUNT(*)'],
        where: 'jornada_id = ?',
        whereArgs: [jornadaId]);
    return results.first['COUNT(*)'] as int;
  }
}
