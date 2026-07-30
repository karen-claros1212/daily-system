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

  Color _estadoColor(String estado) {
    switch (estado) {
      case 'CLOSED_SYNCED': return const Color(0xFF2E7D32);
      case 'CLOSED_LOCAL_PENDING_SYNC': return const Color(0xFF1565C0);
      case 'OPEN': return const Color(0xFFF57F17);
      default: return const Color(0xFF79747E);
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
    return Scaffold(
      appBar: AppBar(
        title: const Text('Historial de Jornadas'),
        elevation: 0,
      ),
      body: _cargando ? const Center(child: CircularProgressIndicator()) :
      _jornadas.isEmpty
          ? Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.history, size: 64, color: const Color(0xFF79747E).withOpacity(0.5)),
                  const SizedBox(height: 16),
                  const Text('No hay jornadas en el historial',
                      style: TextStyle(color: Color(0xFF79747E))),
                ],
              ),
            )
          : ListView.separated(
              padding: const EdgeInsets.all(12),
              itemCount: _jornadas.length,
              separatorBuilder: (_, __) => const SizedBox(height: 8),
              itemBuilder: (context, index) {
                final j = _jornadas[index];
                final color = _estadoColor(j.estado);
                return premiumCard(
                  child: Row(children: [
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: color.withOpacity(0.1),
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
                              style: const TextStyle(
                                  fontSize: 15, fontWeight: FontWeight.w600)),
                          const SizedBox(height: 2),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                            decoration: BoxDecoration(
                              color: color.withOpacity(0.1),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(_estadoLabel(j.estado),
                                style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: color)),
                          ),
                        ],
                      ),
                    ),
                    Text(formatMoney(j.contado),
                        style: const TextStyle(
                            fontSize: 15, fontWeight: FontWeight.w700, color: Color(0xFF2E7D32))),
                  ]),
                );
              },
            ),
    );
  }
}
