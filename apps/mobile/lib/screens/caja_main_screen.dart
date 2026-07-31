// ─── Caja Main Screen ────────────────────────────────────────────
// Displays caja summary for the active jornada.
// Difference = efectivo_contado - efectivo_esperado (not recaudo - esperado).

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
    final jornadas = await db.query('jornada',
        where: 'estado = ?', whereArgs: ['OPEN'],
        orderBy: 'fecha DESC', limit: 1);

    if (jornadas.isEmpty) {
      setState(() => _cargando = false);
      return;
    }

    final j = jornadas.first;
    final jornadaId = j['id'] as String;

    setState(() {
      _jornadaAbierta = true;
      _esperado = j['esperado'] as int? ?? 0;
      _contado = j['contado'] as int? ?? 0;
    });

    final recaudo = await db.rawQuery('''
      SELECT COALESCE(SUM(monto), 0) as total
      FROM pago WHERE jornada_id = ? AND tipo = 'PAYMENT'
    ''', [jornadaId]);
    _recaudoReal = recaudo.first['total'] as int? ?? 0;

    final rev = await db.rawQuery('''
      SELECT COALESCE(SUM(monto), 0) as total
      FROM pago WHERE jornada_id = ? AND tipo = 'REVERSAL'
    ''', [jornadaId]);
    _reversales = rev.first['total'] as int? ?? 0;

    final gastos = await db.rawQuery('''
      SELECT COALESCE(SUM(monto), 0) as total
      FROM movimiento WHERE jornada_id = ? AND naturaleza = 'GASTO'
    ''', [jornadaId]);
    _gastos = gastos.first['total'] as int? ?? 0;

    final ahorro = await db.rawQuery('''
      SELECT COALESCE(SUM(monto), 0) as total
      FROM movimiento WHERE jornada_id = ? AND tipo = 'AHORRO'
    ''', [jornadaId]);
    _ahorro = ahorro.first['total'] as int? ?? 0;

    setState(() => _cargando = false);
  }

  int get diferencia => _contado - _esperado;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Caja'),
        elevation: 0,
      ),
      body: _cargando ? const Center(child: CircularProgressIndicator()) :
      _jornadaAbierta ? SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(children: [
          Row(
            children: [
              Expanded(
                child: _cajaCard(theme, 'Recaudo Real', formatMoney(_recaudoReal),
                    color: theme.colorScheme.secondary, icon: Icons.payment),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _cajaCard(theme, 'Esperado', formatMoney(_esperado),
                    color: theme.colorScheme.primary, icon: Icons.account_balance_wallet),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _cajaCard(theme, 'Reversales', formatMoney(_reversales),
                    color: theme.colorScheme.error, icon: Icons.reply),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _cajaCard(theme, 'Gastos', formatMoney(_gastos),
                    color: theme.colorScheme.error, icon: Icons.money_off),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _cajaCard(theme, 'Ahorro', formatMoney(_ahorro),
              color: theme.colorScheme.tertiary, icon: Icons.savings, wide: true),
          const SizedBox(height: 16),
          premiumCard(
            bgColor: diferencia >= 0 ? theme.colorScheme.secondaryContainer : theme.colorScheme.errorContainer.withValues(alpha: 0.3),
            child: Column(children: [
              Text('Diferencia',
                  style: TextStyle(fontSize: 13, color: theme.colorScheme.onSurfaceVariant)),
              Text(formatMoney(diferencia),
                  style: TextStyle(
                    fontSize: 28, fontWeight: FontWeight.w700,
                    color: diferencia >= 0 ? theme.colorScheme.secondary : theme.colorScheme.error,
                  )),
              const SizedBox(height: 4),
              Text('Contado: \$${formatMoney(_contado)} · Esperado: \$${formatMoney(_esperado)}',
                  style: TextStyle(fontSize: 11, color: theme.colorScheme.onSurfaceVariant)),
            ]),
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
                  if (val != null && val != _contado) {
                    setState(() => _contado = val);
                  }
                },
              ),
            ]),
          ),
        ]),
      ) : Center(child: Text('No hay jornada abierta', style: TextStyle(color: theme.colorScheme.onSurfaceVariant))),
    );
  }

  Widget _cajaCard(ThemeData theme, String label, String value, {required Color color, required IconData icon, bool wide = false}) {
    return premiumCard(
      padding: const EdgeInsets.all(12),
      child: Column(children: [
        Icon(icon, size: 24, color: color),
        const SizedBox(height: 4),
        Text(label, style: TextStyle(fontSize: 11, color: theme.colorScheme.onSurfaceVariant)),
        Text(value, style: TextStyle(fontSize: wide ? 20 : 18, fontWeight: FontWeight.w700, color: color)),
      ]),
    );
  }
}
