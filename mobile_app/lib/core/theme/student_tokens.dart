import 'package:chaqmoq_mobile/core/design/ds_colors.dart';
import 'package:flutter/material.dart';

/// Context-aware o'quvchi palitrasi — Ds (Sky/Slate) bilan bir xil poydevor.
/// `StudentTokens.of(context)` orqali light/dark avtomatik tanlanadi.
class StudentTokens {
  const StudentTokens({
    required this.brightness,
    required this.bg,
    required this.bg2,
    required this.bg3,
    required this.surface,
    required this.surfaceElevated,
    required this.text,
    required this.textMuted,
    required this.textDim,
    required this.primary,
    required this.primarySoft,
    required this.primaryDeep,
    required this.onPrimary,
    required this.secondary,
    required this.secondarySoft,
    required this.danger,
    required this.warning,
    required this.success,
    required this.info,
    required this.border,
    required this.borderStrong,
    required this.glass,
    required this.glassStrong,
    required this.shadow,
    required this.heroGradient,
    required this.bgGradient,
    required this.primaryGradient,
    required this.violetGradient,
    required this.violetTealGradient,
  });

  final Brightness brightness;

  final Color bg;
  final Color bg2;
  final Color bg3;
  final Color surface;
  final Color surfaceElevated;

  final Color text;
  final Color textMuted;
  final Color textDim;

  final Color primary;
  final Color primarySoft;
  final Color primaryDeep;
  final Color onPrimary;
  final Color secondary;
  final Color secondarySoft;

  final Color danger;
  final Color warning;
  final Color success;
  final Color info;

  final Color border;
  final Color borderStrong;
  final Color glass;
  final Color glassStrong;
  final Color shadow;

  final LinearGradient heroGradient;
  final LinearGradient bgGradient;
  final LinearGradient primaryGradient;
  final LinearGradient violetGradient;
  final LinearGradient violetTealGradient;

  bool get isDark => brightness == Brightness.dark;

  Color get cardBg => isDark ? glassStrong : Colors.white;
  Color get cardBorder => isDark ? border : borderStrong;

  Color tonedSurface(Color base) {
    return base.withValues(alpha: isDark ? 0.18 : 0.12);
  }

  Color tonedBorder(Color base) {
    return base.withValues(alpha: isDark ? 0.32 : 0.24);
  }

  static const StudentTokens dark = StudentTokens(
    brightness: Brightness.dark,
    bg: DsPalette.slate900,
    bg2: Color(0xFF13233A),
    bg3: DsPalette.slate800,
    surface: Color(0xFF13233A),
    surfaceElevated: DsPalette.slate800,
    text: DsPalette.slate50,
    textMuted: DsPalette.slate400,
    textDim: DsPalette.slate500,
    primary: DsPalette.sky400,
    primarySoft: DsPalette.sky300,
    primaryDeep: DsPalette.sky500,
    onPrimary: DsPalette.slate900,
    secondary: Color(0xFF38BDF8),
    secondarySoft: Color(0xFFA5B4FC),
    danger: DsPalette.red400,
    warning: DsPalette.amber400,
    success: DsPalette.green400,
    info: DsPalette.sky400,
    border: DsPalette.slate700,
    borderStrong: DsPalette.slate600,
    glass: Color(0x0AFFFFFF),
    glassStrong: Color(0x12FFFFFF),
    shadow: Color(0x66000000),
    heroGradient: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0x380EA5E9), Color(0x2E6366F1), Color(0x05FFFFFF)],
      stops: [0, 0.6, 1],
    ),
    bgGradient: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [DsPalette.slate900, Color(0xFF13233A), DsPalette.slate900],
      stops: [0, 0.5, 1],
    ),
    primaryGradient: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [DsPalette.sky500, DsPalette.sky400],
    ),
    violetGradient: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFF0EA5E9), Color(0xFF38BDF8)],
    ),
    violetTealGradient: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFF0EA5E9), DsPalette.sky400],
    ),
  );

  static const StudentTokens light = StudentTokens(
    brightness: Brightness.light,
    bg: Color(0xFFEDF1F5),
    bg2: DsPalette.white,
    bg3: DsPalette.slate50,
    surface: DsPalette.white,
    surfaceElevated: DsPalette.white,
    text: DsPalette.slate900,
    textMuted: DsPalette.slate500,
    textDim: DsPalette.slate400,
    primary: DsPalette.sky500,
    primarySoft: DsPalette.sky400,
    primaryDeep: DsPalette.sky600,
    onPrimary: DsPalette.white,
    secondary: Color(0xFF0284C7),
    secondarySoft: Color(0xFF0EA5E9),
    danger: DsPalette.red500,
    warning: DsPalette.amber500,
    success: DsPalette.green500,
    info: DsPalette.sky500,
    border: DsPalette.slate200,
    borderStrong: DsPalette.slate300,
    glass: Color(0x080F172A),
    glassStrong: Color(0x0F0F172A),
    shadow: Color(0x14000000),
    heroGradient: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0x220EA5E9), Color(0x1F6366F1), Color(0x05FFFFFF)],
      stops: [0, 0.6, 1],
    ),
    bgGradient: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFFEDF1F5), DsPalette.slate50, Color(0xFFEDF1F5)],
      stops: [0, 0.5, 1],
    ),
    primaryGradient: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [DsPalette.sky500, DsPalette.sky400],
    ),
    violetGradient: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFF0284C7), Color(0xFF0EA5E9)],
    ),
    violetTealGradient: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFF0284C7), DsPalette.sky500],
    ),
  );

  static StudentTokens of(BuildContext context) {
    return Theme.of(context).brightness == Brightness.dark ? dark : light;
  }
}
