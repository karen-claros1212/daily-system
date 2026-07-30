import 'package:path/path.dart';
import 'package:sqflite/sqflite.dart';
import '../database/tables.dart';
import '../database/seed.dart';
import '../database/migration_v2.dart';

Database? _database;

Future<Database> get database async {
  if (_database != null) return _database!;
  _database = await initDatabase();
  return _database!;
}

Future<Database> initDatabase() async {
  final dbPath = await getDatabasesPath();
  final path = join(dbPath, 'daily_system.db');

  return await openDatabase(
    path,
    version: 2,
    onCreate: _onCreate,
    onUpgrade: _onUpgrade,
    onOpen: (_) {},
  );
}

Future<void> _onCreate(Database db, int version) async {
  for (final stmt in Tables.all) {
    await db.execute(stmt);
  }
  await SeedData.seed(db);
  await MigrationV2.migrate(db);
  await assertSchemaV2(db);
}

Future<void> _onUpgrade(Database db, int oldVersion, int newVersion) async {
  if (oldVersion < 2) {
    await MigrationV2.migrate(db);
  }
  await assertSchemaV2(db);
}

Future<void> assertSchemaV2(DatabaseExecutor db) async {
  final rows = await db.rawQuery('''
    SELECT type, name
    FROM sqlite_master
    WHERE name IN (
      'sync_queue',
      'jornada_snapshot',
      'trg_pago_require_open_jornada',
      'trg_movimiento_require_open_jornada'
    )
    ORDER BY type, name
  ''');

  final names = rows
      .map((row) => row['name'])
      .whereType<String>()
      .toSet();

  const required = {
    'sync_queue',
    'jornada_snapshot',
    'trg_pago_require_open_jornada',
    'trg_movimiento_require_open_jornada',
  };

  final missing = required.difference(names);

  if (missing.isNotEmpty) {
    throw StateError(
      'Migración V2 incompleta. Objetos ausentes: '
      '${missing.join(', ')}. Encontrados: ${names.join(', ')}',
    );
  }
}

Future<Database> clearDatabase() async {
  final current = _database;
  _database = null;

  if (current != null && current.isOpen) {
    await current.close();
  }

  final dbPath = await getDatabasesPath();
  final path = join(dbPath, 'daily_system.db');

  await deleteDatabase(path);

  final reopened = await initDatabase();

  if (!reopened.isOpen) {
    throw StateError('La base no quedó abierta después del reset');
  }

  return reopened;
}
