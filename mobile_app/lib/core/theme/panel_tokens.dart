import 'package:flutter/material.dart';

/// Barcha 3 panel (Teacher, Parent, Student) uchun umumiy dizayn tokenlar.
/// Har bir panel o'z accent rangiga ega, lekin card, spacing, radius umumiy.
abstract class PanelTokens {
  // ─── Card ────────────────────────────────────────────────────────────────
  static const double cardRadius = 16.0;
  static const double cardRadiusSm = 12.0;
  static const double cardRadiusLg = 20.0;

  // ─── Spacing ─────────────────────────────────────────────────────────────
  static const double screenPad = 16.0;
  static const double sectionGap = 20.0;
  static const double itemGap = 10.0;

  // ─── Typography ──────────────────────────────────────────────────────────
  static const double fontHero = 26.0;
  static const double fontTitle = 17.0;
  static const double fontSection = 15.0;
  static const double fontBody = 13.0;
  static const double fontCaption = 11.0;
  static const double fontMicro = 10.0;

  // ─── Shared semantic colors ───────────────────────────────────────────────
  static const Color success = Color(0xFF10B981);
  static const Color warning = Color(0xFFF59E0B);
  static const Color danger = Color(0xFFEF4444);
  static const Color info = Color(0xFF3B82F6);

  // ─── Role accent colors ───────────────────────────────────────────────────
  static const Color teacherAccent = Color(0xFF6366F1);    // indigo
  static const Color parentAccent  = Color(0xFF3B82F6);    // blue
  static const Color studentAccent = Color(0xFF10B981);    // emerald

  // ─── Dark bg ─────────────────────────────────────────────────────────────
  static const Color darkBg = Color(0xFF0B1220);
  static const Color darkSurface = Color(0xFF0F1B2A);
  static const Color darkCard = Color(0xFF162436);

  // ─── Light bg ────────────────────────────────────────────────────────────
  static const Color lightBg = Color(0xFFF5F7FB);
  static const Color lightCard = Colors.white;

  // ─── Helpers ─────────────────────────────────────────────────────────────
  static Color bg(bool isDark) => isDark ? darkBg : lightBg;
  static Color surface(bool isDark) => isDark ? darkSurface : lightCard;
  static Color card(bool isDark) => isDark ? darkCard : lightCard;
  static Color border(bool isDark) =>
      isDark ? Colors.white.withValues(alpha: 0.06) : Colors.black.withValues(alpha: 0.05);
  static Color text(bool isDark) =>
      isDark ? Colors.white : const Color(0xFF0F172A);
  static Color textMuted(bool isDark) =>
      isDark ? Colors.white54 : Colors.black54;
  static Color textFaint(bool isDark) =>
      isDark ? Colors.white30 : Colors.black26;

  static BoxDecoration cardDecoration(bool isDark, {Color? accent}) =>
      BoxDecoration(
        color: card(isDark),
        borderRadius: BorderRadius.circular(cardRadius),
        border: Border.all(color: border(isDark)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: isDark ? 0.12 : 0.04),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      );

  static BoxDecoration gradientCard(List<Color> colors, {double radius = 20}) =>
      BoxDecoration(
        gradient: LinearGradient(
          colors: colors,
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(radius),
        boxShadow: [
          BoxShadow(
            color: colors.first.withValues(alpha: 0.35),
            blurRadius: 24,
            offset: const Offset(0, 8),
          ),
        ],
      );
}
