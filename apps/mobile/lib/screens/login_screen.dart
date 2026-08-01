// ─── Login Screen ────────────────────────────────────────────────
// Brand hero + INICIAR SESIÓN. Uses Theme.of(context) for a11y colors.

import 'package:flutter/material.dart';
import '../config.dart' show kDailyDemo;
import '../ui/components/daily_logo.dart';
import '../ui/components/daily_primary_button.dart';

class LoginScreen extends StatefulWidget {
  final Future<void> Function() onLogin;
  const LoginScreen({super.key, required this.onLogin});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _fadeAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 350),
      vsync: this,
    );
    _fadeAnimation = CurvedAnimation(
      parent: _controller,
      curve: Curves.easeOutCubic,
    );
    _controller.forward();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              theme.colorScheme.primary.withValues(alpha: 0.08),
              theme.colorScheme.surface,
            ],
          ),
        ),
        child: SafeArea(
          child: FadeTransition(
            opacity: _fadeAnimation,
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  // Daily logo
                  const DailyLogo(size: 80),
                  const SizedBox(height: 32),

                  // Brand name
                  Text('Daily System',
                      style: TextStyle(fontSize: 28, fontWeight: FontWeight.w700,
                          color: theme.colorScheme.onSurface)),
                  const SizedBox(height: 8),

                  // Tagline
                  Text('Tu ruta, tus cobros y tu caja, incluso sin internet.',
                      style: TextStyle(fontSize: 16, color: theme.colorScheme.onSurfaceVariant)),
                  const SizedBox(height: 48),

                  // Login button
                  DailyPrimaryButton(
                    label: 'INICIAR SESIÓN',
                    onPressed: widget.onLogin,
                    icon: Icons.login,
                  ),
                  if (kDailyDemo) ...[
                    const SizedBox(height: 16),
                    // Demo info — conditional on DAILY_DEMO constant
                    Text('Demo: datos precargados',
                        style: TextStyle(fontSize: 12, color: theme.colorScheme.outlineVariant)),
                    Text('5 clientes • 5 créditos • 1 ruta',
                        style: TextStyle(fontSize: 12, color: theme.colorScheme.outlineVariant)),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
