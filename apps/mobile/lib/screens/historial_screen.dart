import 'package:flutter/material.dart';
import '../services/jornada_service.dart';
import '../models/models.dart';
import '../theme/theme.dart';

class HistorialScreen extends StatefulWidget {
  const HistorialScreen({super.key});

  @override
  State<HistorialScreen> createState() => _HistorialScreenState();
}

class _HistorialScreenState extends State<HistorialScreen> {
  List<Jornada> _jornadas = [];
  bool _cargando = true;

  @override
  void initState() {
    super.initState();
    _cargarHistorial();
  }

  Future<void> _cargarHistorial() async {
    try {
      final jornadas = await JornadaService.getJornadasHistorial('');
      setState(() {
        _jornadas = jornadas;
        _cargando = false;
      });
    } catch (e) {
      setState(() => _cargando = false);
    }
  }

  Color _estadoColor(String estado, ThemeData theme) {
    switch (estado) {
      case 'CLOSED_SYNCED': return theme.colorScheme.secondary;
      case 'CLOSED_LOCAL_PENDING_SYNC': return theme.colorScheme.primary;
      case 'OPEN': return theme.colorScheme.tertiary;
      default: return theme.colorScheme.onSurfaceVariant;
    }
  }

  String _estadoLabel(String estado) {
    switch (estado) {
      case 'CLOSED_SYNCED': return 'Sincronizada ✓';
      case 'CLOSED_LOCAL_PENDING_SYNC': return 'Pendiente sync';
      case 'OPEN': return 'Abierta';
      default: return estado;
    }
  }

  IconData _estadoIcon(String estado) {
    switch (estado) {
      case 'CLOSED_SYNCED': return Icons.cloud_done;
      case 'CLOSED_LOCAL_PENDING_SYNC': return Icons.cloud_queue;
      case 'OPEN': return Icons.open_in_new;
      default: return Icons.event_note;
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Historial de Jornadas'),
        elevation: 0,
      ),
      body: _cargando ? Center(child: CircularProgressIndicator(color: theme.colorScheme.primary)) :
      _jornadas.isEmpty
          ? Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.history, size: 64, color: theme.colorScheme.onSurfaceVariant.withValues(alpha: 0.5)),
                  const SizedBox(height: 16),
                  Text('No hay jornadas en el historial',
                      style: TextStyle(color: theme.colorScheme.onSurfaceVariant)),
                ],
              ),
            )
          : ListView.separated(
              padding: const EdgeInsets.all(12),
              itemCount: _jornadas.length,
              separatorBuilder: (_, _) => const SizedBox(height: 8),
              itemBuilder: (context, index) {
                final j = _jornadas[index];
                final color = _estadoColor(j.estado, theme);
                return premiumCard(
                  child: Row(children: [
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: color.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(_estadoIcon(j.estado), color: color, size: 24),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(j.fecha,
                              style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: theme.colorScheme.onSurface)),
                          const SizedBox(height: 2),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                            decoration: BoxDecoration(
                              color: color.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(_estadoLabel(j.estado),
                                style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: color)),
                          ),
                        ],
                      ),
                    ),
                    Text(formatMoney(j.contado),
                        style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: theme.colorScheme.secondary)),
                  ]),
                );
              },
            ),
    );
  }
}
