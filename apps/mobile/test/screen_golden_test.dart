// ─── Screen Golden Tests — real productive screens ──────────────
// Mounts the actual screens (LoginScreen, InicioScreen, CobrosShell,
// PagoScreen, MovimientosScreen, CajaMainScreen, JornadaCierreScreen,
// HistorialScreen) against the real seeded SQLite DB (FFI), at phone
// (412x915) and tablet (840x900) profiles.
//
// The fixture is built in `setUp` (real-async zone) because the FFI
// DB calls cannot run inside testWidgets' FakeAsync zone.
//
// Regenerate: flutter test --update-goldens test/screen_golden_test.dart

import 'package:daily_system/navigation.dart';
import 'package:daily_system/screens/caja_main_screen.dart';
import 'package:daily_system/screens/cobros_shell.dart';
import 'package:daily_system/screens/historial_screen.dart';
import 'package:daily_system/screens/inicio_screen.dart';
import 'package:daily_system/screens/jornada_cierre_screen.dart';
import 'package:daily_system/screens/login_screen.dart';
import 'package:daily_system/screens/movimientos_screen.dart';
import 'package:daily_system/screens/pago_screen.dart';
import 'package:daily_system/shell/main_shell.dart';
import 'package:daily_system/theme/theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'helpers/fixture.dart';

