import 'package:chaqmoq_mobile/core/theme/app_colors.dart';
import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/app_text_styles.dart';
import 'package:chaqmoq_mobile/widgets/glass_card.dart';
import 'package:flutter/material.dart';

class MetricCard extends StatelessWidget {
  const MetricCard({
    super.key,
    required this.title,
    required this.value,
    required this.subtitle,
    required this.icon,
    required this.color,
    required this.trend,
  });

  final String title;
  final String value;
  final String subtitle;
  final IconData icon;
  final Color color;
  final double trend;

  @override
  Widget build(BuildContext context) {
    final isPositive = trend >= 0;
    return GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.16),
                  borderRadius: BorderRadius.circular(AppRadius.lg),
                ),
                alignment: Alignment.center,
                child: Icon(icon, color: color),
              ),
              const Spacer(),
              Icon(
                isPositive ? Icons.trending_up_rounded : Icons.trending_down_rounded,
                color: isPositive ? AppColors.success : AppColors.danger,
                size: 18,
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.lg),
          Text(title, style: AppTextStyles.subtitle),
          const SizedBox(height: AppSpacing.sm),
          Text(
            value,
            style: AppTextStyles.headline.copyWith(fontSize: 26),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          const Spacer(),
          Text(subtitle, style: AppTextStyles.bodySmall),
        ],
      ),
    );
  }
}
