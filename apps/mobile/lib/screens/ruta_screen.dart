import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../database/database.dart';
import '../models/models.dart';
import '../services/jornada_service.dart';
import '../theme/theme.dart';
import 'jornada_cierre_screen.dart';
import 'hoja_viva_screen.dart';
import 'pago_screen.dart';
import 'movimientos_screen.dart';
import 'caja_screen.dart';

class RutaScreen extends StatefulWidget {
  const RutaScreen({super.key});

  @override
  State<RutaScreen> createState() => _RutaScreenState();
}

class _RutaScreenState extends State<RutaScreen> {
  List<Ruta> _rutas = [];
  bool _cargando = true;
  String _cobradorId = '';
  String _cobradorNombre = '';
  String _negocioId = '';

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    final db = await database;

    final usuarios = await db.query('usuario', where: 'rol = ?', whereArgs: ['COBRADOR']);
    if (usuarios.isEmpty) {
      setState(() => _cargando = false);
      return;
    }
    final cobrador = Usuario.fromMap(usuarios.first);
    _cobradorId = cobrador.id;
    _cobradorNombre = cobrador.nombre;

    final negocios = await db.query('negocio', limit: 1);
    if (negocios.isNotEmpty) {
      _negocioId = (negocios.first as Map<String, dynamic>)['id'] as String;
    }

    final rutasRaw = await db.query('ruta', where: 'activa = ?', whereArgs: [1]);
    setState(() {
      _rutas = rutasRaw.map((m) => Ruta.fromMap(m)).toList();
      _cargando = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Seleccionar Ruta'),
        elevation: 0,
      ),
      body: _cargando ? Center(child: CircularProgressIndicator(color: theme.colorScheme.primary)) :
      _rutas.isEmpty ? Center(child: Text('No hay rutas disponibles', style: TextStyle(color: theme.colorScheme.onSurfaceVariant))) :
      Padding(
        padding: const EdgeInsets.all(16),
        child: Column(children: [
          Text('Elige la ruta del día',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: theme.colorScheme.onSurface)),
          const SizedBox(height: 4),
          Text('Cobrador: $_cobradorNombre',
              style: TextStyle(fontSize: 13, color: theme.colorScheme.onSurfaceVariant)),
          const SizedBox(height: 20),
          Expanded(
            child: ListView.builder(
              itemCount: _rutas.length,
              itemBuilder: (context, index) {
                final ruta = _rutas[index];
                return Padding(padding: const EdgeInsets.only(bottom: 12),
                  child: premiumCard(
                    onTap: () => _seleccionarRuta(ruta),
                    child: Row(children: [
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: theme.colorScheme.secondary.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Icon(Icons.route, color: theme.colorScheme.secondary, size: 24),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(ruta.nombre,
                                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: theme.colorScheme.onSurface)),
                            Text('Ruta activa',
                                style: TextStyle(fontSize: 12, color: theme.colorScheme.onSurfaceVariant)),
                          ],
                        ),
                      ),
                      Icon(Icons.chevron_right, color: theme.colorScheme.onSurfaceVariant),
                    ]),
                  ),
                );
              },
            ),
          ),
        ]),
      ),
    );
  }

  Future<void> _seleccionarRuta(Ruta ruta) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('ruta_id', ruta.id);
    await prefs.setString('ruta_nombre', ruta.nombre);

   if (!context.mounted) return;

    final jornada = await JornadaService.getJornadaAbierta(ruta.id);

 if (jornada != null) {
      if (mounted && context.mounted) {
        Navigator.pushReplacement(context,
            MaterialPageRoute(builder: (_) => RutaActivaScreen(
                ruta: ruta, jornada: jornada,
                cobradorId: _cobradorId, cobradorNombre: _cobradorNombre,
                negocioId: _negocioId)));
      }
    } else {
      try {
        final newJornada = await JornadaService.abrirJornada(
            ruta.id, _cobradorId, _negocioId, 0);
        if (mounted && context.mounted) {
          Navigator.pushReplacement(context,
              MaterialPageRoute(builder: (_) => RutaActivaScreen(
                  ruta: ruta, jornada: newJornada,
                  cobradorId: _cobradorId, cobradorNombre: _cobradorNombre,
                  negocioId: _negocioId)));
        }
      } catch (e) {
        if (mounted && context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('Error: $e')));
        }
      }
    }
  }
}

class RutaActivaScreen extends StatefulWidget {
  final Ruta ruta;
  final Jornada jornada;
  final String cobradorId;
  final String cobradorNombre;
  final String negocioId;

  const RutaActivaScreen({super.key, required this.ruta, required this.jornada,
    required this.cobradorId, required this.cobradorNombre, required this.negocioId});

  @override
  State<RutaActivaScreen> createState() => _RutaActivaScreenState();
}

class _RutaActivaScreenState extends State<RutaActivaScreen>
    with SingleTickerProviderStateMixin {
  int _pageIndex = 0;
  late AnimationController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = AnimationController(
      duration: const Duration(milliseconds: 300),
      vsync: this,
    );
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  void _onTabChanged(int index) {
    _tabController.forward(from: 0);
    setState(() => _pageIndex = index);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.ruta.nombre),
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.arrow_back),
            onPressed: () => Navigator.popUntil(context, (r) => r.isFirst),
            tooltip: 'Volver',
          ),
        ],
      ),
      body: AnimatedSwitcher(
        duration: const Duration(milliseconds: 200),
        switchInCurve: Curves.easeInOut,
        switchOutCurve: Curves.easeInOut,
        child: [
          HojaVivaScreen(key: ValueKey('hoja'), rutaId: widget.ruta.id),
          PagoScreen(key: ValueKey('pago'), jornadaId: widget.jornada.id,
              cobradorId: widget.cobradorId, negocioId: widget.negocioId),
          MovimientosScreen(key: ValueKey('mov'), jornadaId: widget.jornada.id),
          CajaScreen(key: ValueKey('caja'), jornadaId: widget.jornada.id),
          JornadaCierreScreen(key: ValueKey('jornada'), jornada: widget.jornada,
              cobradorNombre: widget.cobradorNombre),
        ][_pageIndex],
      ),
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          border: Border(top: BorderSide(color: theme.colorScheme.surfaceContainerHighest, width: 0.5)),
        ),
        child: BottomNavigationBar(
          currentIndex: _pageIndex,
          onTap: _onTabChanged,
          type: BottomNavigationBarType.fixed,
          backgroundColor: theme.colorScheme.surface,
          selectedItemColor: theme.colorScheme.secondary,
          unselectedItemColor: theme.colorScheme.onSurfaceVariant,
          items: const [
            BottomNavigationBarItem(icon: Icon(Icons.people), label: 'Hoja Viva'),
            BottomNavigationBarItem(icon: Icon(Icons.payment), label: 'Pago'),
            BottomNavigationBarItem(icon: Icon(Icons.receipt_long), label: 'Movimientos'),
            BottomNavigationBarItem(icon: Icon(Icons.calculate), label: 'Caja'),
            BottomNavigationBarItem(icon: Icon(Icons.done_all), label: 'Jornada'),
          ],
        ),
      ),
    );
  }
}
