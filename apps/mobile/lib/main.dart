import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'database/database.dart';
import 'screens/home_screen.dart';
import 'screens/ruta_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize database with seed data
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
    final cobradorId = prefs.getString('cobrador_id');
    setState(() {
      _mostrarLogin = cobradorId == null;
    });
  }

  Future<void> _login() async {
    final prefs = await SharedPreferences.getInstance();
    // For demo: use the seeded cobrador
    final db = await database;
    final usuarios = await db.query('usuario', where: 'rol = ?', whereArgs: ['COBRADOR']);
    if (usuarios.isNotEmpty) {
      final cobrador = usuarios.first;
      await prefs.setString('cobrador_id', cobrador['id'] as String);
      await prefs.setString('cobrador_nombre', cobrador['nombre'] as String);
    }
    setState(() => _mostrarLogin = false);
  }

  Future<void> _logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.clear();
    setState(() => _mostrarLogin = true);
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Daily System',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        primarySwatch: Colors.blue,
        useMaterial3: true,
        appBarTheme: const AppBarTheme(
          centerTitle: true,
          elevation: 0,
        ),
      ),
      home: _mostrarLogin ? _LoginScreen(onLogin: _login, onLogout: _logout) : const HomeScreen(),
    );
  }
}

class _LoginScreen extends StatelessWidget {
  final VoidCallback onLogin;
  final VoidCallback onLogout;
  const _LoginScreen({required this.onLogin, required this.onLogout});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Daily System'),
        backgroundColor: Colors.blue[800],
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: () async {
            await closeDatabase();
            await initDatabase();
            ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Datos reiniciados')));
          }),
        ],
      ),
      body: SafeArea(
        child: Center(
          child: Padding(padding: const EdgeInsets.all(32),
            child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
              const Icon(Icons.account_balance_wallet, size: 80, color: Colors.blue),
              const SizedBox(height: 24),
              const Text('Daily System',
                  style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              const Text('Cobro diario offline',
                  style: TextStyle(fontSize: 16, color: Colors.grey)),
              const SizedBox(height: 48),
              SizedBox(width: double.infinity, height: 55,
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(backgroundColor: Colors.blue[700]),
                  onPressed: onLogin,
                  child: const Text('INICIAR SESIÓN',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white)),
                ),
              ),
              const SizedBox(height: 16),
              const Text('Demo: datos precargados',
                  style: TextStyle(fontSize: 12, color: Colors.grey)),
              const SizedBox(height: 8),
              const Text('5 clientes • 5 créditos • 1 ruta',
                  style: TextStyle(fontSize: 12, color: Colors.grey)),
            ]),
          ),
        ),
      ),
    );
  }
}
