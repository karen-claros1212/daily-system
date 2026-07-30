import 'package:uuid/uuid.dart';
import 'package:sqflite/sqflite.dart';
import 'package:intl/intl.dart';

class SeedData {
  static const _uuid = Uuid();

  static String _uid() => _uuid.v4();

  static final _now = DateFormat('yyyy-MM-dd').format(DateTime.now());

  static Future<void> seed(Database db) async {
    final batch = db.batch();

    // --- Negocio ---
    final negocioId = _uid();
    batch.insert('negocio', {
      'id': negocioId,
      'nombre': 'Cobro Diario Demo',
      'nit': '900.123.456-1',
    });

    // --- Administrador ---
    final adminId = _uid();
    batch.insert('usuario', {
      'id': adminId,
      'negocio_id': negocioId,
      'rol': 'ADMINISTRADOR',
      'nombre': 'Ana García',
      'documento': '1234567890',
    });

    // --- Cobrador ---
    final cobradorId = _uid();
    batch.insert('usuario', {
      'id': cobradorId,
      'negocio_id': negocioId,
      'rol': 'COBRADOR',
      'nombre': 'Carlos López',
      'documento': '9876543210',
    });

    // --- Ruta ---
    final rutaId = _uid();
    batch.insert('ruta', {
      'id': rutaId,
      'negocio_id': negocioId,
      'nombre': 'Ruta Norte - Zona 1',
      'cobrador_id': cobradorId,
      'activa': 1,
    });

    // --- Clientes (5 clientes demo) ---
    final clientes = <Map<String, dynamic>>[
      {
        'id': _uid(),
        'negocio_id': negocioId,
        'primer_apellido': 'Martínez',
        'nombres': 'Juan Pedro',
        'tipo_documento': 'CC',
        'documento_normalizado': '1122334455',
        'telefono_1': '3001234567',
        'direccion': 'Calle 45 #12-34',
        'barrio': 'Centro',
        'ciudad': 'Bogotá',
        'ocupacion': 'Comerciante',
      },
      {
        'id': _uid(),
        'negocio_id': negocioId,
        'primer_apellido': 'Rodríguez',
        'nombres': 'María Elena',
        'tipo_documento': 'CC',
        'documento_normalizado': '2233445566',
        'telefono_1': '3109876543',
        'direccion': 'Cra 23 #56-78',
        'barrio': 'La Merced',
        'ciudad': 'Bogotá',
        'ocupacion': 'Ama de casa',
      },
      {
        'id': _uid(),
        'negocio_id': negocioId,
        'primer_apellido': 'Hernández',
        'nombres': 'Luis Alberto',
        'tipo_documento': 'CC',
        'documento_normalizado': '3344556677',
        'telefono_1': '3205551234',
        'direccion': 'Av. Primera #89-01',
        'barrio': 'Santa Ana',
        'ciudad': 'Bogotá',
        'ocupacion': 'Conductor',
      },
      {
        'id': _uid(),
        'negocio_id': negocioId,
        'primer_apellido': 'Gómez',
        'nombres': 'Carmen Rosa',
        'tipo_documento': 'CC',
        'documento_normalizado': '4455667788',
        'telefono_1': '3156667890',
        'direccion': 'Calle 100 #23-45',
        'barrio': 'Los Andes',
        'ciudad': 'Bogotá',
        'ocupacion': 'Vendedora',
      },
      {
        'id': _uid(),
        'negocio_id': negocioId,
        'primer_apellido': 'Díaz',
        'nombres': 'Roberto Javier',
        'tipo_documento': 'CC',
        'documento_normalizado': '5566778899',
        'telefono_1': '3187771234',
        'direccion': 'Cra 70 #12-34',
        'barrio': 'Usaquén',
        'ciudad': 'Bogotá',
        'ocupacion': 'Técnico',
      },
    ];

    for (final c in clientes) {
      batch.insert('cliente', c);
    }

    // --- Créditos (5 créditos, uno por cliente) ---
    // Cuota=5000, n=40, total=200000, monto=180000 (residuo redondeo)
    final creditos = <Map<String, dynamic>>[
      {
        'id': _uid(),
        'negocio_id': negocioId,
        'cliente_id': clientes[0]['id'],
        'ruta_id': rutaId,
        'cuota': 5000,
        'n_cuotas': 40,
        'monto': 180000,
        'total': 200000,
        'periodicidad': 'DIARIO',
        'fecha_inicio': _now,
        'estado': 'ACTIVO',
      },
      {
        'id': _uid(),
        'negocio_id': negocioId,
        'cliente_id': clientes[1]['id'],
        'ruta_id': rutaId,
        'cuota': 3000,
        'n_cuotas': 30,
        'monto': 80000,
        'total': 90000,
        'periodicidad': 'DIARIO',
        'fecha_inicio': _now,
        'estado': 'ACTIVO',
      },
      {
        'id': _uid(),
        'negocio_id': negocioId,
        'cliente_id': clientes[2]['id'],
        'ruta_id': rutaId,
        'cuota': 7000,
        'n_cuotas': 50,
        'monto': 300000,
        'total': 350000,
        'periodicidad': 'DIARIO',
        'fecha_inicio': _now,
        'estado': 'ACTIVO',
      },
      {
        'id': _uid(),
        'negocio_id': negocioId,
        'cliente_id': clientes[3]['id'],
        'ruta_id': rutaId,
        'cuota': 4000,
        'n_cuotas': 25,
        'monto': 90000,
        'total': 100000,
        'periodicidad': 'DIARIO',
        'fecha_inicio': _now,
        'estado': 'ACTIVO',
      },
      {
        'id': _uid(),
        'negocio_id': negocioId,
        'cliente_id': clientes[4]['id'],
        'ruta_id': rutaId,
        'cuota': 6000,
        'n_cuotas': 35,
        'monto': 190000,
        'total': 210000,
        'periodicidad': 'DIARIO',
        'fecha_inicio': _now,
        'estado': 'ACTIVO',
      },
    ];

    for (final cr in creditos) {
      batch.insert('credito', cr);
    }

    // --- Cuotas programadas (7 días por cada crédito) ---
    for (final credito in creditos) {
      final cuota = credito['cuota'] as int;
      final nCuotas = credito['n_cuotas'] as int;
      final fechaInicio = DateTime.now();

      for (int i = 0; i < nCuotas && i < 7; i++) {
        final fecha = fechaInicio.add(Duration(days: i));
        batch.insert('cuota_programada', {
          'id': _uid(),
          'credito_id': credito['id'],
          'numero': i + 1,
          'fecha_vencimiento': DateFormat('yyyy-MM-dd').format(fecha),
          'monto': cuota,
          'estado': i == 0 ? 'PAGADO' : 'PENDIENTE',
        });
      }
    }

    await batch.commit(noResult: true);
  }
}
