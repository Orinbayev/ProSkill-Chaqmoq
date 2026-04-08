import 'package:chaqmoq_mobile/core/theme/app_foundation.dart';
import 'package:flutter/material.dart';

enum AppButtonVariant { filled, tonal, outlined }

class AppButton extends StatelessWidget {
  const AppButton({
    super.key,
    required this.label,
    this.onPressed,
    this.icon,
    this.loading = false,
    this.expanded = true,
    this.variant = AppButtonVariant.filled,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool loading;
  final bool expanded;
  final AppButtonVariant variant;

  @override
  Widget build(BuildContext context) {
    final child = _ButtonChild(
      label: label,
      icon: icon,
      loading: loading,
      variant: variant,
    );
    final button = switch (variant) {
      AppButtonVariant.filled => FilledButton(
        onPressed: loading ? null : onPressed,
        child: child,
      ),
      AppButtonVariant.tonal => FilledButton.tonal(
        onPressed: loading ? null : onPressed,
        style: FilledButton.styleFrom(
          foregroundColor: AppColors.primary,
          backgroundColor: AppColors.primary.withValues(alpha: 0.10),
        ),
        child: child,
      ),
      AppButtonVariant.outlined => OutlinedButton(
        onPressed: loading ? null : onPressed,
        child: child,
      ),
    };

    if (!expanded) {
      return button;
    }

    return SizedBox(width: double.infinity, child: button);
  }
}

class _ButtonChild extends StatelessWidget {
  const _ButtonChild({
    required this.label,
    required this.icon,
    required this.loading,
    required this.variant,
  });

  final String label;
  final IconData? icon;
  final bool loading;
  final AppButtonVariant variant;

  @override
  Widget build(BuildContext context) {
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 180),
      child: loading
          ? SizedBox(
              key: const ValueKey('loader'),
              width: 20,
              height: 20,
              child: CircularProgressIndicator(
                strokeWidth: 2.2,
                color: switch (variant) {
                  AppButtonVariant.filled => Colors.white,
                  AppButtonVariant.tonal => AppColors.primary,
                  AppButtonVariant.outlined => AppColors.text,
                },
              ),
            )
          : Row(
              key: const ValueKey('content'),
              mainAxisSize: MainAxisSize.min,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                if (icon != null) ...[
                  Icon(icon, size: 18),
                  const SizedBox(width: AppSpacing.xs),
                ],
                Flexible(child: Text(label)),
              ],
            ),
    );
  }
}
