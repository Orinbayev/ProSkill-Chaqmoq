import 'package:chaqmoq_mobile/core/theme/app_foundation.dart';
import 'package:chaqmoq_mobile/widgets/chaqmoq_card.dart';
import 'package:flutter/material.dart';

class AppPageHeader extends StatelessWidget {
  const AppPageHeader({
    super.key,
    required this.title,
    required this.subtitle,
    this.badge,
    this.action,
  });

  final String title;
  final String subtitle;
  final Widget? badge;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return ChaqmoqCard(
      gradient: AppGradients.softSurface,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (badge != null) ...[
            badge!,
            const SizedBox(height: AppSpacing.md),
          ],
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: Theme.of(context).textTheme.titleLarge),
                    const SizedBox(height: AppSpacing.xs),
                    Text(
                      subtitle,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: AppColors.muted,
                      ),
                    ),
                  ],
                ),
              ),
              if (action != null) ...[
                const SizedBox(width: AppSpacing.md),
                action!,
              ],
            ],
          ),
        ],
      ),
    );
  }
}
