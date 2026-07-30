import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';
import 'package:share_plus/share_plus.dart';
import 'package:path_provider/path_provider.dart';
import 'dart:io';
import 'package:intl/intl.dart';

class PdfService {
  static Future<String> generarPdfCierre(Map<String, dynamic> caja,
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
        pw.Text('Total pagos: \$${_formatMoney(caja['recaudo_real'])}', style: pw.TextStyle(fontSize: 12)),
        pw.Text('Total reversales: \$${_formatMoney(caja['reversales'])}', style: pw.TextStyle(fontSize: 12)),
        pw.Text('Pagos realizados: ${caja['pagos_count']}', style: pw.TextStyle(fontSize: 12)),
        pw.SizedBox(height: 20),
        pw.Divider(),
        pw.SizedBox(height: 10),
        pw.Text('MOVIMIENTOS DE CAJA', style: pw.TextStyle(fontSize: 14, fontWeight: pw.FontWeight.bold)),
        pw.SizedBox(height: 10),
        pw.Text('Gastos: \$${_formatMoney(caja['gastos'])}', style: pw.TextStyle(fontSize: 12)),
        pw.Text('Ahorro: \$${_formatMoney(caja['ahorro'])}', style: pw.TextStyle(fontSize: 12)),
        pw.Text('Vales: \$${_formatMoney(caja['vales'])}', style: pw.TextStyle(fontSize: 12)),
        pw.Text('Entregas: \$${_formatMoney(caja['entregas'])}', style: pw.TextStyle(fontSize: 12)),
        pw.Text('Recibidos: \$${_formatMoney(caja['recibidos'])}', style: pw.TextStyle(fontSize: 12)),
        pw.Text('Desembolsos: \$${_formatMoney(caja['desembolsos'])}', style: pw.TextStyle(fontSize: 12)),
        pw.SizedBox(height: 20),
        pw.Divider(),
        pw.SizedBox(height: 10),
        pw.Text('TOTAL EFECTIVO ESPERADO: \$${_formatMoney(caja['efectivo_esperado'])}',
            style: pw.TextStyle(fontSize: 16, fontWeight: pw.FontWeight.bold)),
        pw.SizedBox(height: 30),
        pw.Text('---', style: pw.TextStyle(fontSize: 10)),
        pw.Text('Documento generado automáticamente por Daily System',
            style: pw.TextStyle(fontSize: 8)),
      ],
    ));

    // Save to file
    final dir = await getApplicationDocumentsDirectory();
    final fileName = 'cierre_jornada_${DateTime.now().millisecondsSinceEpoch}.pdf';
    final file = File('${dir.path}/$fileName');
    await file.writeAsBytes(await pdf.save());

    return file.path;
  }

  static pw.Widget _buildCajaTable(Map<String, dynamic> caja) {
    return pw.Column(crossAxisAlignment: pw.CrossAxisAlignment.start, children: [
      _pdfRow('Opening Base', '\$${_formatMoney(caja['opening_base'] as int)}'),
      _pdfRow('Opening Carry', '\$${_formatMoney(caja['opening_carry'] as int)}'),
      _pdfRow('Recaudo Real', '\$${_formatMoney(caja['recaudo_real'] as int)}'),
      _pdfRow('Reversales', '\$${_formatMoney(caja['reversales'] as int)}'),
      pw.SizedBox(height: 8),
      _pdfRowBold('Efectivo Esperado', '\$${_formatMoney(caja['efectivo_esperado'] as int)}'),
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
      final pdf = pw.Document();
      // Re-read and print
      final bytes = await File(filePath).readAsBytes();
      return bytes;
    });
  }
}
