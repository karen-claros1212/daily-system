import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'database/database.dart';
import 'screens/home_screen.dart';
import 'theme/theme.dart';

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

  @override
  void initState() {
    super.initState();
    _checkSession();
  }

  Future<void> _checkSession() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _mostrarLogin = prefs.getString('cobrador_id') == null;
    });
  }

  Future<void> _handleLogin() async {
    final prefs = await SharedPreferences.getInstance();
    final db = await database;
    final usuarios = await db.query('usuario', where: 'rol = ?', whereArgs: ['COBRADOR']);
    if (usuarios.isNotEmpty) {
      final cobrador = usuarios.first;
      await prefs.setString('cobrador_id', cobrador['id'] as String);
      await prefs.setString('cobrador_nombre', cobrador['nombre'] as String);
    }
    setState(() => _mostrarLogin = false);
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Daily System',
      debugShowCheckedModeBanner: false,
      theme: premiumTheme,
      home: _mostrarLogin ? _LoginScreen(onLogin: _handleLogin) : const HomeScreen(),
    );
  }
}

class _LoginScreen extends StatefulWidget {
  final Function onLogin;
  const _LoginScreen({required this.onLogin});

  @override
  State<_LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<_LoginScreen> with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _fadeAnimation;
  late Animation<double> _scaleAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );
    _fadeAnimation = CurvedAnimation(
      parent: _controller,
      curve: Curves.easeOutCubic,
    );
    _scaleAnimation = Tween<double>(begin: 0.9, end: 1.0).animate(
      CurvedAnimation(parent: _controller, curve: Curves.elasticOut),
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
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              Color(0xFFE8F5E9),
              Color(0xFFFDFDF7),
            ],
          ),
        ),
        child: SafeArea(
          child: FadeTransition(
            opacity: _fadeAnimation,
            child: ScaleTransition(
              scale: _scaleAnimation,
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    // Logo
                    Container(
                      width: 80, height: 80,
                      decoration: BoxDecoration(
                        color: const Color(0xFF2E7D32),
                        borderRadius: BorderRadius.circular(20),
                        boxShadow: [
                          BoxShadow(
                            color: const Color(0xFF2E7D32).withOpacity(0.3),
                            blurRadius: 20,
                            offset: const Offset(0, 8),
                          ),
                        ],
                      ),
                      child: const Icon(Icons.account_balance_wallet,
                          color: Colors.white, size: 40),
                    ),
                    const SizedBox(height: 32),
                    const Text('Daily System',
                        style: TextStyle(fontSize: 28, fontWeight: FontWeight.w700,
                            color: Color(0xFF1C1B1F))),
                    const SizedBox(height: 8),
                    Text('Cobro diario offline',
                        style: TextStyle(fontSize: 16, color: const Color(0xFF79747E))),
                    const SizedBox(height: 8),
                    Text('Flutter 3.44 • Material 3',
                        style: const TextStyle(fontSize: 12, color: Color(0xFFCAC4D0))),
                    const SizedBox(height: 48),
                    // Login button
                    compactButton(
                      label: 'INICIAR SESIÓN',
                      onPressed: () async {
                        await widget.onLogin();
                      },
                      color: const Color(0xFF2E7D32),
                      icon: Icons.login,
                    ),
                    const SizedBox(height: 16),
                    Text('Demo: datos precargados',
                        style: const TextStyle(fontSize: 12, color: Color(0xFFCAC4D0))),
                    Text('5 clientes • 5 créditos • 1 ruta',
                        style: const TextStyle(fontSize: 12, color: Color(0xFFCAC4D0))),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
