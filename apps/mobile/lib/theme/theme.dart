// ─── Design Tokens — Material 3 Expressive ────────────────────────
// Principios: espacio eficiente, jerarquía clara, movimiento breve,
// sensación premium, componentes compactos, navegación simple.
//
// Identidad: azul petróleo (primario/confianza), verde esmeralda (acento/operación).

import 'package:flutter/material.dart';
import 'dart:ui';

// Import generated tokens for single source of truth
import 'generated/daily_tokens.dart';

// ── Color Tokens (legacy aliases for generated tokens) ──────────
class AppColors {
  // Primary — petrol blue (matches tokens)
  static const primary = Color(0xFF0B4654);
  static const primaryLight = Color(0xFF125466);
  static const primaryDark = Color(0xFF083340);
  static const primaryContainer = Color(0xFFB0D4DE);
  static const onPrimaryContainer = Color(0xFF071920);

  // Accent — operational emerald (matches tokens)
  static const accent = Color(0xFF0F6B55);
  static const accentLight = Color(0xFF14916F);
  static const accentContainer = Color(0xFFB2DFD6);

  // Secondary — slate
  static const secondary = Color(0xFF455A64);
  static const secondaryLight = Color(0xFF78909C);
  static const secondaryDark = Color(0xFF263238);

  // Tertiary — gold emphasis (matches tokens)
  static const tertiary = Color(0xFFD7A33D);
  static const tertiaryLight = Color(0xFFE8C568);
  static const tertiaryDark = Color(0xFF9A7328);
  static const tertiaryContainer = Color(0xFFF5E6C8);
  static const onTertiary = Color(0xFF3D2E0A);

  // Semantic (matches tokens)
  static const success = Color(0xFF0F6B55);
  static const warning = Color(0xFF8A5A00);
  static const danger = Color(0xFFB3261E);
  static const info = Color(0xFF0B4654);

  // Surface (matches tokens)
  static const surface = Color(0xFFF6F8F7);
  static const surfaceContainer = Color(0xFFEDEDED);
  static const surfaceVariant = Color(0xFFE0E0E0);
  static const outline = Color(0xFFB0B0B0);
  static const outlineVariant = Color(0xFF797979);

  // Text (matches tokens)
  static const textPrimary = Color(0xFF17242B);
  static const textSecondary = Color(0xFF5F6368);
  static const textDisabled = Color(0xFFB0B0B0);

  // Shadow
  static Color shadow = const Color(0x000000).withValues(alpha: 0.08);
}

// ── Shape Tokens ─────────────────────────────────────────────────
class Shapes {
  static const sm = 8.0;
  static const md = 12.0;
  static const lg = 16.0;
  static const xl = 24.0;

  static BorderRadius smRadius = BorderRadius.circular(sm);
  static BorderRadius mdRadius = BorderRadius.circular(md);
  static BorderRadius lgRadius = BorderRadius.circular(lg);
  static BorderRadius xlRadius = BorderRadius.circular(xl);
}

// ── Spacing Tokens ───────────────────────────────────────────────
class Spacing {
  static const xs = 4.0;
  static const sm = 8.0;
  static const md = 16.0;
  static const lg = 24.0;
  static const xl = 32.0;
  static const xxl = 48.0;
}

// ── Motion Tokens ────────────────────────────────────────────────
class Motion {
  static const durationShort = Duration(milliseconds: 200);
  static const durationMedium = Duration(milliseconds: 300);
  static const durationLong = Duration(milliseconds: 400);
  static const curveEmphasized = Curves.easeOutCubic;
  static const curveDecelerated = Curves.easeOut;
}

// ── Theme Extension ──────────────────────────────────────────────
class AppThemeExtension extends ThemeExtension<AppThemeExtension> {
  final Color primary;
  final Color accent;
  final Color tertiary;
  final Color danger;
  final Color success;
  final Color warning;
  final Color surface;
  final Color surfaceContainer;
  final Color outline;
  final Color outlineVariant;
  final Color textPrimary;
  final Color textSecondary;
  final double shapeSm;
  final double shapeMd;
  final double shapeLg;
  final double shapeXl;
  final double spacingSm;
  final double spacingMd;
  final double spacingLg;

