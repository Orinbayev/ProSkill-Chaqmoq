import 'package:chaqmoq_mobile/core/design/ds_colors.dart';
import 'package:flutter/material.dart';

/// O'quvchi palitrasi — yagona Sky/Slate poydevor (boshqa rollar bilan bir xil).
/// Gamification uchun secondary (yumshoq indigo) saqlangan; primary = Sky.
class StudentColors {
  const StudentColors._();

  // Background (Ds dark)
  static const Color bg = DsPalette.slate900;
  static const Color bg2 = Color(0xFF13233A);
  static const Color bg3 = DsPalette.slate800;

  // Text
  static const Color text = DsPalette.slate50;
  static const Color textMuted = DsPalette.slate400;
  static const Color textDim = DsPalette.slate500;

  // Primary (Sky — brand)
  static const Color primary = DsPalette.sky500;
  static const Color primarySoft = DsPalette.sky400;
  static const Color primaryDeep = DsPalette.sky600;
  static const Color onPrimary = DsPalette.white;

  // Secondary (yumshoq accent, secondary actions)
  static const Color secondary = Color(0xFF0EA5E9);
  static const Color secondarySoft = Color(0xFF38BDF8);

  // Semantic
  static const Color danger = DsPalette.red500;
  static const Color warning = DsPalette.amber500;
  static const Color success = DsPalette.green500;
  static const Color info = DsPalette.sky400;

  // Glass / borders
  static const Color border = Color(0x14FFFFFF);
  static const Color borderStrong = Color(0x24FFFFFF);
  static const Color glass = Color(0x0AFFFFFF);
  static const Color glassStrong = Color(0x12FFFFFF);

  static const LinearGradient bgGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [DsPalette.slate900, Color(0xFF13233A), DsPalette.slate900],
    stops: [0, 0.5, 1],
  );

  static const LinearGradient primaryGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [DsPalette.sky500, DsPalette.sky400],
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
      Color(0x380EA5E9),
      Color(0x2E6366F1),
      Color(0x05FFFFFF),
    ],
    stops: [0, 0.6, 1],
  );

  static const LinearGradient violetTealGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [secondary, DsPalette.sky500],
  );

  static const List<BoxShadow> glowTeal = [
    BoxShadow(color: Color(0x520EA5E9), blurRadius: 28, offset: Offset(0, 10)),
  ];
  static const List<BoxShadow> glowViolet = [
    BoxShadow(color: Color(0x526366F1), blurRadius: 24, offset: Offset(0, 10)),
  ];
}
