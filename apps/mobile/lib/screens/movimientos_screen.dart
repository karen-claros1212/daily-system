import 'package:flutter/material.dart';
import 'package:sqflite/sqflite.dart';
import '../database/database.dart';

class MovimientosScreen extends StatefulWidget {
  final String jornadaId;
  const MovimientosScreen({super.key, required this.jornadaId});

  @override
  State<MovimientosScreen> createState() => _MovimientosScreenState();
}

class _MovimientosScreenState extends State<MovimientosScreen> {
  List<Map<String, dynamic>> _movimientos = [];
  bool _cargando = true;
  bool _mostrarForm = false;
  String _tipo = 'GASOLINA';
  final _montoController = TextEditingController();
  final _notaController = TextEditingController();

  final _tipos = ['GASOLINA', 'OFICINA', 'AHORRO', 'VALE', 'ENTREGA', 'RECIBIDO', 'DESEMBOLSO', 'AJUSTE', 'OTRO'];

  @override
  void initState() {
    super.initState();
    _cargarMovimientos();
  }

  Future<void> _cargarMovimientos() async {
    final db = await database;
    final results = await db.query('movimiento',
        where: 'jornada_id = ?',
        whereArgs: [widget.jornadaId],
        orderBy: 'creado_el DESC');
    setState(() {
      _movimientos = results;
      _cargando = false;
    });
  }

  Future<void> _agregarMovimiento() async {
    final montoStr = _montoController.text.trim();
    if (montoStr.isEmpty) return;
    final monto = int.tryParse(montoStr);
    if (monto == null || monto <= 0) return;

    final db = await database;
    await db.insert('movimiento', {
      'id': _uid(),
      'negocio_id': '',
      'jornada_id': widget.jornadaId,
      'tipo': _tipo,
      'naturaleza': _tipo == 'GASOLINA' || _tipo == 'OFICINA' ? 'GASTO' :
                   _tipo == 'AHORRO' ? 'CUSTODIA' :
                   _tipo == 'VALE' ? 'CUENTA_POR_COBRAR' : null,
      'monto': monto,
      'nota': _notaController.text.trim(),
      'creado_el': DateTime.now().toIso8601String(),
    });

    _montoController.clear();
    _notaController.clear();
    setState(() {
      _mostrarForm = false;
      _movimientos.insert(0, {
        'tipo': _tipo,
        'monto': monto,
        'nota': _notaController.text,
        'creado_el': DateTime.now().toIso8601String(),
      });
    });
  }

  String _uid() {
    // Simple UUID v4 generation
    final hex = () => DateTime.now().microsecondsSinceEpoch.toRadixString(16).padLeft(16, '0').substring(0, 16);
    return '${hex()}-${DateTime.now().millisecondsSinceEpoch}';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Movimientos'),
        backgroundColor: Colors.blue[800],
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            onPressed: () => setState(() => _mostrarForm = !_mostrarForm),
            tooltip: 'Nuevo movimiento',
          ),
        ],
      ),
      body: _cargando ? const Center(child: CircularProgressIndicator()) :
      Column(children: [
        // Add movement form
        if (_mostrarForm)
          Padding(padding: const EdgeInsets.all(16),
            child: Card(
              child: Padding(padding: const EdgeInsets.all(16),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Text('Nuevo movimiento', style: TextStyle(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    value: _tipo,
                    decoration: const InputDecoration(labelText: 'Tipo'),
                    items: _tipos.map((t) => DropdownMenuItem(value: t, child: Text(t))).toList(),
                    onChanged: (v) => setState(() => _tipo = v!),
                  ),
                  const SizedBox(height: 8),
                  TextField(controller: _montoController, keyboardType: TextInputType.number,
                      decoration: const InputDecoration(labelText: 'Monto (COP)')),
                  const SizedBox(height: 8),
                  TextField(controller: _notaController,
                      decoration: const InputDecoration(labelText: 'Nota')),
                  const SizedBox(height: 12),
                  SizedBox(width: double.infinity, height: 45,
                    child: ElevatedButton(
                      style: ElevatedButton.styleFrom(backgroundColor: Colors.blue[700]),
                      onPressed: _agregarMovimiento,
                      child: const Text('AGREGAR', style: TextStyle(color: Colors.white)),
                    ),
                  ),
                ]),
              ),
            ),
          ),
        // Movements list
        Expanded(
          child: _movimientos.isEmpty ? Center(child: const Text('No hay movimientos')) :
          ListView.builder(
            itemCount: _movimientos.length,
            itemBuilder: (context, index) {
              final m = _movimientos[index];
              return ListTile(
                leading: Icon(_movimientoIcon(m['tipo'] as String),
                    color: _movimientoColor(m['tipo'] as String)),
                title: Text(m['tipo'] as String),
                subtitle: Text(m['nota'] as String? ?? ''),
                trailing: Text('\$${_formatMoney(m['monto'] as int)}',
                    style: const TextStyle(fontWeight: FontWeight.bold)),
              );
            },
          ),
        ),
      ]),
    );
  }

  IconData _movimientoIcon(String tipo) {
    switch (tipo) {
      case 'GASOLINA': return Icons.local_gas_station;
      case 'OFICINA': return Icons.business;
      case 'AHORRO': return Icons.savings;
      case 'VALE': return Icons.receipt;
      case 'ENTREGA': return Icons.send;
      case 'RECIBIDO': return Icons.arrow_downward;
      case 'DESEMBOLSO': return Icons.money;
      case 'AJUSTE': return Icons.adjust;
      default: return Icons.note;
    }
  }

  Color _movimientoColor(String tipo) {
    switch (tipo) {
      case 'GASOLINA': case 'OFICINA': case 'VALE': case 'DESEMBOLSO': return Colors.red;
      case 'AHORRO': case 'RECIBIDO': return Colors.green;
      default: return Colors.orange;
    }
  }

  String _formatMoney(int amount) {
    return amount.toString().replaceAllMapped(
      RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'),
      (m) => '${m[1]}.',
    );
  }

  @override
  void dispose() {
    _montoController.dispose();
    _notaController.dispose();
    super.dispose();
  }
}
