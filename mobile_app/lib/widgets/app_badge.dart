import 'package:chaqmoq_mobile/core/theme/parent_colors.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

enum AppBadgeTone { success, warning, danger, info, teal, violet, neutral }

/// Pill badge — mirrors primitives.jsx `Badge`.
class AppBadge extends StatelessWidget {
  const AppBadge({
    super.key,
    required this.label,
    this.tone = AppBadgeTone.success,
    this.dark = false,
    this.icon,
    this.iconSize = 14,
  });

  final String label;
  final AppBadgeTone tone;
  final bool dark;
  final IconData? icon;
  final double iconSize;

  @override
  Widget build(BuildContext context) {
    final palette = _palette(tone, dark);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
      decoration: BoxDecoration(
        color: palette.bg,
        borderRadius: BorderRadius.circular(100),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, color: palette.fg, size: iconSize),
            const SizedBox(width: 4),
          ],
          Text(
            label,
            style: GoogleFonts.inter(
              fontSize: 11,
              height: 1.2,
              fontWeight: FontWeight.w700,
              color: palette.fg,
              letterSpacing: 0.1,
            ),
          ),
        ],
      ),
    );
  }

  _BadgePalette _palette(AppBadgeTone tone, bool dark) {
    switch (tone) {
      case AppBadgeTone.success:
        return dark
            ? const _BadgePalette(bg: Color(0x242ED573), fg: Color(0xFF2ED573))
            : _BadgePalette(bg: ParentColors.successBg, fg: ParentColors.success);
      case AppBadgeTone.warning:
        return dark
            ? const _BadgePalette(bg: Color(0x29FFA502), fg: Color(0xFFFFA502))
            : _BadgePalette(bg: ParentColors.warningBg, fg: ParentColors.amberDeep);
      case AppBadgeTone.danger:
        return dark
            ? const _BadgePalette(bg: Color(0x24FF4757), fg: Color(0xFFFF4757))
            : _BadgePalette(bg: ParentColors.dangerBg, fg: ParentColors.danger);
      case AppBadgeTone.info:
        return dark
            ? const _BadgePalette(bg: Color(0x244FC3F7), fg: Color(0xFF4FC3F7))
            : _BadgePalette(bg: ParentColors.infoBg, fg: ParentColors.primaryDeep);
      case AppBadgeTone.teal:
        return const _BadgePalette(bg: Color(0x240EA5E9), fg: Color(0xFF0EA5E9));
      case AppBadgeTone.violet:
        return const _BadgePalette(bg: Color(0x296C63FF), fg: Color(0xFF8C85FF));
      case AppBadgeTone.neutral:
        return dark
            ? const _BadgePalette(bg: Color(0x0FFFFFFF), fg: Color(0xFF8892A4))
            : const _BadgePalette(bg: Color(0xFFF1F5F9), fg: Color(0xFF64748B));
    }
  }
}

class _BadgePalette {
  const _BadgePalette({required this.bg, required this.fg});
  final Color bg;
  final Color fg;
}
