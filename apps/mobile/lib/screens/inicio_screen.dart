// ─── Inicio Screen — Real SQLite Data ────────────────────────────
// Loads open jornada, recaudo, clientes visitados, pendientes.

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../database/database.dart';
import '../models/models.dart';
import '../theme/theme.dart';
import 'cobros_shell.dart';
import 'caja_main_screen.dart';

class InicioScreen extends StatefulWidget {
  final String cobradorId;
  final String cobradorNombre;
  final String negocioId;
  const InicioScreen({super.key, required this.cobradorId, required this.cobradorNombre, required this.negocioId});

  @override
  State<InicioScreen> createState() => _InicioScreenState();
}

class _InicioScreenState extends State<InicioScreen> {
  bool _cargando = true;
  bool _jornadaAbierta = false;
  String _rutaNombre = '';
  String _rutaId = '';
  int _recaudoHoy = 0;
  int _clientesPendientes = 0;
  int _clientesVisitados = 0;
  int _aperturaBase = 0;

  @override
  void initState() {
    super.initState();
    _cargarDatos();
  }

  Future<void> _cargarDatos() async {
    final db = await database;
    final prefs = await SharedPreferences.getInstance();

    // Ruta actual
    final rutaId = prefs.getString('ruta_id') ?? '';
    if (rutaId.isNotEmpty) {
      final rutas = await db.query('ruta', where: 'id = ? AND activa = ?', whereArgs: [rutaId, 1]);
      if (rutas.isNotEmpty) {
        setState(() => _rutaNombre = rutas.first['nombre'] as String);
      }
    }

    // Jornada abierta
    final jornada = await db.rawQuery('''
      SELECT j.*, n.nombre as ruta_nombre
      FROM jornada j
      LEFT JOIN ruta n ON j.ruta_id = n.id
      WHERE j.estado = 'OPEN'
      ORDER BY j.fecha DESC
      LIMIT 1
    ''');

    if (jornada.isNotEmpty) {
      final j = jornada.first;
      setState(() {
        _jornadaAbierta = true;
        _jornadaAbierta = true;
        _aperturaBase = j['opening_base'] as int? ?? 0;
        _rutaId = j['ruta_id'] as String? ?? '';
      });

      // Recaudo real del día
      final recaudo = await db.rawQuery('''
        SELECT COALESCE(SUM(monto), 0) as total
        FROM pago
        WHERE jornada_id = ? AND tipo = 'PAYMENT'
      ''', [j['id'] as String]);
      _recaudoHoy = recaudo.first['total'] as int? ?? 0;

      // Clientes con créditos activos
      final pendientes = await db.rawQuery('''
        SELECT COUNT(DISTINCT c.cliente_id) as cnt
        FROM credito c
        WHERE c.ruta_id = ? AND c.estado = 'ACTIVO'
      ''', [_rutaId]);
      _clientesPendientes = pendientes.first['cnt'] as int? ?? 0;

      // Clientes visitados (pagos registrados hoy)
      final visitados = await db.rawQuery('''
        SELECT COUNT(DISTINCT p.credito_id) as cnt
        FROM pago p
        JOIN credito c ON p.credito_id = c.id
        WHERE p.jornada_id = ? AND p.tipo = 'PAYMENT'
      ''', [j['id'] as String]);
      _clientesVisitados = visitados.first['cnt'] as int? ?? 0;
    }

    setState(() => _cargando = false);
  }

  void _actualizar() {
    if (mounted) {
      _cargarDatos();
    }
  }

