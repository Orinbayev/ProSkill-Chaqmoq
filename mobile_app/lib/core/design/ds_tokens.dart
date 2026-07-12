import 'package:flutter/material.dart';

import 'ds_colors.dart';

/// Burchak radiuslari (dizayn: 8/12/16/20/24/pill).
abstract final class DsRadius {
  static const double sm = 8;
  static const double md = 12;
  static const double card = 16;
  static const double lg = 20;
  static const double xl = 24;
  static const double pill = 999;

  static BorderRadius all(double r) => BorderRadius.circular(r);
}

/// 4pt grid asosidagi masofalar.
abstract final class DsSpace {
  static const double x1 = 4;
  static const double x2 = 8;
  static const double x3 = 12;
  static const double x4 = 16;
  static const double x5 = 20;
  static const double x6 = 24;
  static const double x8 = 32;

  /// Ekran chetki paddingi.
  static const double screen = 16;

  /// Bo'limlar orasidagi masofa.
  static const double section = 20;

  /// Elementlar orasidagi kichik masofa.
  static const double item = 10;
}

/// Yumshoq soyalar (dizayn hujjatidan aynan).
abstract final class DsShadow {
  /// Standart karta soyasi.
  static List<BoxShadow> card(bool isDark) => isDark
      ? const [BoxShadow(color: Color(0x33000000), blurRadius: 12, offset: Offset(0, 4))]
      : const [
          BoxShadow(color: Color(0x0F0F172A), blurRadius: 2, offset: Offset(0, 1)),
          BoxShadow(color: Color(0x0D0F172A), blurRadius: 12, offset: Offset(0, 4)),
        ];

  /// Ko'tarilgan element (bottom-sheet, menyu).
  static List<BoxShadow> raised(bool isDark) => isDark
      ? const [BoxShadow(color: Color(0x59000000), blurRadius: 24, offset: Offset(0, 8))]
      : const [BoxShadow(color: Color(0x1A0F172A), blurRadius: 24, offset: Offset(0, 8))];

  /// Urg'u rangli soya (primary tugma/hero).
  static List<BoxShadow> primaryGlow(Color primary) =>
      [BoxShadow(color: primary.withValues(alpha: 0.35), blurRadius: 16, offset: const Offset(0, 6))];
}

/// Animatsiya davomiyliklari.
abstract final class DsDuration {
  static const Duration fast = Duration(milliseconds: 150);
  static const Duration base = Duration(milliseconds: 220);
  static const Duration slow = Duration(milliseconds: 320);
}

/// Karta uchun tayyor dekoratsiya.
BoxDecoration dsCardDecoration(DsColors ds, {double radius = DsRadius.card, Color? color}) =>
    BoxDecoration(
      color: color ?? ds.card,
      borderRadius: DsRadius.all(radius),
      border: Border.all(color: ds.border),
      boxShadow: DsShadow.card(ds.isDark),
    );
