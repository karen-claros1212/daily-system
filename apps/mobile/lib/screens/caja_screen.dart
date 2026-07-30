import 'package:flutter/material.dart';
import '../theme/theme.dart';
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
        elevation: 0,
      ),
      body: _cargando ? const Center(child: CircularProgressIndicator()) :
      SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(children: [
          // Opening section
          sectionTitle('Apertura'),
          premiumCard(
            child: Column(children: [
              statRow('Opening Base', formatMoney(_caja['opening_base'] ?? 0)),
              statRow('Opening Carry', formatMoney(_caja['opening_carry'] ?? 0)),
            ]),
          ),
          const SizedBox(height: 16),

          // Ingresos
          sectionTitle('Ingresos'),
          premiumCard(
            child: Column(children: [
              statRow('Recaudo Real', formatMoney(_caja['recaudo_real'] ?? 0),
                  valueColor: const Color(0xFF2E7D32)),
              statRow('Pagos realizados', '${_caja['pagos_count'] ?? 0}'),
            ]),
          ),
          const SizedBox(height: 16),

          // Egresos
          sectionTitle('Egresos'),
          premiumCard(
            child: Column(children: [
              statRow('Reversales', formatMoney(_caja['reversales'] ?? 0),
                  valueColor: const Color(0xFFC62828)),
              statRow('Gastos', formatMoney(_caja['gastos'] ?? 0),
                  valueColor: const Color(0xFFC62828)),
              statRow('Ahorro', formatMoney(_caja['ahorro'] ?? 0),
                  valueColor: const Color(0xFFF9A825)),
              statRow('Vales', formatMoney(_caja['vales'] ?? 0)),
              statRow('Entregas', formatMoney(_caja['entregas'] ?? 0)),
              statRow('Recibidos', formatMoney(_caja['recibidos'] ?? 0),
                  valueColor: const Color(0xFF2E7D32)),
              statRow('Desembolsos', formatMoney(_caja['desembolsos'] ?? 0)),
            ]),
          ),
          const SizedBox(height: 16),

          // Total esperado
          premiumCard(
            bgColor: const Color(0xFF2E7D32),
            child: Column(children: [
              const Text('Efectivo Esperado',
                  style: TextStyle(color: Colors.white70, fontSize: 13)),
              Text(formatMoney(_caja['efectivo_esperado'] ?? 0),
                  style: const TextStyle(
                      fontSize: 28, fontWeight: FontWeight.w700, color: Colors.white)),
            ]),
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
            ]),
          ),
          const SizedBox(height: 16),

          // Diferencia
          if (_efectivoContado > 0) ...[
            premiumCard(
              bgColor: _efectivoContado == (_caja['efectivo_esperado'] ?? 0)
                  ? const Color(0xFFE8F5E9)
                  : const Color(0xFFFFEBEE),
              child: Column(children: [
                const Text('Diferencia',
                    style: TextStyle(fontSize: 13, color: Color(0xFF79747E))),
                Text(formatMoney(_efectivoContado - ((_caja['efectivo_esperado'] ?? 0) as num).toInt()),
                    style: TextStyle(
                        fontSize: 24, fontWeight: FontWeight.w700,
                        color: _efectivoContado == (_caja['efectivo_esperado'] ?? 0)
                            ? const Color(0xFF2E7D32)
                            : const Color(0xFFC62828))),
              ]),
            ),
          ],
        ]),
      ),
    );
  }
}
