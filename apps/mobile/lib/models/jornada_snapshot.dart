// Modelo inmutable de jornada_snapshot con hash canónico reproducible.
//
// Toda la lógica de hash vive aquí: JornadaSnapshot.computeHash().
// JornadaService y PdfService usan exactamente esta implementación.
import 'dart:convert';
import 'package:crypto/crypto.dart';

class JornadaSnapshot {
  final String jornadaId;
  final String fecha;
  final String? cobradorId;
  final String rutaId;
  final int openingBase;
  final int openingCarry;
  final int recaudoReal;
  final int reversales;
  final int gastos;
  final int ahorro;
  final int vales;
  final int entregas;
  final int recibidos;
  final int desembolsos;
  final int efectivoEsperado;
  final int contado;
  final int diferencia;
  final String? diferenciaMotivo;
  final String cerradaLocalEl;

  const JornadaSnapshot({
    required this.jornadaId,
    required this.fecha,
    required this.cobradorId,
    required this.rutaId,
    required this.openingBase,
    required this.openingCarry,
    required this.recaudoReal,
    required this.reversales,
    required this.gastos,
    required this.ahorro,
    required this.vales,
    required this.entregas,
    required this.recibidos,
    required this.desembolsos,
    required this.efectivoEsperado,
    required this.contado,
    required this.diferencia,
    required this.diferenciaMotivo,
    required this.cerradaLocalEl,
  });

  /// Hash canónico SHA-256 del snapshot.
  ///
  /// Usa los campos determinísticos del snapshot (no DateTime.now).
  /// Mismo contenido → mismo hash en cualquier momento.
  static String computeHash(JornadaSnapshot snap) {
    final canonical = const JsonEncoder.withIndent('').convert({
      'jornada_id': snap.jornadaId,
      'fecha': snap.fecha,
      'cobrador_id': snap.cobradorId,
      'ruta_id': snap.rutaId,
      'opening_base': snap.openingBase,
      'opening_carry': snap.openingCarry,
      'recaudo_real': snap.recaudoReal,
      'reversales': snap.reversales,
      'gastos': snap.gastos,
      'ahorro': snap.ahorro,
      'vales': snap.vales,
      'entregas': snap.entregas,
      'recibidos': snap.recibidos,
      'desembolsos': snap.desembolsos,
      'efectivo_esperado': snap.efectivoEsperado,
      'contado': snap.contado,
      'diferencia': snap.diferencia,
      'diferencia_motivo': snap.diferenciaMotivo,
      'cerrada_local_el': snap.cerradaLocalEl,
    });
    return sha256.convert(utf8.encode(canonical)).toString();
  }

  /// Crea JornadaSnapshot desde fila de jornada_snapshot en la base de datos.
  factory JornadaSnapshot.fromDbRow(Map<String, dynamic> row) {
    return JornadaSnapshot(
      jornadaId: row['jornada_id'] as String,
      fecha: row['fecha'] as String? ?? 'desconocida',
      cobradorId: row['cobrador_id'] as String?,
      rutaId: row['ruta_id'] as String? ?? 'Ruta Demo',
      openingBase: row['opening_base'] as int? ?? 0,
      openingCarry: row['opening_carry'] as int? ?? 0,
      recaudoReal: row['recaudo_real'] as int? ?? 0,
      reversales: row['reversales'] as int? ?? 0,
      gastos: row['gastos'] as int? ?? 0,
      ahorro: row['ahorro'] as int? ?? 0,
      vales: row['vales'] as int? ?? 0,
      entregas: row['entregas'] as int? ?? 0,
      recibidos: row['recibidos'] as int? ?? 0,
      desembolsos: row['desembolsos'] as int? ?? 0,
      efectivoEsperado: row['efectivo_esperado'] as int? ?? 0,
      contado: row['contado'] as int? ?? 0,
      diferencia: row['diferencia'] as int? ?? 0,
      diferenciaMotivo: row['diferencia_motivo'] as String?,
      cerradaLocalEl: row['cerrada_local_el'] as String? ?? '',
    );
  }
}
