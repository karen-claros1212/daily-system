import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../theme/theme.dart';
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
  final bool _sinConexion = true;
  final bool _jornadaAbierta = false;

  @override
  void initState() {
    super.initState();
    _loadSession();
  }

  Future<void> _loadSession() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _cobradorNombre = prefs.getString('cobrador_nombre') ?? '';
      _rutaNombre = prefs.getString('ruta_nombre') ?? '';
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              Color(0xFFF5F5F0),
              Color(0xFFFDFDF7),
            ],
          ),
        ),
        child: SafeArea(
          child: Column(children: [
            // Status bar
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              color: _jornadaAbierta ? const Color(0xFF2E7D32) : const Color(0xFF455A64),
              child: Row(children: [
                Icon(_sinConexion ? Icons.wifi_off : Icons.wifi,
                    color: Colors.white, size: 16),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(_jornadaAbierta
                      ? 'JORNADA ACTIVA'
                      : 'MODO OFFLINE',
                      style: const TextStyle(
                          color: Colors.white,
                          fontSize: 13,
                          fontWeight: FontWeight.w600)),
                ),
                if (_rutaNombre.isNotEmpty)
                  Text(_rutaNombre,
                      style: const TextStyle(
                          color: Colors.white70, fontSize: 12)),
                const SizedBox(width: 12),
                IconButton(
                  icon: const Icon(Icons.history, size: 20, color: Colors.white70),
                  onPressed: () => Navigator.push(context,
                      MaterialPageRoute(builder: (_) => const HistorialScreen())),
                  tooltip: 'Historial',
                ),
              ]),
            ),
            // Content
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(16),
                child: Column(children: [
                  // Welcome card
                  premiumCard(
                    child: Column(children: [
                      Row(children: [
                        Container(
                          width: 48, height: 48,
                          decoration: BoxDecoration(
                            color: const Color(0xFF2E7D32),
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: const Icon(Icons.person, color: Colors.white, size: 24),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(_cobradorNombre.isEmpty ? 'Cobrador' : _cobradorNombre,
                                  style: const TextStyle(
                                      fontSize: 18, fontWeight: FontWeight.w600)),
                              Text(_rutaNombre.isNotEmpty ? _rutaNombre : 'Sin ruta seleccionada',
                                  style: const TextStyle(fontSize: 13, color: Color(0xFF79747E))),
                            ],
                          ),
                        ),
                        IconButton(
                          icon: const Icon(Icons.logout, size: 20, color: Color(0xFF79747E)),
                          onPressed: () async {
                            final prefs = await SharedPreferences.getInstance();
                            await prefs.clear();
                            if (context.mounted) Navigator.popUntil(context, (r) => r.isFirst);
                          },
                          tooltip: 'Cerrar sesión',
                        ),
                      ]),
                    ]),
                  ),
                  const SizedBox(height: 20),
                  // Quick actions
                  if (_rutaNombre.isEmpty) ...[
                    const Text('Selecciona una ruta para comenzar',
                        style: TextStyle(fontSize: 14, color: Color(0xFF79747E))),
                    const SizedBox(height: 20),
                    compactButton(
                      label: 'SELECCIONAR RUTA',
                      onPressed: () => Navigator.push(context,
                          MaterialPageRoute(builder: (_) => const RutaScreen())),
                      color: const Color(0xFF2E7D32),
                      icon: Icons.route,
                    ),
                  ] else ...[
                    // Stats row
                    Row(
                      children: [
                        Expanded(
                          child: premiumCard(
                            padding: const EdgeInsets.all(12),
                            child: Column(children: [
                              const Icon(Icons.people, size: 24, color: Color(0xFF2E7D32)),
                              const SizedBox(height: 6),
                              Text('Clientes',
                                  style: const TextStyle(fontSize: 12, color: Color(0xFF79747E))),
                              const Text('5',
                                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
                            ]),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: premiumCard(
                            padding: const EdgeInsets.all(12),
                            child: Column(children: [
                              const Icon(Icons.account_balance_wallet, size: 24, color: Color(0xFFF9A825)),
                              const SizedBox(height: 6),
                              Text('Créditos',
                                  style: const TextStyle(fontSize: 12, color: Color(0xFF79747E))),
                              const Text('5',
                                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
                            ]),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    // Actions grid
                    const Text('Acciones',
                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 10),
                    _actionTile(context, Icons.people, 'Hoja Viva',
                        'Ver cartera y semáforos', const Color(0xFF2E7D32),
                        () => Navigator.push(context,
                            MaterialPageRoute(builder: (_) => RutaScreen()))),
                    _actionTile(context, Icons.payment, 'Registrar Pago',
                        'Abono a crédito', const Color(0xFF1565C0),
                        () => Navigator.push(context,
                            MaterialPageRoute(builder: (_) => RutaScreen()))),
                    _actionTile(context, Icons.receipt_long, 'Movimientos',
                        'Gastos, ahorro, vales', const Color(0xFFE65100),
                        () => Navigator.push(context,
                            MaterialPageRoute(builder: (_) => RutaScreen()))),
                    _actionTile(context, Icons.calculate, 'Caja',
                        'Efectivo esperado vs contado', const Color(0xFF6A1B9A),
                        () => Navigator.push(context,
                            MaterialPageRoute(builder: (_) => RutaScreen()))),
                    const SizedBox(height: 10),
                    premiumCard(
                      bgColor: const Color(0xFF2E7D32),
                      child: Row(children: [
                        Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: 0.2),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: const Icon(Icons.done_all, color: Colors.white, size: 24),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text('TERMINAR JORNADA',
                                  style: TextStyle(
                                      color: Colors.white,
                                      fontSize: 16,
                                      fontWeight: FontWeight.w600)),
                              Text('Cerrar jornada y generar PDF',
                                  style: TextStyle(fontSize: 12, color: Colors.white70)),
                            ],
                          ),
                        ),
                        const Icon(Icons.arrow_forward_ios,
                            color: Colors.white54, size: 18),
                      ]),
                    ),
                  ],
                  const SizedBox(height: 20),
                ]),
              ),
            ),
          ]),
        ),
      ),
    );
  }

  Widget _actionTile(BuildContext context, IconData icon, String title,
      String subtitle, Color color, VoidCallback onTap) {
    return premiumCard(
      onTap: onTap,
      child: Row(children: [
        Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(icon, color: color, size: 22),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title,
                  style: const TextStyle(
                      fontSize: 15, fontWeight: FontWeight.w600)),
              Text(subtitle,
                  style: const TextStyle(fontSize: 12, color: Color(0xFF79747E))),
            ],
          ),
        ),
        const Icon(Icons.chevron_right, color: Color(0xFFCAC4D0), size: 20),
      ]),
    );
  }
}
