// ─── Caja Main Screen ────────────────────────────────────────────
// Displays caja summary for the active jornada.

import 'package:flutter/material.dart';
import '../database/database.dart';
import '../theme/theme.dart';

class CajaMainScreen extends StatefulWidget {
  const CajaMainScreen({super.key});

  @override
  State<CajaMainScreen> createState() => _CajaMainScreenState();
}

class _CajaMainScreenState extends State<CajaMainScreen> {
  bool _cargando = true;
  bool _jornadaAbierta = false;
  int _recaudoReal = 0;
  int _reversales = 0;
  int _gastos = 0;
  int _ahorro = 0;
  int _esperado = 0;
  int _contado = 0;

  @override
  void initState() {
    super.initState();
    _cargarCaja();
  }

  Future<void> _cargarCaja() async {
    final db = await database;

    // Find active jornada
    final jornadas = await db.query('jornada',
        where: 'estado = ?', whereArgs: ['OPEN'],
        orderBy: 'fecha DESC', limit: 1);

    if (jornadas.isEmpty) {
      setState(() {
        _cargando = false;
      });
      return;
    }

    final j = jornadas.first;
    final jornadaId = j['id'] as String;

    setState(() => _jornadaAbierta = true);

    // Recaudo real
    final recaudo = await db.rawQuery('''
      SELECT COALESCE(SUM(monto), 0) as total
      FROM pago WHERE jornada_id = ? AND tipo = 'PAYMENT'
    ''', [jornadaId]);
    _recaudoReal = recaudo.first['total'] as int? ?? 0;

    // Reversales
    final rev = await db.rawQuery('''
      SELECT COALESCE(SUM(monto), 0) as total
      FROM pago WHERE jornada_id = ? AND tipo = 'REVERSAL'
    ''', [jornadaId]);
    _reversales = rev.first['total'] as int? ?? 0;

    // Movimientos gastos
    final gastos = await db.rawQuery('''
      SELECT COALESCE(SUM(monto), 0) as total
      FROM movimiento WHERE jornada_id = ? AND naturaleza = 'GASTO'
    ''', [jornadaId]);
    _gastos = gastos.first['total'] as int? ?? 0;

    // Ahorro
    final ahorro = await db.rawQuery('''
      SELECT COALESCE(SUM(monto), 0) as total
      FROM movimiento WHERE jornada_id = ? AND tipo = 'AHORRO'
    ''', [jornadaId]);
    _ahorro = ahorro.first['total'] as int? ?? 0;

    final esperado = j['esperado'] as int? ?? 0;
    final contado = j['contado'] as int? ?? 0;
    setState(() {
      _esperado = esperado;
      _contado = contado;
      _cargando = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Caja'),
        elevation: 0,
      ),
      body: _cargando ? const Center(child: CircularProgressIndicator()) :
      _jornadaAbierta ? SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(children: [
          // Summary cards
          Row(
            children: [
              Expanded(
                child: _cajaCard('Recaudo Real', formatMoney(_recaudoReal),
                    color: AppColors.accent, icon: Icons.payment),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _cajaCard('Esperado', formatMoney(_esperado),
                    color: AppColors.primary, icon: Icons.account_balance_wallet),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _cajaCard('Reversales', formatMoney(_reversales),
                    color: AppColors.danger, icon: Icons.reply),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _cajaCard('Gastos', formatMoney(_gastos),
                    color: AppColors.danger, icon: Icons.money_off),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _cajaCard('Ahorro', formatMoney(_ahorro),
              color: AppColors.tertiary, icon: Icons.savings, wide: true),
          const SizedBox(height: 16),
          // Difference card
          premiumCard(
            bgColor: _esperado > 0 ? (_recaudoReal >= _esperado ? AppColors.accentContainer : const Color(0xFFFFEBEE)) : AppColors.surfaceContainer,
            child: Column(children: [
              const Text('Diferencia',
                  style: TextStyle(fontSize: 13, color: AppColors.outlineVariant)),
              Text(formatMoney(_recaudoReal - _esperado),
                  style: TextStyle(
                    fontSize: 28, fontWeight: FontWeight.w700,
                    color: _recaudoReal >= _esperado ? AppColors.accent : AppColors.danger,
                  )),
            ]),
          ),
        ]),
      ) : const Center(child: Text('No hay jornada abierta')),
    );
  }

  Widget _cajaCard(String label, String value, {required Color color, required IconData icon, bool wide = false}) {
    return premiumCard(
      padding: const EdgeInsets.all(12),
      child: Column(children: [
        Icon(icon, size: 24, color: color),
        const SizedBox(height: 4),
        Text(label, style: const TextStyle(fontSize: 11, color: AppColors.outlineVariant)),
        Text(value, style: TextStyle(fontSize: wide ? 20 : 18, fontWeight: FontWeight.w700, color: color)),
      ]),
    );
  }
}
