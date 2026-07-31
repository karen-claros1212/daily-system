import 'package:flutter/material.dart';
import '../database/database.dart';
import '../theme/theme.dart';
import '../services/movimiento_service.dart';
import '../domain/domain_exceptions.dart';

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
        orderBy: 'ROWID DESC');
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

    try {
      final cobradorId = await _getCobradorId();
      final negocioId = await _getNegocioId();
      await MovimientoService.registrarMovimiento(
        jornadaId: widget.jornadaId,
        tipo: _tipo,
        monto: monto,
        nota: _notaController.text.trim(),
        cobradorId: cobradorId,
        negocioId: negocioId,
      );
      _montoController.clear();
      _notaController.clear();
      setState(() => _mostrarForm = false);
      _cargarMovimientos();
    } on JornadaNoEncontradaException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    } on JornadaCerradaException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error al registrar movimiento: $e')));
    }
  }

  Future<String> _getCobradorId() async {
    final jornadas = await _getJornadaRaw();
    return (jornadas['cobrador_id'] as String?) ?? '';
  }

  Future<String> _getNegocioId() async {
    final jornadas = await _getJornadaRaw();
    return (jornadas['negocio_id'] as String?) ?? '';
  }

  Future<Map<String, dynamic>> _getJornadaRaw() async {
    final db = await database;
    final jornadas = await db.query('jornada', limit: 1, where: 'id = ?', whereArgs: [widget.jornadaId]);
    return jornadas.first;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final successColor = theme.colorScheme.secondary;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Movimientos'),
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            onPressed: () => setState(() => _mostrarForm = !_mostrarForm),
            tooltip: 'Nuevo movimiento',
          ),
        ],
      ),
      body: _cargando ? const Center(child: CircularProgressIndicator()) :
      SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(children: [
          if (_mostrarForm)
            premiumCard(
              child: Column(children: [
                Text('Nuevo movimiento',
                    style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: theme.colorScheme.onSurface)),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: _tipo,
                  decoration: InputDecoration(labelText: 'Tipo', labelStyle: TextStyle(color: theme.colorScheme.onSurfaceVariant)),
                  items: _tipos.map((t) => DropdownMenuItem(value: t, child: Text(t))).toList(),
                  onChanged: (v) => setState(() => _tipo = v!),
                ),
                const SizedBox(height: 10),
                TextField(controller: _montoController, keyboardType: TextInputType.number,
                    decoration: InputDecoration(labelText: 'Monto (COP)', labelStyle: TextStyle(color: theme.colorScheme.onSurfaceVariant))),
                const SizedBox(height: 10),
                TextField(controller: _notaController,
                    decoration: InputDecoration(labelText: 'Nota', labelStyle: TextStyle(color: theme.colorScheme.onSurfaceVariant))),
                const SizedBox(height: 12),
                compactButton(
                  label: 'AGREGAR',
                  onPressed: _agregarMovimiento,
                  color: successColor,
                ),
              ]),
            ),
          const SizedBox(height: 16),
          if (_movimientos.isEmpty)
            Text('No hay movimientos', style: TextStyle(color: theme.colorScheme.onSurfaceVariant))
          else
            ..._movimientos.map((m) {
              final tipo = m['tipo'] as String;
              final color = _movimientoColor(tipo, theme);
              return Padding(padding: const EdgeInsets.only(bottom: 8),
                child: premiumCard(
                  child: Row(children: [
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: color.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Icon(_movimientoIcon(tipo), color: color, size: 20),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(tipo, style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: theme.colorScheme.onSurface)),
                          Text(m['nota'] as String? ?? '',
                              style: TextStyle(fontSize: 12, color: theme.colorScheme.onSurfaceVariant)),
                        ],
                      ),
                    ),
                    Text(formatMoney(m['monto'] as int),
                        style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: color)),
                  ]),
                ),
              );
            }),
        ]),
      ),
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

  Color _movimientoColor(String tipo, ThemeData theme) {
    switch (tipo) {
      case 'GASOLINA': case 'OFICINA': case 'VALE': case 'DESEMBOLSO': return theme.colorScheme.error;
      case 'AHORRO': case 'RECIBIDO': return theme.colorScheme.secondary;
      default: return theme.colorScheme.tertiary;
    }
  }

  @override
  void dispose() {
    _montoController.dispose();
    _notaController.dispose();
    super.dispose();
  }
}
