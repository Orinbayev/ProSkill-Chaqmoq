import 'package:flutter/material.dart';

/// Parent (light, soft blue) palette — extracted from tokens.css.
/// Used only by parent-facing screens to avoid clashing with the
/// existing dark `AppColors` palette consumed by other roles.
class ParentColors {
  const ParentColors._();

  // Background / surface
  static const Color bg = Color(0xFFF4F7FB);
  static const Color bgSoft = Color(0xFFEAF1F9);
  static const Color card = Color(0xFFFFFFFF);

  // Text
  static const Color text = Color(0xFF0F1E33);
  static const Color textSoft = Color(0xFF4B5B72);
  static const Color textMuted = Color(0xFF8090A8);

  // Lines
  static const Color line = Color(0xFFE4ECF5);
  static const Color lineStrong = Color(0xFFCBD7E7);

  // Primary blue
  static const Color primary = Color(0xFF3B82F6);
  static const Color primaryDeep = Color(0xFF2563EB);
  static const Color primarySoft = Color(0xFFDBEAFE);
  static const Color primaryTint = Color(0xFFEFF6FF);

  // Amber
  static const Color amber = Color(0xFFF59E0B);
  static const Color amberBg = Color(0xFFFEF3C7);
  static const Color amberDeep = Color(0xFFB45309);

  // Semantic
  static const Color success = Color(0xFF10B981);
  static const Color successBg = Color(0xFFDCFCE7);
  static const Color successLine = Color(0xFFBBF7D0);
  static const Color warning = Color(0xFFF59E0B);
  static const Color warningBg = Color(0xFFFEF3C7);
  static const Color danger = Color(0xFFEF4444);
  static const Color dangerBg = Color(0xFFFEE2E2);
  static const Color info = Color(0xFF3B82F6);
  static const Color infoBg = Color(0xFFDBEAFE);
  static const Color violet = Color(0xFF7C3AED);
  static const Color violetBg = Color(0xFFEDE9FE);

  // Gradients
  static const LinearGradient primaryGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [primary, primaryDeep],
  );

  static const LinearGradient heroBlueGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF3B82F6), Color(0xFF2563EB), Color(0xFF1E40AF)],
  );

  static const LinearGradient successGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF10B981), Color(0xFF059669)],
  );

  static const LinearGradient violetGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF6C63FF), Color(0xFF4F46E5)],
  );

  static const LinearGradient paymentsHeroGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF1E40AF), Color(0xFF3B82F6)],
  );

  // Shadows
  static const List<BoxShadow> shadowSm = [
    BoxShadow(color: Color(0x0A0F1E33), blurRadius: 2, offset: Offset(0, 1)),
    BoxShadow(color: Color(0x0F0F1E33), blurRadius: 3, offset: Offset(0, 1)),
  ];
  static const List<BoxShadow> shadowMd = [
    BoxShadow(color: Color(0x0F0F1E33), blurRadius: 12, offset: Offset(0, 4)),
    BoxShadow(color: Color(0x0A0F1E33), blurRadius: 3, offset: Offset(0, 1)),
  ];
  static const List<BoxShadow> shadowLg = [
    BoxShadow(color: Color(0x140F1E33), blurRadius: 32, offset: Offset(0, 12)),
    BoxShadow(color: Color(0x0A0F1E33), blurRadius: 6, offset: Offset(0, 2)),
  ];
  static const List<BoxShadow> shadowBlue = [
    BoxShadow(color: Color(0x473B82F6), blurRadius: 22, offset: Offset(0, 10)),
  ];
}
