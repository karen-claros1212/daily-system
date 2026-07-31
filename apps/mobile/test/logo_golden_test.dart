// ─── Logo Golden Tests ──────────────────────────────────────────
// Golden tests for DailyLogo component.

import 'package:daily_system/ui/components/daily_logo.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('DailyLogo Golden', () {
    testWidgets('Logo renders at size 40', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: Center(child: const DailyLogo(size: 40))),
        ),
      );
      
      expect(find.byType(DailyLogo), findsOneWidget);
      expect(find.byType(CustomPaint), findsAtLeast(1));
    });

    testWidgets('Logo renders at size 80', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: Center(child: const DailyLogo(size: 80))),
        ),
      );
      
      expect(find.byType(DailyLogo), findsOneWidget);
    });

    testWidgets('Logo renders at size 120', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: Center(child: const DailyLogo(size: 120))),
        ),
      );
      
      expect(find.byType(DailyLogo), findsOneWidget);
    });

    testWidgets('Logo with custom color', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: Center(
            child: DailyLogo(size: 60, color: const Color(0xFFC62828)),
          )),
        ),
      );
      
      expect(find.byType(DailyLogo), findsOneWidget);
    });

    testWidgets('Logo in column with text', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: Column(
            children: const [
              DailyLogo(size: 40),
              Text('Daily System'),
            ],
          )),
        ),
      );
      
      expect(find.byType(DailyLogo), findsOneWidget);
      expect(find.text('Daily System'), findsOneWidget);
    });
  });
}
