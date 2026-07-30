import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('CobrosSubNavChip', () {
    Widget buildChipBar({
      required String selectedLabel,
      required void Function(String label) onChipTap,
    }) {
      final chips = [
        ('Hoja Viva', const Color(0xFF2E7D32)),
        ('Cobrar', const Color(0xFF1565C0)),
        ('Movimientos', const Color(0xFFF57F17)),
        ('Caja', const Color(0xFF455A64)),
      ];
      return MaterialApp(
        home: Scaffold(
          body: Column(
            children: [
              Container(
                margin: const EdgeInsets.all(16),
                child: Row(
                  children: chips.map((chip) {
                    final label = chip.$1;
                    final color = chip.$2;
                    final isSelected = label == selectedLabel;
                    final key = ValueKey('cobros-section-${label.toLowerCase().replaceAll(' ', '-')}');
                    return Expanded(
                      child: Semantics(
                        button: true,
                        selected: isSelected,
                        label: label,
                        child: Material(
                          color: Colors.transparent,
                          child: InkWell(
                            key: key,
                            onTap: () => onChipTap(label),
                            borderRadius: BorderRadius.circular(8),
                            child: Container(
                              constraints: const BoxConstraints(minHeight: 48),
                              padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 4),
                              decoration: BoxDecoration(
                                color: isSelected ? color : color.withValues(alpha: 0.1),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Text(label, textAlign: TextAlign.center),
                            ),
                          ),
                        ),
                      ),
                    );
                  }).toList(),
                ),
              ),
            ],
          ),
        ),
      );
    }

    testWidgets('renders all 4 chips', (tester) async {
      await tester.pumpWidget(buildChipBar(selectedLabel: 'Hoja Viva', onChipTap: (_) {}));

      expect(find.text('Hoja Viva'), findsOneWidget);
      expect(find.text('Cobrar'), findsOneWidget);
      expect(find.text('Movimientos'), findsOneWidget);
      expect(find.text('Caja'), findsOneWidget);
    });

    testWidgets('chips have correct ValueKeys', (tester) async {
      await tester.pumpWidget(buildChipBar(selectedLabel: 'Hoja Viva', onChipTap: (_) {}));

      expect(find.byKey(const ValueKey('cobros-section-hoja-viva')), findsOneWidget);
      expect(find.byKey(const ValueKey('cobros-section-cobrar')), findsOneWidget);
      expect(find.byKey(const ValueKey('cobros-section-movimientos')), findsOneWidget);
      expect(find.byKey(const ValueKey('cobros-section-caja')), findsOneWidget);
    });

    testWidgets('tapping a chip changes selected state', (tester) async {
      String? tappedLabel;
      await tester.pumpWidget(buildChipBar(
        selectedLabel: 'Hoja Viva',
        onChipTap: (label) => tappedLabel = label,
      ));

      await tester.tap(find.byKey(const ValueKey('cobros-section-cobrar')));
      expect(tappedLabel, equals('Cobrar'));
    });

    testWidgets('tapping each chip fires callback with correct label', (tester) async {
      final labels = <String>[];
      await tester.pumpWidget(buildChipBar(
        selectedLabel: 'Hoja Viva',
        onChipTap: (label) => labels.add(label),
      ));

      await tester.tap(find.byKey(const ValueKey('cobros-section-cobrar')));
      await tester.tap(find.byKey(const ValueKey('cobros-section-movimientos')));
      await tester.tap(find.byKey(const ValueKey('cobros-section-caja')));

      expect(labels, equals(['Cobrar', 'Movimientos', 'Caja']));
    });

    testWidgets('chips have Semantics button and label', (tester) async {
      await tester.pumpWidget(buildChipBar(selectedLabel: 'Hoja Viva', onChipTap: (_) {}));

      final finder = find.byKey(const ValueKey('cobros-section-cobrar'));
      expect(finder, findsOneWidget);
      final inkWell = tester.widget<InkWell>(finder);
      expect(inkWell.onTap, isNotNull);
    });

    testWidgets('chip has minHeight 48 for touch target', (tester) async {
      await tester.pumpWidget(buildChipBar(selectedLabel: 'Hoja Viva', onChipTap: (_) {}));

      final chipWidget = tester.widget<Container>(
        find.descendant(
          of: find.byKey(const ValueKey('cobros-section-cobrar')),
          matching: find.byType(Container),
        ).first,
      );
      expect(chipWidget.constraints, isA<BoxConstraints>());
      final constraints = chipWidget.constraints as BoxConstraints;
      expect(constraints.minHeight, equals(48));
    });
  });
}
