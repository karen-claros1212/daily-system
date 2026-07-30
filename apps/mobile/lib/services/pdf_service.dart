import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';
import 'package:share_plus/share_plus.dart';
import 'package:path_provider/path_provider.dart';
import 'dart:io';
import 'package:intl/intl.dart';
import '../models/caja_resultado.dart';
import '../database/database.dart';

class PdfService {
  /// Genera PDF desde CajaResultado tipado (fuente única de verdad).
  static Future<String> generarPdfDesdeCaja(CajaResultado caja,
      String jornadaId, String rutaNombre, String cobradorNombre) async {
    final pdf = pw.Document();
    final fecha = DateFormat('dd/MM/yyyy').format(DateTime.now());
    final hora = DateFormat('HH:mm').format(DateTime.now());

    pdf.addPage(pw.MultiPage(
      pageFormat: PdfPageFormat.a5,
      build: (context) => [
        pw.Header(level: 0, child: pw.Text('DAILY SYSTEM - CIERRE DE JORNADA',
            style: pw.TextStyle(fontSize: 18, fontWeight: pw.FontWeight.bold))),
        pw.SizedBox(height: 10),
        pw.Row(children: [
          pw.Text('Fecha: $fecha', style: pw.TextStyle(fontSize: 12)),
          pw.SizedBox(width: 20),
          pw.Text('Hora: $hora', style: pw.TextStyle(fontSize: 12)),
        ]),
        pw.SizedBox(height: 10),
        pw.Divider(),
        pw.SizedBox(height: 10),
        pw.Text('RUTA: $rutaNombre', style: pw.TextStyle(fontSize: 14, fontWeight: pw.FontWeight.bold)),
        pw.Text('COBRADOR: $cobradorNombre', style: pw.TextStyle(fontSize: 12)),
        pw.Text('JORNADA ID: $jornadaId', style: pw.TextStyle(fontSize: 10)),
        pw.SizedBox(height: 20),
        pw.Text('RESUMEN DE CAJA', style: pw.TextStyle(fontSize: 14, fontWeight: pw.FontWeight.bold)),
        pw.SizedBox(height: 10),
        _buildCajaTable(caja),
        pw.SizedBox(height: 20),
        pw.Divider(),
        pw.SizedBox(height: 10),
        pw.Text('INFORME DE PAGOS', style: pw.TextStyle(fontSize: 14, fontWeight: pw.FontWeight.bold)),
        pw.SizedBox(height: 10),
        pw.Text('Total pagos: \$${_formatMoney(caja.recaudoReal)}', style: pw.TextStyle(fontSize: 12)),
        pw.Text('Total reversales: \$${_formatMoney(caja.reversales)}', style: pw.TextStyle(fontSize: 12)),
        pw.Text('Pagos realizados: ${caja.pagosCount}', style: pw.TextStyle(fontSize: 12)),
        pw.SizedBox(height: 20),
        pw.Divider(),
        pw.SizedBox(height: 10),
        pw.Text('MOVIMIENTOS DE CAJA', style: pw.TextStyle(fontSize: 14, fontWeight: pw.FontWeight.bold)),
        pw.SizedBox(height: 10),
        pw.Text('Gastos: \$${_formatMoney(caja.gastos)}', style: pw.TextStyle(fontSize: 12)),
        pw.Text('Ahorro: \$${_formatMoney(caja.ahorro)}', style: pw.TextStyle(fontSize: 12)),
        pw.Text('Vales: \$${_formatMoney(caja.vales)}', style: pw.TextStyle(fontSize: 12)),
        pw.Text('Entregas: \$${_formatMoney(caja.entregas)}', style: pw.TextStyle(fontSize: 12)),
        pw.Text('Recibidos: \$${_formatMoney(caja.recibidos)}', style: pw.TextStyle(fontSize: 12)),
        pw.Text('Desembolsos: \$${_formatMoney(caja.desembolsos)}', style: pw.TextStyle(fontSize: 12)),
        pw.SizedBox(height: 20),
        pw.Divider(),
        pw.SizedBox(height: 10),
        pw.Text('TOTAL EFECTIVO ESPERADO: \$${_formatMoney(caja.efectivoEsperado)}',
            style: pw.TextStyle(fontSize: 16, fontWeight: pw.FontWeight.bold)),
        pw.SizedBox(height: 30),
        pw.Text('---', style: pw.TextStyle(fontSize: 10)),
        pw.Text('Documento generado automáticamente desde snapshot de Daily System',
            style: pw.TextStyle(fontSize: 8)),
      ],
    ));

    // Save to file
    final dir = await getApplicationDocumentsDirectory();
    final fileName = 'cierre_jornada_${jornadaId}_${DateTime.now().millisecondsSinceEpoch}.pdf';
    final file = File('${dir.path}/$fileName');
    await file.writeAsBytes(await pdf.save());

    return file.path;
  }

