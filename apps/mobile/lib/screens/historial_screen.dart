import 'package:flutter/material.dart';
import '../services/jornada_service.dart';
import '../models/models.dart';

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
      case 'OPEN': return Colors.orange;
      case 'CLOSED_LOCAL_PENDING_SYNC': return Colors.blue;
      case 'CLOSED_SYNCED': return Colors.green;
      default: return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Historial de Jornadas'),
        backgroundColor: Colors.blue[800],
      ),
      body: _cargando ? const Center(child: CircularProgressIndicator()) :
      _jornadas.isEmpty ? Center(child: const Text('No hay jornadas en el historial')) :
      ListView.builder(
        itemCount: _jornadas.length,
        itemBuilder: (context, index) {
          final j = _jornadas[index];
          return Card(
            margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            child: ListTile(
              leading: CircleAvatar(
                backgroundColor: _estadoColor(j.estado),
                child: Icon(j.isClosed ? Icons.check : Icons.open_in_new,
                    color: Colors.white, size: 20),
              ),
              title: Text('Fecha: ${j.fecha}'),
              subtitle: Text('Estado: ${j.estado}'),
              trailing: Text('Contado: \$${_formatMoney(j.contado)}',
                  style: const TextStyle(fontWeight: FontWeight.bold)),
            ),
          );
        },
      ),
    );
  }

  String _formatMoney(int amount) {
    return amount.toString().replaceAllMapped(
      RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'),
      (m) => '${m[1]}.',
    );
  }
}
