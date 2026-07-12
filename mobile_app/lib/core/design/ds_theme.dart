import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import 'ds_colors.dart';

/// Yagona dizayn tizimi asosidagi [ThemeData].
///
/// Bu tema faqat yangi (Sky/Slate) panellar uchun. Mavjud ilova temasi
/// (`app_theme.dart`) o'zgarmaydi.
abstract final class DsTheme {
  static ThemeData light() => _build(DsColors.light);
  static ThemeData dark() => _build(DsColors.dark);

  static ThemeData _build(DsColors ds) {
    final base = ThemeData(useMaterial3: true, brightness: ds.brightness);
    return base.copyWith(
      scaffoldBackgroundColor: ds.bg,
      textTheme: GoogleFonts.interTextTheme(base.textTheme).apply(
        bodyColor: ds.textPrimary,
        displayColor: ds.textPrimary,
      ),
      colorScheme: base.colorScheme.copyWith(
        primary: ds.primary,
        onPrimary: ds.primaryFg,
        surface: ds.surface,
        onSurface: ds.textPrimary,
        error: ds.danger,
      ),
      dividerColor: ds.border,
      splashColor: ds.primary.withValues(alpha: 0.08),
      highlightColor: ds.primary.withValues(alpha: 0.04),
      appBarTheme: AppBarTheme(
        backgroundColor: ds.surface,
        foregroundColor: ds.textPrimary,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
      ),
      bottomNavigationBarTheme: BottomNavigationBarThemeData(
        backgroundColor: ds.surface,
        selectedItemColor: ds.primary,
        unselectedItemColor: ds.textFaint,
        type: BottomNavigationBarType.fixed,
        elevation: 0,
      ),
    );
  }
}

/// App-bar / bottom-nav soyasi uchun yordamchi ajratgich chizig'i.
class DsHairline extends StatelessWidget {
  const DsHairline({super.key});
  @override
  Widget build(BuildContext context) => Container(height: 1, color: context.ds.border);
}
