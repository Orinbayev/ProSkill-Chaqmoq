import 'package:flutter/material.dart';

class AppColors {
  const AppColors._();

  static const Color background = Color(0xFF08111B);
  static const Color surface = Color(0xFF0F1B2A);
  static const Color surfaceAlt = Color(0xFF162436);
  static const Color primary = Color(0xFF2563EB);
  static const Color secondary = Color(0xFF0F766E);
  static const Color danger = Color(0xFFE35D6A);
  static const Color warning = Color(0xFFD97706);
  static const Color success = Color(0xFF1A936F);
  static const Color textPrimary = Color(0xFFF1F2F6);
  static const Color textMuted = Color(0xFF8892A4);
  static const Color white = Color(0xFFFFFFFF);
  static const Color black = Color(0xFF000000);

  static const Color border = Color.fromRGBO(255, 255, 255, 0.08);
  static const Color glass = Color.fromRGBO(255, 255, 255, 0.04);
  static const Color glassStrong = Color.fromRGBO(255, 255, 255, 0.07);
  static const Color glowPrimary = Color.fromRGBO(37, 99, 235, 0.24);
  static const Color glowSecondary = Color.fromRGBO(15, 118, 110, 0.22);
  static const Color shadow = Color.fromRGBO(0, 0, 0, 0.4);

  static const LinearGradient appBackground = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF08111B), Color(0xFF0F1B2A), Color(0xFF08111B)],
    stops: [0, 0.52, 1],
  );

  static const LinearGradient cardHighlight = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [
      Color.fromRGBO(37, 99, 235, 0.18),
      Color.fromRGBO(15, 118, 110, 0.12),
      Color.fromRGBO(255, 255, 255, 0.02),
    ],
  );

  static const LinearGradient primaryGradient = LinearGradient(
    begin: Alignment.centerLeft,
    end: Alignment.centerRight,
    colors: [Color(0xFF2563EB), Color(0xFF4F8CFF)],
  );

  static const LinearGradient accentGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF2563EB), Color(0xFF0F766E)],
  );
}
