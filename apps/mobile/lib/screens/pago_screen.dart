import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';
import '../database/database.dart';
import '../services/pago_service.dart';
import '../theme/theme.dart';

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
  bool _registrando = false;
  String? _idempotenciaKey;

  String _iniciarIdempotencia() {
    _idempotenciaKey ??= const Uuid().v4();
    return _idempotenciaKey!;
  }

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
    if (_creditoSeleccionado == null || _registrando) return;
    final montoStr = _montoController.text.trim();
    if (montoStr.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Ingresa el monto')));
      return;
    }
    final monto = int.tryParse(montoStr);
    if (monto == null || monto <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Monto inválido')));
      return;
    }

    setState(() => _registrando = true);
    try {
      final creditoId = _creditoSeleccionado!['credito_id'] as String;
      final clave = _iniciarIdempotencia();
      await PagoService.registrarPago(
        creditoId,
        widget.jornadaId,
        widget.cobradorId,
        widget.negocioId,
        monto,
        _notaController.text.trim(),
        clave,
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Pago registrado')));
        _montoController.clear();
        _notaController.clear();
        setState(() {
          _creditoSeleccionado = null;
          _registrando = false;
          _idempotenciaKey = null;
        });
        _cargarCreditos();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Error: $e')));
        setState(() => _registrando = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Registrar Pago'),
        elevation: 0,
      ),
      body: _cargando ? const Center(child: CircularProgressIndicator()) :
      SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(children: [
          // Creditor selector
          premiumCard(
            child: Column(children: [
              const Text('Seleccionar deudor',
                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
              const SizedBox(height: 10),
              DropdownButton<Map<String, dynamic>>(
                isExpanded: true,
                hint: const Text('Seleccionar deudor...'),
                value: _creditoSeleccionado,
                underline: const SizedBox(),
                items: _creditos.map((c) {
                  final nombre = '${c['primer_apellido']} ${c['nombres']}';
                  return DropdownMenuItem(value: c, child: Text(nombre));
                }).toList(),
                onChanged: (v) {
                  setState(() {
                    _creditoSeleccionado = v;
                    _idempotenciaKey = null;
                  });
                },
              ),
            ]),
          ),
          const SizedBox(height: 16),
          // Amount
          premiumCard(
            child: Column(children: [
              const Text('Monto del abono',
                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
              const SizedBox(height: 10),
              TextField(
                controller: _montoController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Monto (COP)',
                  prefixIcon: Icon(Icons.attach_money, size: 20),
                ),
                style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700),
                onChanged: (v) {
                  // Regenerar clave de idempotencia cuando cambia el monto
                  if (_registrando && v.isNotEmpty) {
                    setState(() => _idempotenciaKey = null);
                  }
                },
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _notaController,
                decoration: const InputDecoration(
                  labelText: 'Nota (opcional)',
                  prefixIcon: Icon(Icons.note, size: 20),
                ),
              ),
              const SizedBox(height: 16),
              compactButton(
                label: 'REGISTRAR PAGO',
                onPressed: _registrarPago,
                color: const Color(0xFF2E7D32),
                isLoading: _registrando,
              ),
            ]),
          ),
          const SizedBox(height: 20),
          // Creditor list
          const Text('Deudores activos',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
          const SizedBox(height: 10),
          ..._creditos.map((c) {
            final nombre = '${c['primer_apellido']} ${c['nombres']}';
            return Padding(padding: const EdgeInsets.only(bottom: 8),
              child: premiumCard(
                onTap: () => setState(() => _creditoSeleccionado = c),
                child: Row(children: [
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: const Color(0xFF2E7D32).withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Icon(Icons.person, color: Color(0xFF2E7D32), size: 20),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(nombre,
                            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                        Text('Cuota: \$${formatMoney(c['cuota'] as int)}',
                            style: const TextStyle(fontSize: 12, color: Color(0xFF79747E))),
                      ],
                    ),
                  ),
                  Text('\$${formatMoney(c['total'] as int)}',
                      style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                ]),
              ),
            );
          }),
        ]),
      ),
    );
  }

  @override
  void dispose() {
    _montoController.dispose();
    _notaController.dispose();
    super.dispose();
  }
}
