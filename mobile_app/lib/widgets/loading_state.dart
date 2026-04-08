import 'package:chaqmoq_mobile/core/theme/app_foundation.dart';
import 'package:chaqmoq_mobile/widgets/chaqmoq_card.dart';
import 'package:flutter/material.dart';

class LoadingState extends StatelessWidget {
  const LoadingState({
    super.key,
    this.title = 'Ma\'lumotlar yuklanmoqda...',
    this.message = 'Iltimos, markaz ma\'lumotlari sinxronlanishini kuting.',
  });

  final String title;
  final String message;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 420),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: ChaqmoqCard(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 72,
                  height: 72,
                  decoration: BoxDecoration(
                    color: Theme.of(
                      context,
                    ).colorScheme.primary.withValues(alpha: 0.10),
                    borderRadius: BorderRadius.circular(AppRadius.lg),
                  ),
                  alignment: Alignment.center,
                  child: const CircularProgressIndicator.adaptive(),
                ),
                const SizedBox(height: AppSpacing.lg),
                Text(title, style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: AppSpacing.xs),
                Text(
                  message,
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: AppColors.muted,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
