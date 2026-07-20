import 'package:chaqmoq_mobile/core/design/ds_colors.dart';
import 'package:flutter/material.dart';

/// Global AppColors — "Chaqmoq Panellar" (Sky/Slate) dizayn tizimiga mos.
/// Barcha rollar shu poydevordan foydalanadi; o'zgarishlar `DsPalette`/`DsColors` dan keladi.
class AppColors {
  const AppColors._();

  // Dark surfaces
  static const Color background = DsPalette.slate900;
  static const Color surface = Color(0xFF13233A);
  static const Color surfaceAlt = DsPalette.slate800;

  // Brand — Sky
  static const Color primary = DsPalette.sky500;
  static const Color secondary = DsPalette.sky600;
  static const Color danger = DsPalette.red500;
  static const Color warning = DsPalette.amber500;
  static const Color success = DsPalette.green500;

  // Text — dark
  static const Color textPrimary = DsPalette.slate50;
  static const Color textMuted = DsPalette.slate400;
  static const Color white = DsPalette.white;
  static const Color black = Color(0xFF000000);

  // Glass / borders — dark
  static const Color border = Color(0x14FFFFFF);
  static const Color glass = Color(0x0AFFFFFF);
  static const Color glassStrong = Color(0x12FFFFFF);
  static const Color glowPrimary = Color(0x3D0EA5E9);
  static const Color glowSecondary = Color(0x380284C7);
  static const Color shadow = Color(0x66000000);

  // Light variants
  static const Color backgroundLight = Color(0xFFEDF1F5);
  static const Color surfaceLight = DsPalette.white;
  static const Color surfaceAltLight = DsPalette.slate50;
  static const Color textPrimaryLight = DsPalette.slate900;
  static const Color textMutedLight = DsPalette.slate500;
  static const Color borderLight = DsPalette.slate200;
  static const Color glassLight = Color(0x0A0F172A);
  static const Color glassStrongLight = Color(0x0F0F172A);

  static const LinearGradient appBackground = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [DsPalette.slate900, Color(0xFF13233A), DsPalette.slate900],
    stops: [0, 0.52, 1],
  );

  static const LinearGradient cardHighlight = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [
      Color(0x2E0EA5E9),
      Color(0x1F0284C7),
      Color(0x05FFFFFF),
    ],
  );

  static const LinearGradient primaryGradient = LinearGradient(
    begin: Alignment.centerLeft,
    end: Alignment.centerRight,
    colors: [DsPalette.sky500, DsPalette.sky400],
  );

  static const LinearGradient accentGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [DsPalette.sky500, DsPalette.sky600],
  );
}
