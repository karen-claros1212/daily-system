import 'package:flutter/material.dart';
import 'package:sqflite/sqflite.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../database/database.dart';
import '../models/models.dart';
import '../services/jornada_service.dart';
import '../services/hoja_viva_service.dart';
import '../services/caja_service.dart';
import '../services/pago_service.dart';
import '../services/pdf_service.dart';
import 'hoja_viva_screen.dart';
import 'pago_screen.dart';
import 'movimientos_screen.dart';
import 'caja_screen.dart';
import 'jornada_cierre_screen.dart';

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

    // Get usuario
    final usuarios = await db.query('usuario', where: 'rol = ?', whereArgs: ['COBRADOR']);
    if (usuarios.isEmpty) {
      setState(() => _cargando = false);
      return;
    }
    final cobrador = Usuario.fromMap(usuarios.first);
    _cobradorId = cobrador.id;
    _cobradorNombre = cobrador.nombre;

    // Get negocio
    final negocios = await db.query('negocio', limit: 1);
    if (negocios.isNotEmpty) {
      _negocioId = (negocios.first as Map<String, dynamic>)['id'] as String;
    }

    // Get rutas
    final rutasRaw = await db.query('ruta', where: 'activa = ?', whereArgs: [1]);
    setState(() {
      _rutas = rutasRaw.map((m) => Ruta.fromMap(m)).toList();
      _cargando = false;
    });

    // Save session
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('cobrador_id', _cobradorId);
    await prefs.setString('cobrador_nombre', _cobradorNombre);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Seleccionar Ruta'),
        backgroundColor: Colors.blue[800],
      ),
      body: _cargando ? const Center(child: CircularProgressIndicator()) :
      _rutas.isEmpty ? Center(child: const Text('No hay rutas disponibles')) :
      ListView.builder(
        itemCount: _rutas.length,
        itemBuilder: (context, index) {
          final ruta = _rutas[index];
          return Card(
            margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: ListTile(
              leading: const Icon(Icons.route, color: Colors.blue),
              title: Text(ruta.nombre, style: const TextStyle(fontWeight: FontWeight.bold)),
              subtitle: const Text('Ruta activa'),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => _seleccionarRuta(ruta),
            ),
          );
        },
      ),
    );
  }

  Future<void> _seleccionarRuta(Ruta ruta) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('ruta_id', ruta.id);
    await prefs.setString('ruta_nombre', ruta.nombre);

    if (!mounted) return;

    // Check if there's an open jornada for this route
    final jornada = await JornadaService.getJornadaAbierta(ruta.id);

    if (jornada != null) {
      // Navigate to main route screen with open jornada
      Navigator.pushReplacement(context,
          MaterialPageRoute(builder: (_) => RutaActivaScreen(ruta: ruta, jornada: jornada,
              cobradorId: _cobradorId, cobradorNombre: _cobradorNombre,
              negocioId: _negocioId)));
    } else {
      // Open new jornada
      try {
        final newJornada = await JornadaService.abrirJornada(
            ruta.id, _cobradorId, _negocioId, 0);
        Navigator.pushReplacement(context,
            MaterialPageRoute(builder: (_) => RutaActivaScreen(ruta: ruta, jornada: newJornada,
                cobradorId: _cobradorId, cobradorNombre: _cobradorNombre,
                negocioId: _negocioId)));
      } catch (e) {
        if (mounted) {
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

class _RutaActivaScreenState extends State<RutaActivaScreen> {
  int _pageIndex = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.ruta.nombre),
        backgroundColor: Colors.blue[800],
        actions: [
          IconButton(
            icon: const Icon(Icons.exit_to_app),
            onPressed: () => Navigator.popUntil(context, (r) => r.isFirst),
            tooltip: 'Volver',
          ),
        ],
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _pageIndex,
        onTap: (i) => setState(() => _pageIndex = i),
        type: BottomNavigationBarType.fixed,
        backgroundColor: Colors.blue[800],
        selectedItemColor: Colors.white,
        unselectedItemColor: Colors.white70,
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.people), label: 'Hoja Viva'),
          BottomNavigationBarItem(icon: Icon(Icons.payment), label: 'Pago'),
          BottomNavigationBarItem(icon: Icon(Icons.receipt_long), label: 'Movimientos'),
          BottomNavigationBarItem(icon: Icon(Icons.calculate), label: 'Caja'),
          BottomNavigationBarItem(icon: Icon(Icons.done_all), label: 'Jornada'),
        ],
      ),
      body: [
        HojaVivaScreen(rutaId: widget.ruta.id),
        PagoScreen(jornadaId: widget.jornada.id, cobradorId: widget.cobradorId,
            negocioId: widget.negocioId),
        MovimientosScreen(jornadaId: widget.jornada.id),
        CajaScreen(jornadaId: widget.jornada.id),
        JornadaCierreScreen(jornada: widget.jornada, cobradorNombre: widget.cobradorNombre),
      ][_pageIndex],
    );
  }
}
