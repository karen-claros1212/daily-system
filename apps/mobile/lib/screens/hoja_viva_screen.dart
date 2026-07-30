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

  Color _semaforoColor(String semaforo) {
    switch (semaforo) {
      case 'VERDE': return const Color(0xFF2E7D32);
      case 'AMARILLO': return const Color(0xFFF9A825);
      case 'ROJO': return const Color(0xFFC62828);
      default: return const Color(0xFF9E9E9E);
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
    return Scaffold(
      appBar: AppBar(
        title: const Text('Hoja Viva'),
        elevation: 0,
      ),
      body: _cargando ? const Center(child: CircularProgressIndicator()) :
      _clientes.isEmpty ? Center(child: const Text('No hay clientes en esta ruta')) :
      Padding(
        padding: const EdgeInsets.all(16),
        child: Column(children: [
          // Summary chips
          Row(children: [
            _chip('VERDE', _clientes.where((c) => c['semaforo'] == 'VERDE').length,
                const Color(0xFF2E7D32)),
            const SizedBox(width: 8),
            _chip('AMARILLO', _clientes.where((c) => c['semaforo'] == 'AMARILLO').length,
                const Color(0xFFF9A825)),
            const SizedBox(width: 8),
            _chip('ROJO', _clientes.where((c) => c['semaforo'] == 'ROJO').length,
                const Color(0xFFC62828)),
          ]),
          const SizedBox(height: 16),
          // Client list
          Expanded(
            child: ListView.builder(
              itemCount: _clientes.length,
              itemBuilder: (context, index) {
                final c = _clientes[index];
                final color = _semaforoColor(c['semaforo'] as String);
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
                                  style: const TextStyle(
                                      fontSize: 15, fontWeight: FontWeight.w600)),
                              Text(_semaforoLabel(c['semaforo'] as String),
                                  style: TextStyle(fontSize: 12, color: color)),
                            ],
                          ),
                        ),
                        const Icon(Icons.chevron_right, color: Color(0xFFCAC4D0)),
                      ]),
                      // Expandable details
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          Expanded(
                            child: _detailChip('Cuota', formatMoney(c['cuota'] as int)),
                          ),
                          Expanded(
                            child: _detailChip('Saldo', formatMoney(c['saldo'] as int)),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Expanded(
                            child: _detailChip('Mora', '${c['mora_legacy']} cuotas'),
                          ),
                          Expanded(
                            child: _detailChip('Pico', formatMoney(c['pico'] as int)),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Expanded(
                            child: _detailChip('Pagadas', '${c['cuotas_pagadas']}/${c['n_cuotas']}'),
                          ),
                          Expanded(
                            child: _detailChip('Total', formatMoney(c['total'] as int)),
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

  Widget _chip(String label, int count, Color color) {
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

  Widget _detailChip(String label, String value) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: const Color(0xFFF5F5F0),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text('$label: $value',
          style: const TextStyle(fontSize: 11, color: Color(0xFF79747E))),
    );
  }
}