void main() {
  const phone = Size(412, 915);
  const tablet = Size(840, 900);

  late Fixture fixture;

  setUpAll(() {
    initTestDatabase();
  });

  setUp(() async {
    fixture = await crearFixture();
  });

  Future<void> pumpScreen(WidgetTester tester, Widget home,
      {Size size = phone, ThemeMode mode = ThemeMode.light}) async {
    tester.view.physicalSize = size;
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      MaterialApp(
        theme: premiumTheme,
        darkTheme: premiumDarkTheme,
        themeMode: mode,
        home: home,
      ),
    );
    await tester.pumpAndSettle();
  }

  group('Screen goldens — phone (412x915)', () {
    testWidgets('LoginScreen light', (tester) async {
      await pumpScreen(
        tester,
        LoginScreen(onLogin: () async {}),
      );
      await expectLater(find.byType(LoginScreen),
          matchesGoldenFile('goldens/screen_login_light.png'));
    });

    testWidgets('LoginScreen dark', (tester) async {
      await pumpScreen(
        tester,
        LoginScreen(onLogin: () async {}),
        mode: ThemeMode.dark,
      );
      await expectLater(find.byType(LoginScreen),
          matchesGoldenFile('goldens/screen_login_dark.png'));
    });

    testWidgets('InicioScreen', (tester) async {
      await pumpScreen(
        tester,
        InicioScreen(
          cobradorId: fixture.cobradorId,
          cobradorNombre: fixture.cobradorNombre,
          negocioId: fixture.negocioId,
          onOpenCobros: (_) {},
          onOpenMas: () {},
        ),
      );
      await expectLater(find.byType(InicioScreen),
          matchesGoldenFile('goldens/screen_inicio.png'));
    });

    testWidgets('CobrosShell hoja viva', (tester) async {
      await pumpScreen(
        tester,
        CobrosShell(
          cobradorId: fixture.cobradorId,
          cobradorNombre: fixture.cobradorNombre,
          negocioId: fixture.negocioId,
          initialSection: CobrosSection.hojaViva,
        ),
      );
      await expectLater(find.byType(CobrosShell),
          matchesGoldenFile('goldens/screen_cobros.png'));
    });

    testWidgets('PagoScreen', (tester) async {
      await pumpScreen(
        tester,
        PagoScreen(
          jornadaId: fixture.jornada.id,
          cobradorId: fixture.cobradorId,
          negocioId: fixture.negocioId,
        ),
      );
      await expectLater(find.byType(PagoScreen),
          matchesGoldenFile('goldens/screen_pago.png'));
    });

    testWidgets('MovimientosScreen', (tester) async {
      await pumpScreen(
        tester,
        MovimientosScreen(jornadaId: fixture.jornada.id),
      );
      await expectLater(find.byType(MovimientosScreen),
          matchesGoldenFile('goldens/screen_movimientos.png'));
    });

    testWidgets('CajaMainScreen', (tester) async {
      await pumpScreen(
        tester,
        const CajaMainScreen(),
      );
      await expectLater(find.byType(CajaMainScreen),
          matchesGoldenFile('goldens/screen_caja.png'));
    });

    testWidgets('JornadaCierreScreen', (tester) async {
      await pumpScreen(
        tester,
        JornadaCierreScreen(
          jornada: fixture.jornada,
          cobradorNombre: fixture.cobradorNombre,
        ),
      );
      await expectLater(find.byType(JornadaCierreScreen),
          matchesGoldenFile('goldens/screen_cierre.png'));
    });

    testWidgets('HistorialScreen', (tester) async {
      await pumpScreen(
        tester,
        const HistorialScreen(),
      );
      await expectLater(find.byType(HistorialScreen),
          matchesGoldenFile('goldens/screen_historial.png'));
    });
  });

  group('Screen goldens — tablet (840x900)', () {
    testWidgets('LoginScreen tablet', (tester) async {
      await pumpScreen(
        tester,
        LoginScreen(onLogin: () async {}),
        size: tablet,
      );
      await expectLater(find.byType(LoginScreen),
          matchesGoldenFile('goldens/screen_login_tablet.png'));
    });

    testWidgets('InicioScreen tablet', (tester) async {
      await pumpScreen(
        tester,
        InicioScreen(
          cobradorId: fixture.cobradorId,
          cobradorNombre: fixture.cobradorNombre,
          negocioId: fixture.negocioId,
          onOpenCobros: (_) {},
          onOpenMas: () {},
        ),
        size: tablet,
      );
      await expectLater(find.byType(InicioScreen),
          matchesGoldenFile('goldens/screen_inicio_tablet.png'));
    });

    testWidgets('CobrosShell tablet', (tester) async {
      await pumpScreen(
        tester,
        CobrosShell(
          cobradorId: fixture.cobradorId,
          cobradorNombre: fixture.cobradorNombre,
          negocioId: fixture.negocioId,
          initialSection: CobrosSection.hojaViva,
        ),
        size: tablet,
      );
      await expectLater(find.byType(CobrosShell),
          matchesGoldenFile('goldens/screen_cobros_tablet.png'));
    });

    testWidgets('PagoScreen tablet', (tester) async {
      await pumpScreen(
        tester,
        PagoScreen(
          jornadaId: fixture.jornada.id,
          cobradorId: fixture.cobradorId,
          negocioId: fixture.negocioId,
        ),
        size: tablet,
      );
      await expectLater(find.byType(PagoScreen),
          matchesGoldenFile('goldens/screen_pago_tablet.png'));
    });

    testWidgets('CajaMainScreen tablet', (tester) async {
      await pumpScreen(
        tester,
        const CajaMainScreen(),
        size: tablet,
      );
      await expectLater(find.byType(CajaMainScreen),
          matchesGoldenFile('goldens/screen_caja_tablet.png'));
    });

    testWidgets('JornadaCierreScreen tablet', (tester) async {
      await pumpScreen(
        tester,
        JornadaCierreScreen(
          jornada: fixture.jornada,
          cobradorNombre: fixture.cobradorNombre,
        ),
        size: tablet,
      );
      await expectLater(find.byType(JornadaCierreScreen),
          matchesGoldenFile('goldens/screen_cierre_tablet.png'));
    });

    testWidgets('HistorialScreen tablet', (tester) async {
      await pumpScreen(
        tester,
        const HistorialScreen(),
        size: tablet,
      );
      await expectLater(find.byType(HistorialScreen),
          matchesGoldenFile('goldens/screen_historial_tablet.png'));
    });

    testWidgets('MainShell tablet', (tester) async {
      await pumpScreen(
        tester,
        MainShell(
          cobradorId: fixture.cobradorId,
          cobradorNombre: fixture.cobradorNombre,
          negocioId: fixture.negocioId,
        ),
        size: tablet,
      );
      await expectLater(find.byType(MainShell),
          matchesGoldenFile('goldens/screen_mainshell_tablet.png'));
    });
  });
}
