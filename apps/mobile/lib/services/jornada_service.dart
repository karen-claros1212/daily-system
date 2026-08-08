import 'dart:convert';
import 'package:sqflite/sqflite.dart';
import 'package:intl/intl.dart';
import '../database/database.dart';
// domain_exceptions imported where needed
import '../models/models.dart';
import '../models/caja_resultado.dart';
import 'caja_service.dart';
import 'jornada_guard.dart';

class JornadaService {
  static Future<Jornada> abrirJornada(String rutaId, String cobradorId, String negocioId,
      int openingBase, {String? fecha}) async {
    final db = await database;
    final fechaDia = fecha ?? DateFormat('yyyy-MM-dd').format(DateTime.now());

    // Check for existing open jornada
    final existing = await db.query('jornada', where: 'fecha = ? AND estado = ? AND ruta_id = ?',
        whereArgs: [fechaDia, 'OPEN', rutaId]);
    if (existing.isNotEmpty) {
      throw Exception('Ya existe una jornada abierta para esta ruta hoy');
    }

    // opening_carry(D) = sobrante_manana(D-1) de la jornada cerrada previa
    final openingCarry = await _calcularCarry(db, rutaId, fechaDia);

    final jornada = Jornada(
      id: uid(),
      negocioId: negocioId,
      rutaId: rutaId,
      cobradorId: cobradorId,
      fecha: fechaDia,
      estado: 'OPEN',
      openingBase: openingBase,
      openingCarry: openingCarry,
    );

    await db.insert('jornada', jornada.toMap());
    return jornada;
  }

  /// opening_carry(D) = sobrante_manana(D-1); 0 si no hay jornada cerrada el día anterior.
  static Future<int> _calcularCarry(Database db, String rutaId, String fecha) async {
    final f = DateTime.parse(fecha);
    final ayer = DateFormat('yyyy-MM-dd')
        .format(DateTime(f.year, f.month, f.day - 1));
    final previas = await db.query('jornada',
        columns: ['sobrante_manana'],
        where: 'ruta_id = ? AND fecha = ? AND estado IN (?, ?)',
        whereArgs: [rutaId, ayer, 'CLOSED_LOCAL_PENDING_SYNC', 'CLOSED_SYNCED'],
        orderBy: 'fecha DESC',
        limit: 1);
    if (previas.isEmpty) return 0;
    return previas.first['sobrante_manana'] as int? ?? 0;
  }

  static Future<Jornada?> getJornadaAbierta(String rutaId) async {
    final db = await database;
    final fecha = DateFormat('yyyy-MM-dd').format(DateTime.now());
    final results = await db.query('jornada', where: 'fecha = ? AND estado = ? AND ruta_id = ?',
        whereArgs: [fecha, 'OPEN', rutaId]);
    if (results.isEmpty) return null;
    return Jornada.fromMap(results.first);
  }

  /// Cierra la jornada de forma transaccional.
  ///
  /// Transacción atómica:
  /// 1. JornadaGuard.requireOpenOn(txn, jornadaId) — dentro del callback
  /// 2. CajaService.calcularCaja(jornadaId, executor: txn) — dentro de la transacción
  /// 3. Calcular diferencia
  /// 4. Insertar snapshot inmutable mediante txn
  /// 5. Actualizar jornada a CLOSED_LOCAL_PENDING_SYNC mediante txn
  /// 6. Insertar sync_queue de cierre mediante txn
  ///
  /// No existe ventana entre calcular caja y cerrar jornada.
  static Future<ResultadoCierre> cerrarJornada(String jornadaId, int contado, String diferenciaMotivo) async {
    final db = await database;
    return db.transaction((txn) async {
      // Guardia DENTRO de la transacción — cero ventana de carrera
      final jornadaMap = await JornadaGuard.requireOpenOn(txn, jornadaId);

      // Calcular caja DENTRO de la transacción
      final caja = await CajaService.calcularCaja(jornadaId, executor: txn);
      final diferencia = contado - caja.efectivoEsperado;

      final now = DateTime.now().toIso8601String();

      // Insertar snapshot inmutable dentro de la transacción
      await _insertSnapshot(txn, jornadaId, jornadaMap, caja, contado, diferencia, diferenciaMotivo, now);

      // Actualizar jornada a CLOSED_LOCAL_PENDING_SYNC
      await txn.update('jornada', {
        'estado': 'CLOSED_LOCAL_PENDING_SYNC',
        'contado': contado,
        'esperado': caja.efectivoEsperado,
        'diferencia': diferencia,
        'diferencia_motivo': diferenciaMotivo,
        'sobrante_manana': contado,
        'cerrada_local_el': now,
      }, where: 'id = ?', whereArgs: [jornadaId]);

      // Insertar sync_queue de cierre dentro de la transacción
      await txn.insert('sync_queue', {
        'id': uid(),
        'tipo': 'jornada_cierre',
        'entidad_id': jornadaId,
        'datos': jsonEncode({'contado': contado, 'esperado': caja.efectivoEsperado, 'diferencia': diferencia}),
        'creado_el': now,
        'estado': 'PENDIENTE_DE_SINCRONIZAR',
      });

      // Construir resultado
      final jornada = Jornada.fromMap(jornadaMap);
      jornada.estado = 'CLOSED_LOCAL_PENDING_SYNC';
      jornada.contado = contado;
      jornada.diferencia = diferencia;
      jornada.diferenciaMotivo = diferenciaMotivo;
      jornada.cerradaLocalEl = now;

      return ResultadoCierre(
        jornada: jornada,
        snapshotId: _snapshotId(jornadaId),
        efectivoEsperado: caja.efectivoEsperado,
        contado: contado,
        diferencia: diferencia,
      );
    });
  }

