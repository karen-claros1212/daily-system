// ─── Más Screen — Historial + Settings ───────────────────────────

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../database/database.dart';
import '../theme/theme.dart';
import 'historial_screen.dart';

class MasScreen extends StatefulWidget {
  final String cobradorId;
  final String cobradorNombre;
  const MasScreen({super.key, required this.cobradorId, required this.cobradorNombre});

  @override
  State<MasScreen> createState() => _MasScreenState();
}

class _MasScreenState extends State<MasScreen> {
  int _jornadasCount = 0;

  @override
  void initState() {
    super.initState();
    _cargarCount();
  }

  Future<void> _cargarCount() async {
    final db = await database;
    final count = await db.rawQuery('SELECT COUNT(*) as cnt FROM jornada');
    setState(() => _jornadasCount = count.first['cnt'] as int? ?? 0);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Más'),
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(children: [
          // Profile card
          premiumCard(
            child: Row(children: [
              Container(
                width: 56, height: 56,
                decoration: BoxDecoration(
                  color: theme.colorScheme.primary,
                  borderRadius: BorderRadius.circular(16),
                ),
                child: const Icon(Icons.person, color: Colors.white, size: 28),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(widget.cobradorNombre,
                        style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: theme.colorScheme.onSurface)),
                    Text('Cobrador',
                        style: TextStyle(fontSize: 13, color: theme.colorScheme.onSurfaceVariant)),
                  ],
                ),
              ),
              Icon(Icons.chevron_right, color: theme.colorScheme.onSurfaceVariant),
            ]),
          ),
          const SizedBox(height: 20),

          // Historial
          sectionTitle('Historial'),
          premiumCard(
            onTap: () => Navigator.push(context,
                MaterialPageRoute(builder: (_) => const HistorialScreen())),
            child: Row(children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: theme.colorScheme.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(Icons.history, color: theme.colorScheme.primary, size: 22),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Historial de Jornadas',
                        style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: theme.colorScheme.onSurface)),
                    Text('$_jornadasCount jornadas registradas',
                        style: TextStyle(fontSize: 12, color: theme.colorScheme.onSurfaceVariant)),
                  ],
                ),
              ),
              Icon(Icons.chevron_right, color: theme.colorScheme.onSurfaceVariant),
            ]),
          ),
          const SizedBox(height: 12),

          // Settings
          sectionTitle('Configuración'),
          premiumCard(
            child: Row(children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: theme.colorScheme.secondary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(Icons.settings, color: theme.colorScheme.secondary, size: 22),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Text('Configuración',
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: theme.colorScheme.onSurface)),
              ),
              Icon(Icons.chevron_right, color: theme.colorScheme.onSurfaceVariant),
            ]),
          ),
          const SizedBox(height: 12),
          premiumCard(
            child: Row(children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: theme.colorScheme.tertiary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(Icons.info_outline, color: theme.colorScheme.tertiary, size: 22),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Acerca de',
                        style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: theme.colorScheme.onSurface)),
                    Text('Daily System v1.0',
                        style: TextStyle(fontSize: 12, color: theme.colorScheme.onSurfaceVariant)),
                  ],
                ),
              ),
            ]),
          ),
          const SizedBox(height: 24),

          // Logout
          compactButton(
            label: 'CERRAR SESIÓN',
            onPressed: () async {
              final prefs = await SharedPreferences.getInstance();
              await prefs.clear();
              if (context.mounted) Navigator.popUntil(context, (r) => r.isFirst);
            },
            color: theme.colorScheme.error,
            icon: Icons.logout,
          ),
        ]),
      ),
    );
  }
}
