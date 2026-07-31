import 'package:flutter/material.dart';
import '../models/models.dart';
import '../models/caja_resultado.dart';
import '../services/caja_service.dart';
import '../services/jornada_service.dart';
import '../services/pdf_service.dart';
import '../theme/theme.dart';

class JornadaCierreScreen extends StatefulWidget {
  final Jornada jornada;
  final String cobradorNombre;
  const JornadaCierreScreen({super.key, required this.jornada, required this.cobradorNombre});

  @override
  State<JornadaCierreScreen> createState() => _JornadaCierreScreenState();
}

class _JornadaCierreScreenState extends State<JornadaCierreScreen> {
  CajaResultado? _caja;
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
      await JornadaService.cerrarJornada(widget.jornada.id, efectivo,
          _motivoController.text.trim());
      setState(() => _jornadaCerrada = true);
      await PdfService.generarPdfDesdeSnapshot(widget.jornada.id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Jornada cerrada \u2713')));
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
    final theme = Theme.of(context);
    final successColor = theme.colorScheme.secondary;
    final warningColor = theme.colorScheme.tertiary;
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
            bgColor: _jornadaCerrada
                ? successColor.withValues(alpha: 0.1)
                : warningColor.withValues(alpha: 0.15),
            child: Column(children: [
              Row(children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: _jornadaCerrada ? successColor : warningColor,
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
                              color: _jornadaCerrada ? successColor : warningColor)),
                      Text('Estado: ${widget.jornada.estado}',
                          style: TextStyle(fontSize: 12, color: theme.colorScheme.onSurfaceVariant)),
                    ],
                  ),
                ),
              ]),
            ]),
          ),
          const SizedBox(height: 20),

          if (!_jornadaCerrada && _caja != null) ...[
            Row(
              children: [
                Expanded(
                  child: premiumCard(
                    padding: const EdgeInsets.all(12),
                    child: Column(children: [
                      Icon(Icons.payment, size: 20, color: successColor),
                      const SizedBox(height: 4),
                      Text('Recaudo', style: TextStyle(fontSize: 11, color: theme.colorScheme.onSurfaceVariant)),
                      Text(formatMoney(_caja!.recaudoReal),
                          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: successColor)),
                    ]),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: premiumCard(
                    padding: const EdgeInsets.all(12),
                    child: Column(children: [
                      Icon(Icons.account_balance_wallet, size: 20, color: theme.colorScheme.primary),
                      const SizedBox(height: 4),
                      Text('Esperado', style: TextStyle(fontSize: 11, color: theme.colorScheme.onSurfaceVariant)),
                      Text(formatMoney(_caja!.efectivoEsperado),
                          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: theme.colorScheme.primary)),
                    ]),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),

            premiumCard(
              child: Column(children: [
                Text('Efectivo contado',
                    style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: theme.colorScheme.onSurface)),
                const SizedBox(height: 10),
                TextField(
                  keyboardType: TextInputType.number,
                  decoration: InputDecoration(
                    labelText: 'Contado (COP)',
                    labelStyle: TextStyle(color: theme.colorScheme.onSurfaceVariant),
                    prefixIcon: Icon(Icons.money, size: 20, color: theme.colorScheme.onSurfaceVariant),
                  ),
                  style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: theme.colorScheme.onSurface),
                  onChanged: (v) {
                    final val = int.tryParse(v);
                    if (val != null) setState(() => _efectivoContado = val);
                  },
                ),
                const SizedBox(height: 10),
                TextField(controller: _motivoController,
                    decoration: InputDecoration(
                        labelText: 'Motivo de diferencia (opcional)',
                        labelStyle: TextStyle(color: theme.colorScheme.onSurfaceVariant),
                        prefixIcon: Icon(Icons.note, size: 20, color: theme.colorScheme.onSurfaceVariant))),
                const SizedBox(height: 16),
                compactButton(
                  label: 'TERMINAR JORNADA',
                  onPressed: _cerrarJornada,
                  color: theme.colorScheme.error,
                  isLoading: _cerrando,
                ),
              ]),
            ),
          ] else if (_jornadaCerrada) ...[
            premiumCard(
              bgColor: successColor.withValues(alpha: 0.1),
              child: Column(children: [
                Text('Jornada cerrada localmente',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: successColor)),
                const SizedBox(height: 4),
                Text('Pendiente de sincronización',
                    style: TextStyle(fontSize: 12, color: warningColor)),
                const SizedBox(height: 12),
                statRow('Contado', formatMoney(_efectivoContado),
                    valueColor: successColor),
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
