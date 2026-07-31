import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'database/database.dart';
import 'models/models.dart';
import 'shell/main_shell.dart';
import 'theme/theme.dart';
import 'ui/components/daily_logo.dart';
import 'ui/components/daily_primary_button.dart';

// ═══ Demo flag — set to false to hide demo info in release builds ═══
const bool kDailyDemo = bool.fromEnvironment('DAILY_DEMO', defaultValue: true);

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initDatabase();
  runApp(const DailySystemApp());
}

class DailySystemApp extends StatefulWidget {
  const DailySystemApp({super.key});

  @override
  State<DailySystemApp> createState() => _DailySystemAppState();
}

class _DailySystemAppState extends State<DailySystemApp> {
  bool _mostrarLogin = true;
  String _cobradorId = '';
  String _cobradorNombre = '';
  String _negocioId = '';

  @override
  void initState() {
    super.initState();
    _checkSession();
  }

  Future<void> _checkSession() async {
    final prefs = await SharedPreferences.getInstance();
    final cobradorId = prefs.getString('cobrador_id');
    final cobradorNombre = prefs.getString('cobrador_nombre');
    final negocioId = prefs.getString('negocio_id');

    if (cobradorId != null) {
      setState(() {
        _mostrarLogin = false;
        _cobradorId = cobradorId;
        _cobradorNombre = cobradorNombre ?? '';
        _negocioId = negocioId ?? '';
      });
    }
  }

  Future<void> _handleLogin() async {
    final prefs = await SharedPreferences.getInstance();
    final db = await database;
    final usuarios = await db.query('usuario', where: 'rol = ?', whereArgs: ['COBRADOR']);
    if (usuarios.isNotEmpty) {
      final cobrador = Usuario.fromMap(usuarios.first);
      await prefs.setString('cobrador_id', cobrador.id);
      await prefs.setString('cobrador_nombre', cobrador.nombre);

      final negocios = await db.query('negocio', limit: 1);
      if (negocios.isNotEmpty) {
        await prefs.setString('negocio_id', negocios.first['id'] as String);
        _negocioId = negocios.first['id'] as String;
      }

      setState(() {
        _cobradorId = cobrador.id;
        _cobradorNombre = cobrador.nombre;
        _mostrarLogin = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Daily System',
      debugShowCheckedModeBanner: false,
      theme: premiumTheme,
      darkTheme: premiumDarkTheme,
      themeMode: ThemeMode.system,
      home: _mostrarLogin ? _LoginScreen(onLogin: _handleLogin) :
          MainShell(cobradorId: _cobradorId, cobradorNombre: _cobradorNombre, negocioId: _negocioId),
    );
  }
}

class _LoginScreen extends StatefulWidget {
  final Future<void> Function() onLogin;
  const _LoginScreen({required this.onLogin});

  @override
  State<_LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<_LoginScreen> with SingleTickerProviderStateMixin {
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
    // theme.brightness checked via theme.colorScheme.onSurface for accessibility
    
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
                  DailyLogo(size: 80),
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
