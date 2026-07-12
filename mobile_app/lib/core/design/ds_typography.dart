import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Inter asosidagi tipografiya shkalasi (dizayn: Display 28 → Micro 11).
///
/// Har bir uslub rangni parametr sifatida oladi, chunki matn rangi
/// [DsColors] kontekstiga bog'liq (yorug'/qorong'i).
abstract final class DsType {
  static const List<FontFeature> _tabular = [FontFeature.tabularFigures()];

  static TextStyle _inter(
    double size,
    FontWeight weight,
    Color color, {
    double? height,
    double? letterSpacing,
    bool tabular = false,
  }) =>
      GoogleFonts.inter(
        fontSize: size,
        fontWeight: weight,
        color: color,
        height: height,
        letterSpacing: letterSpacing,
        fontFeatures: tabular ? _tabular : null,
      );

  /// 28 · w800 — hero raqam / sarlavha.
  static TextStyle display(Color c) => _inter(28, FontWeight.w800, c, letterSpacing: -0.5, height: 1.1);

  /// 24 · w700.
  static TextStyle h1(Color c) => _inter(24, FontWeight.w700, c, letterSpacing: -0.3, height: 1.15);

  /// 20 · w600.
  static TextStyle h2(Color c) => _inter(20, FontWeight.w600, c, height: 1.2);

  /// 18 · w600.
  static TextStyle h3(Color c) => _inter(18, FontWeight.w600, c, height: 1.25);

  /// 15 · w400 — asosiy matn.
  static TextStyle body(Color c) => _inter(15, FontWeight.w400, c, height: 1.45);

  /// 15 · w600.
  static TextStyle bodyStrong(Color c) => _inter(15, FontWeight.w600, c, height: 1.35);

  /// 13 · w500 — yordamchi matn.
  static TextStyle caption(Color c) => _inter(13, FontWeight.w500, c, height: 1.4);

  /// 12 · w500 — meta.
  static TextStyle small(Color c) => _inter(12, FontWeight.w500, c, height: 1.35);

  /// 11 · w600 — mikro yorliq (badge, tab).
  static TextStyle micro(Color c) => _inter(11, FontWeight.w600, c, letterSpacing: 0.2);

  /// Pul summasi — tabular raqamlar bilan.
  static TextStyle money(Color c, {double size = 22}) =>
      _inter(size, FontWeight.w700, c, tabular: true, letterSpacing: -0.2);
}
