// ─── Design Tokens — Material 3 Expressive ─────────────────────────
// Principios: espacio eficiente, jerarquía clara, movimiento breve,
// sensación premium, componentes compactos, navegación simple.

import 'package:flutter/material.dart';

// ── Color Scheme ──────────────────────────────────────────────────
// Paleta inspirada en aplicaciones financieras modernas:
// - Primario: verde esmeralda (confianza, crecimiento)
// - Secundario: slate (neutralidad, profesionalismo)
// - Acento: ámbar (alertas, acciones)
// - Superficies: grises cálidos, no fríos

final ColorScheme _colorScheme = ColorScheme.fromSeed(
  seedColor: const Color(0xFF1B5E20), // verde oscuro premium
  brightness: Brightness.light,
  primary: const Color(0xFF2E7D32),
  onPrimary: Colors.white,
  primaryContainer: const Color(0xFFA5D6A7),
  onPrimaryContainer: const Color(0xFF0A2E0E),
  secondary: const Color(0xFF455A64),
  onSecondary: Colors.white,
  secondaryContainer: const Color(0xFFB0C4CE),
  onSecondaryContainer: const Color(0xFF1A2A30),
  tertiary: const Color(0xFFF9A825),
  onTertiary: const Color(0xFF3E2C00),
  tertiaryContainer: const Color(0xFFFFD973),
  onTertiaryContainer: const Color(0xFF3E2C00),
  error: const Color(0xFFC62828),
  onError: Colors.white,
  errorContainer: const Color(0xFFEF9A9A),
  onErrorContainer: const Color(0xFF410002),
  surface: const Color(0xFFFDFDF7),
  onSurface: const Color(0xFF1C1B1F),
  onSurfaceVariant: const Color(0xFF49454F),
  surfaceVariant: const Color(0xFFE7E0EC),
  outline: const Color(0xFF79747E),
  outlineVariant: const Color(0xFFCAC4D0),
  shadow: Colors.black.withOpacity(0.08),
);

// ── Typography Scale ──────────────────────────────────────────────
// Jerarquía clara: título > subtítulo > cuerpo > caption
final ThemeData premiumTheme = ThemeData(
  useMaterial3: true,
  colorScheme: _colorScheme,

  // Tipografía: texto legible en sol, una mano, TalkBack
  textTheme: const TextTheme(
    displayLarge: TextStyle(
      fontSize: 32, fontWeight: FontWeight.w600, height: 1.2,
      letterSpacing: -0.5,
    ),
    displayMedium: TextStyle(
      fontSize: 28, fontWeight: FontWeight.w600, height: 1.2,
      letterSpacing: -0.3,
    ),
    headlineLarge: TextStyle(
      fontSize: 24, fontWeight: FontWeight.w600, height: 1.3,
    ),
    headlineMedium: TextStyle(
      fontSize: 20, fontWeight: FontWeight.w500, height: 1.3,
    ),
    titleLarge: TextStyle(
      fontSize: 18, fontWeight: FontWeight.w500, height: 1.4,
    ),
    titleMedium: TextStyle(
      fontSize: 16, fontWeight: FontWeight.w500, height: 1.4,
    ),
    bodyLarge: TextStyle(
      fontSize: 16, fontWeight: FontWeight.w400, height: 1.5,
    ),
    bodyMedium: TextStyle(
      fontSize: 14, fontWeight: FontWeight.w400, height: 1.5,
    ),
    bodySmall: TextStyle(
      fontSize: 12, fontWeight: FontWeight.w400, height: 1.4,
      color: Color(0xFF79747E),
    ),
    labelLarge: TextStyle(
      fontSize: 14, fontWeight: FontWeight.w600, height: 1.4,
      letterSpacing: 0.5,
    ),
    labelMedium: TextStyle(
      fontSize: 12, fontWeight: FontWeight.w600, height: 1.4,
      letterSpacing: 0.5,
    ),
  ),

  // AppBar: flotante, sutil, sin bordes duros
  appBarTheme: const AppBarTheme(
    centerTitle: true,
    elevation: 0,
    scrolledUnderElevation: 1,
    backgroundColor: Color(0xFFFDFDF7),
    foregroundColor: Color(0xFF1C1B1F),
    surfaceTintColor: Colors.transparent,
    titleTextStyle: TextStyle(
      fontSize: 20, fontWeight: FontWeight.w600, color: Color(0xFF1C1B1F),
    ),
    iconTheme: IconThemeData(color: Color(0xFF1C1B1F)),
  ),

  // Cards: bordes suaves, sombra sutil, padding generoso
  cardTheme: CardThemeData(
    elevation: 0,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(16),
      side: const BorderSide(color: Color(0xFFE7E0EC), width: 0.5),
    ),
    clipBehavior: Clip.antiAlias,
  ),

  // Botones: compactos, redondeados, con micro-interacción
  filledButtonTheme: FilledButtonThemeData(
    style: FilledButton.styleFrom(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
      elevation: 0,
      textStyle: const TextStyle(
        fontSize: 16, fontWeight: FontWeight.w600, letterSpacing: 0.5,
      ),
    ),
  ),

  // Outlined buttons
  outlinedButtonTheme: OutlinedButtonThemeData(
    style: OutlinedButton.styleFrom(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
      side: const BorderSide(color: Color(0xFF79747E), width: 1),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
      textStyle: const TextStyle(
        fontSize: 14, fontWeight: FontWeight.w600, letterSpacing: 0.5,
      ),
    ),
  ),

  // Text fields: estilo outlined premium
  inputDecorationTheme: InputDecorationTheme(
    filled: true,
    fillColor: const Color(0xFFF5F5F0),
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: const BorderSide(color: Color(0xFFCAC4D0), width: 1),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: const BorderSide(color: Color(0xFFCAC4D0), width: 1),
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: const BorderSide(color: Color(0xFF2E7D32), width: 2),
    ),
    errorBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: const BorderSide(color: Color(0xFFC62828), width: 1.5),
    ),
    focusedErrorBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: const BorderSide(color: Color(0xFFC62828), width: 2),
    ),
    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
    labelStyle: const TextStyle(color: Color(0xFF79747E)),
    hintStyle: const TextStyle(color: Color(0xFFCAC4D0)),
  ),

  // Bottom navigation: elegante, compacto
  bottomNavigationBarTheme: const BottomNavigationBarThemeData(
    type: BottomNavigationBarType.fixed,
    backgroundColor: Color(0xFFFDFDF7),
    selectedItemColor: Color(0xFF2E7D32),
    unselectedItemColor: Color(0xFF79747E),
    selectedLabelStyle: TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
    unselectedLabelStyle: TextStyle(fontSize: 10, fontWeight: FontWeight.w400),
    elevation: 0,
    selectedIconTheme: IconThemeData(size: 24),
    unselectedIconTheme: IconThemeData(size: 24, color: Color(0xFF79747E)),
  ),

  // Chip: compacto, informativo
  chipTheme: ChipThemeData(
    backgroundColor: const Color(0xFFF5F5F0),
    selectedColor: const Color(0xFFA5D6A7),
    labelStyle: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500),
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(8),
      side: BorderSide.none,
    ),
  ),

  // Divider: sutil
  dividerTheme: const DividerThemeData(
    color: Color(0xFFE7E0EC),
    thickness: 0.5,
    space: 1,
  ),

  // SnackBar: premium, no intrusivo
  snackBarTheme: SnackBarThemeData(
    backgroundColor: const Color(0xFF1C1B1F),
    contentTextStyle: const TextStyle(color: Colors.white, fontSize: 14),
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
    behavior: SnackBarBehavior.floating,
  ),

  // List tile: compacto, limpio
  listTileTheme: const ListTileThemeData(
    contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 4),
    minVerticalPadding: 8,
    minLeadingWidth: 36,
  ),

  // Scrollbar: sutil
  scrollbarTheme: ScrollbarThemeData(
    trackVisibility: const WidgetStatePropertyAll(true),
    trackColor: WidgetStatePropertyAll(Color(0xFF79747E).withOpacity(0.2)),
    radius: const Radius.circular(4),
    thickness: WidgetStatePropertyAll(4),
  ),
);

