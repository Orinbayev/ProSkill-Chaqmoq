import 'package:flutter/material.dart';

class AppColors {
  const AppColors._();

  static const Color background = Color(0xFF0A0A0F);
  static const Color surface = Color(0xFF13131A);
  static const Color surfaceAlt = Color(0xFF1A1A24);
  static const Color primary = Color(0xFF6C63FF);
  static const Color secondary = Color(0xFF00D4AA);
  static const Color danger = Color(0xFFFF4757);
  static const Color warning = Color(0xFFFFA502);
  static const Color success = Color(0xFF2ED573);
  static const Color textPrimary = Color(0xFFF1F2F6);
  static const Color textMuted = Color(0xFF8892A4);
  static const Color white = Color(0xFFFFFFFF);
  static const Color black = Color(0xFF000000);

  static const Color border = Color.fromRGBO(255, 255, 255, 0.08);
  static const Color glass = Color.fromRGBO(255, 255, 255, 0.04);
  static const Color glassStrong = Color.fromRGBO(255, 255, 255, 0.07);
  static const Color glowPrimary = Color.fromRGBO(108, 99, 255, 0.25);
  static const Color glowSecondary = Color.fromRGBO(0, 212, 170, 0.22);
  static const Color shadow = Color.fromRGBO(0, 0, 0, 0.4);

  static const LinearGradient appBackground = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [
      Color(0xFF0A0A0F),
      Color(0xFF13131A),
      Color(0xFF0A0A0F),
    ],
    stops: [0, 0.52, 1],
  );

  static const LinearGradient cardHighlight = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [
      Color.fromRGBO(108, 99, 255, 0.18),
      Color.fromRGBO(0, 212, 170, 0.08),
      Color.fromRGBO(255, 255, 255, 0.02),
    ],
  );

  static const LinearGradient primaryGradient = LinearGradient(
    begin: Alignment.centerLeft,
    end: Alignment.centerRight,
    colors: [Color(0xFF6C63FF), Color(0xFF8C85FF)],
  );

  static const LinearGradient accentGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF6C63FF), Color(0xFF00D4AA)],
  );
}
