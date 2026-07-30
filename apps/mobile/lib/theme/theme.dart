// ─── Design Tokens — Material 3 Expressive ────────────────────────
// Principios: espacio eficiente, jerarquía clara, movimiento breve,
// sensación premium, componentes compactos, navegación simple.
//
// Identidad: azul petróleo (primario/confianza), verde esmeralda (acento/operación).

import 'package:flutter/material.dart';
import 'dart:ui';

// ── Color Tokens ─────────────────────────────────────────────────
class AppColors {
  // Primary — petrol blue
  static const primary = Color(0xFF1565C0);
  static const primaryLight = Color(0xFF42A5F5);
  static const primaryDark = Color(0xFF0D47A1);
  static const primaryContainer = Color(0xFFBBDEFB);
  static const onPrimaryContainer = Color(0xFF0A1929);

  // Accent — green emerald (operational)
  static const accent = Color(0xFF2E7D32);
  static const accentLight = Color(0xFF66BB6A);
  static const accentDark = Color(0xFF1B5E20);
  static const accentContainer = Color(0xFFC8E6C9);

  // Secondary — slate
  static const secondary = Color(0xFF455A64);
  static const secondaryLight = Color(0xFF78909C);
  static const secondaryDark = Color(0xFF263238);

  // Tertiary — amber
  static const tertiary = Color(0xFFF9A825);
  static const tertiaryLight = Color(0xFFFFD54F);
  static const tertiaryDark = Color(0xFFF57F17);

  // Semantic
  static const success = Color(0xFF2E7D32);
  static const warning = Color(0xFFF57F17);
  static const danger = Color(0xFFC62828);
  static const info = Color(0xFF1565C0);

  // Surface
  static const surface = Color(0xFFFDFDF7);
  static const surfaceContainer = Color(0xFFF5F5F0);
  static const surfaceVariant = Color(0xFFE7E0EC);
  static const outline = Color(0xFFCAC4D0);
  static const outlineVariant = Color(0xFF79747E);

  // Text
  static const textPrimary = Color(0xFF1C1B1F);
  static const textSecondary = Color(0xFF79747E);
  static const textDisabled = Color(0xFFCAC4D0);

  // Shadow
  static Color shadow = Colors.black.withOpacity(0.08);
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
  static const durationLong = Duration(milliseconds: 500);
  static const curveEmphasized = Curves.easeOutCubic;
  static const curveDecelerated = Curves.easeOut;
  static const curveElastic = Curves.elasticOut;
}

