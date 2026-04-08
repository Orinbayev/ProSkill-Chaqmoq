import 'package:chaqmoq_mobile/core/theme/app_foundation.dart';
import 'package:flutter/material.dart';

class ChaqmoqCard extends StatelessWidget {
  const ChaqmoqCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(AppSpacing.lg),
    this.onTap,
    this.gradient,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final VoidCallback? onTap;
  final Gradient? gradient;

  @override
  Widget build(BuildContext context) {
    final shape = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(AppRadius.lg),
    );

    return DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(AppRadius.lg),
        boxShadow: gradient == null ? AppShadows.soft : AppShadows.medium,
      ),
      child: Card(
        clipBehavior: Clip.antiAlias,
        shape: shape,
        child: InkWell(
          onTap: onTap,
          child: Ink(
            decoration: BoxDecoration(
              gradient: gradient,
              borderRadius: BorderRadius.circular(AppRadius.lg),
            ),
            child: Padding(padding: padding, child: child),
          ),
        ),
      ),
    );
  }
}
