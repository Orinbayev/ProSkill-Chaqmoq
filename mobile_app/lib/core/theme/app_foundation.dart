import 'package:flutter/material.dart';

class AppColors {
  static const Color primary = Color(0xFF0F6CBD);
  static const Color primaryDark = Color(0xFF0B4F8A);
  static const Color secondary = Color(0xFF14B8A6);
  static const Color accent = Color(0xFFF59E0B);
  static const Color canvas = Color(0xFFF4F7FB);
  static const Color surface = Colors.white;
  static const Color surfaceAlt = Color(0xFFF8FAFC);
  static const Color border = Color(0xFFE2E8F0);
  static const Color text = Color(0xFF0F172A);
  static const Color muted = Color(0xFF64748B);
  static const Color success = Color(0xFF16A34A);
  static const Color danger = Color(0xFFDC2626);
  static const Color warning = Color(0xFFF59E0B);
}

class AppGradients {
  static const LinearGradient brand = LinearGradient(
    colors: [Color(0xFF0B4F8A), Color(0xFF0F6CBD), Color(0xFF14B8A6)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient darkHero = LinearGradient(
    colors: [Color(0xFF0B1220), Color(0xFF10243D), Color(0xFF164E63)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient softSurface = LinearGradient(
    colors: [Color(0xFFFFFFFF), Color(0xFFF7FBFF)],
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
  );
}

class AppRadius {
  static const double sm = 14;
  static const double md = 20;
  static const double lg = 26;
  static const double xl = 32;
  static const double pill = 999;
}

class AppSpacing {
  static const double xxs = 4;
  static const double xs = 8;
  static const double sm = 12;
  static const double md = 16;
  static const double lg = 20;
  static const double xl = 24;
  static const double xxl = 32;
}

class AppShadows {
  static const List<BoxShadow> soft = [
    BoxShadow(
      color: Color(0x0F0F172A),
      blurRadius: 30,
      offset: Offset(0, 10),
    ),
  ];

  static const List<BoxShadow> medium = [
    BoxShadow(
      color: Color(0x140F172A),
      blurRadius: 34,
      offset: Offset(0, 14),
    ),
  ];
}