  /// Genera PDF recuperable desde la fila inmutable jornada_snapshot.
  ///
  /// Usa la fecha almacenada en el snapshot (no DateTime.now()),
  /// el hash_content como parte del nombre de archivo,
  /// y todos los datos numéricos directamente desde la fila.
  static Future<String> generarPdfDesdeSnapshot(String jornadaId) async {
    final db = await database;
    final results = await db.query('jornada_snapshot',
        where: 'jornada_id = ?', whereArgs: [jornadaId], limit: 1);
    if (results.isEmpty) {
      throw Exception('Snapshot no encontrado para jornada: $jornadaId');
    }
    final snap = results.first;

    final caja = CajaResultado(
      openingBase: snap['opening_base'] as int? ?? 0,
      openingCarry: snap['opening_carry'] as int? ?? 0,
      recaudoReal: snap['recaudo_real'] as int? ?? 0,
      reversales: snap['reversales'] as int? ?? 0,
      gastos: snap['gastos'] as int? ?? 0,
      ahorro: snap['ahorro'] as int? ?? 0,
      vales: snap['vales'] as int? ?? 0,
      entregas: snap['entregas'] as int? ?? 0,
      recibidos: snap['recibidos'] as int? ?? 0,
      desembolsos: snap['desembolsos'] as int? ?? 0,
      efectivoEsperado: snap['efectivo_esperado'] as int? ?? 0,
      pagosCount: snap['pagos_count'] as int? ?? 0,
      reversalesCount: snap['reversales_count'] as int? ?? 0,
      movimientosCount: snap['movimientos_count'] as int? ?? 0,
    );

    final fecha = snap['fecha'] as String? ?? 'desconocida';
    final hash = snap['hash_content'] as String? ?? jornadaId;
    final rutaNombre = snap['ruta_id'] as String? ?? 'Ruta Demo';
    final cobradorNombre = snap['cobrador_id'] as String? ?? 'Cobrador';
    final contado = snap['contado'] as int? ?? 0;
    final diferencia = snap['diferencia'] as int? ?? 0;
    final diferenciaMotivo = snap['diferencia_motivo'] as String? ?? '';

    final pdf = pw.Document();

    pdf.addPage(pw.MultiPage(
      pageFormat: PdfPageFormat.a5,
      build: (context) => [
        pw.Header(level: 0, child: pw.Text('DAILY SYSTEM - CIERRE DE JORNADA',
            style: pw.TextStyle(fontSize: 18, fontWeight: pw.FontWeight.bold))),
        pw.SizedBox(height: 10),
        pw.Row(children: [
          pw.Text('Fecha: $fecha', style: pw.TextStyle(fontSize: 12)),
          pw.SizedBox(width: 20),
          pw.Text('Hash: ${hash.substring(0, 16)}...', style: pw.TextStyle(fontSize: 9)),
        ]),
        pw.SizedBox(height: 10),
        pw.Divider(),
        pw.SizedBox(height: 10),
        pw.Text('RUTA: $rutaNombre', style: pw.TextStyle(fontSize: 14, fontWeight: pw.FontWeight.bold)),
        pw.Text('COBRADOR: $cobradorNombre', style: pw.TextStyle(fontSize: 12)),
        pw.Text('JORNADA ID: $jornadaId', style: pw.TextStyle(fontSize: 10)),
        pw.SizedBox(height: 20),
        pw.Text('RESUMEN DE CAJA', style: pw.TextStyle(fontSize: 14, fontWeight: pw.FontWeight.bold)),
        pw.SizedBox(height: 10),
        _buildCajaTable(caja),
        pw.SizedBox(height: 20),
        pw.Divider(),
        pw.SizedBox(height: 10),
        pw.Text('INFORME DE PAGOS', style: pw.TextStyle(fontSize: 14, fontWeight: pw.FontWeight.bold)),
        pw.SizedBox(height: 10),
        pw.Text('Total pagos: \$${_formatMoney(caja.recaudoReal)}', style: pw.TextStyle(fontSize: 12)),
        pw.Text('Total reversales: \$${_formatMoney(caja.reversales)}', style: pw.TextStyle(fontSize: 12)),
        pw.Text('Pagos realizados: ${caja.pagosCount}', style: pw.TextStyle(fontSize: 12)),
        pw.SizedBox(height: 20),
        pw.Divider(),
        pw.SizedBox(height: 10),
        pw.Text('MOVIMIENTOS DE CAJA', style: pw.TextStyle(fontSize: 14, fontWeight: pw.FontWeight.bold)),
        pw.SizedBox(height: 10),
        pw.Text('Gastos: \$${_formatMoney(caja.gastos)}', style: pw.TextStyle(fontSize: 12)),
        pw.Text('Ahorro: \$${_formatMoney(caja.ahorro)}', style: pw.TextStyle(fontSize: 12)),
        pw.Text('Vales: \$${_formatMoney(caja.vales)}', style: pw.TextStyle(fontSize: 12)),
        pw.Text('Entregas: \$${_formatMoney(caja.entregas)}', style: pw.TextStyle(fontSize: 12)),
        pw.Text('Recibidos: \$${_formatMoney(caja.recibidos)}', style: pw.TextStyle(fontSize: 12)),
        pw.Text('Desembolsos: \$${_formatMoney(caja.desembolsos)}', style: pw.TextStyle(fontSize: 12)),
        pw.SizedBox(height: 20),
        pw.Divider(),
        pw.SizedBox(height: 10),
        pw.Text('TOTAL EFECTIVO ESPERADO: \$${_formatMoney(caja.efectivoEsperado)}',
            style: pw.TextStyle(fontSize: 16, fontWeight: pw.FontWeight.bold)),
        pw.SizedBox(height: 10),
        pw.Text('Efectivo contado: \$${_formatMoney(contado)}',
            style: pw.TextStyle(fontSize: 14, fontWeight: pw.FontWeight.bold)),
        pw.SizedBox(height: 10),
        pw.Text('Diferencia: \$${_formatMoney(diferencia)}',
            style: pw.TextStyle(fontSize: 14,
                fontWeight: pw.FontWeight.bold,
                color: diferencia == 0 ? PdfColor.fromHex('2E7D32') : PdfColor.fromHex('C62828'))),
        if (diferenciaMotivo.isNotEmpty) ...[
          pw.SizedBox(height: 5),
          pw.Text('Motivo: $diferenciaMotivo',
              style: pw.TextStyle(fontSize: 10, fontStyle: pw.FontStyle.italic)),
        ],
        pw.SizedBox(height: 30),
        pw.Text('---', style: pw.TextStyle(fontSize: 10)),
        pw.Text('Snapshot inmutable v2 — ${snap['cerrada_local_el'] ?? fecha}',
            style: pw.TextStyle(fontSize: 8)),
      ],
    ));

    final dir = await getApplicationDocumentsDirectory();
    final safeHash = hash.replaceAll(RegExp(r'[^a-zA-Z0-9_]'), '_');
    final fileName = 'cierre_${jornadaId}_${safeHash.substring(0, 16)}.pdf';
    final file = File('${dir.path}/$fileName');
    await file.writeAsBytes(await pdf.save());

    return file.path;
  }

