// ─── Cobros Shell — Route + Hoja Viva + Pago ─────────────────────
// Handles route selection and the cobros workflow.
// Uses CobrosSection enum — no magic numbers.

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../database/database.dart';
import '../models/models.dart';
import '../navigation.dart';
import '../services/jornada_service.dart';
import '../theme/theme.dart';
import '../screens/hoja_viva_screen.dart';
import '../screens/pago_screen.dart';
import '../screens/movimientos_screen.dart';
import '../screens/caja_screen.dart';
import '../screens/jornada_cierre_screen.dart';

class CobrosShell extends StatefulWidget {
  final String cobradorId;
  final String cobradorNombre;
  final String negocioId;
  final CobrosSection initialSection;
  const CobrosShell({
    super.key,
    required this.cobradorId,
    required this.cobradorNombre,
    required this.negocioId,
    this.initialSection = CobrosSection.seleccionarRuta,
  });

  @override
  State<CobrosShell> createState() => _CobrosShellState();
}

class _CobrosShellState extends State<CobrosShell> {
  CobrosSection _section = CobrosSection.seleccionarRuta;
  Ruta? _ruta;
  Jornada? _jornada;
  bool _cargando = true;
  String _cobradorId = '';
  String _negocioId = '';

  @override
  void initState() {
    super.initState();
    _section = widget.initialSection;
    _cobradorId = widget.cobradorId;
    _negocioId = widget.negocioId;
    _cargarDatos();
  }

  Future<void> _cargarDatos() async {
    final db = await database;
    final prefs = await SharedPreferences.getInstance();

    if (_section == CobrosSection.seleccionarRuta) {
      await db.query('ruta', where: 'activa = ?', whereArgs: [1]);
      setState(() => _cargando = false);
    } else {
      final rutaId = prefs.getString('ruta_id') ?? '';
      if (rutaId.isNotEmpty) {
        final rutas = await db.query('ruta', where: 'id = ?', whereArgs: [rutaId]);
        if (rutas.isNotEmpty) {
          setState(() => _ruta = Ruta.fromMap(rutas.first));
          final jornada = await JornadaService.getJornadaAbierta(rutaId);
          if (jornada != null) setState(() => _jornada = jornada);
        }
      }
      setState(() => _cargando = false);
    }
  }

  Future<void> _seleccionarRuta(Ruta ruta) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('ruta_id', ruta.id);
    await prefs.setString('ruta_nombre', ruta.nombre);

    try {
      final jornada = await JornadaService.getJornadaAbierta(ruta.id);
      if (jornada != null) {
        setState(() {
          _ruta = ruta;
          _jornada = jornada;
          _section = CobrosSection.hojaViva;
        });
      } else {
        final db = await database;
        final usuarios = await db.query('usuario', where: 'rol = ?', whereArgs: ['COBRADOR']);
        final cobrador = Usuario.fromMap(usuarios.first);
        final negocios = await db.query('negocio', limit: 1);
        final negocioId = negocios.isNotEmpty ? negocios.first['id'] as String : '';
        final newJornada = await JornadaService.abrirJornada(ruta.id, cobrador.id, negocioId, 0);
        setState(() {
          _ruta = ruta;
          _jornada = newJornada;
          _section = CobrosSection.hojaViva;
        });
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _cargando ? const Center(child: CircularProgressIndicator()) : _buildState(),
    );
  }

  Widget _buildState() {
    switch (_section) {
      case CobrosSection.seleccionarRuta:
        return _buildRouteSelection();
      case CobrosSection.cerrarJornada:
        if (_jornada != null) return JornadaCierreScreen(jornada: _jornada!, cobradorNombre: widget.cobradorNombre);
        return const Center(child: Text('No hay jornada abierta'));
      default:
        if (_ruta == null || _jornada == null) return _buildRouteSelection();
        return _buildActiveState();
    }
  }

