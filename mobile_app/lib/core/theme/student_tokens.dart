import 'package:flutter/material.dart';

/// Context-aware student palette. Use `StudentTokens.of(context)` inside any
/// student-panel widget — the right palette is picked from
/// `Theme.of(context).brightness`, so a single rebuild flips light/dark.
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

  // Surfaces
  final Color bg;
  final Color bg2;
  final Color bg3;
  final Color surface;
  final Color surfaceElevated;

  // Text
  final Color text;
  final Color textMuted;
  final Color textDim;

  // Brand
  final Color primary;
  final Color primarySoft;
  final Color primaryDeep;
  final Color onPrimary;
  final Color secondary;
  final Color secondarySoft;

  // Semantic
  final Color danger;
  final Color warning;
  final Color success;
  final Color info;

  // Glass / borders
  final Color border;
  final Color borderStrong;
  final Color glass;
  final Color glassStrong;
  final Color shadow;

  // Gradients
  final LinearGradient heroGradient;
  final LinearGradient bgGradient;
  final LinearGradient primaryGradient;
  final LinearGradient violetGradient;
  final LinearGradient violetTealGradient;

  bool get isDark => brightness == Brightness.dark;

  Color get cardBg => isDark ? glassStrong : Colors.white;
  Color get cardBorder => isDark ? border : borderStrong;

  /// Tone-tinted surfaces used by metric tile icon backgrounds.
  Color tonedSurface(Color base) {
    return base.withValues(alpha: isDark ? 0.18 : 0.12);
  }

  /// Outline used on accent borders — softer in light mode.
  Color tonedBorder(Color base) {
    return base.withValues(alpha: isDark ? 0.32 : 0.24);
  }

  static const StudentTokens dark = StudentTokens(
    brightness: Brightness.dark,
    bg: Color(0xFF0A0A0F),
    bg2: Color(0xFF13131A),
    bg3: Color(0xFF1A1A24),
    surface: Color(0xFF161622),
    surfaceElevated: Color(0xFF1E1E2C),
    text: Color(0xFFF1F2F6),
    textMuted: Color(0xFF8892A4),
    textDim: Color(0xFF5A6478),
    primary: Color(0xFF00D4AA),
    primarySoft: Color(0xFF2BE5BF),
    primaryDeep: Color(0xFF00A88A),
    onPrimary: Color(0xFF0A1F1A),
    secondary: Color(0xFF6C63FF),
    secondarySoft: Color(0xFF8C85FF),
    danger: Color(0xFFFF4757),
    warning: Color(0xFFFFA502),
    success: Color(0xFF2ED573),
    info: Color(0xFF4FC3F7),
    border: Color(0x14FFFFFF),
    borderStrong: Color(0x24FFFFFF),
    glass: Color(0x0AFFFFFF),
    glassStrong: Color(0x12FFFFFF),
    shadow: Color(0x66000000),
    heroGradient: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0x3800D4AA), Color(0x2E6C63FF), Color(0x05FFFFFF)],
      stops: [0, 0.6, 1],
    ),
    bgGradient: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFF0A0A0F), Color(0xFF131322), Color(0xFF0A0A0F)],
      stops: [0, 0.5, 1],
    ),
    primaryGradient: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFF00D4AA), Color(0xFF2BE5BF)],
    ),
    violetGradient: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFF6C63FF), Color(0xFF8C85FF)],
    ),
    violetTealGradient: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFF6C63FF), Color(0xFF00D4AA)],
    ),
  );

  static const StudentTokens light = StudentTokens(
    brightness: Brightness.light,
    bg: Color(0xFFF5F7FB),
    bg2: Color(0xFFFFFFFF),
    bg3: Color(0xFFEDF1F7),
    surface: Color(0xFFFFFFFF),
    surfaceElevated: Color(0xFFFAFBFD),
    text: Color(0xFF0E1422),
    textMuted: Color(0xFF5F6B7E),
    textDim: Color(0xFF93A1B5),
    primary: Color(0xFF00A88A),
    primarySoft: Color(0xFF1AC0A1),
    primaryDeep: Color(0xFF008A72),
    onPrimary: Color(0xFFFFFFFF),
    secondary: Color(0xFF5B53E0),
    secondarySoft: Color(0xFF7B73F2),
    danger: Color(0xFFE63946),
    warning: Color(0xFFE07A00),
    success: Color(0xFF1A9D6A),
    info: Color(0xFF1B97D8),
    border: Color(0x140E1422),
    borderStrong: Color(0x240E1422),
    glass: Color(0x080E1422),
    glassStrong: Color(0x0F0E1422),
    shadow: Color(0x14000000),
    heroGradient: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0x2200A88A), Color(0x1F5B53E0), Color(0x05FFFFFF)],
      stops: [0, 0.6, 1],
    ),
    bgGradient: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFFF5F7FB), Color(0xFFEDF1F7), Color(0xFFF5F7FB)],
      stops: [0, 0.5, 1],
    ),
    primaryGradient: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFF00A88A), Color(0xFF1AC0A1)],
    ),
    violetGradient: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFF5B53E0), Color(0xFF7B73F2)],
    ),
    violetTealGradient: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFF5B53E0), Color(0xFF00A88A)],
    ),
  );

  static StudentTokens of(BuildContext context) {
    return Theme.of(context).brightness == Brightness.dark ? dark : light;
  }
}
