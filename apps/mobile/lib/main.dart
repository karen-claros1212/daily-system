import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'database/database.dart';
import 'models/models.dart';
import 'screens/login_screen.dart';
import 'shell/main_shell.dart';
import 'theme/theme.dart';

// ═══ Demo flag — set to false to hide demo info in release builds ═══
// Const kDailyDemo now lives in config.dart (shared with login_screen.dart).

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
      home: _mostrarLogin ? LoginScreen(onLogin: _handleLogin) :
          MainShell(cobradorId: _cobradorId, cobradorNombre: _cobradorNombre, negocioId: _negocioId),
    );
  }
}
