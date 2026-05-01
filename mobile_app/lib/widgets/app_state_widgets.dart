import 'package:chaqmoq_mobile/core/theme/parent_colors.dart';
import 'package:chaqmoq_mobile/core/theme/parent_text_styles.dart';
import 'package:chaqmoq_mobile/core/theme/student_colors.dart';
import 'package:chaqmoq_mobile/widgets/app_primary_button.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:shimmer/shimmer.dart';

/// Skeleton loader for cards. Matches LoadingState from JSX.
class AppLoadingState extends StatelessWidget {
  const AppLoadingState({super.key, this.dark = false, this.cardHeights = defaultHeights});

  final bool dark;
  final List<double> cardHeights;

  static const List<double> defaultHeights = [120, 90, 70, 70, 90];

  @override
  Widget build(BuildContext context) {
    final card = dark ? StudentColors.glass : Colors.white;
    final line = dark ? StudentColors.border : ParentColors.line;
    final base = dark ? const Color(0xFF1A1A24) : const Color(0xFFEAF1F9);
    final highlight = dark ? const Color(0xFF24243A) : const Color(0xFFF4F7FB);

    return ListView(
      padding: const EdgeInsets.fromLTRB(18, 12, 18, 24),
      children: [
        Shimmer.fromColors(
          baseColor: base,
          highlightColor: highlight,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _SkeletonBar(width: 140, height: 24),
              const SizedBox(height: 10),
              _SkeletonBar(width: 200, height: 14),
              const SizedBox(height: 18),
              for (final h in cardHeights) ...[
                Container(
                  height: h,
                  decoration: BoxDecoration(
                    color: card,
                    borderRadius: BorderRadius.circular(18),
                    border: Border.all(color: line),
                  ),
                ),
                const SizedBox(height: 10),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class _SkeletonBar extends StatelessWidget {
  const _SkeletonBar({required this.width, required this.height});
  final double width;
  final double height;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        color: Colors.grey.shade200,
        borderRadius: BorderRadius.circular(8),
      ),
    );
  }
}

class AppEmptyState extends StatelessWidget {
  const AppEmptyState({
    super.key,
    required this.title,
    required this.subtitle,
    this.icon = Icons.inbox_rounded,
    this.ctaLabel,
    this.ctaIcon,
    this.onCta,
    this.dark = false,
  });

  final String title;
  final String subtitle;
  final IconData icon;
  final String? ctaLabel;
  final IconData? ctaIcon;
  final VoidCallback? onCta;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    final iconBg = dark ? const Color(0x1A00D4AA) : ParentColors.primaryTint;
    final iconFg = dark ? StudentColors.primary : ParentColors.primary;
    final titleColor = dark ? StudentColors.text : ParentColors.text;
    final subtitleColor = dark ? StudentColors.textMuted : ParentColors.textMuted;

    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 100,
              height: 100,
              decoration: BoxDecoration(
                color: iconBg,
                borderRadius: BorderRadius.circular(32),
              ),
              child: Icon(icon, color: iconFg, size: 48),
            ),
            const SizedBox(height: 18),
            Text(
              title,
              textAlign: TextAlign.center,
              style: GoogleFonts.inter(
                fontSize: 18,
                fontWeight: FontWeight.w800,
                color: titleColor,
                letterSpacing: -0.2,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              subtitle,
              textAlign: TextAlign.center,
              style: GoogleFonts.inter(
                fontSize: 13,
                fontWeight: FontWeight.w500,
                color: subtitleColor,
                height: 1.5,
              ),
            ),
            if (ctaLabel != null && onCta != null) ...[
              const SizedBox(height: 18),
              AppPrimaryButton(
                label: ctaLabel!,
                onPressed: onCta,
                icon: ctaIcon ?? Icons.refresh_rounded,
                full: false,
                dark: dark,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class AppErrorState extends StatelessWidget {
  const AppErrorState({
    super.key,
    this.title = 'Ma\'lumot yuklanmadi',
    required this.message,
    this.onRetry,
    this.dark = false,
  });

  final String title;
  final String message;
  final VoidCallback? onRetry;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    final iconBg = dark ? const Color(0x1FFF4757) : ParentColors.dangerBg;
    final iconFg = dark ? StudentColors.danger : ParentColors.danger;
    final titleColor = dark ? StudentColors.text : ParentColors.text;
    final subtitleColor = dark ? StudentColors.textMuted : ParentColors.textMuted;

    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 100,
              height: 100,
              decoration: BoxDecoration(
                color: iconBg,
                borderRadius: BorderRadius.circular(32),
              ),
              child: Icon(Icons.error_outline_rounded, color: iconFg, size: 48),
            ),
            const SizedBox(height: 18),
            Text(
              title,
              textAlign: TextAlign.center,
              style: GoogleFonts.inter(
                fontSize: 18,
                fontWeight: FontWeight.w800,
                color: titleColor,
                letterSpacing: -0.2,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              message,
              textAlign: TextAlign.center,
              style: GoogleFonts.inter(
                fontSize: 13,
                fontWeight: FontWeight.w500,
                color: subtitleColor,
                height: 1.5,
              ),
            ),
            if (onRetry != null) ...[
              const SizedBox(height: 18),
              AppPrimaryButton(
                label: 'Qayta urinish',
                onPressed: onRetry,
                icon: Icons.refresh_rounded,
                full: false,
                dark: dark,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class AppOfflineBanner extends StatelessWidget {
  const AppOfflineBanner({super.key, this.lastSync, this.dark = false});

  final String? lastSync;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    final bg = dark ? const Color(0x1AFFA502) : ParentColors.warningBg;
    final border = dark ? const Color(0x52FFA502) : const Color(0xFFFDE68A);
    final fg = dark ? StudentColors.warning : ParentColors.amberDeep;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: border),
      ),
      child: Row(
        children: [
          Icon(Icons.cloud_off_rounded, color: fg, size: 22),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'Oflayn rejim',
                  style: ParentTextStyles.sectionTitle.copyWith(color: fg),
                ),
                const SizedBox(height: 2),
                Text(
                  lastSync ?? 'Internet aloqa cheklangan',
                  style: GoogleFonts.inter(
                    fontSize: 11.5,
                    fontWeight: FontWeight.w600,
                    color: fg.withAlpha((0.85 * 255).round()),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
