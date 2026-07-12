import 'package:flutter/material.dart';

/// ChaqmoqApp yagona dizayn tizimi — xom rang shkalalari.
///
/// Qiymatlar "Chaqmoq Panellar" dizayn hujjatidan aynan olingan:
/// Primary = Sky, Neutral = Slate. Bu shkalalarni to'g'ridan-to'g'ri ishlatmang —
/// odatda [DsColors] semantik tokenlaridan foydalaning.
abstract final class DsPalette {
  // ─── Sky (primary) ─────────────────────────────────────────────
  static const sky50 = Color(0xFFF0F9FF);
  static const sky100 = Color(0xFFE0F2FE);
  static const sky200 = Color(0xFFBAE6FD);
  static const sky300 = Color(0xFF7DD3FC);
  static const sky400 = Color(0xFF38BDF8);
  static const sky500 = Color(0xFF0EA5E9);
  static const sky600 = Color(0xFF0284C7);
  static const sky700 = Color(0xFF0369A1);
  static const sky800 = Color(0xFF075985);
  static const sky900 = Color(0xFF0C4A6E);

  // ─── Slate (neutral) ───────────────────────────────────────────
  static const slate50 = Color(0xFFF8FAFC);
  static const slate100 = Color(0xFFF1F5F9);
  static const slate200 = Color(0xFFE2E8F0);
  static const slate300 = Color(0xFFCBD5E1);
  static const slate400 = Color(0xFF94A3B8);
  static const slate500 = Color(0xFF64748B);
  static const slate600 = Color(0xFF475569);
  static const slate700 = Color(0xFF334155);
  static const slate800 = Color(0xFF1E293B);
  static const slate900 = Color(0xFF0F172A);

  // ─── Xom semantik ──────────────────────────────────────────────
  static const green500 = Color(0xFF22C55E);
  static const green400 = Color(0xFF4ADE80);
  static const green700 = Color(0xFF15803D);
  static const greenBg = Color(0xFFDCFCE7);

  static const amber500 = Color(0xFFF59E0B);
  static const amber400 = Color(0xFFFBBF24);
  static const amber700 = Color(0xFFB45309);
  static const amberBg = Color(0xFFFEF3C7);

  static const red500 = Color(0xFFEF4444);
  static const red400 = Color(0xFFF87171);
  static const red700 = Color(0xFFB91C1C);
  static const redBg = Color(0xFFFEE2E2);

  static const blue500 = Color(0xFF3B82F6);

  static const white = Color(0xFFFFFFFF);
}

/// Brightness'ga bog'liq semantik rang tokenlari.
///
/// `context.ds` orqali oling (pastdagi extension'ga qarang) — u joriy
/// mavzuning yorug'/qorong'i rejimiga mos [DsColors] qaytaradi.
@immutable
class DsColors {
  const DsColors({
    required this.brightness,
    required this.bg,
    required this.surface,
    required this.card,
    required this.cardAlt,
    required this.border,
    required this.borderStrong,
    required this.primary,
    required this.primaryFg,
    required this.primarySoft,
    required this.primarySoftFg,
    required this.textPrimary,
    required this.textSecondary,
    required this.textMuted,
    required this.textFaint,
    required this.success,
    required this.successFg,
    required this.successBg,
    required this.warning,
    required this.warningFg,
    required this.warningBg,
    required this.danger,
    required this.dangerFg,
    required this.dangerBg,
    required this.info,
  });

  final Brightness brightness;
  bool get isDark => brightness == Brightness.dark;

  /// Sahifa foni (scaffold).
  final Color bg;

  /// App-bar / yuqori yuza.
  final Color surface;

  /// Standart karta foni.
  final Color card;

  /// Karta ichidagi ikkilamchi yuza (masalan jadval qatori).
  final Color cardAlt;

  /// Nozik chegara.
  final Color border;

  /// Kuchliroq chegara (input focus tashqarisi).
  final Color borderStrong;

  /// Asosiy urg'u (Sky).
  final Color primary;

  /// Urg'u ustidagi matn/ikon rangi.
  final Color primaryFg;

  /// Urg'uning yumshoq foni (chip/badge).
  final Color primarySoft;

  /// Yumshoq urg'u foni ustidagi matn.
  final Color primarySoftFg;

  final Color textPrimary;
  final Color textSecondary;
  final Color textMuted;
  final Color textFaint;

  final Color success;
  final Color successFg;
  final Color successBg;

  final Color warning;
  final Color warningFg;
  final Color warningBg;

  final Color danger;
  final Color dangerFg;
  final Color dangerBg;

  final Color info;

  /// Urg'u gradienti (hero kartalar, logotip).
  List<Color> get primaryGradient =>
      isDark ? const [Color(0xFF0284C7), Color(0xFF38BDF8)] : const [Color(0xFF0EA5E9), Color(0xFF38BDF8)];

  static const DsColors light = DsColors(
    brightness: Brightness.light,
    bg: Color(0xFFEDF1F5),
    surface: DsPalette.white,
    card: DsPalette.white,
    cardAlt: DsPalette.slate50,
    border: DsPalette.slate200,
    borderStrong: DsPalette.slate300,
    primary: DsPalette.sky500,
    primaryFg: DsPalette.white,
    primarySoft: DsPalette.sky100,
    primarySoftFg: DsPalette.sky700,
    textPrimary: DsPalette.slate900,
    textSecondary: DsPalette.slate600,
    textMuted: DsPalette.slate500,
    textFaint: DsPalette.slate400,
    success: DsPalette.green500,
    successFg: DsPalette.green700,
    successBg: DsPalette.greenBg,
    warning: DsPalette.amber500,
    warningFg: DsPalette.amber700,
    warningBg: DsPalette.amberBg,
    danger: DsPalette.red500,
    dangerFg: DsPalette.red700,
    dangerBg: DsPalette.redBg,
    info: DsPalette.blue500,
  );

  static const DsColors dark = DsColors(
    brightness: Brightness.dark,
    bg: DsPalette.slate900,
    surface: Color(0xFF13233A),
    card: DsPalette.slate800,
    cardAlt: Color(0xFF243449),
    border: DsPalette.slate700,
    borderStrong: DsPalette.slate600,
    primary: DsPalette.sky400,
    primaryFg: DsPalette.slate900,
    primarySoft: Color(0xFF11324B),
    primarySoftFg: DsPalette.sky300,
    textPrimary: DsPalette.slate50,
    textSecondary: DsPalette.slate300,
    textMuted: DsPalette.slate400,
    textFaint: DsPalette.slate500,
    success: DsPalette.green400,
    successFg: DsPalette.green400,
    successBg: Color(0xFF14351F),
    warning: DsPalette.amber400,
    warningFg: DsPalette.amber400,
    warningBg: Color(0xFF3A2E10),
    danger: DsPalette.red400,
    dangerFg: DsPalette.red400,
    dangerBg: Color(0xFF3A1B1B),
    info: DsPalette.sky400,
  );

  static DsColors of(BuildContext context) =>
      Theme.of(context).brightness == Brightness.dark ? dark : light;
}

/// Qulaylik: `context.ds.primary` kabi ishlatish uchun.
extension DsColorsContext on BuildContext {
  DsColors get ds => DsColors.of(this);
}
