// ignore: file_names
// GENERATED FILE — do not edit manually.
// Run: dart run tool/generate_design_tokens.dart

import 'package:flutter/widgets.dart';

// ─── Design Tokens — Daily System ────────────────────────────────
// Auto-generated from design/tokens/daily-system.tokens.json

class DailyTokens {
  DailyTokens._();

  // ═══ Light Mode Colors ═══
  // Petrol blue — trust, main brand
  static const Color primary = Color(0xFF0B4654);
  // Elevated petrol
  static const Color primaryLight = Color(0xFF125466);
  // Deep petrol for dark mode
  static const Color primaryDark = Color(0xFF083340);
  // Primary container light
  static const Color primaryContainer = Color(0xFFB0D4DE);
  // Text on primary
  static const Color onPrimary = Color(0xFFFFFFFF);
  // Text on primary container
  static const Color onPrimaryContainer = Color(0xFF071920);
  // Operational emerald
  static const Color accent = Color(0xFF0F6B55);
  // Elevated emerald
  static const Color accentLight = Color(0xFF14916F);
  // Accent container light
  static const Color accentContainer = Color(0xFFB2DFD6);
  // Text on accent
  static const Color onAccent = Color(0xFFFFFFFF);
  // Gold emphasis — premium detail
  static const Color tertiary = Color(0xFFD7A33D);
  // Light gold
  static const Color tertiaryLight = Color(0xFFE8C568);
  // Dark gold
  static const Color tertiaryDark = Color(0xFF9A7328);
  // Tertiary container
  static const Color tertiaryContainer = Color(0xFFF5E6C8);
  // Text on tertiary
  static const Color onTertiary = Color(0xFF3D2E0A);
  // Success green
  static const Color success = Color(0xFF0F6B55);
  static const Color successContainer = Color(0xFFC8E6C9);
  static const Color onSuccess = Color(0xFFFFFFFF);
  // Warning amber
  static const Color warning = Color(0xFF8A5A00);
  static const Color warningContainer = Color(0xFFFFF3CD);
  static const Color onWarning = Color(0xFF3D2E0A);
  // Error red
  static const Color error = Color(0xFFB3261E);
  static const Color errorContainer = Color(0xFFF9DEDC);
  static const Color onError = Color(0xFFFFFFFF);
  // Light background
  static const Color surface = Color(0xFFF6F8F7);
  // Surface container
  static const Color surfaceContainer = Color(0xFFEDEDED);
  // Surface variant / borders
  static const Color surfaceVariant = Color(0xFFE0E0E0);
  // Outline border
  static const Color outline = Color(0xFFB0B0B0);
  // Outline variant / secondary text
  static const Color outlineVariant = Color(0xFF797979);
  // Primary text
  static const Color textPrimary = Color(0xFF17242B);
  // Secondary text
  static const Color textSecondary = Color(0xFF5F6368);
  // Disabled text
  static const Color textDisabled = Color(0xFFB0B0B0);
  static const Color shadow = Color(0x14000000);
  static Color shadowWithAlpha(double a) => shadow.withValues(alpha: a);
  static const Color overlay = Color(0x4D000000);
  static Color overlayWithAlpha(double a) => overlay.withValues(alpha: a);

  // ═══ Dark Mode Colors ═══
  // Light mode primary inverted
  static const Color darkprimary = Color(0xFF8CD4E8);
  // Lighter primary
  static const Color darkprimaryLight = Color(0xFFA8DFF0);
  // Darker primary
  static const Color darkprimaryDark = Color(0xFF5BB8D4);
  // Primary container dark
  static const Color darkprimaryContainer = Color(0xFF0B4654);
  // Text on primary dark
  static const Color darkonPrimary = Color(0xFF071920);
  // Text on primary container dark
  static const Color darkonPrimaryContainer = Color(0xFFB0D4DE);
  // Light mode accent inverted
  static const Color darkaccent = Color(0xFF7ED8C0);
  // Lighter accent
  static const Color darkaccentLight = Color(0xFFA0E8D6);
  // Accent container dark
  static const Color darkaccentContainer = Color(0xFF0F6B55);
  // Text on accent dark
  static const Color darkonAccent = Color(0xFF072A1F);
  // Gold emphasis light
  static const Color darktertiary = Color(0xFFE8C568);
  // Lighter gold
  static const Color darktertiaryLight = Color(0xFFF0D88A);
  // Dark gold
  static const Color darktertiaryDark = Color(0xFFD7A33D);
  // Tertiary container dark
  static const Color darktertiaryContainer = Color(0xFF5A4418);
  // Text on tertiary dark
  static const Color darkonTertiary = Color(0xFF3D2E0A);
  // Success light
  static const Color darksuccess = Color(0xFF7ED8C0);
  static const Color darksuccessContainer = Color(0xFF0F6B55);
  static const Color darkonSuccess = Color(0xFF072A1F);
  // Warning light
  static const Color darkwarning = Color(0xFFF0D88A);
  static const Color darkwarningContainer = Color(0xFF5A4418);
  static const Color darkonWarning = Color(0xFF3D2E0A);
  // Error light
  static const Color darkerror = Color(0xFFF29993);
  static const Color darkerrorContainer = Color(0xFF8C1D18);
  static const Color darkonError = Color(0xFF690E0A);
  // Dark background
  static const Color darksurface = Color(0xFF0E1A21);
  // Dark surface container
  static const Color darksurfaceContainer = Color(0xFF17242B);
  // Dark surface variant
  static const Color darksurfaceVariant = Color(0xFF3A4A52);
  // Dark outline
  static const Color darkoutline = Color(0xFF5A6A72);
  // Dark outline variant
  static const Color darkoutlineVariant = Color(0xFF798A92);
  // Primary text dark
  static const Color darktextPrimary = Color(0xFFE0E0E0);
  // Secondary text dark
  static const Color darktextSecondary = Color(0xFF9AA0A6);
  // Disabled text dark
  static const Color darktextDisabled = Color(0xFF5A6A72);
  static const Color darkshadow = Color(0xFF000000);
  static const Color darkoverlay = Color(0xFF000000);