  /// Método legacy para compatibilidad con tests antiguos.
  @Deprecated('Usar generarPdfDesdeCaja')
  static Future<String> generarPdfCierre(Map<String, dynamic> caja,
      String jornadaId, String rutaNombre, String cobradorNombre) async {
    // Convert Map to CajaResultado (legacy)
    final cajaTyped = CajaResultado(
      openingBase: caja['opening_base'] as int? ?? 0,
      openingCarry: caja['opening_carry'] as int? ?? 0,
      recaudoReal: caja['recaudo_real'] as int? ?? 0,
      reversales: caja['reversales'] as int? ?? 0,
      gastos: caja['gastos'] as int? ?? 0,
      ahorro: caja['ahorro'] as int? ?? 0,
      vales: caja['vales'] as int? ?? 0,
      entregas: caja['entregas'] as int? ?? 0,
      recibidos: caja['recibidos'] as int? ?? 0,
      desembolsos: caja['desembolsos'] as int? ?? 0,
      efectivoEsperado: caja['efectivo_esperado'] as int? ?? 0,
      pagosCount: caja['pagos_count'] as int? ?? 0,
      reversalesCount: caja['reversales_count'] as int? ?? 0,
      movimientosCount: caja['movimientos_count'] as int? ?? 0,
    );
    return generarPdfDesdeCaja(cajaTyped, jornadaId, rutaNombre, cobradorNombre);
  }

