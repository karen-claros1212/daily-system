// ─── Real Semantics Tests — productive screens ───────────────────
// Uses getSemantics + matchesSemantics against the ACTUAL LoginScreen,
// CobrosShell, PagoScreen, JornadaCierreScreen and MainShell
// (fixture DB + SharedPreferences seeded via helpers).
//
// Fixture is built in setUp (real-async) because FFI DB calls cannot
// run inside testWidgets' FakeAsync zone.

import 'dart:ui' show Tristate;

import 'package:daily_system/navigation.dart';
import 'package:daily_system/screens/caja_main_screen.dart';
import 'package:daily_system/screens/cobros_shell.dart';
import 'package:daily_system/screens/historial_screen.dart';
import 'package:daily_system/screens/jornada_cierre_screen.dart';
import 'package:daily_system/screens/login_screen.dart';
import 'package:daily_system/screens/pago_screen.dart';
import 'package:daily_system/shell/main_shell.dart';
import 'package:daily_system/theme/theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart' show SemanticsAction, SemanticsFlag;
import 'package:flutter_test/flutter_test.dart';

import 'helpers/fixture.dart';

void main() {
  late Fixture fixture;

  setUpAll(() {
    initTestDatabase();
  });

  setUp(() async {
    fixture = await crearFixture();
  });

  Future<void> pump(WidgetTester tester, Widget home) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: premiumTheme,
        darkTheme: premiumDarkTheme,
        themeMode: ThemeMode.light,
        home: home,
      ),
    );
    await tester.pumpAndSettle();
  }

  void expectHasFlag(WidgetTester tester, Finder finder, SemanticsFlag flag,
      {String? label, bool expectSelected = false}) {
    final data = tester.getSemantics(finder).getSemanticsData();
    final flags = data.flagsCollection;
    final bool hasFlag = switch (flag) {
      SemanticsFlag.isButton => flags.isButton,
      SemanticsFlag.isSelected => flags.isSelected == Tristate.isTrue,
      _ => false,
    };
    expect(hasFlag, isTrue, reason: '$finder debe exponer flag $flag — data: $data');
    if (label != null) {
      expect(data.label, contains(label),
          reason: '$finder debe tener label "$label" — data: $data');
    }
    if (expectSelected) {
      expect(flags.isSelected == Tristate.isTrue, isTrue,
          reason: '$finder debe exponer isSelected');
    }
    expect(data.hasAction(SemanticsAction.tap), isTrue,
        reason: '$finder debe ser tappable');
  }

  group('LoginScreen semantics', () {
    testWidgets('INICIAR SESIÓN is an exposed button', (tester) async {
      final handle = tester.ensureSemantics();
      await pump(tester, LoginScreen(onLogin: () async {}));

      expectHasFlag(tester, find.text('INICIAR SESIÓN'), SemanticsFlag.isButton,
          label: 'INICIAR SESIÓN');
      expect(find.text('INICIAR SESIÓN'), findsOneWidget);
      handle.dispose();
    });

    testWidgets('brand + tagline are readable text', (tester) async {
      final handle = tester.ensureSemantics();
      await pump(tester, LoginScreen(onLogin: () async {}));

      expect(find.text('Daily System'), findsOneWidget);
      expect(find.text('Tu ruta, tus cobros y tu caja, incluso sin internet.'),
          findsOneWidget);
      handle.dispose();
    });

    testWidgets('tapping INICIAR SESIÓN fires onLogin', (tester) async {
      var called = false;
      await pump(tester, LoginScreen(onLogin: () async => called = true));

      await tester.tap(find.text('INICIAR SESIÓN'));
      await tester.pumpAndSettle();
      expect(called, isTrue);
    });
  });

  group('CobrosShell semantics (hoja viva)', () {
    Future<void> pumpHojaViva(WidgetTester tester) async {
      await pump(
        tester,
        CobrosShell(
          cobradorId: fixture.cobradorId,
          cobradorNombre: fixture.cobradorNombre,
          negocioId: fixture.negocioId,
          initialSection: CobrosSection.hojaViva,
        ),
      );
    }

    testWidgets('4 sub-nav chips exposed with button semantics', (tester) async {
      final handle = tester.ensureSemantics();
      await pumpHojaViva(tester);

      for (final label in ['Hoja Viva', 'Cobrar', 'Movimientos', 'Caja']) {
        final key = ValueKey(
            'cobros-section-${label.toLowerCase().replaceAll(' ', '-')}');
        expectHasFlag(tester, find.byKey(key), SemanticsFlag.isButton,
            label: label);
      }
      handle.dispose();
    });

    testWidgets('active chip has selected state', (tester) async {
      final handle = tester.ensureSemantics();
      await pumpHojaViva(tester);

      expectHasFlag(
          tester,
          find.byKey(const ValueKey('cobros-section-hoja-viva')),
          SemanticsFlag.isButton,
          label: 'Hoja Viva',
          expectSelected: true);
      handle.dispose();
    });

    testWidgets('chips are tappable and switch sections', (tester) async {
      await pumpHojaViva(tester);

      await tester.tap(find.byKey(const ValueKey('cobros-section-cobrar')));
      await tester.pumpAndSettle();
      expect(find.byType(PagoScreen), findsOneWidget);
    });

    testWidgets('route header shows jornada date', (tester) async {
      await pumpHojaViva(tester);

      expect(find.textContaining('Jornada del'), findsOneWidget);
    });
  });

  group('PagoScreen semantics', () {
    Future<void> pumpPago(WidgetTester tester) async {
      await pump(
        tester,
        PagoScreen(
          jornadaId: fixture.jornada.id,
          cobradorId: fixture.cobradorId,
          negocioId: fixture.negocioId,
        ),
      );
    }

    testWidgets('active debtor list renders with payment action', (tester) async {
      final handle = tester.ensureSemantics();
      await pumpPago(tester);

      expect(find.text('Deudores activos'), findsOneWidget);
      expect(find.text('REGISTRAR PAGO'), findsOneWidget);
      expectHasFlag(tester, find.text('REGISTRAR PAGO'), SemanticsFlag.isButton,
          label: 'REGISTRAR PAGO');
      handle.dispose();
    });

    testWidgets('dropdown lists fixture debtors', (tester) async {
      await pumpPago(tester);

      expect(find.byType(DropdownButton<Map<String, dynamic>>), findsOneWidget);
      await tester.tap(find.byType(DropdownButton<Map<String, dynamic>>));
      await tester.pumpAndSettle();
      expect(find.byType(DropdownMenuItem<Map<String, dynamic>>), findsWidgets);
    });
  });

  group('JornadaCierreScreen semantics', () {
    testWidgets('open jornada shows TERMINAR JORNADA action', (tester) async {
      final handle = tester.ensureSemantics();
      await pump(
        tester,
        JornadaCierreScreen(
          jornada: fixture.jornada,
          cobradorNombre: fixture.cobradorNombre,
        ),
      );

      expect(find.text('JORNADA ABIERTA'), findsOneWidget);
      expectHasFlag(tester, find.text('TERMINAR JORNADA'), SemanticsFlag.isButton,
          label: 'TERMINAR JORNADA');
      handle.dispose();
    });

    testWidgets('contado and motivo fields are editable', (tester) async {
      await pump(
        tester,
        JornadaCierreScreen(
          jornada: fixture.jornada,
          cobradorNombre: fixture.cobradorNombre,
        ),
      );

      expect(find.byType(TextField), findsNWidgets(2));
      await tester.enterText(find.byType(TextField).first, '65000');
      await tester.pumpAndSettle();
      expect(find.text('65000'), findsOneWidget);
    });
  });

  group('CajaMainScreen semantics', () {
    testWidgets('shows recaudo summary for open jornada', (tester) async {
      await pump(tester, const CajaMainScreen());

      expect(find.text('Recaudo Real'), findsOneWidget);
      expect(find.text('Esperado'), findsOneWidget);
    });
  });

  group('HistorialScreen semantics', () {
    testWidgets('lists open jornada with estado label', (tester) async {
      await pump(tester, const HistorialScreen());

      expect(find.textContaining('Abierta'), findsWidgets);
    });
  });

  group('MainShell semantics', () {
    testWidgets('NavigationBar exposes 4 destinations', (tester) async {
      final handle = tester.ensureSemantics();
      await pump(
        tester,
        MainShell(
          cobradorId: fixture.cobradorId,
          cobradorNombre: fixture.cobradorNombre,
          negocioId: fixture.negocioId,
        ),
      );

      expect(find.byType(NavigationBar), findsOneWidget);
      for (final label in ['Inicio', 'Cobros', 'Caja', 'Más']) {
        expect(
          find.descendant(
            of: find.byType(NavigationBar),
            matching: find.text(label),
          ),
          findsOneWidget,
          reason: 'Destino $label debe existir en la barra',
        );
      }
      handle.dispose();
    });

    testWidgets('tap Cobros destination switches tab', (tester) async {
      await pump(
        tester,
        MainShell(
          cobradorId: fixture.cobradorId,
          cobradorNombre: fixture.cobradorNombre,
          negocioId: fixture.negocioId,
        ),
      );

      await tester.tap(find.descendant(
        of: find.byType(NavigationBar),
        matching: find.text('Cobros'),
      ));
      await tester.pumpAndSettle();
      expect(find.byType(CobrosShell), findsOneWidget);
    });
  });
}
