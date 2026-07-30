import 'package:flutter/material.dart';
import '../services/caja_service.dart';

class CajaScreen extends StatefulWidget {
  final String jornadaId;
  const CajaScreen({super.key, required this.jornadaId});

  @override
  State<CajaScreen> createState() => _CajaScreenState();
}

class _CajaScreenState extends State<CajaScreen> {
  Map<String, dynamic> _caja = {};
  bool _cargando = true;
  int _efectivoContado = 0;

  @override
  void initState() {
    super.initState();
    _cargarCaja();
  }

  Future<void> _cargarCaja() async {
    try {
      final caja = await CajaService.calcularCaja(widget.jornadaId);
      setState(() {
        _caja = caja;
        _cargando = false;
      });
    } catch (e) {
      setState(() => _cargando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Caja'),
        backgroundColor: Colors.blue[800],
      ),
      body: _cargando ? const Center(child: CircularProgressIndicator()) :
      SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          // Opening
          _sectionTitle('APERTURA'),
          _cajaRow('Opening Base', '\$${_formatMoney(_caja['opening_base'] ?? 0)}'),
          _cajaRow('Opening Carry', '\$${_formatMoney(_caja['opening_carry'] ?? 0)}'),
          const SizedBox(height: 16),

          // Ingresos
          _sectionTitle('INGRESOS', color: Colors.green),
          _cajaRow('Recaudo Real', '\$${_formatMoney(_caja['recaudo_real'] ?? 0)}',
              color: Colors.green),
          _cajaRow('Pagos realizados', '${_caja['pagos_count'] ?? 0}'),
          const SizedBox(height: 16),

          // Egresos
          _sectionTitle('EGRESOS', color: Colors.red),
          _cajaRow('Reversales', '\$${_formatMoney(_caja['reversales'] ?? 0)}',
              color: Colors.red),
          _cajaRow('Gastos', '\$${_formatMoney(_caja['gastos'] ?? 0)}', color: Colors.red),
          _cajaRow('Ahorro', '\$${_formatMoney(_caja['ahorro'] ?? 0)}', color: Colors.orange),
          _cajaRow('Vales', '\$${_formatMoney(_caja['vales'] ?? 0)}'),
          _cajaRow('Entregas', '\$${_formatMoney(_caja['entregas'] ?? 0)}'),
          _cajaRow('Recibidos', '\$${_formatMoney(_caja['recibidos'] ?? 0)}',
              color: Colors.green),
          _cajaRow('Desembolsos', '\$${_formatMoney(_caja['desembolsos'] ?? 0)}'),
          const SizedBox(height: 16),

          // Totals
          _sectionTitle('TOTALES', color: Colors.blue),
          Container(width: double.infinity, padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(color: Colors.blue[50], borderRadius: BorderRadius.circular(8)),
            child: Column(children: [
              Text('Efectivo Esperado', style: TextStyle(fontSize: 14, color: Colors.grey[700])),
              Text('\$${_formatMoney(_caja['efectivo_esperado'] ?? 0)}',
                  style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Colors.blue)),
            ]),
          ),
          const SizedBox(height: 24),

          // Efectivo contado
          const Text('Efectivo contado en caja:', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          TextField(
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
              labelText: 'Contado',
              prefixText: '\$ ',
              border: OutlineInputBorder(),
            ),
            onChanged: (v) {
              final val = int.tryParse(v);
              if (val != null) setState(() => _efectivoContado = val);
            },
          ),
          const SizedBox(height: 16),

          // Diferencia
          if (_efectivoContado > 0)
            Container(width: double.infinity, padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: _efectivoContado == (_caja['efectivo_esperado'] ?? 0) ? Colors.green[50] : Colors.red[50],
                borderRadius: BorderRadius.circular(8)),
              child: Column(children: [
                Text('Diferencia', style: const TextStyle(fontSize: 14)),
                Text('\$${_formatMoney(_efectivoContado - ((_caja['efectivo_esperado'] as num?) ?? 0).toInt())}',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold,
                        color: _efectivoContado == (_caja['efectivo_esperado'] ?? 0) ? Colors.green : Colors.red)),
              ]),
            ),
        ]),
      ),
    );
  }

  Widget _sectionTitle(String title, {Color? color}) {
    return Padding(padding: const EdgeInsets.only(bottom: 8),
      child: Text(title, style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold,
          color: color ?? Colors.black)),
    );
  }

  Widget _cajaRow(String label, String value, {Color? color}) {
    return Padding(padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(children: [
        Expanded(child: Text(label)),
        Text(value, style: TextStyle(fontWeight: FontWeight.bold, color: color)),
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