  Widget _buildRouteSelection() {
    return FutureBuilder<List<Ruta>>(
      future: _cargarRutas(),
      builder: (context, snapshot) {
        if (snapshot.hasData && snapshot.data!.isNotEmpty) {
          final rutas = snapshot.data!;
          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(children: [
              premiumCard(
                child: Column(children: [
                  Container(
                    width: 64, height: 64,
                    decoration: BoxDecoration(
                      color: Theme.of(context).colorScheme.primary,
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: const Icon(Icons.route, color: Colors.white, size: 32),
                  ),
                  const SizedBox(height: 16),
                  const Text('Seleccionar Ruta', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                  const SizedBox(height: 4),
                  Text('Elige la ruta del día', style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.onSurfaceVariant)),
                ]),
              ),
              const SizedBox(height: 20),
              ...rutas.map((ruta) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: premiumCard(
                  onTap: () => _seleccionarRuta(ruta),
                  child: Row(children: [
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(Icons.route, color: Theme.of(context).colorScheme.primary, size: 24),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(ruta.nombre, style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: Theme.of(context).colorScheme.onSurface)),
                          Text('Ruta activa', style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.onSurfaceVariant)),
                        ],
                      ),
                    ),
                    Icon(Icons.chevron_right, color: Theme.of(context).colorScheme.onSurfaceVariant),
                  ]),
                ),
              )),
            ]),
          );
        }
        return SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(children: [
            premiumCard(
              child: Column(children: [
                Container(
                  width: 64, height: 64,
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.primary,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: const Icon(Icons.route, color: Colors.white, size: 32),
                ),
                const SizedBox(height: 16),
                const Text('Seleccionar Ruta', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                const SizedBox(height: 4),
                Text('Elige la ruta del día', style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.onSurfaceVariant)),
              ]),
            ),
            const SizedBox(height: 20),
            Text('No hay rutas configuradas', style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant)),
          ]),
        );
      },
    );
  }

  Future<List<Ruta>> _cargarRutas() async {
    final db = await database;
    final rutasRaw = await db.query('ruta', where: 'activa = ?', whereArgs: [1]);
    return rutasRaw.map((m) => Ruta.fromMap(m)).toList();
  }

  Widget _buildActiveState() {
    final theme = Theme.of(context);
    return Column(
      children: [
        // Route header
        Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          color: theme.colorScheme.primary,
          child: Row(children: [
            IconButton(
              icon: const Icon(Icons.arrow_back, color: Colors.white),
              onPressed: () => setState(() => _section = CobrosSection.seleccionarRuta),
              tooltip: 'Cambiar ruta',
            ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(_ruta!.nombre, style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600)),
                  Text('Jornada del ${_jornada!.fecha}', style: const TextStyle(color: Colors.white70, fontSize: 12)),
                ],
              ),
            ),
          ]),
        ),
        // Sub-navigation
        Container(
          margin: const EdgeInsets.all(16),
          child: Row(
            children: [
              _subNavChip(context, 'Hoja Viva', _section == CobrosSection.hojaViva, theme.colorScheme.secondary,
                  () => setState(() => _section = CobrosSection.hojaViva)),
              const SizedBox(width: 8),
              _subNavChip(context, 'Cobrar', _section == CobrosSection.pago, theme.colorScheme.primary,
                  () => setState(() => _section = CobrosSection.pago)),
              const SizedBox(width: 8),
              _subNavChip(context, 'Movimientos', _section == CobrosSection.movimientos, theme.colorScheme.tertiary,
                  () => setState(() => _section = CobrosSection.movimientos)),
              const SizedBox(width: 8),
              _subNavChip(context, 'Caja', _section == CobrosSection.caja, theme.colorScheme.onSurfaceVariant,
                  () => setState(() => _section = CobrosSection.caja)),
            ],
          ),
        ),
        Expanded(child: _buildSubContent()),
      ],
    );
  }

  Widget _subNavChip(BuildContext context, String label, bool selected, Color color, VoidCallback onTap) {
    final key = ValueKey('cobros-section-${label.toLowerCase().replaceAll(' ', '-')}');
    return Expanded(
      child: Semantics(
        button: true,
        selected: selected,
        label: label,
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            key: key,
            onTap: onTap,
            borderRadius: BorderRadius.circular(8),
            child: Container(
              constraints: const BoxConstraints(minHeight: 48),
              padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 4),
              decoration: BoxDecoration(
                color: selected ? color : color.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(label,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
                    color: selected ? Colors.white : color,
                  )),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildSubContent() {
    switch (_section) {
      case CobrosSection.hojaViva:
        return HojaVivaScreen(rutaId: _ruta!.id);
      case CobrosSection.pago:
        return PagoScreen(jornadaId: _jornada!.id, cobradorId: _cobradorId, negocioId: _negocioId);
      case CobrosSection.movimientos:
        return MovimientosScreen(jornadaId: _jornada!.id);
      case CobrosSection.caja:
        return CajaScreen(jornadaId: _jornada!.id);
      default:
        return const Center(child: Text('Selecciona una sección'));
    }
  }
}
