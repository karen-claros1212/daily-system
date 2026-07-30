import 'package:flutter/material.dart';
import 'package:sqflite/sqflite.dart';
import '../database/database.dart';
import '../services/pago_service.dart';

class PagoScreen extends StatefulWidget {
  final String jornadaId;
  final String cobradorId;
  final String negocioId;
  const PagoScreen({super.key, required this.jornadaId, required this.cobradorId, required this.negocioId});

  @override
  State<PagoScreen> createState() => _PagoScreenState();
}

class _PagoScreenState extends State<PagoScreen> {
  List<Map<String, dynamic>> _creditos = [];
  bool _cargando = true;
  final _montoController = TextEditingController();
  final _notaController = TextEditingController();
  Map<String, dynamic>? _creditoSeleccionado;

  @override
  void initState() {
    super.initState();
    _cargarCreditos();
  }

  Future<void> _cargarCreditos() async {
    final db = await database;
    final results = await db.rawQuery('''
      SELECT c.id as credito_id, c.cuota, c.total, c.n_cuotas,
             cl.primer_apellido, cl.nombres, cl.telefono_1
      FROM credito c
      JOIN cliente cl ON c.cliente_id = cl.id
      WHERE c.estado = 'ACTIVO'
    ''');
    setState(() {
      _creditos = results;
      _cargando = false;
    });
  }

  Future<void> _registrarPago() async {
    if (_creditoSeleccionado == null) return;
    final montoStr = _montoController.text.trim();
    if (montoStr.isEmpty) {
      _showError('Ingresa el monto');
      return;
    }
    final monto = int.tryParse(montoStr);
    if (monto == null || monto <= 0) {
      _showError('Monto inválido');
      return;
    }

    try {
      await PagoService.registrarPago(
        _creditoSeleccionado!['credito_id'] as String,
        widget.jornadaId,
        widget.cobradorId,
        widget.negocioId,
        monto,
        _notaController.text.trim(),
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Pago registrado correctamente')));
        _montoController.clear();
        _notaController.clear();
        setState(() => _creditoSeleccionado = null);
      }
    } catch (e) {
      if (mounted) _showError('Error: $e');
    }
  }

  void _showError(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Registrar Pago'),
        backgroundColor: Colors.blue[800],
      ),
      body: _cargando ? const Center(child: CircularProgressIndicator()) :
      Column(children: [
        // Creditor selector
        Padding(padding: const EdgeInsets.all(16),
          child: Column(children: [
            const Text('Seleccionar deudor:', style: TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            DropdownButton<Map<String, dynamic>>(
              isExpanded: true,
              hint: const Text('Seleccionar deudor...'),
              value: _creditoSeleccionado,
              items: _creditos.map((c) {
                final nombre = '${c['primer_apellido']} ${c['nombres']}';
                return DropdownMenuItem(value: c, child: Text(nombre));
              }).toList(),
              onChanged: (v) => setState(() => _creditoSeleccionado = v),
            ),
          ]),
        ),
        // Amount input
        Padding(padding: const EdgeInsets.symmetric(horizontal: 16),
          child: TextField(
            controller: _montoController,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
              labelText: 'Monto (COP)',
              prefixText: '\$ ',
              border: OutlineInputBorder(),
            ),
          ),
        ),
        const SizedBox(height: 8),
        Padding(padding: const EdgeInsets.symmetric(horizontal: 16),
          child: TextField(
            controller: _notaController,
            decoration: const InputDecoration(
              labelText: 'Nota (opcional)',
              border: OutlineInputBorder(),
            ),
          ),
        ),
        const SizedBox(height: 16),
        Padding(padding: const EdgeInsets.symmetric(horizontal: 32),
          child: SizedBox(
            width: double.infinity,
            height: 50,
            child: ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: Colors.green[700]),
              onPressed: _registrarPago,
              child: const Text('REGISTRAR PAGO',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white)),
            ),
          ),
        ),
        const SizedBox(height: 16),
        const Divider(),
        // Payment history
        const Padding(padding: EdgeInsets.all(16),
          child: Text('Pagos de hoy:', style: TextStyle(fontWeight: FontWeight.bold))),
        Expanded(
          child: ListView.builder(
            itemCount: _creditos.length,
            itemBuilder: (context, index) {
              final c = _creditos[index];
              return ListTile(
                leading: const Icon(Icons.person, color: Colors.blue),
                title: Text('${c['primer_apellido']} ${c['nombres']}'),
                subtitle: Text('Cuota: \$${_formatMoney(c['cuota'] as int)}'),
                trailing: Text('Total: \$${_formatMoney(c['total'] as int)}'),
                onTap: () => setState(() => _creditoSeleccionado = c),
              );
            },
          ),
        ),
      ]),
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
    _montoController.dispose();
    _notaController.dispose();
    super.dispose();
  }
}
