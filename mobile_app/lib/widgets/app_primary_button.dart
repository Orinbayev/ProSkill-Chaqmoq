import 'package:chaqmoq_mobile/core/theme/parent_colors.dart';
import 'package:chaqmoq_mobile/core/theme/student_colors.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

enum AppButtonVariant { primary, secondary, ghost, violet }

/// Primary button — mirrors primitives.jsx `PButton`. 52dp height,
/// gradient bg + glow shadow.
class AppPrimaryButton extends StatelessWidget {
  const AppPrimaryButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.variant = AppButtonVariant.primary,
    this.dark = false,
    this.icon,
    this.full = true,
    this.loading = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final AppButtonVariant variant;
  final bool dark;
  final IconData? icon;
  final bool full;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    final v = _resolve(variant, dark);
    final isDisabled = onPressed == null;

    return SizedBox(
      width: full ? double.infinity : null,
      height: 52,
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(16),
        child: InkWell(
          onTap: isDisabled || loading ? null : onPressed,
          borderRadius: BorderRadius.circular(16),
          child: Ink(
            decoration: BoxDecoration(
              gradient: v.gradient,
              color: v.color,
              borderRadius: BorderRadius.circular(16),
              border: v.border,
              boxShadow: isDisabled ? null : v.shadow,
            ),
            child: Padding(
              padding: EdgeInsets.symmetric(horizontal: full ? 16 : 22),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                mainAxisSize: full ? MainAxisSize.max : MainAxisSize.min,
                children: [
                  if (loading)
                    SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2.2,
                        color: v.foreground,
                      ),
                    )
                  else ...[
                    if (icon != null) ...[
                      Icon(icon, size: 20, color: v.foreground),
                      const SizedBox(width: 8),
                    ],
                    Flexible(
                      child: Text(
                        label,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: GoogleFonts.inter(
                          fontSize: 14.5,
                          fontWeight: FontWeight.w700,
                          color: v.foreground,
                          letterSpacing: 0.1,
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  _ButtonResolved _resolve(AppButtonVariant variant, bool dark) {
    if (dark) {
      switch (variant) {
        case AppButtonVariant.primary:
          return const _ButtonResolved(
            gradient: StudentColors.primaryGradient,
            foreground: StudentColors.onPrimary,
            shadow: StudentColors.glowTeal,
          );
        case AppButtonVariant.violet:
          return const _ButtonResolved(
            gradient: StudentColors.violetGradient,
            foreground: Colors.white,
            shadow: StudentColors.glowViolet,
          );
        case AppButtonVariant.secondary:
          return _ButtonResolved(
            color: StudentColors.glassStrong,
            foreground: StudentColors.text,
            border: Border.all(color: StudentColors.borderStrong),
          );
        case AppButtonVariant.ghost:
          return _ButtonResolved(
            color: Colors.transparent,
            foreground: StudentColors.primary,
            border: Border.all(color: StudentColors.border),
          );
      }
    }
    switch (variant) {
      case AppButtonVariant.primary:
        return const _ButtonResolved(
          gradient: ParentColors.primaryGradient,
          foreground: Colors.white,
          shadow: ParentColors.shadowBlue,
        );
      case AppButtonVariant.violet:
        return const _ButtonResolved(
          gradient: ParentColors.violetGradient,
          foreground: Colors.white,
          shadow: ParentColors.shadowMd,
        );
      case AppButtonVariant.secondary:
        return _ButtonResolved(
          color: ParentColors.card,
          foreground: ParentColors.text,
          border: Border.all(color: ParentColors.lineStrong),
          shadow: ParentColors.shadowSm,
        );
      case AppButtonVariant.ghost:
        return _ButtonResolved(
          color: Colors.transparent,
          foreground: ParentColors.primary,
        );
    }
  }
}

class _ButtonResolved {
  const _ButtonResolved({
    this.gradient,
    this.color,
    required this.foreground,
    this.border,
    this.shadow,
  });

  final Gradient? gradient;
  final Color? color;
  final Color foreground;
  final BoxBorder? border;
  final List<BoxShadow>? shadow;
}
