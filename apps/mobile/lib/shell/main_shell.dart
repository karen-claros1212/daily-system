// ─── Main Shell — IndexedStack Navigation ────────────────────────
// Material 3 NavigationBar: Inicio / Cobros / Caja / Más
// Preserves scroll, filters, search, form state per tab.

import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../screens/inicio_screen.dart';
import '../screens/cobros_shell.dart';
import '../screens/caja_main_screen.dart';
import '../screens/mas_screen.dart';

class MainShell extends StatefulWidget {
  final String cobradorId;
  final String cobradorNombre;
  final String negocioId;
  const MainShell({super.key, required this.cobradorId, required this.cobradorNombre, required this.negocioId});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _currentIndex = 0;

  List<Widget> get _screens => [
    InicioScreen(cobradorId: widget.cobradorId, cobradorNombre: widget.cobradorNombre, negocioId: widget.negocioId),
    CobrosShell(cobradorId: widget.cobradorId, cobradorNombre: widget.cobradorNombre, negocioId: widget.negocioId),
    const CajaMainScreen(),
    MasScreen(cobradorId: widget.cobradorId, cobradorNombre: widget.cobradorNombre),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (i) => setState(() => _currentIndex = i),
        indicatorColor: AppColors.primary.withOpacity(0.12),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined), selectedIcon: Icon(Icons.home), label: 'Inicio'),
          NavigationDestination(icon: Icon(Icons.payment_outlined), selectedIcon: Icon(Icons.payment), label: 'Cobros'),
          NavigationDestination(icon: Icon(Icons.account_balance_wallet_outlined), selectedIcon: Icon(Icons.account_balance_wallet), label: 'Caja'),
          NavigationDestination(icon: Icon(Icons.more_horiz), selectedIcon: Icon(Icons.more_horiz), label: 'Más'),
        ],
      ),
    );
  }
}
