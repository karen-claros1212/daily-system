import 'dart:io';
import 'package:crypto/crypto.dart';
import 'package:sqflite/sqflite.dart' show DatabaseException;
import 'package:uuid/uuid.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';
import 'package:share_plus/share_plus.dart';
import 'package:path_provider/path_provider.dart';
import 'package:intl/intl.dart';
import '../models/caja_resultado.dart';
import '../models/jornada_snapshot.dart';
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

  /// Registra documento PDF en jornada_documento.
  static Future<void> _registrarDocumento(
      String jornadaId, String estado, String? ruta, String? pdfHashSha256,
      String? snapshotHash, String? error, String creadoEl, String generadoEl) async {
    final db = await database;
    final id = _uuidV4();
    try {
      await db.insert('jornada_documento', {
        'id': id,
        'jornada_id': jornadaId,
        'tipo': 'PDF_CIERRE',
        'estado': estado,
        'ruta': ruta,
        'snapshot_hash': snapshotHash,
        'pdf_hash_sha256': pdfHashSha256,
        'bytes_b64': null,
        'error': error,
        'creado_el': creadoEl,
        'generado_el': generadoEl,
      });
    } on DatabaseException catch (e) {
      // UNIQUE constraint puede fallar si ya existe; actualizar estado
      if (e.toString().contains('UNIQUE constraint failed')) {
        await db.update('jornada_documento', {
          'estado': estado,
          'ruta': ruta,
          'snapshot_hash': snapshotHash,
          'pdf_hash_sha256': pdfHashSha256,
          'error': error,
          'generado_el': generadoEl,
        }, where: 'jornada_id = ? AND tipo = ?', whereArgs: [jornadaId, 'PDF_CIERRE']);
      } else {
        rethrow;
      }
    }
  }

  /// Genera PDF recuperable desde la fila inmutable jornada_snapshot.
  ///
  /// Flujo completo:
  /// 1. Obtiene snapshot y valida hash_content contra hash recomputado
  /// 2. Verifica PDF existente en disco (%PDF header + hash_sha256)
  /// 3. Si hash mismatch → aborta con FAILED_RETRYABLE
  /// 4. Si existe PDF válido → reutiliza
  /// 5. Si no existe → genera desde snapshot y registra
  static Future<String> generarPdfDesdeSnapshot(String jornadaId) async {
    final db = await database;
    final now = DateTime.now().toIso8601String();

    // 1. Obtener snapshot
    final results = await db.query('jornada_snapshot',
        where: 'jornada_id = ?', whereArgs: [jornadaId], limit: 1);
    if (results.isEmpty) {
      await _registrarDocumento(jornadaId, 'FAILED_PERMANENT', null, null,
          null, 'Snapshot no encontrado para jornada: $jornadaId', now, now);
      throw Exception('Snapshot no encontrado para jornada: $jornadaId');
    }
    final snap = results.first;

    // 2. Validar hash_content del snapshot
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
    final cobradorId = snap['cobrador_id'] as String?;
    final rutaId = snap['ruta_id'] as String? ?? 'Ruta Demo';
    final contado = snap['contado'] as int? ?? 0;
    final diferencia = snap['diferencia'] as int? ?? 0;
    final diferenciaMotivo = snap['diferencia_motivo'] as String? ?? '';
    final storedHash = snap['hash_content'] as String?;
    final cerradaLocalEl = snap['cerrada_local_el'] as String? ?? '';

    final recomputedHash = _recomputeSnapshotHash(
        jornadaId, caja, fecha, cobradorId, rutaId, contado,
        diferencia, diferenciaMotivo, cerradaLocalEl);

    // Hash mismatch → aborta generación (integridad del snapshot)
    if (storedHash != null && storedHash != recomputedHash) {
      await _registrarDocumento(jornadaId, 'FAILED_RETRYABLE', null,
          null, storedHash, 'Hash mismatch: stored=$storedHash computed=$recomputedHash', now, now);
      throw Exception('Snapshot corrupto: hash mismatch (stored=$storedHash computed=$recomputedHash)');
    }

    // 3. Verificar PDF existente en disco
    final existingPdfPath = await _findExistingPdf(jornadaId, storedHash);
    if (existingPdfPath != null) {
      final pdfFile = File(existingPdfPath);
      if (await pdfFile.exists()) {
        final fileSize = await pdfFile.length();
        if (fileSize > 1024) {
          // Verificar encabezado %PDF
          final headerBytes = (await pdfFile.readAsBytes()).sublist(0, 5);
          final header = String.fromCharCodes(headerBytes);
          if (header == '%PDF-') {
            // Verificar hash del archivo si existe storedHash
            String? storedPdfHash;
            if (storedHash != null) {
              final fileBytes = await pdfFile.readAsBytes();
              final fileSha256 = sha256.convert(fileBytes).toString();
              // storedHash es snapshot_hash, buscar pdf_hash_sha256 en jornada_documento
              final docResults = await db.query('jornada_documento',
                  where: 'jornada_id = ? AND tipo = ?',
                  whereArgs: [jornadaId, 'PDF_CIERRE'], limit: 1);
              if (docResults.isNotEmpty) {
                storedPdfHash = docResults.first['pdf_hash_sha256'] as String?;
              }
              if (storedPdfHash != null && storedPdfHash == fileSha256) {
                // Hash coincide — PDF válido
                await _registrarDocumento(jornadaId, 'GENERATED', existingPdfPath,
                    fileSha256, storedHash, null, now, now);
                return existingPdfPath;
              }
              // Hash no coincide pero header correcto — regenerar
              await _registrarDocumento(jornadaId, 'FAILED_RETRYABLE', null,
                  fileSha256, storedHash, 'PDF hash mismatch: stored=${storedPdfHash ?? 'N/A'} computed=$fileSha256', now, now);
            } else {
              // No hay hash almacenado, header correcto suficiente
              await _registrarDocumento(jornadaId, 'GENERATED', existingPdfPath,
                  null, null, null, now, now);
              return existingPdfPath;
            }
          }
        }
      }
    }

    // 4. Generar PDF desde snapshot
    final pdf = pw.Document();
    final rutaNombre = rutaId;
    final cobradorNombre = cobradorId ?? 'Cobrador';

    pdf.addPage(pw.MultiPage(
      pageFormat: PdfPageFormat.a5,
      build: (context) => [
        pw.Header(level: 0, child: pw.Text('DAILY SYSTEM - CIERRE DE JORNADA',
            style: pw.TextStyle(fontSize: 18, fontWeight: pw.FontWeight.bold))),
        pw.SizedBox(height: 10),
        pw.Row(children: [
          pw.Text('Fecha: $fecha', style: pw.TextStyle(fontSize: 12)),
          pw.SizedBox(width: 20),
          pw.Text('Hash: ${storedHash?.substring(0, 16) ?? 'N/A'}...',
              style: pw.TextStyle(fontSize: 9)),
        ]),
        pw.SizedBox(height: 10),
        pw.Divider(),
        pw.SizedBox(height: 10),
        pw.Text('RUTA: $rutaNombre',
            style: pw.TextStyle(fontSize: 14, fontWeight: pw.FontWeight.bold)),
        pw.Text('COBRADOR: $cobradorNombre',
            style: pw.TextStyle(fontSize: 12)),
        pw.Text('JORNADA ID: $jornadaId',
            style: pw.TextStyle(fontSize: 10)),
        pw.SizedBox(height: 20),
        pw.Text('RESUMEN DE CAJA',
            style: pw.TextStyle(fontSize: 14, fontWeight: pw.FontWeight.bold)),
        pw.SizedBox(height: 10),
        _buildCajaTable(caja),
        pw.SizedBox(height: 20),
        pw.Divider(),
        pw.SizedBox(height: 10),
        pw.Text('INFORME DE PAGOS',
            style: pw.TextStyle(fontSize: 14, fontWeight: pw.FontWeight.bold)),
        pw.SizedBox(height: 10),
        pw.Text(
            'Total pagos: \$${_formatMoney(caja.recaudoReal)}',
            style: pw.TextStyle(fontSize: 12)),
        pw.Text(
            'Total reversales: \$${_formatMoney(caja.reversales)}',
            style: pw.TextStyle(fontSize: 12)),
        pw.Text(
            'Pagos realizados: ${caja.pagosCount}',
            style: pw.TextStyle(fontSize: 12)),
        pw.SizedBox(height: 20),
        pw.Divider(),
        pw.SizedBox(height: 10),
        pw.Text('MOVIMIENTOS DE CAJA',
            style: pw.TextStyle(fontSize: 14, fontWeight: pw.FontWeight.bold)),
        pw.SizedBox(height: 10),
        pw.Text('Gastos: \$${_formatMoney(caja.gastos)}',
            style: pw.TextStyle(fontSize: 12)),
        pw.Text('Ahorro: \$${_formatMoney(caja.ahorro)}',
            style: pw.TextStyle(fontSize: 12)),
        pw.Text('Vales: \$${_formatMoney(caja.vales)}',
            style: pw.TextStyle(fontSize: 12)),
        pw.Text('Entregas: \$${_formatMoney(caja.entregas)}',
            style: pw.TextStyle(fontSize: 12)),
        pw.Text('Recibidos: \$${_formatMoney(caja.recibidos)}',
            style: pw.TextStyle(fontSize: 12)),
        pw.Text('Desembolsos: \$${_formatMoney(caja.desembolsos)}',
            style: pw.TextStyle(fontSize: 12)),
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
            style: pw.TextStyle(fontSize: 14, fontWeight: pw.FontWeight.bold,
                color: diferencia == 0
                    ? PdfColor.fromHex('2E7D32')
                    : PdfColor.fromHex('C62828'))),
        if (diferenciaMotivo.isNotEmpty) ...[
          pw.SizedBox(height: 5),
          pw.Text('Motivo: $diferenciaMotivo',
              style: pw.TextStyle(fontSize: 10, fontStyle: pw.FontStyle.italic)),
        ],
        pw.SizedBox(height: 30),
        pw.Text('---', style: pw.TextStyle(fontSize: 10)),
        pw.Text('Snapshot inmutable v2 — ${cerradaLocalEl.isNotEmpty ? cerradaLocalEl : fecha}',
            style: pw.TextStyle(fontSize: 8)),
      ],
    ));

    // 5. Guardar PDF en disco
    final dir = await getApplicationDocumentsDirectory();
    final safeHash = storedHash?.replaceAll(RegExp(r'[^a-zA-Z0-9_]'), '_') ?? jornadaId;
    final fileName = 'cierre_${jornadaId}_${safeHash.substring(0, 16)}.pdf';
    final file = File('${dir.path}/$fileName');
    final bytes = await pdf.save();

    try {
      await file.writeAsBytes(bytes);
      final pdfSha256 = sha256.convert(bytes).toString();
      await _registrarDocumento(jornadaId, 'GENERATED', file.path,
          pdfSha256, storedHash, null, now, now);
      return file.path;
    } catch (e) {
      await _registrarDocumento(jornadaId, 'FAILED_RETRYABLE', null,
          null, storedHash, 'Error al guardar PDF: $e', now, now);
      rethrow;
    }
  }

  /// Busca PDF existente para esta jornada (por hash o nombre).
  /// Primero consulta jornada_documento para obtener pdf_hash_sha256,
  /// luego busca archivo que coincida.
  static Future<String?> _findExistingPdf(String jornadaId, String? storedHash) async {
    final db = await database;
    // 1. Buscar pdf_hash_sha256 en jornada_documento
    final docResults = await db.query('jornada_documento',
        where: 'jornada_id = ? AND tipo = ? AND estado = ?',
        whereArgs: [jornadaId, 'PDF_CIERRE', 'GENERATED'], limit: 1);
    String? storedPdfHash;
    String? storedRuta;
    if (docResults.isNotEmpty) {
      storedPdfHash = docResults.first['pdf_hash_sha256'] as String?;
      storedRuta = docResults.first['ruta'] as String?;
    }

    // Si tenemos ruta almacenada, verificar que existe
    if (storedRuta != null) {
      final pdfFile = File(storedRuta);
      if (await pdfFile.exists()) {
        final fileSize = await pdfFile.length();
        if (fileSize > 1024) {
          final headerBytes = (await pdfFile.readAsBytes()).sublist(0, 5);
          final header = String.fromCharCodes(headerBytes);
          if (header == '%PDF-') {
            return storedRuta;
          }
        }
      }
    }

    // 2. Buscar por nombre de archivo
    final dir = await getApplicationDocumentsDirectory();
    final prefix = 'cierre_${jornadaId}_';
    final dirHandle = Directory('${dir.path}/');
    final files = await dirHandle.list().toList();

    for (final entity in files) {
      if (entity is File) {
        final name = entity.path.split('/').last;
        if (!name.startsWith(prefix)) continue;
        // Si tenemos hash almacenado, buscar archivo con ese hash en el nombre
        if (storedPdfHash != null && name.contains(storedPdfHash.substring(0, 8))) {
          return entity.path;
        }
        // Si tenemos storedHash (snapshot), buscar por snapshot hash
        if (storedHash != null && name.contains(storedHash.substring(0, 8))) {
          return entity.path;
        }
        // Si no hay hash, cualquier archivo con prefix cuenta
        if (storedPdfHash == null && storedHash == null) {
          return entity.path;
        }
      }
    }
    return null;
  }

  static String _recomputeSnapshotHash(String jornadaId, CajaResultado caja,
      String fecha, String? cobradorId, String rutaId, int contado,
      int diferencia, String diferenciaMotivo, String cerradaLocalEl) {
    final snapshot = JornadaSnapshot(
      jornadaId: jornadaId,
      fecha: fecha,
      cobradorId: cobradorId,
      rutaId: rutaId,
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
      cerradaLocalEl: cerradaLocalEl,
    );
    return JornadaSnapshot.computeHash(snapshot);
  }

  static String _uuidV4() => const Uuid().v4();

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
