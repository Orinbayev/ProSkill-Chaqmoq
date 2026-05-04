import 'package:flutter/material.dart';

/// Parent ranglar palitrasi — light va dark variantlari bilan.
/// Static getterlar joriy mavzuni `_resolver` orqali aniqlaydi (App'da
/// `ParentColors.attach(context)` chaqirilsa). Aks holda light qiymat
/// qaytaradi.
class ParentColors {
  const ParentColors._();

  // Mavzuga moslashuvchi static "current brightness" — ParentColorsScope orqali
  // har build siklida yangilanib turadi.
  static Brightness _brightness = Brightness.light;

  /// ParentColorsScope joriy mavzuga qarab static brightness'ni yangilaydi.
  static void update(Brightness b) {
    _brightness = b;
  }

  static bool get _isDark => _brightness == Brightness.dark;

  // ===== Background / surface =====
  static Color get bg =>
      _isDark ? const Color(0xFF0B0F17) : const Color(0xFFF4F7FB);
  static Color get bgSoft =>
      _isDark ? const Color(0xFF111726) : const Color(0xFFEAF1F9);
  static Color get card =>
      _isDark ? const Color(0xFF141926) : const Color(0xFFFFFFFF);

  // ===== Text =====
  static Color get text =>
      _isDark ? const Color(0xFFEAF1FB) : const Color(0xFF0F1E33);
  static Color get textSoft =>
      _isDark ? const Color(0xFFB6C2D6) : const Color(0xFF4B5B72);
  static Color get textMuted =>
      _isDark ? const Color(0xFF94A3B8) : const Color(0xFF8090A8);

  // ===== Lines =====
  static Color get line =>
      _isDark ? const Color(0xFF24304A) : const Color(0xFFE4ECF5);
  static Color get lineStrong =>
      _isDark ? const Color(0xFF2C3854) : const Color(0xFFCBD7E7);

  // ===== Primary blue (brand) =====
  static const Color primary = Color(0xFF3B82F6);
  static const Color primaryDeep = Color(0xFF2563EB);
  static Color get primarySoft =>
      _isDark ? const Color(0xFF1F2C44) : const Color(0xFFDBEAFE);
  static Color get primaryTint =>
      _isDark ? const Color(0xFF14213A) : const Color(0xFFEFF6FF);

  // ===== Amber =====
  static const Color amber = Color(0xFFF59E0B);
  static Color get amberBg =>
      _isDark ? const Color(0xFF3A2C0E) : const Color(0xFFFEF3C7);
  static const Color amberDeep = Color(0xFFB45309);

  // ===== Semantic =====
  static const Color success = Color(0xFF10B981);
  static Color get successBg =>
      _isDark ? const Color(0xFF0F2A1F) : const Color(0xFFDCFCE7);
  static Color get successLine =>
      _isDark ? const Color(0xFF1F4A37) : const Color(0xFFBBF7D0);
  static const Color warning = Color(0xFFF59E0B);
  static Color get warningBg =>
      _isDark ? const Color(0xFF3A2C0E) : const Color(0xFFFEF3C7);
  static const Color danger = Color(0xFFEF4444);
  static Color get dangerBg =>
      _isDark ? const Color(0xFF3A1818) : const Color(0xFFFEE2E2);
  static const Color info = Color(0xFF3B82F6);
  static Color get infoBg =>
      _isDark ? const Color(0xFF14213A) : const Color(0xFFDBEAFE);
  static const Color violet = Color(0xFF7C3AED);
  static Color get violetBg =>
      _isDark ? const Color(0xFF26204A) : const Color(0xFFEDE9FE);

  // ===== Gradients =====
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

  // ===== Shadows =====
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

/// Bu widget joriy mavzuni qo'lga oladi va ParentColors static brightness'ini
/// yangilaydi. Parent role app shellni shu bilan o'rab qo'yish kerak.
class ParentColorsScope extends StatelessWidget {
  const ParentColorsScope({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    ParentColors.update(Theme.of(context).brightness);
    return child;
  }
}