  const AppThemeExtension({
    required this.primary,
    required this.accent,
    required this.tertiary,
    required this.danger,
    required this.success,
    required this.warning,
    required this.surface,
    required this.surfaceContainer,
    required this.outline,
    required this.outlineVariant,
    required this.textPrimary,
    required this.textSecondary,
    required this.shapeSm,
    required this.shapeMd,
    required this.shapeLg,
    required this.shapeXl,
    required this.spacingSm,
    required this.spacingMd,
    required this.spacingLg,
  });

  static AppThemeExtension of(BuildContext context) {
    final ext = Theme.of(context).extension<AppThemeExtension>();
    return ext ?? const AppThemeExtension(
      primary: AppColors.primary,
      accent: AppColors.accent,
      tertiary: AppColors.tertiary,
      danger: AppColors.danger,
      success: AppColors.success,
      warning: AppColors.warning,
      surface: AppColors.surface,
      surfaceContainer: AppColors.surfaceContainer,
      outline: AppColors.outline,
      outlineVariant: AppColors.outlineVariant,
      textPrimary: AppColors.textPrimary,
      textSecondary: AppColors.textSecondary,
      shapeSm: Shapes.sm,
      shapeMd: Shapes.md,
      shapeLg: Shapes.lg,
      shapeXl: Shapes.xl,
      spacingSm: Spacing.sm,
      spacingMd: Spacing.md,
      spacingLg: Spacing.lg,
    );
  }

  @override
  ThemeExtension<AppThemeExtension> copyWith({
    Color? primary, Color? accent, Color? tertiary, Color? danger,
    Color? success, Color? warning, Color? surface, Color? surfaceContainer,
    Color? outline, Color? outlineVariant, Color? textPrimary, Color? textSecondary,
    double? shapeSm, double? shapeMd, double? shapeLg, double? shapeXl,
    double? spacingSm, double? spacingMd, double? spacingLg,
  }) {
    return AppThemeExtension(
      primary: primary ?? this.primary,
      accent: accent ?? this.accent,
      tertiary: tertiary ?? this.tertiary,
      danger: danger ?? this.danger,
      success: success ?? this.success,
      warning: warning ?? this.warning,
      surface: surface ?? this.surface,
      surfaceContainer: surfaceContainer ?? this.surfaceContainer,
      outline: outline ?? this.outline,
      outlineVariant: outlineVariant ?? this.outlineVariant,
      textPrimary: textPrimary ?? this.textPrimary,
      textSecondary: textSecondary ?? this.textSecondary,
      shapeSm: shapeSm ?? this.shapeSm,
      shapeMd: shapeMd ?? this.shapeMd,
      shapeLg: shapeLg ?? this.shapeLg,
      shapeXl: shapeXl ?? this.shapeXl,
      spacingSm: spacingSm ?? this.spacingSm,
      spacingMd: spacingMd ?? this.spacingMd,
      spacingLg: spacingLg ?? this.spacingLg,
    );
  }

  @override
  ThemeExtension<AppThemeExtension> lerp(
      covariant ThemeExtension<AppThemeExtension>? other, double t) {
    if (other is! AppThemeExtension) return this;
    return AppThemeExtension(
      primary: Color.lerp(primary, other.primary, t) ?? primary,
      accent: Color.lerp(accent, other.accent, t) ?? accent,
      tertiary: Color.lerp(tertiary, other.tertiary, t) ?? tertiary,
      danger: Color.lerp(danger, other.danger, t) ?? danger,
      success: Color.lerp(success, other.success, t) ?? success,
      warning: Color.lerp(warning, other.warning, t) ?? warning,
      surface: Color.lerp(surface, other.surface, t) ?? surface,
      surfaceContainer: Color.lerp(surfaceContainer, other.surfaceContainer, t) ?? surfaceContainer,
      outline: Color.lerp(outline, other.outline, t) ?? outline,
      outlineVariant: Color.lerp(outlineVariant, other.outlineVariant, t) ?? outlineVariant,
      textPrimary: Color.lerp(textPrimary, other.textPrimary, t) ?? textPrimary,
      textSecondary: Color.lerp(textSecondary, other.textSecondary, t) ?? textSecondary,
      shapeSm: lerpDouble(shapeSm, other.shapeSm, t) ?? shapeSm,
      shapeMd: lerpDouble(shapeMd, other.shapeMd, t) ?? shapeMd,
      shapeLg: lerpDouble(shapeLg, other.shapeLg, t) ?? shapeLg,
      shapeXl: lerpDouble(shapeXl, other.shapeXl, t) ?? shapeXl,
      spacingSm: lerpDouble(spacingSm, other.spacingSm, t) ?? spacingSm,
      spacingMd: lerpDouble(spacingMd, other.spacingMd, t) ?? spacingMd,
      spacingLg: lerpDouble(spacingLg, other.spacingLg, t) ?? spacingLg,
    );
  }

