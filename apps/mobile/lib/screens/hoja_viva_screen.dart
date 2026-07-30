import 'package:flutter/material.dart';
import '../services/hoja_viva_service.dart';

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
      case 'VERDE': return Colors.green;
      case 'AMARILLO': return Colors.orange;
      case 'ROJO': return Colors.red;
      default: return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Hoja Viva'),
        backgroundColor: Colors.blue[800],
      ),
      body: _cargando ? const Center(child: CircularProgressIndicator()) :
      _clientes.isEmpty ? Center(child: const Text('No hay clientes en esta ruta')) :
      ListView.builder(
        itemCount: _clientes.length,
        itemBuilder: (context, index) {
          final c = _clientes[index];
          final color = _semaforoColor(c['semaforo'] as String);
          return Card(
            margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            child: ExpansionTile(
              leading: Container(
                width: 12,
                height: 12,
                decoration: BoxDecoration(color: color, shape: BoxShape.circle),
              ),
              title: Text(c['cliente_nombre'] as String,
                  style: const TextStyle(fontWeight: FontWeight.bold)),
              subtitle: Text('Cuota: \$${_formatMoney(c['cuota'] as int)}',
                  style: const TextStyle(fontSize: 12)),
              children: [
                Padding(padding: const EdgeInsets.all(16),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _infoRow('Saldo pendiente', '\$${_formatMoney(c['saldo'] as int)}'),
                      _infoRow('Mora legacy', '${c['mora_legacy']} cuotas vencidas'),
                      _infoRow('Pico', '\$${_formatMoney(c['pico'] as int)}'),
                      _infoRow('Cuotas pagadas', '${c['cuotas_pagadas']}/${c['n_cuotas']}'),
                      _infoRow('Total crédito', '\$${_formatMoney(c['total'] as int)}'),
                    ],
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _infoRow(String label, String value) {
    return Padding(padding: const EdgeInsets.only(bottom: 4),
      child: Row(children: [
        Text('$label: ', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
        Expanded(child: Text(value, style: const TextStyle(fontSize: 13))),
      ]),
    );
  }

  String _formatMoney(int amount) {
    return amount.toString().replaceAllMapped(
      RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'),
      (m) => '${m[1]}.',
    );
  }
}
