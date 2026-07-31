/// Design token generator for Daily System.
/// 
/// Usage:
///   dart run tool/generate_design_tokens.dart
///   dart run tool/generate_design_tokens.dart --check

import 'dart:convert';
import 'dart:io';

void main(List<String> args) {
  final checkMode = args.contains('--check');
  final tokensPath = '${Directory.current.path}/design/tokens/daily-system.tokens.json';
  
  if (!File(tokensPath).existsSync()) {
    print('ERROR: $tokensPath not found');
    exit(1);
  }

  final tokensFile = File(tokensPath);
  final tokensJson = tokensFile.readAsStringSync();
  final tokens = jsonDecode(tokensJson) as Map<String, dynamic>;

  // Generate Dart tokens
  final dartOutput = _generateDartTokens(tokens);
  final dartPath = '${Directory.current.path}/apps/mobile/lib/theme/generated/daily_tokens.dart';
  
  if (checkMode) {
    final existing = File(dartPath).existsSync() 
        ? File(dartPath).readAsStringSync() 
        : '';
    if (existing == dartOutput) {
      print('Dart tokens: OK (matches)');
    } else {
      print('Dart tokens: MISMATCH');
      print('Expected: ${dartOutput.length} chars');
      print('Got:      ${existing.length} chars');
      exit(1);
    }
  } else {
    File(dartPath).writeAsStringSync(dartOutput);
    print('Generated: $dartPath');
  }

  // Generate CSS tokens
  final cssOutput = _generateCssTokens(tokens);
  final cssPath = '${Directory.current.path}/design/tokens/generated/daily-system.css';
  
  if (checkMode) {
    final cssDir = Directory(cssPath.substring(0, cssPath.lastIndexOf('/')));
    if (!cssDir.existsSync()) cssDir.createSync(recursive: true);
    
    final existing = File(cssPath).existsSync() 
        ? File(cssPath).readAsStringSync() 
        : '';
    if (existing == cssOutput) {
      print('CSS tokens: OK (matches)');
    } else {
      print('CSS tokens: MISMATCH');
      exit(1);
    }
  } else {
    final cssDir = Directory(cssPath.substring(0, cssPath.lastIndexOf('/')));
    if (!cssDir.existsSync()) cssDir.createSync(recursive: true);
    File(cssPath).writeAsStringSync(cssOutput);
    print('Generated: $cssPath');
  }

  print('Token generation complete.');
}