  @override
  String toString() => 'AppThemeExtension($runtimeType)';
}

// ── Light Theme ──────────────────────────────────────────────────
ThemeData get premiumTheme => _buildTheme(
  isDark: false,
  surface: DailyTokens.surface,
  surfaceContainer: DailyTokens.surfaceContainer,
  surfaceVariant: DailyTokens.surfaceVariant,
  outline: DailyTokens.outline,
  outlineVariant: DailyTokens.outlineVariant,
  textPrimary: DailyTokens.textPrimary,
  textSecondary: DailyTokens.textSecondary,
  primary: DailyTokens.primary,
  onPrimary: DailyTokens.onPrimary,
  primaryContainer: DailyTokens.primaryContainer,
  onPrimaryContainer: DailyTokens.onPrimaryContainer,
  accent: DailyTokens.accent,
  accentContainer: DailyTokens.accentContainer,
  tertiary: DailyTokens.tertiary,
  tertiaryContainer: DailyTokens.tertiaryContainer,
  onTertiary: DailyTokens.onTertiary,
  danger: DailyTokens.error,
  success: DailyTokens.success,
  warning: DailyTokens.warning,
);

// ── Dark Theme ───────────────────────────────────────────────────
ThemeData get premiumDarkTheme => _buildTheme(
  isDark: true,
  surface: DailyTokens.darkSurface,
  surfaceContainer: DailyTokens.darkSurfaceContainer,
  surfaceVariant: DailyTokens.darkSurfaceVariant,
  outline: DailyTokens.darkOutline,
  outlineVariant: DailyTokens.darkOutlineVariant,
  textPrimary: DailyTokens.darkTextPrimary,
  textSecondary: DailyTokens.darkTextSecondary,
  primary: DailyTokens.darkPrimary,
  onPrimary: DailyTokens.darkOnPrimary,
  primaryContainer: DailyTokens.darkPrimaryContainer,
  onPrimaryContainer: DailyTokens.darkOnPrimaryContainer,
  accent: DailyTokens.darkAccent,
  accentContainer: DailyTokens.darkAccentContainer,
  tertiary: DailyTokens.darkTertiary,
  tertiaryContainer: DailyTokens.darkTertiaryContainer,
  onTertiary: DailyTokens.darkOnTertiary,
  danger: DailyTokens.darkDanger,
  success: DailyTokens.darkSuccess,
  warning: DailyTokens.darkWarning,
);

// ── Shadow helpers ───────────────────────────────────────────────
extension ColorAlphaExt on Color {
  Color withAlpha(double a) => withValues(alpha: a);
}

