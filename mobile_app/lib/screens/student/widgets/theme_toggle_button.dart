import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/providers/app_preferences_provider.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

/// Compact pill that toggles between light and dark theme.
/// Tapping cycles light ↔ dark (system mode is reachable from full Theme screen).
class ThemeToggleButton extends StatelessWidget {
  const ThemeToggleButton({super.key, this.size = 40});

  final double size;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final prefs = context.watch<AppPreferencesProvider>();
    final isDark = tokens.isDark;
    final icon = isDark ? Icons.light_mode_rounded : Icons.dark_mode_rounded;

    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: () {
          final next = isDark ? AppThemePreference.light : AppThemePreference.dark;
          prefs.setThemePreference(next);
        },
        borderRadius: BorderRadius.circular(12),
        child: Container(
          width: size,
          height: size,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: tokens.glass,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: tokens.border),
          ),
          child: AnimatedSwitcher(
            duration: const Duration(milliseconds: 220),
            transitionBuilder: (w, anim) => RotationTransition(
              turns: Tween<double>(begin: 0.7, end: 1).animate(anim),
              child: FadeTransition(opacity: anim, child: w),
            ),
            child: Icon(
              icon,
              key: ValueKey(isDark),
              size: 20,
              color: tokens.primary,
            ),
          ),
        ),
      ),
    );
  }
}
