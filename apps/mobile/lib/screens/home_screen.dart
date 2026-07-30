import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'ruta_screen.dart';
import 'historial_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  String _cobradorNombre = '';
  String _rutaNombre = '';
  bool _sinConexion = false;

  @override
  void initState() {
    super.initState();
    _loadSession();
    _checkConnection();
  }

  Future<void> _loadSession() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _cobradorNombre = prefs.getString('cobrador_nombre') ?? '';
      _rutaNombre = prefs.getString('ruta_nombre') ?? '';
    });
  }

  Future<void> _checkConnection() async {
    // Simulate connection check - in real app would use connectivity_plus
    // For offline alpha, we're always offline
    setState(() => _sinConexion = true);
  }

  Future<void> _logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.clear();
    if (mounted) {
      setState(() {
        _cobradorNombre = '';
        _rutaNombre = '';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Daily System'),
        backgroundColor: Colors.blue[800],
        actions: [
          IconButton(
            icon: const Icon(Icons.history),
            onPressed: () => Navigator.push(context,
                MaterialPageRoute(builder: (_) => const HistorialScreen())),
            tooltip: 'Historial',
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: _logout,
            tooltip: 'Cerrar sesión',
          ),
        ],
      ),
      body: SafeArea(
        child: Column(children: [
          // Connection indicator
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            color: _sinConexion ? Colors.orange[700] : Colors.green[600],
            child: Row(children: [
              Icon(_sinConexion ? Icons.wifi_off : Icons.wifi, color: Colors.white, size: 18),
              const SizedBox(width: 8),
              Text(_sinConexion ? 'SIN CONEXIÓN - Modo offline' : 'Conectado',
                  style: const TextStyle(color: Colors.white, fontSize: 13)),
            ]),
          ),
          // Welcome
          Padding(padding: const EdgeInsets.all(24),
            child: Column(children: [
              const Icon(Icons.account_balance_wallet, size: 64, color: Colors.blue),
              const SizedBox(height: 16),
              Text('Bienvenido, $_cobradorNombre',
                  style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              Text(_rutaNombre,
                  style: TextStyle(fontSize: 16, color: Colors.grey[600])),
            ]),
          ),
          const Spacer(),
          // Action buttons
          Padding(padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Column(children: [
              _actionButton(context, Icons.route, 'Hoja Viva', Colors.green, () {
                Navigator.push(context,
                    MaterialPageRoute(builder: (_) => const RutaScreen()));
              }),
              const SizedBox(height: 16),
              _actionButton(context, Icons.payment, 'Registrar Pago', Colors.blue, () {
                Navigator.push(context,
                    MaterialPageRoute(builder: (_) => const RutaScreen()));
              }),
              const SizedBox(height: 16),
              _actionButton(context, Icons.receipt_long, 'Movimientos', Colors.orange, () {
                ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Selecciona una ruta primero')));
              }),
              const SizedBox(height: 16),
              _actionButton(context, Icons.calculate, 'Caja', Colors.purple, () {
                ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Selecciona una ruta primero')));
              }),
              const SizedBox(height: 16),
              _actionButton(context, Icons.done_all, 'TERMINAR JORNADA', Colors.red, () {
                ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Selecciona una ruta primero')));
              }),
            ]),
          ),
          const Spacer(flex: 2),
        ]),
      ),
    );
  }

  Widget _actionButton(BuildContext context, IconData icon, String label,
      Color color, VoidCallback onTap) {
    return Material(
      color: color,
      borderRadius: BorderRadius.circular(12),
      elevation: 4,
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 24),
          child: Row(children: [
            Icon(icon, color: Colors.white, size: 28),
            const SizedBox(width: 16),
            Text(label, style: const TextStyle(color: Colors.white,
                fontSize: 18, fontWeight: FontWeight.bold)),
            const Spacer(),
            const Icon(Icons.arrow_forward_ios, color: Colors.white, size: 18),
          ]),
        ),
      ),
    );
  }
}