ThemeData _buildTheme({
  required bool isDark,
  required Color surface,
  required Color surfaceContainer,
  required Color surfaceVariant,
  required Color outline,
  required Color outlineVariant,
  required Color textPrimary,
  required Color textSecondary,
  required Color primary,
  required Color onPrimary,
  required Color primaryContainer,
  required Color onPrimaryContainer,
  required Color accent,
  required Color accentContainer,
  required Color tertiary,
  required Color tertiaryContainer,
  required Color onTertiary,
  required Color danger,
  required Color success,
  required Color warning,
}) {
  return ThemeData(
    useMaterial3: true,
    brightness: isDark ? Brightness.dark : Brightness.light,
    extensions: [
      AppThemeExtension(
        primary: primary,
        accent: accent,
        tertiary: tertiary,
        danger: danger,
        success: success,
        warning: warning,
        surface: surface,
        surfaceContainer: surfaceContainer,
        outline: outline,
        outlineVariant: outlineVariant,
        textPrimary: textPrimary,
        textSecondary: textSecondary,
        shapeSm: Shapes.sm,
        shapeMd: Shapes.md,
        shapeLg: Shapes.lg,
        shapeXl: Shapes.xl,
        spacingSm: Spacing.sm,
        spacingMd: Spacing.md,
        spacingLg: Spacing.lg,
      ),
    ],
    colorScheme: ColorScheme(
      brightness: isDark ? Brightness.dark : Brightness.light,
      primary: primary,
      onPrimary: onPrimary,
      primaryContainer: primaryContainer,
      onPrimaryContainer: onPrimaryContainer,
      secondary: accent,
      onSecondary: onPrimary,
      secondaryContainer: accentContainer,
      onSecondaryContainer: textPrimary,
      tertiary: tertiary,
      onTertiary: onTertiary,
      tertiaryContainer: tertiaryContainer,
      onTertiaryContainer: onTertiary,
      error: danger,
      onError: onPrimary,
      errorContainer: danger.withValues(alpha: 0.15),
      onErrorContainer: danger,
      surface: surface,
      onSurface: textPrimary,
      onSurfaceVariant: outlineVariant,
      outline: outline,
      outlineVariant: outline,
      shadow: isDark ? DailyTokens.darkShadow : DailyTokens.shadowColor,
    ),
    appBarTheme: AppBarTheme(
      centerTitle: true,
      elevation: 0,
      scrolledUnderElevation: 1,
      backgroundColor: surface,
      foregroundColor: textPrimary,
      surfaceTintColor: Colors.transparent,
      titleTextStyle: const TextStyle(
        fontSize: 20, fontWeight: FontWeight.w600,
      ),
      iconTheme: IconThemeData(color: textPrimary),
    ),
    cardTheme: CardThemeData(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(Shapes.lg),
        side: BorderSide(color: surfaceVariant, width: 0.5),
      ),
      clipBehavior: Clip.antiAlias,
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(Shapes.md),
        ),
        elevation: 0,
        textStyle: const TextStyle(
          fontSize: 16, fontWeight: FontWeight.w600, letterSpacing: 0.5,
        ),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
        side: BorderSide(color: outlineVariant, width: 1),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(Shapes.md),
        ),
        textStyle: const TextStyle(
          fontSize: 14, fontWeight: FontWeight.w600, letterSpacing: 0.5,
        ),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: surfaceContainer,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(Shapes.md),
        borderSide: BorderSide(color: outline, width: 1),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(Shapes.md),
        borderSide: BorderSide(color: outline, width: 1),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(Shapes.md),
        borderSide: BorderSide(color: primary, width: 2),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(Shapes.md),
        borderSide: BorderSide(color: danger, width: 1.5),
      ),
      focusedErrorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(Shapes.md),
        borderSide: BorderSide(color: danger, width: 2),
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      labelStyle: TextStyle(color: outlineVariant),
      hintStyle: TextStyle(color: outline),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: surface,
      iconTheme: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.selected)) {
          return const IconThemeData(size: 24, color: DailyTokens.primary);
        }
        return const IconThemeData(size: 24, color: DailyTokens.outlineVariant);
      }),
      labelTextStyle: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.selected)) {
          return const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: DailyTokens.primary);
        }
        return const TextStyle(fontSize: 10, fontWeight: FontWeight.w400, color: DailyTokens.outlineVariant);
      }),
      elevation: 0,
      shadowColor: Colors.transparent,
    ),
    chipTheme: ChipThemeData(
      backgroundColor: surfaceContainer,
      selectedColor: accentContainer,
      labelStyle: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(Shapes.sm),
        side: BorderSide.none,
      ),
    ),
    dividerTheme: const DividerThemeData(
      color: DailyTokens.surfaceVariant,
      thickness: 0.5,
      space: 1,
    ),
    snackBarTheme: SnackBarThemeData(
      backgroundColor: DailyTokens.textPrimary,
      contentTextStyle: const TextStyle(color: Colors.white, fontSize: 14),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(Shapes.md)),
      behavior: SnackBarBehavior.floating,
    ),
    listTileTheme: const ListTileThemeData(
      contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      minVerticalPadding: 8,
      minLeadingWidth: 36,
    ),
    scrollbarTheme: ScrollbarThemeData(
      trackVisibility: const WidgetStatePropertyAll(true),
      trackColor: WidgetStatePropertyAll(outlineVariant.withValues(alpha: 0.2)),
      radius: const Radius.circular(4),
      thickness: WidgetStatePropertyAll(4),
    ),
  );
}

