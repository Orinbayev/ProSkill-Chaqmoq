import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/parent_colors.dart';
import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:flutter/material.dart';

/// Parent (light) card. Mirrors `PCard` from primitives.jsx.
class AppPCard extends StatelessWidget {
  const AppPCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.borderRadius,
    this.background,
    this.borderColor,
    this.shadow = ParentColors.shadowSm,
    this.onTap,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final BorderRadius? borderRadius;
  final Color? background;
  final Color? borderColor;
  final List<BoxShadow> shadow;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final radius = borderRadius ?? BorderRadius.circular(AppRadius.lg);
    final card = Container(
      decoration: BoxDecoration(
        color: background ?? ParentColors.card,
        borderRadius: radius,
        border: Border.all(color: borderColor ?? ParentColors.line),
        boxShadow: shadow,
      ),
      padding: padding,
      child: child,
    );
    if (onTap == null) return card;
    return Material(
      color: Colors.transparent,
      borderRadius: radius,
      child: InkWell(
        borderRadius: radius,
        onTap: onTap,
        child: card,
      ),
    );
  }
}

/// Student (dark glass) card. Mirrors `GCard` from primitives.jsx.
class AppGCard extends StatelessWidget {
  const AppGCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.borderRadius,
    this.background,
    this.borderColor,
    this.strong = false,
    this.onTap,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final BorderRadius? borderRadius;
  final Color? background;
  final Color? borderColor;
  final bool strong;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final radius = borderRadius ?? BorderRadius.circular(AppRadius.lg);
    final defaultBg = tokens.isDark
        ? (strong ? tokens.glassStrong : tokens.glass)
        : (strong ? tokens.surfaceElevated : tokens.surface);
    final card = Container(
      decoration: BoxDecoration(
        color: background ?? defaultBg,
        borderRadius: radius,
        border: Border.all(color: borderColor ?? tokens.border),
        boxShadow: tokens.isDark
            ? null
            : [BoxShadow(color: tokens.shadow, blurRadius: 16, offset: const Offset(0, 4))],
      ),
      padding: padding,
      child: child,
    );
    if (onTap == null) return card;
    return Material(
      color: Colors.transparent,
      borderRadius: radius,
      child: InkWell(
        borderRadius: radius,
        onTap: onTap,
        child: card,
      ),
    );
  }
}
