import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/models.dart';
import '../services/caja_service.dart';
import '../services/jornada_service.dart';
import '../services/pdf_service.dart';
import '../services/sync_queue_service.dart';

class JornadaCierreScreen extends StatefulWidget {
  final Jornada jornada;
  final String cobradorNombre;
  const JornadaCierreScreen({super.key, required this.jornada, required this.cobradorNombre});

  @override
  State<JornadaCierreScreen> createState() => _JornadaCierreScreenState();
}

class _JornadaCierreScreenState extends State<JornadaCierreScreen> {
  Map<String, dynamic> _caja = {};
  int _efectivoContado = 0;
  bool _cargando = true;
  final _motivoController = TextEditingController();
  bool _jornadaCerrada = false;

  @override
  void initState() {
    super.initState();
    _cargarCaja();
  }

  Future<void> _cargarCaja() async {
    try {
      final caja = await CajaService.calcularCaja(widget.jornada.id);
      setState(() {
        _caja = caja;
        _cargando = false;
      });
    } catch (e) {
      setState(() => _cargando = false);
    }
  }

  Future<void> _cerrarJornada() async {
    if (_jornadaCerrada) return;

    final efectivo = _efectivoContado;
    if (efectivo <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Ingresa el efectivo contado')));
      return;
    }

    try {
      // Calculate expected
      final esperado = _caja['efectivo_esperado'] as int? ?? 0;
      final diferencia = efectivo - esperado;

      // Close jornada
      await JornadaService.cerrarJornada(widget.jornada.id, efectivo,
          _motivoController.text.trim());

      setState(() {
        _jornadaCerrada = true;
      });

      // Generate PDF
      final pdfPath = await PdfService.generarPdfCierre(
        _caja, widget.jornada.id, 'Ruta Demo', widget.cobradorNombre);

      // Share PDF
      await PdfService.compartirPdf(pdfPath);

      // Queue for sync
      await SyncQueueService.enqueue('jornada', widget.jornada.id, {
        'jornada_id': widget.jornada.id,
        'contado': efectivo,
        'esperado': esperado,
        'diferencia': diferencia,
        'diferencia_motivo': _motivoController.text.trim(),
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Jornada cerrada ✓')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Error: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Jornada'),
        backgroundColor: Colors.blue[800],
      ),
      body: _cargando ? const Center(child: CircularProgressIndicator()) :
      SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(children: [
          // Status
          Container(width: double.infinity, padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: _jornadaCerrada ? Colors.green[100] : Colors.orange[100],
              borderRadius: BorderRadius.circular(8)),
            child: Column(children: [
              Icon(_jornadaCerrada ? Icons.check_circle : Icons.hourglass_empty,
                  size: 48, color: _jornadaCerrada ? Colors.green : Colors.orange),
              const SizedBox(height: 8),
              Text(_jornadaCerrada ? 'JORNADA CERRADA' : 'JORNADA ABIERTA',
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 4),
              Text('Estado: ${widget.jornada.estado}',
                  style: const TextStyle(fontSize: 14)),
            ]),
          ),
          const SizedBox(height: 24),

          // Summary
          if (!_jornadaCerrada) ...[
            _summaryCard('Recaudo', '\$${_formatMoney(_caja['recaudo_real'] ?? 0)}', Colors.green),
            _summaryCard('Reversales', '\$${_formatMoney(_caja['reversales'] ?? 0)}', Colors.red),
            _summaryCard('Efectivo Esperado', '\$${_formatMoney(_caja['efectivo_esperado'] ?? 0)}', Colors.blue),
            const SizedBox(height: 24),

            // Efectivo contado
            const Text('Efectivo contado en caja:',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
            const SizedBox(height: 8),
            TextField(
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: 'Contado (COP)',
                prefixText: '\$ ',
                border: OutlineInputBorder(),
              ),
              onChanged: (v) {
                final val = int.tryParse(v);
                if (val != null) setState(() => _efectivoContado = val);
              },
            ),
            const SizedBox(height: 8),
            TextField(controller: _motivoController,
                decoration: const InputDecoration(
                    labelText: 'Motivo de diferencia (opcional)',
                    border: OutlineInputBorder())),
            const SizedBox(height: 24),

            // Close button
            SizedBox(width: double.infinity, height: 55,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(backgroundColor: Colors.red[700]),
                onPressed: _cerrarJornada,
                child: const Text('TERMINAR JORNADA',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white)),
              ),
            ),
          ] else ...[
            const SizedBox(height: 16),
            const Text('Jornada cerrada localmente',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            const Text('Pendiente de sincronización',
                style: TextStyle(color: Colors.orange)),
            const SizedBox(height: 16),
            Container(width: double.infinity, padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(color: Colors.green[50], borderRadius: BorderRadius.circular(8)),
              child: Column(children: [
                const Text('Contado', style: TextStyle(fontSize: 14)),
                Text('\$${_formatMoney(_efectivoContado)}',
                    style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.green)),
              ]),
            ),
          ],
        ]),
      ),
    );
  }

  Widget _summaryCard(String label, String value, Color color) {
    return Padding(padding: const EdgeInsets.only(bottom: 12),
      child: Container(width: double.infinity, padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(color: color.withOpacity(0.1),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: color)),
        child: Column(children: [
          Text(label, style: TextStyle(fontSize: 14, color: color)),
          Text(value, style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: color)),
        ]),
      ),
    );
  }

  String _formatMoney(int amount) {
    return amount.toString().replaceAllMapped(
      RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'),
      (m) => '${m[1]}.',
    );
  }

  @override
  void dispose() {
    _motivoController.dispose();
    super.dispose();
  }
}