  static pw.Widget _buildCajaTable(CajaResultado caja) {
    return pw.Column(crossAxisAlignment: pw.CrossAxisAlignment.start, children: [
      _pdfRow('Opening Base', '\$${_formatMoney(caja.openingBase)}'),
      _pdfRow('Opening Carry', '\$${_formatMoney(caja.openingCarry)}'),
      _pdfRow('Recaudo Real', '\$${_formatMoney(caja.recaudoReal)}'),
      _pdfRow('Reversales', '\$${_formatMoney(caja.reversales)}'),
      pw.SizedBox(height: 8),
      _pdfRowBold('Efectivo Esperado', '\$${_formatMoney(caja.efectivoEsperado)}'),
    ]);
  }

  static pw.Widget _pdfRow(String label, String value) {
    return pw.Padding(padding: const pw.EdgeInsets.symmetric(vertical: 2),
      child: pw.Row(children: [
        pw.Expanded(child: pw.Text(label, style: pw.TextStyle(fontSize: 11))),
        pw.Text(value, style: pw.TextStyle(fontSize: 11), textAlign: pw.TextAlign.right),
      ]),
    );
  }

  static pw.Widget _pdfRowBold(String label, String value) {
    return pw.Padding(padding: const pw.EdgeInsets.symmetric(vertical: 2),
      child: pw.Row(children: [
        pw.Expanded(child: pw.Text(label, style: pw.TextStyle(fontSize: 11, fontWeight: pw.FontWeight.bold))),
        pw.Text(value, style: pw.TextStyle(fontSize: 11, fontWeight: pw.FontWeight.bold), textAlign: pw.TextAlign.right),
      ]),
    );
  }

  static String _formatMoney(int amount) {
    return amount.toString().replaceAllMapped(
      RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'),
      (Match m) => '${m[1]}.',
    );
  }

  static Future<void> compartirPdf(String filePath) async {
    await Share.shareXFiles([XFile(filePath)], subject: 'Cierre de Jornada - Daily System');
  }

  static Future<void> imprimirPdf(String filePath) async {
    await Printing.layoutPdf(onLayout: (PdfPageFormat format) async {
      // Re-read and print
      final bytes = await File(filePath).readAsBytes();
      return bytes;
    });
  }
}