// ── Shape Tokens ──────────────────────────────────────────────────
class Shapes {
  static const sm = Radius.circular(8);
  static const md = Radius.circular(12);
  static const lg = Radius.circular(16);
  static const xl = Radius.circular(24);
}

// ── Spacing Tokens ────────────────────────────────────────────────
class Spacing {
  static const xs = 4.0;
  static const sm = 8.0;
  static const md = 16.0;
  static const lg = 24.0;
  static const xl = 32.0;
  static const xxl = 48.0;
}

// ── Status Colors ─────────────────────────────────────────────────
class StatusColors {
  static const verdel = Color(0xFF2E7D32);
  static const amarillo = Color(0xFFF9A825);
  static const rojo = Color(0xFFC62828);
  static const gris = Color(0xFF9E9E9E);
  static const azul = Color(0xFF1565C0);
}

// ── Money Formatter ───────────────────────────────────────────────
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

// ── Premium Card ──────────────────────────────────────────────────
Widget premiumCard({
  required Widget child,
  Color? bgColor,
  EdgeInsetsGeometry? padding,
  VoidCallback? onTap,
}) {
  return Material(
    color: bgColor ?? const Color(0xFFFDFDF7),
    elevation: 0,
    borderRadius: BorderRadius.circular(16),
    child: InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: onTap,
      child: Container(
        decoration: BoxDecoration(
          color: bgColor ?? const Color(0xFFFDFDF7),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: const Color(0xFFE7E0EC), width: 0.5),
        ),
        child: Padding(
          padding: padding ?? const EdgeInsets.all(16),
          child: child,
        ),
      ),
    ),
  );
}

// ── Compact Button ────────────────────────────────────────────────
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
        backgroundColor: color,
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

// ── Stat Row ──────────────────────────────────────────────────────
Widget statRow(String label, String value, {Color? valueColor}) {
  return Padding(
    padding: const EdgeInsets.symmetric(vertical: 3),
    child: Row(children: [
      Expanded(
        child: Text(label, style: const TextStyle(fontSize: 13, color: Color(0xFF79747E))),
      ),
      Text(value, style: TextStyle(
        fontSize: 15, fontWeight: FontWeight.w600, color: valueColor,
      )),
    ]),
  );
}

// ── Section Title ─────────────────────────────────────────────────
Widget sectionTitle(String title) {
  return Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Row(children: [
      Container(
        width: 3, height: 18,
        decoration: BoxDecoration(
          color: const Color(0xFF2E7D32),
          borderRadius: BorderRadius.circular(2),
        ),
      ),
      const SizedBox(width: 10),
      Text(title, style: const TextStyle(
        fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF1C1B1F),
      )),
    ]),
  );
}
