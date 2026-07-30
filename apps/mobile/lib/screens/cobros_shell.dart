// ─── Cobros Shell — Route + Hoja Viva + Pago ─────────────────────
// Handles route selection and the cobros workflow.

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../database/database.dart';
import '../models/models.dart';
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
  final int initialTab; // -1 = route selection, -2 = jornada cierre, 0+ = sub-tab
  const CobrosShell({super.key, required this.cobradorId, required this.cobradorNombre, required this.negocioId, this.initialTab = 0});

  @override
  State<CobrosShell> createState() => _CobrosShellState();
}

class _CobrosShellState extends State<CobrosShell> {
  int _state = 0; // 0 = route select, 1 = hoja viva, 2 = pago, 3 = movimientos, 4 = caja, 5 = jornada cierre
  Ruta? _ruta;
  Jornada? _jornada;
  bool _cargando = true;
  String _cobradorId = '';
  String _negocioId = '';

  @override
  void initState() {
    super.initState();
    _state = widget.initialTab;
    _cargarDatos();
  }

  Future<void> _cargarDatos() async {
    final db = await database;
    final prefs = await SharedPreferences.getInstance();

    final cobradorId = prefs.getString('cobrador_id') ?? widget.cobradorId;
    final negocioId = prefs.getString('negocio_id') ?? widget.negocioId;

    if (_state == 0) {
      // Show route selection
      final rutasRaw = await db.query('ruta', where: 'activa = ?', whereArgs: [1]);
      setState(() {
        _cargando = false;
      });
    } else {
      // Load active route/jornada
      final rutaId = prefs.getString('ruta_id') ?? '';
      if (rutaId.isNotEmpty) {
        final rutas = await db.query('ruta', where: 'id = ?', whereArgs: [rutaId]);
        if (rutas.isNotEmpty) {
          setState(() {
            _ruta = Ruta.fromMap(rutas.first);
            _cobradorId = cobradorId;
            _negocioId = negocioId;
          });

          final jornada = await JornadaService.getJornadaAbierta(rutaId);
          if (jornada != null) {
            setState(() => _jornada = jornada);
          }
        }
      }
      setState(() => _cargando = false);
    }
  }

  void _seleccionarRuta(Ruta ruta) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('ruta_id', ruta.id);
    await prefs.setString('ruta_nombre', ruta.nombre);

    try {
      final jornada = await JornadaService.getJornadaAbierta(ruta.id);
      if (jornada != null) {
        setState(() {
          _ruta = ruta;
          _jornada = jornada;
          _state = 1; // Go to hoja viva
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
          _state = 1;
        });
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _cargando ? const Center(child: CircularProgressIndicator()) :
      _buildState(),
    );
  }

  Widget _buildState() {
    switch (_state) {
      case 0: // Route selection
        return _buildRouteSelection();
      case 5: // Jornada cierre
        if (_jornada != null) {
          return JornadaCierreScreen(jornada: _jornada!, cobradorNombre: widget.cobradorNombre);
        }
        return const Center(child: Text('No hay jornada abierta'));
      default:
        if (_ruta == null || _jornada == null) {
          return _buildRouteSelection();
        }
        return _buildActiveState();
    }
  }

  Widget _buildRouteSelection() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(children: [
        premiumCard(
          child: Column(children: [
            Container(
              width: 64, height: 64,
              decoration: BoxDecoration(
                color: AppColors.primary,
                borderRadius: BorderRadius.circular(16),
              ),
              child: const Icon(Icons.route, color: Colors.white, size: 32),
            ),
            const SizedBox(height: 16),
            const Text('Seleccionar Ruta',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
            const SizedBox(height: 4),
            Text('Elige la ruta del día',
                style: const TextStyle(fontSize: 13, color: AppColors.outlineVariant)),
          ]),
        ),
        const SizedBox(height: 20),
        // TODO: Load routes from DB
        const Text('No hay rutas configuradas',
            style: TextStyle(color: AppColors.outlineVariant)),
      ]),
    );
  }

  Widget _buildActiveState() {
    return Column(
      children: [
        // Route header
        Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          color: AppColors.primary,
          child: Row(children: [
            IconButton(
              icon: const Icon(Icons.arrow_back, color: Colors.white),
              onPressed: () => setState(() => _state = 0),
              tooltip: 'Cambiar ruta',
            ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(_ruta!.nombre,
                      style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600)),
                  Text('Jornada del ${_jornada!.fecha}',
                      style: const TextStyle(color: Colors.white70, fontSize: 12)),
                ],
              ),
            ),
            IconButton(
              icon: const Icon(Icons.more_vert, color: Colors.white),
              onPressed: () {},
            ),
          ]),
        ),
        // Sub-navigation
        Container(
          margin: const EdgeInsets.all(16),
          child: Row(
            children: [
              _subNavChip('Hoja Viva', _state == 1, AppColors.accent, () => setState(() => _state = 1)),
              const SizedBox(width: 8),
              _subNavChip('Cobrar', _state == 2, AppColors.primary, () => setState(() => _state = 2)),
              const SizedBox(width: 8),
              _subNavChip('Movimientos', _state == 3, AppColors.tertiaryDark, () => setState(() => _state = 3)),
              const SizedBox(width: 8),
              _subNavChip('Caja', _state == 4, AppColors.secondary, () => setState(() => _state = 4)),
            ],
          ),
        ),
        // Content
        Expanded(
          child: _buildSubContent(),
        ),
      ],
    );
  }

  Widget _subNavChip(String label, bool selected, Color color, VoidCallback onTap) {
    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 8),
          decoration: BoxDecoration(
            color: selected ? color : color.withOpacity(0.1),
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
    );
  }

  Widget _buildSubContent() {
    switch (_state) {
      case 1:
        return HojaVivaScreen(rutaId: _ruta!.id);
      case 2:
        return PagoScreen(jornadaId: _jornada!.id, cobradorId: _cobradorId, negocioId: _negocioId);
      case 3:
        return MovimientosScreen(jornadaId: _jornada!.id);
      case 4:
        return CajaScreen(jornadaId: _jornada!.id);
      default:
        return const Center(child: Text('Selecciona una sección'));
    }
  }
}
