// ─── Design Token Generator Tests ────────────────────────────────
// Validates: CSS structure, color opacity, determinism, balanced braces.

import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

Directory findRepositoryRoot() {
  var current = Directory.current.absolute;

  while (true) {
    final generator = File(
      '${current.path}/tool/generate_design_tokens.dart',
    );
    final tokens = File(
      '${current.path}/design/tokens/daily-system.tokens.json',
    );
    final mobilePubspec = File(
      '${current.path}/apps/mobile/pubspec.yaml',
    );

    if (generator.existsSync() &&
        tokens.existsSync() &&
        mobilePubspec.existsSync()) {
      return current;
    }

    final parent = current.parent;

    if (parent.path == current.path) {
      throw StateError(
        'No se encontró el root de daily-system desde '
        '\${Directory.current.path}',
      );
    }

    current = parent;
  }
}

void main() {
  final repoRoot = findRepositoryRoot();
  final tokensPath = '${repoRoot.path}/design/tokens/daily-system.tokens.json';

  group('Generator — CSS structure', () {
    test(':root selector has balanced braces', () {
      final tokensFile = File(tokensPath);
      final tokens = jsonDecode(tokensFile.readAsStringSync()) as Map<String, dynamic>;
      final colors = tokens['colors'] as Map<String, dynamic>;
      final light = colors['light'] as Map<String, dynamic>;
      final dark = colors['dark'] as Map<String, dynamic>;

      final sb = StringBuffer();
      sb.writeln(':root {');
      for (final entry in light.entries) {
        final val = entry.value as Map<String, dynamic>;
        sb.writeln('  --ds-${_kebab(entry.key)}: ${val['value']};');
      }
      sb.writeln('}');
      sb.writeln('');
      sb.writeln(':root[data-theme="dark"] {');
      for (final entry in dark.entries) {
        final val = entry.value as Map<String, dynamic>;
        sb.writeln('  --ds-${_kebab(entry.key)}: ${val['value']};');
      }
      sb.writeln('}');

      final css = sb.toString();
      expect(css.contains(':root {'), isTrue);
      expect(css.contains(':root[data-theme="dark"] {'), isTrue);
      expect(css.split('{').length - 1, css.split('}').length - 1,
          reason: 'Llaves de apertura y cierre deben balancearse');
    });

    test(':root and :root[data-theme="dark"] are independent selectors', () {
      final tokensFile = File(tokensPath);
      final tokens = jsonDecode(tokensFile.readAsStringSync()) as Map<String, dynamic>;
      final colors = tokens['colors'] as Map<String, dynamic>;
      final light = colors['light'] as Map<String, dynamic>;
      final dark = colors['dark'] as Map<String, dynamic>;

      final sb = StringBuffer();
      sb.writeln(':root {');
      for (final entry in light.entries) {
        final val = entry.value as Map<String, dynamic>;
        sb.writeln('  --ds-${_kebab(entry.key)}: ${val['value']};');
      }
      sb.writeln('}');
      sb.writeln('');
      sb.writeln(':root[data-theme="dark"] {');
      for (final entry in dark.entries) {
        final val = entry.value as Map<String, dynamic>;
        sb.writeln('  --ds-${_kebab(entry.key)}: ${val['value']};');
      }
      sb.writeln('}');

      final css = sb.toString();
      final rootClosePos = css.indexOf('}', css.indexOf(':root {'));
      final darkOpenPos = css.indexOf(':root[data-theme="dark"]');
      expect(rootClosePos < darkOpenPos, isTrue,
          reason: ':root debe cerrarse antes de que abra :root[data-theme="dark"]');
    });

    test('CSS has exactly 2 :root selectors', () {
      final tokensFile = File(tokensPath);
      final tokens = jsonDecode(tokensFile.readAsStringSync()) as Map<String, dynamic>;
      final colors = tokens['colors'] as Map<String, dynamic>;
      final light = colors['light'] as Map<String, dynamic>;
      final dark = colors['dark'] as Map<String, dynamic>;

      final sb = StringBuffer();
      sb.writeln(':root {');
      for (final entry in light.entries) {
        final val = entry.value as Map<String, dynamic>;
        sb.writeln('  --ds-${_kebab(entry.key)}: ${val['value']};');
      }
      sb.writeln('}');
      sb.writeln('');
      sb.writeln(':root[data-theme="dark"] {');
      for (final entry in dark.entries) {
        final val = entry.value as Map<String, dynamic>;
        sb.writeln('  --ds-${_kebab(entry.key)}: ${val['value']};');
      }
      sb.writeln('}');

      final css = sb.toString();
      expect(css.split(':root').length - 1, equals(2),
          reason: 'Deben existir exactamente 2 selectores :root');
    });
  });

  group('Generator — Color opacity', () {
    test('Light colors generate with FF alpha (opaque)', () {
      final tokensFile = File(tokensPath);
      final tokens = jsonDecode(tokensFile.readAsStringSync()) as Map<String, dynamic>;
      final colors = tokens['colors'] as Map<String, dynamic>;
      final light = colors['light'] as Map<String, dynamic>;

      // Check that colors WITHOUT alpha in the token generate with FF prefix
      for (final entry in light.entries) {
        final val = entry.value as Map<String, dynamic>;
        final alpha = val.containsKey('alpha') ? val['alpha'] : null;
        if (alpha == null) {
          // No alpha in token → must generate 0xFF prefix
          final hex = val['value'] as String;
          expect(hex, matches(r'^#[0-9a-fA-F]{6}$'),
              reason: '${entry.key} sin alpha debe ser #RRGGBB');
        }
      }
    });

    test('Shadow colors with alpha are allowed to be transparent', () {
      final tokensFile = File(tokensPath);
      final tokens = jsonDecode(tokensFile.readAsStringSync()) as Map<String, dynamic>;
      final colors = tokens['colors'] as Map<String, dynamic>;
      final light = colors['light'] as Map<String, dynamic>;

      final shadow = light['shadow'];
      if (shadow != null && shadow is Map) {
        expect(shadow.containsKey('alpha'), isTrue,
            reason: 'shadow debe tener alpha definido');
        final alpha = shadow['alpha'] as double;
        expect(alpha, lessThan(1.0),
            reason: 'shadow alpha debe ser < 1.0 (transparente)');
      }
    });

    test('No opaque color has alpha 00', () {
      final tokensFile = File(tokensPath);
      final tokens = jsonDecode(tokensFile.readAsStringSync()) as Map<String, dynamic>;
      final colors = tokens['colors'] as Map<String, dynamic>;
      final light = colors['light'] as Map<String, dynamic>;

      for (final entry in light.entries) {
        final val = entry.value as Map<String, dynamic>;
        final alpha = val.containsKey('alpha') ? val['alpha'] : null;
        if (alpha == null) {
          final hex = val['value'] as String;
          expect(hex, matches(r'^#[0-9a-fA-F]{6}$'),
              reason: '${entry.key} sin alpha debe ser #RRGGBB');
        }
      }
    });
  });

  group('Generator — Determinism', () {
    test('--check mode does not modify files', () async {
      final repoRoot = findRepositoryRoot();

      final dartTokens = File(
        '${repoRoot.path}/apps/mobile/lib/theme/generated/daily_tokens.dart',
      );
      final cssTokens = File(
        '${repoRoot.path}/design/tokens/generated/daily-system.css',
      );

      final dartBefore = await dartTokens.readAsBytes();
      final cssBefore = await cssTokens.readAsBytes();

      // Run --check (should pass if files match)
      final result = await Process.run(
        'dart',
        [
          'run',
          'tool/generate_design_tokens.dart',
          '--check',
        ],
        workingDirectory: repoRoot.path,
      );

      expect(result.exitCode, equals(0),
          reason: '''
stdout:
${result.stdout}

stderr:
${result.stderr}
''');

      // Verify files were not modified by --check
      expect(await dartTokens.readAsBytes(), dartBefore,
          reason: 'El archivo Dart no debe modificarse con --check');
      expect(await cssTokens.readAsBytes(), cssBefore,
          reason: 'El archivo CSS no debe modificarse con --check');
    });
  });

  group('Generator — Token count consistency', () {
    test('Light and dark have same color keys', () {
      final tokensFile = File(tokensPath);
      final tokens = jsonDecode(tokensFile.readAsStringSync()) as Map<String, dynamic>;
      final colors = tokens['colors'] as Map<String, dynamic>;
      final light = colors['light'] as Map<String, dynamic>;
      final dark = colors['dark'] as Map<String, dynamic>;

      final lightKeys = light.keys.toSet();
      final darkKeys = dark.keys.toSet();

      expect(darkKeys.difference(lightKeys).isEmpty, isTrue,
          reason: 'Dark no debe tener keys que light no tenga');
    });
  });
}

String _kebab(String camel) {
  return camel.replaceAllMapped(
    RegExp(r'[A-Z]'),
    (m) => m[0] != null && m[0]!.isNotEmpty ? '-${m[0]![0].toLowerCase()}' : '',
  );
}
