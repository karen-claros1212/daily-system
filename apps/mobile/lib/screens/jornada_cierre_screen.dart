import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/models.dart';
import '../services/caja_service.dart';
import '../services/jornada_service.dart';
import '../services/pdf_service.dart';
import '../services/sync_queue_service.dart';
import '../theme/theme.dart';

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
  bool _cerrando = false;

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
    if (_jornadaCerrada || _cerrando) return;
    final efectivo = _efectivoContado;
    if (efectivo <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Ingresa el efectivo contado')));
      return;
    }

    setState(() => _cerrando = true);
    try {
      final esperado = _caja['efectivo_esperado'] as int? ?? 0;
      final diferencia = efectivo - esperado;

      await JornadaService.cerrarJornada(widget.jornada.id, efectivo,
          _motivoController.text.trim());

      setState(() => _jornadaCerrada = true);

      await PdfService.generarPdfCierre(
        _caja, widget.jornada.id, 'Ruta Demo', widget.cobradorNombre);
      // PDF generado — en producción se compartiría

      await SyncQueueService.enqueue('jornada', widget.jornada.id, {
        'jornada_id': widget.jornada.id,
        'contado': efectivo,
        'esperado': esperado,
        'diferencia': diferencia,
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Jornada cerrada ✓')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Error: $e')));
        setState(() => _cerrando = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Jornada'),
        elevation: 0,
      ),
      body: _cargando ? const Center(child: CircularProgressIndicator()) :
      SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(children: [
          // Status
          premiumCard(
            bgColor: _jornadaCerrada ? const Color(0xFFE8F5E9) : const Color(0xFFFFF8E1),
            child: Column(children: [
              Row(children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: _jornadaCerrada ? const Color(0xFF2E7D32) : const Color(0xFFF9A825),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(_jornadaCerrada ? Icons.check_circle : Icons.hourglass_empty,
                      color: Colors.white, size: 24),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(_jornadaCerrada ? 'JORNADA CERRADA' : 'JORNADA ABIERTA',
                          style: TextStyle(
                              fontSize: 16, fontWeight: FontWeight.w600,
                              color: _jornadaCerrada ? const Color(0xFF2E7D32) : const Color(0xFFF57F17))),
                      Text('Estado: ${widget.jornada.estado}',
                          style: const TextStyle(fontSize: 12, color: Color(0xFF79747E))),
                    ],
                  ),
                ),
              ]),
            ]),
          ),
          const SizedBox(height: 20),

          if (!_jornadaCerrada) ...[
            // Summary cards
            Row(
              children: [
                Expanded(
                  child: premiumCard(
                    padding: const EdgeInsets.all(12),
                    child: Column(children: [
                      const Icon(Icons.payment, size: 20, color: Color(0xFF2E7D32)),
                      const SizedBox(height: 4),
                      const Text('Recaudo', style: TextStyle(fontSize: 11, color: Color(0xFF79747E))),
                      Text(formatMoney(_caja['recaudo_real'] ?? 0),
                          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Color(0xFF2E7D32))),
                    ]),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: premiumCard(
                    padding: const EdgeInsets.all(12),
                    child: Column(children: [
                      const Icon(Icons.account_balance_wallet, size: 20, color: Color(0xFF1565C0)),
                      const SizedBox(height: 4),
                      const Text('Esperado', style: TextStyle(fontSize: 11, color: Color(0xFF79747E))),
                      Text(formatMoney(_caja['efectivo_esperado'] ?? 0),
                          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Color(0xFF1565C0))),
                    ]),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),

            // Efectivo contado
            premiumCard(
              child: Column(children: [
                const Text('Efectivo contado',
                    style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                const SizedBox(height: 10),
                TextField(
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Contado (COP)',
                    prefixIcon: Icon(Icons.money, size: 20),
                  ),
                  style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700),
                  onChanged: (v) {
                    final val = int.tryParse(v);
                    if (val != null) setState(() => _efectivoContado = val);
                  },
                ),
                const SizedBox(height: 10),
                TextField(controller: _motivoController,
                    decoration: const InputDecoration(
                        labelText: 'Motivo de diferencia (opcional)',
                        prefixIcon: Icon(Icons.note, size: 20))),
                const SizedBox(height: 16),
                compactButton(
                  label: 'TERMINAR JORNADA',
                  onPressed: _cerrarJornada,
                  color: const Color(0xFFC62828),
                  isLoading: _cerrando,
                ),
              ]),
            ),
          ] else ...[
            premiumCard(
              bgColor: const Color(0xFFE8F5E9),
              child: Column(children: [
                const Text('Jornada cerrada localmente',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF2E7D32))),
                const SizedBox(height: 4),
                const Text('Pendiente de sincronización',
                    style: TextStyle(fontSize: 12, color: Color(0xFFF57F17))),
                const SizedBox(height: 12),
                statRow('Contado', formatMoney(_efectivoContado),
                    valueColor: const Color(0xFF2E7D32)),
              ]),
            ),
          ],
        ]),
      ),
    );
  }

  @override
  void dispose() {
    _motivoController.dispose();
    super.dispose();
  }
}