  void _navegarA(String destino) {
    // Navigate to the appropriate tab (Cobros, Caja, etc.)
    // This will be handled by the parent shell
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Navegando a: $destino')),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_cargando) {
      return Scaffold(
        body: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [AppColors.primary.withOpacity(0.05), AppColors.surface],
            ),
          ),
          child: const Center(child: CircularProgressIndicator(color: AppColors.primary)),
        ),
      );
    }

    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [AppColors.primary.withOpacity(0.05), AppColors.surface],
          ),
        ),
        child: SafeArea(
          child: CustomScrollView(
            slivers: [
              // Status bar
              SliverToBoxAdapter(
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  color: _jornadaAbierta ? AppColors.accent : AppColors.secondary,
                  child: Row(children: [
                    Icon(_jornadaAbierta ? Icons.check_circle : Icons.wifi_off,
                        color: Colors.white, size: 18),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(_jornadaAbierta ? 'JORNADA ACTIVA' : 'MODO OFFLINE',
                          style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w600)),
                    ),
                    if (_rutaNombre.isNotEmpty)
                      Text(_rutaNombre,
                          style: const TextStyle(color: Colors.white70, fontSize: 12)),
                  ]),
                ),
              ),
              // Content
              SliverPadding(
                padding: const EdgeInsets.all(16),
                sliver: SliverToBoxAdapter(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    // Welcome card
                    premiumCard(
                      child: Row(children: [
                        Container(
                          width: 48, height: 48,
                          decoration: BoxDecoration(
                            color: AppColors.primary,
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: const Icon(Icons.person, color: Colors.white, size: 24),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(widget.cobradorNombre,
                                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                              Text(_rutaNombre.isNotEmpty ? _rutaNombre : 'Sin ruta',
                                  style: const TextStyle(fontSize: 13, color: AppColors.outlineVariant)),
                            ],
                          ),
                        ),
                        _buildLogoutButton(),
                      ]),
                    ),
                    const SizedBox(height: 20),

                    if (_jornadaAbierta) ...[
                      // Real stats
                      const Text('Resumen del día',
                          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(
                            child: _statCard(Icons.payment, 'Recaudado', formatMoney(_recaudoHoy),
                                color: AppColors.accent),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: _statCard(Icons.people, 'Pendientes', '$_clientesPendientes',
                                color: AppColors.tertiary),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Row(
                        children: [
                          Expanded(
                            child: _statCard(Icons.check_circle, 'Visitados', '$_clientesVisitados',
                                color: AppColors.primary),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: _statCard(Icons.account_balance_wallet, 'Apertura', formatMoney(_aperturaBase),
                                color: AppColors.secondary),
                          ),
                        ],
                      ),
                      const SizedBox(height: 20),

                      // Actions
                      const Text('Acciones',
                          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                      const SizedBox(height: 12),
                      _actionTile(context, Icons.people, 'Hoja Viva',
                          'Ver cartera y semáforos', AppColors.accent,
                          () => _navegarACobros(0)),
                      _actionTile(context, Icons.payment, 'Cobrar',
                          'Seleccionar cliente y abono', AppColors.primary,
                          () => _navegarACobros(1)),
                      _actionTile(context, Icons.receipt_long, 'Movimientos',
                          'Gastos, ahorro, vales', AppColors.tertiaryDark,
                          () => _navegarACaja()),
                      _actionTile(context, Icons.calculate, 'Caja',
                          'Efectivo esperado vs contado', AppColors.secondary,
                          () => _navegarACaja()),
                      const SizedBox(height: 12),
                      // TERMINAR JORNADA — with onTap
                      premiumCard(
                        bgColor: AppColors.danger,
                        onTap: () => _navegarAJornadaCierre(),
                        child: Row(children: [
                          Container(
                            padding: const EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              color: Colors.white.withOpacity(0.2),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: const Icon(Icons.done_all, color: Colors.white, size: 22),
                          ),
                          const SizedBox(width: 14),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text('TERMINAR JORNADA',
                                    style: TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.w600)),
                                Text('Contado: \$${formatMoney(_recaudoHoy)}',
                                    style: TextStyle(fontSize: 12, color: Colors.white70)),
                              ],
                            ),
                          ),
                          const Icon(Icons.arrow_forward_ios, color: Colors.white54, size: 18),
                        ]),
                      ),
                    ] else ...[
                      // No jornada — select route
                      const Text('Bienvenido',
                          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                      const SizedBox(height: 8),
                      Text('Selecciona una ruta para comenzar tu jornada de cobro.',
                          style: const TextStyle(fontSize: 14, color: AppColors.outlineVariant)),
                      const SizedBox(height: 20),
                      compactButton(
                        label: 'SELECCIONAR RUTA',
                        onPressed: () => _navegarACobros(-1),
                        color: AppColors.primary,
                        icon: Icons.route,
                      ),
                    ],
                    const SizedBox(height: 24),
                  ]),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _statCard(IconData icon, String label, String value, {required Color color}) {
    return premiumCard(
      padding: const EdgeInsets.all(12),
      child: Column(children: [
        Icon(icon, size: 24, color: color),
        const SizedBox(height: 4),
        Text(label, style: const TextStyle(fontSize: 11, color: AppColors.outlineVariant)),
        Text(value, style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: color)),
      ]),
    );
  }

  Widget _actionTile(BuildContext context, IconData icon, String title,
      String subtitle, Color color, VoidCallback onTap) {
    return Padding(padding: const EdgeInsets.only(bottom: 8),
      child: premiumCard(
        onTap: onTap,
        child: Row(children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: color.withOpacity(0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: color, size: 22),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                Text(subtitle, style: const TextStyle(fontSize: 12, color: AppColors.outlineVariant)),
              ],
            ),
          ),
          const Icon(Icons.chevron_right, color: AppColors.outline, size: 20),
        ]),
      ),
    );
  }

  Widget _buildLogoutButton() {
    return IconButton(
      icon: const Icon(Icons.logout, size: 20, color: AppColors.outlineVariant),
      onPressed: () async {
        final prefs = await SharedPreferences.getInstance();
        await prefs.clear();
        if (mounted) Navigator.popUntil(context, (r) => r.isFirst);
      },
      tooltip: 'Cerrar sesión',
    );
  }

  void _navegarACobros(int tabIndex) {
    // Signal to parent shell to switch to Cobros tab with optional sub-tab
    // This uses a callback pattern — the shell will handle navigation
    final navigator = Navigator.of(context);
    navigator.push(
      MaterialPageRoute(
        builder: (_) => CobrosShell(
          cobradorId: widget.cobradorId,
          cobradorNombre: widget.cobradorNombre,
          negocioId: widget.negocioId,
          initialTab: tabIndex,
        ),
      ),
    ).then((_) => _actualizar());
  }

  void _navegarACaja() {
    final navigator = Navigator.of(context);
    navigator.push(
      MaterialPageRoute(
        builder: (_) => const CajaMainScreen(),
      ),
    ).then((_) => _actualizar());
  }

  void _navegarAJornadaCierre() {
    // Navigate to jornada cierre via Cobros shell
    final navigator = Navigator.of(context);
    navigator.push(
      MaterialPageRoute(
        builder: (_) => CobrosShell(
          cobradorId: widget.cobradorId,
          cobradorNombre: widget.cobradorNombre,
          negocioId: widget.negocioId,
          initialTab: -2, // Special tab for jornada cierre
        ),
      ),
    ).then((_) => _actualizar());
  }
}
