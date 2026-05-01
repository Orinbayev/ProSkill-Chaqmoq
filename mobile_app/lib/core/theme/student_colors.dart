import 'package:flutter/material.dart';

/// Student (dark, teal-forward) palette — extracted from tokens.css.
class StudentColors {
  const StudentColors._();

  // Background
  static const Color bg = Color(0xFF0A0A0F);
  static const Color bg2 = Color(0xFF13131A);
  static const Color bg3 = Color(0xFF1A1A24);

  // Text
  static const Color text = Color(0xFFF1F2F6);
  static const Color textMuted = Color(0xFF8892A4);
  static const Color textDim = Color(0xFF5A6478);

  // Primary (teal)
  static const Color primary = Color(0xFF00D4AA);
  static const Color primarySoft = Color(0xFF2BE5BF);
  static const Color primaryDeep = Color(0xFF00A88A);
  static const Color onPrimary = Color(0xFF0A1F1A);

  // Secondary (violet)
  static const Color secondary = Color(0xFF6C63FF);
  static const Color secondarySoft = Color(0xFF8C85FF);

  // Semantic
  static const Color danger = Color(0xFFFF4757);
  static const Color warning = Color(0xFFFFA502);
  static const Color success = Color(0xFF2ED573);
  static const Color info = Color(0xFF4FC3F7);

  // Glass / borders
  static const Color border = Color(0x14FFFFFF);
  static const Color borderStrong = Color(0x24FFFFFF);
  static const Color glass = Color(0x0AFFFFFF);
  static const Color glassStrong = Color(0x12FFFFFF);

  // Gradients
  static const LinearGradient bgGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF0A0A0F), Color(0xFF131322), Color(0xFF0A0A0F)],
    stops: [0, 0.5, 1],
  );

  static const LinearGradient primaryGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [primary, primarySoft],
  );

  static const LinearGradient violetGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [secondary, secondarySoft],
  );

  static const LinearGradient heroGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [
      Color(0x3800D4AA),
      Color(0x2E6C63FF),
      Color(0x05FFFFFF),
    ],
    stops: [0, 0.6, 1],
  );

  static const LinearGradient violetTealGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [secondary, primary],
  );

  // Glows
  static const List<BoxShadow> glowTeal = [
    BoxShadow(color: Color(0x5200D4AA), blurRadius: 28, offset: Offset(0, 10)),
  ];
  static const List<BoxShadow> glowViolet = [
    BoxShadow(color: Color(0x526C63FF), blurRadius: 24, offset: Offset(0, 10)),
  ];
}
