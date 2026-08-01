// ─── Logo Golden Tests ──────────────────────────────────────────
// Real golden files via matchesGoldenFile for DailyLogo component.
// Regenerate with: flutter test --update-goldens test/logo_golden_test.dart

import 'package:daily_system/theme/theme.dart';
import 'package:daily_system/ui/components/daily_logo.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  Future<void> pumpLogo(WidgetTester tester, Widget child,
      {Brightness brightness = Brightness.light}) async {
    tester.view.physicalSize = const Size(412, 915);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      MaterialApp(
        theme: premiumTheme,
        darkTheme: premiumDarkTheme,
        themeMode:
            brightness == Brightness.dark ? ThemeMode.dark : ThemeMode.light,
        home: Scaffold(body: Center(child: child)),
      ),
    );
    await tester.pumpAndSettle();
  }

  group('DailyLogo Golden', () {
    testWidgets('Logo renders at size 40', (tester) async {
      await pumpLogo(tester, const DailyLogo(size: 40));
      await expectLater(
          find.byType(DailyLogo), matchesGoldenFile('goldens/logo_40.png'));
    });

    testWidgets('Logo renders at size 80', (tester) async {
      await pumpLogo(tester, const DailyLogo(size: 80));
      await expectLater(
          find.byType(DailyLogo), matchesGoldenFile('goldens/logo_80.png'));
    });

    testWidgets('Logo renders at size 120', (tester) async {
      await pumpLogo(tester, const DailyLogo(size: 120));
      await expectLater(
          find.byType(DailyLogo), matchesGoldenFile('goldens/logo_120.png'));
    });

    testWidgets('Logo with custom color', (tester) async {
      await pumpLogo(tester,
          DailyLogo(size: 60, color: const Color(0xFFC62828)));
      await expectLater(
          find.byType(DailyLogo), matchesGoldenFile('goldens/logo_color.png'));
    });

    testWidgets('Logo in column with text', (tester) async {
      await pumpLogo(tester, const Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          DailyLogo(size: 40),
          SizedBox(height: 8),
          Text('Daily System'),
        ],
      ));
      await expectLater(find.byType(Column),
          matchesGoldenFile('goldens/logo_column.png'));
    });

    testWidgets('Logo dark theme at size 80', (tester) async {
      await pumpLogo(tester, const DailyLogo(size: 80),
          brightness: Brightness.dark);
      await expectLater(find.byType(DailyLogo),
          matchesGoldenFile('goldens/logo_80_dark.png'));
    });
  });
}