// ── Theme Extension (real ThemeExtension) ────────────────────────
// Extends ThemeExtension<AppThemeExtension> with copyWith and lerp.
// Accessible via context.extend<AppThemeExtension>().

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

  static const AppThemeExtension _default = AppThemeExtension(
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

  /// Access the theme extension from context.
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
    Color? primary,
    Color? accent,
    Color? tertiary,
    Color? danger,
    Color? success,
    Color? warning,
    Color? surface,
    Color? surfaceContainer,
    Color? outline,
    Color? outlineVariant,
    Color? textPrimary,
    Color? textSecondary,
    double? shapeSm,
    double? shapeMd,
    double? shapeLg,
    double? shapeXl,
    double? spacingSm,
    double? spacingMd,
    double? spacingLg,
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

// ── Premium ThemeData ────────────────────────────────────────────
final ThemeData premiumTheme = ThemeData(
  useMaterial3: true,
  extensions: [
    const AppThemeExtension(
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
    ),
  ],
  colorScheme: ColorScheme.fromSeed(
    seedColor: AppColors.primary,
    brightness: Brightness.light,
    primary: AppColors.primary,
    onPrimary: Colors.white,
    primaryContainer: AppColors.primaryContainer,
    onPrimaryContainer: AppColors.onPrimaryContainer,
    secondary: AppColors.secondary,
    onSecondary: Colors.white,
    secondaryContainer: AppColors.surfaceVariant,
    onSecondaryContainer: AppColors.textPrimary,
    tertiary: AppColors.tertiary,
    onTertiary: AppColors.tertiaryDark,
    tertiaryContainer: AppColors.tertiaryLight,
    onTertiaryContainer: AppColors.tertiaryDark,
    error: AppColors.danger,
    onError: Colors.white,
    errorContainer: AppColors.danger.withOpacity(0.15),
    onErrorContainer: AppColors.danger,
    surface: AppColors.surface,
    onSurface: AppColors.textPrimary,
    onSurfaceVariant: AppColors.outlineVariant,
    outline: AppColors.outline,
    outlineVariant: AppColors.outline,
    shadow: AppColors.shadow,
  ),

  // AppBar
  appBarTheme: const AppBarTheme(
    centerTitle: true,
    elevation: 0,
    scrolledUnderElevation: 1,
    backgroundColor: AppColors.surface,
    foregroundColor: AppColors.textPrimary,
    surfaceTintColor: Colors.transparent,
    titleTextStyle: TextStyle(
      fontSize: 20, fontWeight: FontWeight.w600, color: AppColors.textPrimary,
    ),
    iconTheme: IconThemeData(color: AppColors.textPrimary),
  ),

  // Cards
  cardTheme: CardThemeData(
    elevation: 0,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(16),
      side: const BorderSide(color: AppColors.surfaceVariant, width: 0.5),
    ),
    clipBehavior: Clip.antiAlias,
  ),

  // Filled buttons
  filledButtonTheme: FilledButtonThemeData(
    style: FilledButton.styleFrom(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
      elevation: 0,
      backgroundColor: AppColors.primary,
      textStyle: const TextStyle(
        fontSize: 16, fontWeight: FontWeight.w600, letterSpacing: 0.5,
      ),
    ),
  ),

  // Outlined buttons
  outlinedButtonTheme: OutlinedButtonThemeData(
    style: OutlinedButton.styleFrom(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
      side: const BorderSide(color: AppColors.outlineVariant, width: 1),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
      textStyle: const TextStyle(
        fontSize: 14, fontWeight: FontWeight.w600, letterSpacing: 0.5,
      ),
    ),
  ),

  // Text fields
  inputDecorationTheme: InputDecorationTheme(
    filled: true,
    fillColor: AppColors.surfaceContainer,
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: const BorderSide(color: AppColors.outline, width: 1),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: const BorderSide(color: AppColors.outline, width: 1),
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: const BorderSide(color: AppColors.primary, width: 2),
    ),
    errorBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: const BorderSide(color: AppColors.danger, width: 1.5),
    ),
    focusedErrorBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: const BorderSide(color: AppColors.danger, width: 2),
    ),
    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
    labelStyle: const TextStyle(color: AppColors.outlineVariant),
    hintStyle: const TextStyle(color: AppColors.outline),
  ),

  // Bottom navigation
  navigationBarTheme: NavigationBarThemeData(
    backgroundColor: AppColors.surface,
    iconTheme: WidgetStateProperty.resolveWith((states) {
      if (states.contains(WidgetState.selected)) {
        return const IconThemeData(size: 24, color: AppColors.primary);
      }
      return const IconThemeData(size: 24, color: AppColors.outlineVariant);
    }),
    labelTextStyle: WidgetStateProperty.resolveWith((states) {
      if (states.contains(WidgetState.selected)) {
        return const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppColors.primary);
      }
      return const TextStyle(fontSize: 10, fontWeight: FontWeight.w400, color: AppColors.outlineVariant);
    }),
    elevation: 0,
    shadowColor: Colors.transparent,
  ),

  // Chips
  chipTheme: ChipThemeData(
    backgroundColor: AppColors.surfaceContainer,
    selectedColor: AppColors.accentContainer,
    labelStyle: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500),
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(8),
      side: BorderSide.none,
    ),
  ),

  // Dividers
  dividerTheme: const DividerThemeData(
    color: AppColors.surfaceVariant,
    thickness: 0.5,
    space: 1,
  ),

  // Snack bars
  snackBarTheme: SnackBarThemeData(
    backgroundColor: const Color(0xFF1C1B1F),
    contentTextStyle: const TextStyle(color: Colors.white, fontSize: 14),
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
    behavior: SnackBarBehavior.floating,
  ),

  // List tiles
  listTileTheme: const ListTileThemeData(
    contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 4),
    minVerticalPadding: 8,
    minLeadingWidth: 36,
  ),

  // Scrollbar
  scrollbarTheme: ScrollbarThemeData(
    trackVisibility: const WidgetStatePropertyAll(true),
    trackColor: WidgetStatePropertyAll(AppColors.outlineVariant.withOpacity(0.2)),
    radius: const Radius.circular(4),
    thickness: WidgetStatePropertyAll(4),
  ),
);

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
    borderRadius: BorderRadius.circular(16),
    child: InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: onTap,
      child: Container(
        decoration: BoxDecoration(
          color: bgColor ?? AppColors.surface,
          borderRadius: BorderRadius.circular(16),
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
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
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
  static const verde = Color(0xFF2E7D32);
  static const amarillo = Color(0xFFF9A825);
  static const rojo = Color(0xFFC62828);
  static const gris = Color(0xFF9E9E9E);
  static const azul = Color(0xFF1565C0);
}
