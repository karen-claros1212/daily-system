import 'package:flutter/material.dart';
import '../services/hoja_viva_service.dart';
import '../theme/theme.dart';

class HojaVivaScreen extends StatefulWidget {
  final String rutaId;
  const HojaVivaScreen({super.key, required this.rutaId});

  @override
  State<HojaVivaScreen> createState() => _HojaVivaScreenState();
}

class _HojaVivaScreenState extends State<HojaVivaScreen> {
  List<Map<String, dynamic>> _clientes = [];
  bool _cargando = true;

  @override
  void initState() {
    super.initState();
    _cargarHojaViva();
  }

  Future<void> _cargarHojaViva() async {
    try {
      final clientes = await HojaVivaService.getHojaViva(widget.rutaId, '');
      setState(() {
        _clientes = clientes;
        _cargando = false;
      });
    } catch (e) {
      setState(() => _cargando = false);
    }
  }

  Color _semaforoColor(String semaforo, ThemeData theme) {
    switch (semaforo) {
      case 'VERDE': return theme.colorScheme.secondary;
      case 'AMARILLO': return theme.colorScheme.tertiary;
      case 'ROJO': return theme.colorScheme.error;
      default: return theme.colorScheme.onSurfaceVariant;
    }
  }

  String _semaforoLabel(String s) {
    switch (s) {
      case 'VERDE': return 'Favorable';
      case 'AMARILLO': return 'Precaución';
      case 'ROJO': return 'Riesgo alto';
      default: return 'Sin historial';
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Hoja Viva'),
        elevation: 0,
      ),
      body: _cargando ? Center(child: CircularProgressIndicator(color: theme.colorScheme.primary)) :
      _clientes.isEmpty ? Center(child: Text('No hay clientes en esta ruta', style: TextStyle(color: theme.colorScheme.onSurfaceVariant))) :
      Padding(
        padding: const EdgeInsets.all(16),
        child: Column(children: [
          // Summary chips
          Row(children: [
            _chip(theme, 'VERDE', _clientes.where((c) => c['semaforo'] == 'VERDE').length, theme.colorScheme.secondary),
            const SizedBox(width: 8),
            _chip(theme, 'AMARILLO', _clientes.where((c) => c['semaforo'] == 'AMARILLO').length, theme.colorScheme.tertiary),
            const SizedBox(width: 8),
            _chip(theme, 'ROJO', _clientes.where((c) => c['semaforo'] == 'ROJO').length, theme.colorScheme.error),
          ]),
          const SizedBox(height: 16),
          // Client list
          Expanded(
            child: ListView.builder(
              itemCount: _clientes.length,
              itemBuilder: (context, index) {
                final c = _clientes[index];
                final color = _semaforoColor(c['semaforo'] as String, theme);
                return Padding(padding: const EdgeInsets.only(bottom: 8),
                  child: premiumCard(
                    child: Column(children: [
                      Row(children: [
                        Container(
                          width: 10, height: 10,
                          decoration: BoxDecoration(
                            color: color,
                            shape: BoxShape.circle,
                            boxShadow: [
                              BoxShadow(color: color.withValues(alpha: 0.4), blurRadius: 6),
                            ],
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(c['cliente_nombre'] as String,
                                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: theme.colorScheme.onSurface)),
                              Text(_semaforoLabel(c['semaforo'] as String),
                                  style: TextStyle(fontSize: 12, color: color)),
                            ],
                          ),
                        ),
                        Icon(Icons.chevron_right, color: theme.colorScheme.onSurfaceVariant),
                      ]),
                      // Expandable details
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          Expanded(
                            child: _detailChip(theme, 'Cuota', formatMoney(c['cuota'] as int)),
                          ),
                          Expanded(
                            child: _detailChip(theme, 'Saldo', formatMoney(c['saldo'] as int)),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Expanded(
                            child: _detailChip(theme, 'Mora', '${c['mora_legacy']} cuotas'),
                          ),
                          Expanded(
                            child: _detailChip(theme, 'Pico', formatMoney(c['pico'] as int)),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Expanded(
                            child: _detailChip(theme, 'Pagadas', '${c['cuotas_pagadas']}/${c['n_cuotas']}'),
                          ),
                          Expanded(
                            child: _detailChip(theme, 'Total', formatMoney(c['total'] as int)),
                          ),
                        ],
                      ),
                    ]),
                  ),
                );
              },
            ),
          ),
        ]),
      ),
    );
  }

  Widget _chip(ThemeData theme, String label, int count, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(children: [
        Container(width: 6, height: 6, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
        const SizedBox(width: 6),
        Text('$label: $count', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: color)),
      ]),
    );
  }

  Widget _detailChip(ThemeData theme, String label, String value) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainer,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text('$label: $value',
          style: TextStyle(fontSize: 11, color: theme.colorScheme.onSurfaceVariant)),
    );
  }
}