  // ═══ Dark Theme Convenience Colors ═══
  static Color get darkSurface => darksurface;
  static Color get darkSurfaceContainer => darksurfaceContainer;
  static Color get darkSurfaceVariant => darksurfaceVariant;
  static Color get darkOutline => darkoutline;
  static Color get darkOutlineVariant => darkoutlineVariant;
  static Color get darkTextPrimary => darktextPrimary;
  static Color get darkTextSecondary => darktextSecondary;
  static Color get darkTextDisabled => darktextDisabled;
  static Color get darkPrimary => darkprimary;
  static Color get darkOnPrimary => darkonPrimary;
  static Color get darkPrimaryContainer => darkprimaryContainer;
  static Color get darkOnPrimaryContainer => darkonPrimaryContainer;
  static Color get darkAccent => darkaccent;
  static Color get darkAccentContainer => darkaccentContainer;
  static Color get darkTertiary => darktertiary;
  static Color get darkTertiaryContainer => darktertiaryContainer;
  static Color get darkOnTertiary => darkonTertiary;
  static Color get darkDanger => darkerror;
  static Color get darkSuccess => darksuccess;
  static Color get darkWarning => darkwarning;
  static Color get darkShadow => const Color(0x000000);
  static Color get shadowColor => shadow.withValues(alpha: 0.08);

  // ═══ Shapes ═══
  static const double shapeSM = 8.0;
  static const double shapeMD = 12.0;
  static const double shapeLG = 16.0;
  static const double shapeXL = 24.0;

  // ═══ Spacing ═══
  static const double spacingXS = 4.0;
  static const double spacingSM = 8.0;
  static const double spacingMD = 16.0;
  static const double spacingLG = 24.0;
  static const double spacingXL = 32.0;
  static const double spacingXXL = 48.0;

  // ═══ Motion ═══
  static const Duration fast = Duration(milliseconds: 150);
  static const Duration normal = Duration(milliseconds: 250);
  static const Duration long = Duration(milliseconds: 400);
  static final curveEmphasized = Curves.easeOutCubic;
  static final curveDecelerated = Curves.easeOut;

  // ═══ Typography ═══
  static const String fontFamily = "Inter Variable";
  static const bool tabularNumbers = true;

  // Typography scales
  static const displayTextStyle = TextStyle(
    fontSize: 32,
    fontWeight: FontWeight.w700,
    height: 1.1875,
  );
  static const headlineTextStyle = TextStyle(
    fontSize: 26,
    fontWeight: FontWeight.w700,
    height: 1.2307692307692308,
  );
  static const titleLTextStyle = TextStyle(
    fontSize: 20,
    fontWeight: FontWeight.w600,
    height: 1.3,
  );
  static const titleMTextStyle = TextStyle(
    fontSize: 17,
    fontWeight: FontWeight.w600,
    height: 1.2941176470588236,
  );
  static const bodyLTextStyle = TextStyle(
    fontSize: 16,
    fontWeight: FontWeight.w400,
    height: 1.5,
  );
  static const bodyMTextStyle = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w400,
    height: 1.4285714285714286,
  );
  static const labelLTextStyle = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w600,
    height: 1.2857142857142858,
  );
  static const labelMTextStyle = TextStyle(
    fontSize: 12,
    fontWeight: FontWeight.w600,
    height: 1.3333333333333333,
  );
  static const moneyHeroTextStyle = TextStyle(
    fontSize: 32,
    fontWeight: FontWeight.w700,
    height: 1.1875,
    fontFeatures: const [FontFeature.tabularFigures()],
  );
  static const moneyNormalTextStyle = TextStyle(
    fontSize: 18,
    fontWeight: FontWeight.w700,
    height: 1.3333333333333333,
    fontFeatures: const [FontFeature.tabularFigures()],
  );

  // ═══ Breakpoints (dp) ═══
  static const int compactBreakpoint = 599;
  static const int mediumBreakpoint = 600;
  static const int expandedBreakpoint = 840;

  // ═══ UI States ═══
  // loading: Skeleton geometry matching content
  // empty: Empty state with illustration + CTA
  // error: Recoverable error with explanation + retry
  // offline: Saved locally, pending sync
  // syncing: Sync in progress
  // synced: All synced
  // success: Action completed
}
