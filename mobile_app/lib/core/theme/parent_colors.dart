import 'package:chaqmoq_mobile/core/design/ds_colors.dart';
import 'package:flutter/material.dart';

/// Ota-ona palitrasi — yagona "Chaqmoq Panellar" (Sky/Slate) dizayni.
/// Static getterlar joriy mavzuni `_brightness` orqali aniqlaydi
/// ([ParentColorsScope] orqali yangilanadi).
class ParentColors {
  const ParentColors._();

  static Brightness _brightness = Brightness.light;

  static void update(Brightness b) {
    _brightness = b;
  }

  static bool get _isDark => _brightness == Brightness.dark;
  static DsColors get _ds => _isDark ? DsColors.dark : DsColors.light;

  // ===== Background / surface =====
  static Color get bg => _ds.bg;
  static Color get bgSoft => _ds.cardAlt;
  static Color get card => _ds.card;

  // ===== Text =====
  static Color get text => _ds.textPrimary;
  static Color get textSoft => _ds.textSecondary;
  static Color get textMuted => _ds.textMuted;

  // ===== Lines =====
  static Color get line => _ds.border;
  static Color get lineStrong => _ds.borderStrong;

  // ===== Primary — Sky =====
  static const Color primary = DsPalette.sky500;
  static const Color primaryDeep = DsPalette.sky600;
  static Color get primarySoft => _ds.primarySoft;
  static Color get primaryTint =>
      _isDark ? const Color(0xFF11324B) : DsPalette.sky50;

  // ===== Amber =====
  static const Color amber = DsPalette.amber500;
  static Color get amberBg => _ds.warningBg;
  static const Color amberDeep = DsPalette.amber700;

  // ===== Semantic =====
  static const Color success = DsPalette.green500;
  static Color get successBg => _ds.successBg;
  static Color get successLine =>
      _isDark ? const Color(0xFF1F4A37) : const Color(0xFFBBF7D0);
  static const Color warning = DsPalette.amber500;
  static Color get warningBg => _ds.warningBg;
  static const Color danger = DsPalette.red500;
  static Color get dangerBg => _ds.dangerBg;
  static const Color info = DsPalette.sky500;
  static Color get infoBg => _ds.primarySoft;
  static const Color violet = Color(0xFF7C3AED);
  static Color get violetBg =>
      _isDark ? const Color(0xFF26204A) : const Color(0xFFEDE9FE);

  // ===== Gradients =====
  static const LinearGradient primaryGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [DsPalette.sky500, DsPalette.sky400],
  );

  static const LinearGradient heroBlueGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [DsPalette.sky500, DsPalette.sky600, DsPalette.sky700],
  );

  static const LinearGradient successGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [DsPalette.green500, DsPalette.green700],
  );

  static const LinearGradient violetGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [DsPalette.sky500, DsPalette.sky600],
  );

  static const LinearGradient paymentsHeroGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [DsPalette.sky700, DsPalette.sky500],
  );

  // ===== Shadows =====
  static const List<BoxShadow> shadowSm = [
    BoxShadow(color: Color(0x0F0F172A), blurRadius: 2, offset: Offset(0, 1)),
    BoxShadow(color: Color(0x0D0F172A), blurRadius: 3, offset: Offset(0, 1)),
  ];
  static const List<BoxShadow> shadowMd = [
    BoxShadow(color: Color(0x0F0F172A), blurRadius: 12, offset: Offset(0, 4)),
    BoxShadow(color: Color(0x0A0F172A), blurRadius: 3, offset: Offset(0, 1)),
  ];
  static const List<BoxShadow> shadowLg = [
    BoxShadow(color: Color(0x140F172A), blurRadius: 32, offset: Offset(0, 12)),
    BoxShadow(color: Color(0x0A0F172A), blurRadius: 6, offset: Offset(0, 2)),
  ];
  static const List<BoxShadow> shadowBlue = [
    BoxShadow(color: Color(0x470EA5E9), blurRadius: 22, offset: Offset(0, 10)),
  ];
}

/// Parent shell uchun joriy brightness ni sinxronlaydi.
class ParentColorsScope extends StatelessWidget {
  const ParentColorsScope({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    ParentColors.update(Theme.of(context).brightness);
    return child;
  }
}