// ── Money Formatter ──────────────────────────────────────────────
String formatMoney(int amount) {
  if (amount < 0) {
    return '-\$${formatMoney(-amount)}';
  }
  final s = amount.toString();
  return s.replaceAllMapped(
    RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'),
    (m) => '${m[1]}.',
  );
}

// ── Premium Card ─────────────────────────────────────────────────
Widget premiumCard({
  required Widget child,
  Color? bgColor,
  EdgeInsetsGeometry? padding,
  VoidCallback? onTap,
}) {
  return Material(
    color: bgColor ?? AppColors.surface,
    elevation: 0,
    borderRadius: BorderRadius.circular(Shapes.lg),
    child: InkWell(
      borderRadius: BorderRadius.circular(Shapes.lg),
      onTap: onTap,
      child: Container(
        decoration: BoxDecoration(
          color: bgColor ?? AppColors.surface,
          borderRadius: BorderRadius.circular(Shapes.lg),
          border: Border.all(color: AppColors.surfaceVariant, width: 0.5),
        ),
        child: Padding(
          padding: padding ?? const EdgeInsets.all(16),
          child: child,
        ),
      ),
    ),
  );
}

// ── Compact Button ───────────────────────────────────────────────
Widget compactButton({
  required String label,
  required VoidCallback onPressed,
  Color? color,
  IconData? icon,
  bool isLoading = false,
  double? width,
}) {
  return SizedBox(
    width: width ?? double.infinity,
    height: 48,
    child: FilledButton.icon(
      style: FilledButton.styleFrom(
        backgroundColor: color ?? AppColors.primary,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(Shapes.md)),
        textStyle: const TextStyle(
          fontSize: 15, fontWeight: FontWeight.w600, letterSpacing: 0.5,
        ),
      ),
      onPressed: isLoading ? null : onPressed,
      icon: isLoading
          ? const SizedBox(width: 20, height: 20,
              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
          : (icon != null ? Icon(icon, size: 20) : const SizedBox()),
      label: Text(label),
    ),
  );
}

// ── Stat Row ─────────────────────────────────────────────────────
Widget statRow(String label, String value, {Color? valueColor}) {
  return Padding(
    padding: const EdgeInsets.symmetric(vertical: 3),
    child: Row(children: [
      Expanded(
        child: Text(label, style: const TextStyle(fontSize: 13, color: AppColors.outlineVariant)),
      ),
      Text(value, style: TextStyle(
        fontSize: 15, fontWeight: FontWeight.w600, color: valueColor,
      )),
    ]),
  );
}

// ── Section Title ────────────────────────────────────────────────
Widget sectionTitle(String title) {
  return Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Row(children: [
      Container(
        width: 3, height: 18,
        decoration: BoxDecoration(
          color: AppColors.accent,
          borderRadius: BorderRadius.circular(2),
        ),
      ),
      const SizedBox(width: 10),
      Text(title, style: const TextStyle(
        fontSize: 16, fontWeight: FontWeight.w600, color: AppColors.textPrimary,
      )),
    ]),
  );
}

// ── Status Colors ────────────────────────────────────────────────
class StatusColors {
  static const verde = DailyTokens.success;
  static const amarillo = DailyTokens.warning;
  static const rojo = DailyTokens.error;
  static const gris = DailyTokens.outlineVariant;
  static const azul = DailyTokens.primary;
}
