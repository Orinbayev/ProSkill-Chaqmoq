import 'package:chaqmoq_mobile/core/design/ds_colors.dart';
import 'package:chaqmoq_mobile/core/design/ds_tokens.dart';
import 'package:flutter/material.dart';

/// Barcha rollar (Teacher, Parent, Student, Manager, Director) uchun
/// umumiy dizayn tokenlar — "Chaqmoq Panellar" (Sky/Slate).
///
/// Accent faqat rol "badge"/chip uchun biroz farq qiladi; card, spacing,
/// radius, bg, text — hammasi bir xil.
abstract class PanelTokens {
  // ─── Card ────────────────────────────────────────────────────────────────
  static const double cardRadius = DsRadius.card;
  static const double cardRadiusSm = DsRadius.md;
  static const double cardRadiusLg = DsRadius.lg;

  // ─── Spacing ─────────────────────────────────────────────────────────────
  static const double screenPad = DsSpace.screen;
  static const double sectionGap = DsSpace.section;
  static const double itemGap = DsSpace.item;

  // ─── Typography ──────────────────────────────────────────────────────────
  static const double fontHero = 26.0;
  static const double fontTitle = 17.0;
  static const double fontSection = 15.0;
  static const double fontBody = 13.0;
  static const double fontCaption = 11.0;
  static const double fontMicro = 10.0;

  // ─── Shared semantic colors ───────────────────────────────────────────────
  static const Color success = DsPalette.green500;
  static const Color warning = DsPalette.amber500;
  static const Color danger = DsPalette.red500;
  static const Color info = DsPalette.sky500;

  // ─── Role accent (primary = Sky family; secondary tint for identity) ──────
  static const Color directorAccent = DsPalette.sky500;
  static const Color managerAccent = DsPalette.sky600;
  static const Color teacherAccent = DsPalette.sky500;
  static const Color parentAccent = DsPalette.sky500;
  static const Color studentAccent = DsPalette.sky500;

  // ─── Dark / light (Ds bilan bir xil) ─────────────────────────────────────
  static const Color darkBg = DsPalette.slate900;
  static const Color darkSurface = Color(0xFF13233A);
  static const Color darkCard = DsPalette.slate800;

  static const Color lightBg = Color(0xFFEDF1F5);
  static const Color lightCard = DsPalette.white;

  static Color bg(bool isDark) => isDark ? darkBg : lightBg;
  static Color surface(bool isDark) => isDark ? darkSurface : lightCard;
  static Color card(bool isDark) => isDark ? darkCard : lightCard;
  static Color border(bool isDark) =>
      isDark ? DsPalette.slate700 : DsPalette.slate200;
  static Color text(bool isDark) =>
      isDark ? DsPalette.slate50 : DsPalette.slate900;
  static Color textMuted(bool isDark) =>
      isDark ? DsPalette.slate400 : DsPalette.slate500;
  static Color textFaint(bool isDark) =>
      isDark ? DsPalette.slate500 : DsPalette.slate400;

  static Color accentForRole(String role) {
    switch (role.trim().toLowerCase()) {
      case 'manager':
        return managerAccent;
      case 'teacher':
        return teacherAccent;
      case 'parent':
        return parentAccent;
      case 'student':
        return studentAccent;
      case 'director':
      case 'superadmin':
      case 'superuser':
      default:
        return directorAccent;
    }
  }

  static BoxDecoration cardDecoration(bool isDark, {Color? accent}) =>
      BoxDecoration(
        color: card(isDark),
        borderRadius: BorderRadius.circular(cardRadius),
        border: Border.all(color: border(isDark)),
        boxShadow: DsShadow.card(isDark),
      );

  static BoxDecoration gradientCard(List<Color> colors, {double radius = 20}) =>
      BoxDecoration(
        gradient: LinearGradient(
          colors: colors,
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(radius),
        boxShadow: DsShadow.primaryGlow(colors.first),
      );
}
