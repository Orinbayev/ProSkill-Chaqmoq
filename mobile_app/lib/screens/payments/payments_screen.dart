import 'package:chaqmoq_mobile/core/theme/app_colors.dart';
import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/app_text_styles.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/payments_provider.dart';
import 'package:chaqmoq_mobile/widgets/empty_state.dart';
import 'package:chaqmoq_mobile/widgets/glass_card.dart';
import 'package:chaqmoq_mobile/widgets/shimmer_loader.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class PaymentsScreen extends StatefulWidget {
  const PaymentsScreen({super.key});

  @override
  State<PaymentsScreen> createState() => _PaymentsScreenState();
}

class _PaymentsScreenState extends State<PaymentsScreen> {
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final user = context.read<AuthProvider>().user;
    if (user != null) {
      context.read<PaymentsProvider>().load(user);
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().user;
    final payments = context.watch<PaymentsProvider>();
    if (user == null) {
      return const SizedBox.shrink();
    }

    return RefreshIndicator(
      onRefresh: () => payments.refresh(user),
      child: ListView(
        padding: const EdgeInsets.all(AppSpacing.xl),
        children: [
          Wrap(
            spacing: AppSpacing.lg,
            runSpacing: AppSpacing.lg,
            children: [
              _SummaryCard(label: 'Total received', value: payments.summary.totalReceived, color: AppColors.secondary),
              _SummaryCard(label: 'Open debt', value: payments.summary.openDebt, color: AppColors.danger),
              _SummaryCard(label: 'This month', value: payments.summary.thisMonth, color: AppColors.primary),
            ],
          ),
          const SizedBox(height: AppSpacing.xl),
          Row(
            children: [
              _PaymentFilterChip(
                label: 'All',
                selected: payments.filter == 'all',
                onTap: () => payments.setFilter('all'),
              ),
              _PaymentFilterChip(
                label: 'Received',
                selected: payments.filter == 'received',
                onTap: () => payments.setFilter('received'),
              ),
              _PaymentFilterChip(
                label: 'Debt',
                selected: payments.filter == 'debt',
                onTap: () => payments.setFilter('debt'),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.xl),
          if (payments.state == ViewState.loading)
            const ShimmerLoader.list()
          else if (payments.state == ViewState.error)
            EmptyState(
              title: 'To\'lovlar yuklanmadi',
              message: payments.errorMessage ?? 'Qayta urinib ko\'ring',
              icon: Icons.credit_card_off_rounded,
              actionLabel: 'Qayta yuklash',
              onAction: () => payments.refresh(user),
            )
          else if (payments.filteredItems.isEmpty)
            const EmptyState(
              title: 'To\'lov topilmadi',
              message: 'Tanlangan filtr bo\'yicha yozuv yo\'q',
              icon: Icons.receipt_long_rounded,
            )
          else
            ...payments.filteredItems.map(
              (payment) => Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.lg),
                child: GlassCard(
                  child: Row(
                    children: [
                      CircleAvatar(
                        backgroundColor: AppColors.primary.withValues(alpha: 0.16),
                        child: Text(
                          Formatters.initials(payment.studentName),
                          style: AppTextStyles.bodySmall,
                        ),
                      ),
                      const SizedBox(width: AppSpacing.md),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(payment.studentName, style: AppTextStyles.body),
                            const SizedBox(height: AppSpacing.xs),
                            Text(
                              '${payment.groupName.isEmpty ? 'Guruh ko\'rsatilmagan' : payment.groupName} • ${Formatters.relative(payment.date)}',
                              style: AppTextStyles.bodySmall,
                            ),
                          ],
                        ),
                      ),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Text(
                            Formatters.currency(payment.amount),
                            style: AppTextStyles.label.copyWith(color: AppColors.success),
                          ),
                          const SizedBox(height: AppSpacing.xs),
                          Text(payment.method.isEmpty ? 'Naqd' : payment.method, style: AppTextStyles.bodySmall),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({
    required this.label,
    required this.value,
    required this.color,
  });

  final String label;
  final int value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 160,
      child: GlassCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: AppTextStyles.bodySmall),
            const SizedBox(height: AppSpacing.md),
            Text(
              Formatters.currency(value, compact: true),
              style: AppTextStyles.title.copyWith(color: color),
            ),
          ],
        ),
      ),
    );
  }
}

class _PaymentFilterChip extends StatelessWidget {
  const _PaymentFilterChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: AppSpacing.sm),
      child: FilterChip(
        selected: selected,
        onSelected: (_) => onTap(),
        label: Text(label),
      ),
    );
  }
}