  static Future<void> _insertSnapshot(DatabaseExecutor txn, String jornadaId,
      Map<String, dynamic> jornadaMap, CajaResultado caja,
      int contado, int diferencia, String diferenciaMotivo, String now) async {
    final snapshot = JornadaSnapshot(
      jornadaId: jornadaId,
      fecha: jornadaMap['fecha'] as String,
      cobradorId: jornadaMap['cobrador_id'] as String?,
      rutaId: jornadaMap['ruta_id'] as String,
      openingBase: caja.openingBase,
      openingCarry: caja.openingCarry,
      recaudoReal: caja.recaudoReal,
      reversales: caja.reversales,
      gastos: caja.gastos,
      ahorro: caja.ahorro,
      vales: caja.vales,
      entregas: caja.entregas,
      recibidos: caja.recibidos,
      desembolsos: caja.desembolsos,
      efectivoEsperado: caja.efectivoEsperado,
      contado: contado,
      diferencia: diferencia,
      diferenciaMotivo: diferenciaMotivo,
      cerradaLocalEl: now,
    );

    await txn.insert('jornada_snapshot', {
      'jornada_id': jornadaId,
      'fecha': jornadaMap['fecha'] as String,
      'cobrador_id': jornadaMap['cobrador_id'] as String?,
      'ruta_id': jornadaMap['ruta_id'] as String,
      'opening_base': caja.openingBase,
      'opening_carry': caja.openingCarry,
      'recaudo_real': caja.recaudoReal,
      'reversales': caja.reversales,
      'gastos': caja.gastos,
      'ahorro': caja.ahorro,
      'vales': caja.vales,
      'entregas': caja.entregas,
      'recibidos': caja.recibidos,
      'desembolsos': caja.desembolsos,
      'efectivo_esperado': caja.efectivoEsperado,
      'contado': contado,
      'diferencia': diferencia,
      'diferencia_motivo': diferenciaMotivo,
      'pagos_count': caja.pagosCount,
      'reversales_count': caja.reversalesCount,
      'movimientos_count': caja.movimientosCount,
      'cerrada_local_el': now,
      'version_esquema': 2,
      'hash_content': JornadaSnapshot.computeHash(snapshot),
    });
  }

  static String _snapshotId(String jornadaId) => 'snapshot_$jornadaId';

  static Future<List<Jornada>> getJornadasHistorial(String rutaId) async {
    final db = await database;
    final results = rutaId.isEmpty
        ? await db.query('jornada', orderBy: 'fecha DESC')
        : await db.query('jornada',
            where: 'ruta_id = ?',
            whereArgs: [rutaId],
            orderBy: 'fecha DESC');
    return results.map((m) => Jornada.fromMap(m)).toList();
  }
}

/// Resultado tipado de JornadaService.cerrarJornada().
class ResultadoCierre {
  final Jornada jornada;
  final String snapshotId;
  final int efectivoEsperado;
  final int contado;
  final int diferencia;

  const ResultadoCierre({
    required this.jornada,
    required this.snapshotId,
    required this.efectivoEsperado,
    required this.contado,
    required this.diferencia,
  });
}
