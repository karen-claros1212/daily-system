import 'package:path/path.dart';
import 'package:sqflite/sqflite.dart';
import '../database/tables.dart';
import '../database/seed.dart';

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
    version: 1,
    onCreate: _onCreate,
    onOpen: (_) {},
  );
}

Future<void> _onCreate(Database db, int version) async {
  for (final stmt in Tables.all) {
    await db.execute(stmt);
  }
  await SeedData.seed(db);
}

Future<void> closeDatabase() async {
  final db = _database;
  if (db != null) {
    await db.close();
    _database = null;
  }
}

Future<void> clearDatabase() async {
  final dbPath = await getDatabasesPath();
  final path = join(dbPath, 'daily_system.db');
  await deleteDatabase(path);
  _database = null;
  await initDatabase();
}
