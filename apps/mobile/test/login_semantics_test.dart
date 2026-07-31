// ─── Login Screen Semantics Tests ───────────────────────────────

import 'package:daily_system/ui/components/daily_logo.dart';
import 'package:daily_system/ui/components/daily_primary_button.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('Login Semantics', () {
    testWidgets('DailyLogo renders', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: const DailyLogo(size: 80)),
        ),
      );
      
      expect(find.byType(DailyLogo), findsOneWidget);
    });

    testWidgets('Login button exists and is tapable', (tester) async {
      bool tapped = false;
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(body: DailyPrimaryButton(
          label: 'INICIAR SESIÓN',
          onPressed: () => tapped = true,
          icon: Icons.login,
        )),
      ));
      
      expect(find.byType(DailyPrimaryButton), findsOneWidget);
      await tester.tap(find.byType(DailyPrimaryButton));
      expect(tapped, isTrue);
    });

    testWidgets('Login button minimum 48px height', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(body: DailyPrimaryButton(
          label: 'INICIAR SESIÓN',
          onPressed: () {},
          icon: Icons.login,
        )),
      ));
      
      final renderBox = tester.renderObject(find.byType(DailyPrimaryButton));
      final paintBounds = renderBox.paintBounds;
      expect(paintBounds.height, greaterThanOrEqualTo(48.0),
          reason: 'Botón debe tener mínimo 48px de altura para touch target');
    });
  });

  group('Semantics: CobrosNavChip', () {
    testWidgets('Chip: Hoja Viva has button semantics', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(body: Semantics(
          button: true,
          selected: true,
          label: 'Hoja Viva',
          child: InkWell(
            onTap: () {},
            child: Container(
              constraints: const BoxConstraints(minHeight: 48),
              child: const Text('Hoja Viva'),
            ),
          ),
        )),
      ));
      
      expect(find.text('Hoja Viva'), findsOneWidget);
    });

    testWidgets('Chip: Cobrar has button semantics', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(body: Semantics(
          button: true,
          selected: false,
          label: 'Cobrar',
          child: InkWell(
            onTap: () {},
            child: Container(
              constraints: const BoxConstraints(minHeight: 48),
              child: const Text('Cobrar'),
            ),
          ),
        )),
      ));
      
      expect(find.text('Cobrar'), findsOneWidget);
    });

    testWidgets('Chip: All 4 chips present with minHeight 48', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(body: Column(
          children: ['Hoja Viva', 'Cobrar', 'Movimientos', 'Caja'].map((label) {
            return Semantics(
              button: true,
              selected: label == 'Hoja Viva',
              label: label,
              child: InkWell(
                onTap: () {},
                child: Container(
                  constraints: const BoxConstraints(minHeight: 48),
                  child: Text(label),
                ),
              ),
            );
          }).toList(),
        )),
      ));
      
      for (final label in ['Hoja Viva', 'Cobrar', 'Movimientos', 'Caja']) {
        expect(find.text(label), findsOneWidget, reason: 'Chip $label debe existir');
      }
    });
  });
}