String _generateDartTokens(Map<String, dynamic> tokens) {
  final colors = tokens['colors'] as Map<String, dynamic>;
  final shapes = tokens['shapes'] as Map<String, dynamic>;
  final spacing = tokens['spacing'] as Map<String, dynamic>;
  final motion = tokens['motion'] as Map<String, dynamic>;
  final typography = tokens['typography'] as Map<String, dynamic>;
  final breakpoints = tokens['breakpoints'] as Map<String, dynamic>;
  final states = tokens['states'] as Map<String, dynamic>;

  final sb = StringBuffer();
  sb.writeln('// ignore: file_names');
  sb.writeln('// GENERATED FILE — do not edit manually.');
  sb.writeln('// Run: dart run tool/generate_design_tokens.dart');
  sb.writeln('');
  sb.writeln("import 'package:flutter/widgets.dart';");
  sb.writeln('');
  sb.writeln('// ─── Design Tokens — Daily System ────────────────────────────────');
  sb.writeln('// Auto-generated from design/tokens/daily-system.tokens.json');
  sb.writeln('');
  sb.writeln('class DailyTokens {');
  sb.writeln('  DailyTokens._();');
  sb.writeln('');
  
  // Colors light
  sb.writeln('  // ═══ Light Mode Colors ═══');
  final light = colors['light'] as Map<String, dynamic>;
  for (final entry in light.entries) {
    final key = entry.key;
    final val = entry.value as Map<String, dynamic>;
    final hex = val['value'] as String;
    final desc = val.containsKey('description') ? val['description'] : null;
    final alpha = val.containsKey('alpha') ? val['alpha'] : null;
    
    if (desc != null) {
      sb.writeln('  // $desc');
    }
    if (alpha != null) {
      sb.writeln('  static const Color $key = Color(0x${hex.replaceFirst('#', '')});');
      sb.writeln('  static Color ${key}WithAlpha(double a) => ${key}.withValues(alpha: a);');
    } else {
      sb.writeln('  static const Color $key = Color(0x${hex.replaceFirst('#', '')});');
    }
  }
  sb.writeln('');
  
  // Colors dark
  sb.writeln('  // ═══ Dark Mode Colors ═══');
  final dark = colors['dark'] as Map<String, dynamic>;
  for (final entry in dark.entries) {
    final key = entry.key;
    final val = entry.value as Map<String, dynamic>;
    final hex = val['value'] as String;
    final desc = val.containsKey('description') ? val['description'] : null;
    if (desc != null) {
      sb.writeln('  // $desc');
    }
    sb.writeln('  static const Color dark$key = Color(0x${hex.replaceFirst('#', '')});');
  }
  sb.writeln('');
  
  // Convenience getters for dark theme
  sb.writeln('  // ═══ Dark Theme Convenience Colors ═══');
  sb.writeln('  static Color get darkSurface => darksurface;');
  sb.writeln('  static Color get darkSurfaceContainer => darksurfaceContainer;');
  sb.writeln('  static Color get darkSurfaceVariant => darksurfaceVariant;');
  sb.writeln('  static Color get darkOutline => darkoutline;');
  sb.writeln('  static Color get darkOutlineVariant => darkoutlineVariant;');
  sb.writeln('  static Color get darkTextPrimary => darktextPrimary;');
  sb.writeln('  static Color get darkTextSecondary => darktextSecondary;');
  sb.writeln('  static Color get darkTextDisabled => darktextDisabled;');
  sb.writeln('  static Color get darkPrimary => darkprimary;');
  sb.writeln('  static Color get darkOnPrimary => darkonPrimary;');
  sb.writeln('  static Color get darkPrimaryContainer => darkprimaryContainer;');
  sb.writeln('  static Color get darkOnPrimaryContainer => darkonPrimaryContainer;');
  sb.writeln('  static Color get darkAccent => darkaccent;');
  sb.writeln('  static Color get darkAccentContainer => darkaccentContainer;');
  sb.writeln('  static Color get darkTertiary => darktertiary;');
  sb.writeln('  static Color get darkTertiaryContainer => darktertiaryContainer;');
  sb.writeln('  static Color get darkOnTertiary => darkonTertiary;');
  sb.writeln('  static Color get darkDanger => darkerror;');
  sb.writeln('  static Color get darkSuccess => darksuccess;');
  sb.writeln('  static Color get darkWarning => darkwarning;');
  sb.writeln('  static Color get darkShadow => const Color(0x000000);');
  sb.writeln('  static Color get shadowColor => shadow.withValues(alpha: 0.08);');
  sb.writeln('');
  
  // Shapes
  sb.writeln('  // ═══ Shapes ═══');
  for (final entry in shapes.entries) {
    sb.writeln('  static const double shape${entry.key.toUpperCase()} = ${entry.value};');
  }
  sb.writeln('');
  
  // Spacing
  sb.writeln('  // ═══ Spacing ═══');
  for (final entry in spacing.entries) {
    sb.writeln('  static const double spacing${entry.key.toUpperCase()} = ${entry.value};');
  }
  sb.writeln('');
  
  // Motion
  sb.writeln('  // ═══ Motion ═══');
  for (final entry in motion.entries) {
    if (entry.key == 'curveEmphasized' || entry.key == 'curveDecelerated') {
      sb.writeln('  static final ${entry.key} = ${_curveToDart(entry.value as String)};');
    } else if (entry.key == 'duration' || entry.key == 'fast' || entry.key == 'normal' || entry.key == 'long') {
      final dur = entry.value is Map ? (entry.value as Map)['duration'] : entry.value;
      sb.writeln('  static const Duration ${entry.key} = Duration(milliseconds: ${dur});');
    }
  }
  sb.writeln('');
  
  // Typography
  sb.writeln('  // ═══ Typography ═══');
  sb.writeln('  static const String fontFamily = "${typography['fontFamily']}";');
  sb.writeln('  static const bool tabularNumbers = ${typography['tabularNumbers']};');
  sb.writeln('');
  sb.writeln('  // Typography scales');
  final scales = typography['scales'] as Map<String, dynamic>;
  for (final entry in scales.entries) {
    final scale = entry.value as Map<String, dynamic>;
    final name = entry.key;
    sb.writeln('  static const ${name}TextStyle = TextStyle(');
    sb.writeln('    fontSize: ${scale['fontSize']},');
    sb.writeln('    fontWeight: FontWeight.w${scale['fontWeight']},');
    sb.writeln('    height: ${scale['lineHeight'] / scale['fontSize']},');
    if (scale.containsKey('features') && (scale['features'] as List).contains('tnum')) {
      sb.writeln('    fontFeatures: const [FontFeature.tabularFigures()],');
    }
    sb.writeln('  );');
  }
  sb.writeln('');
  
  // Breakpoints
  sb.writeln('  // ═══ Breakpoints (dp) ═══');
  for (final entry in breakpoints.entries) {
    final val = entry.value as Map<String, dynamic>;
    sb.writeln('  static const int ${entry.key}Breakpoint = ${val['min'] ?? val['max']};');
  }
  sb.writeln('');
  
  // States
  sb.writeln('  // ═══ UI States ═══');
  for (final entry in states.entries) {
    final state = entry.value as Map<String, dynamic>;
    sb.writeln('  // ${entry.key}: ${state['description']}');
  }
  sb.writeln('}');

  return sb.toString();
}

String _generateCssTokens(Map<String, dynamic> tokens) {
  final colors = tokens['colors'] as Map<String, dynamic>;
  final shapes = tokens['shapes'] as Map<String, dynamic>;
  final spacing = tokens['spacing'] as Map<String, dynamic>;
  final motion = tokens['motion'] as Map<String, dynamic>;
  final breakpoints = tokens['breakpoints'] as Map<String, dynamic>;

  final sb = StringBuffer();
  sb.writeln('/* Daily System Design Tokens */');
  sb.writeln('/* Generated from design/tokens/daily-system.tokens.json */');
  sb.writeln('');
  sb.writeln(':root {');
  
  // Light mode CSS custom properties
  sb.writeln('  /* ── Light Mode ── */');
  final light = colors['light'] as Map<String, dynamic>;
  for (final entry in light.entries) {
    final key = entry.key;
    final val = entry.value as Map<String, dynamic>;
    final hex = val['value'] as String;
    sb.writeln('  --ds-${_kebab(key)}: ${hex};');
  }
  sb.writeln('');
  
  // Dark mode
  sb.writeln('  /* ── Dark Mode ── */');
  sb.writeln(':root[data-theme="dark"] {');
  final dark = colors['dark'] as Map<String, dynamic>;
  for (final entry in dark.entries) {
    final key = entry.key;
    final val = entry.value as Map<String, dynamic>;
    final hex = val['value'] as String;
    sb.writeln('  --ds-${_kebab(key)}: ${hex};');
  }
  sb.writeln('}');
  sb.writeln('');
  
  // Shapes
  sb.writeln('  /* ── Shapes ── */');
  for (final entry in shapes.entries) {
    sb.writeln('  --ds-shape-${entry.key}: ${entry.value}px;');
  }
  sb.writeln('');
  
  // Spacing
  sb.writeln('  /* ── Spacing ── */');
  for (final entry in spacing.entries) {
    sb.writeln('  --ds-spacing-${entry.key}: ${entry.value}px;');
  }
  sb.writeln('');
  
  // Motion
  sb.writeln('  /* ── Motion ── */');
  for (final entry in motion.entries) {
    if (entry.key == 'duration' || entry.key == 'fast' || entry.key == 'normal' || entry.key == 'long') {
      final dur = entry.value is Map ? (entry.value as Map)['duration'] : entry.value;
      sb.writeln('  --ds-motion-${entry.key}: ${dur}ms;');
    }
  }
  sb.writeln('');
  
  // Breakpoints
  sb.writeln('  /* ── Breakpoints ── */');
  for (final entry in breakpoints.entries) {
    final val = entry.value as Map<String, dynamic>;
    sb.writeln('  --ds-breakpoint-${entry.key}: ${val['min'] ?? val['max']}px;');
  }
  sb.writeln('}');

  return sb.toString();
}

String _kebab(String camel) {
  return camel.replaceAllMapped(
    RegExp(r'[A-Z]'),
    (m) => m[0] != null && m[0]!.isNotEmpty ? '-${m[0]![0].toLowerCase()}' : '',
  );
}

String _curveToDart(String name) {
  switch (name) {
    case 'easeOutCubic':
      return 'Curves.easeOutCubic';
    case 'easeOut':
      return 'Curves.easeOut';
    default:
      return 'Curves.linear';
  }
}
