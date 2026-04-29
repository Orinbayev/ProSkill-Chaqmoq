import 'package:chaqmoq_mobile/core/theme/app_colors.dart';
import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/app_text_styles.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/core/utils/role_panel_style.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/payments_provider.dart';
import 'package:chaqmoq_mobile/widgets/empty_state.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class StudentPaymentsScreen extends StatefulWidget {
  const StudentPaymentsScreen({super.key});

  @override
  State<StudentPaymentsScreen> createState() => _StudentPaymentsScreenState();
}

class _StudentPaymentsScreenState extends State<StudentPaymentsScreen> {
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
    final provider = context.watch<PaymentsProvider>();
    if (user == null) {
      return const SizedBox.shrink();
    }

    final panel = RolePanelStyles.of(user.role);

    return DecoratedBox(
      decoration: const BoxDecoration(gradient: AppColors.appBackground),
      child: RefreshIndicator(
        onRefresh: () => provider.refresh(user),
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(
            parent: BouncingScrollPhysics(),
          ),
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.xl,
            AppSpacing.xl,
            AppSpacing.xl,
            32,
          ),
          children: [
            _PaymentsHeroCard(
              panel: panel,
              summary: provider.summary,
              isLoading: provider.state == ViewState.loading,
            ),
            const SizedBox(height: AppSpacing.xl),
            _FilterRow(
              currentFilter: provider.filter,
              onFilterChanged: provider.setFilter,
            ),
            const SizedBox(height: AppSpacing.lg),
            if (provider.state == ViewState.loading &&
                provider.filteredItems.isEmpty)
              const _PaymentsLoadingCard()
            else if (provider.state == ViewState.error &&
                provider.filteredItems.isEmpty)
              EmptyState(
                title: 'To‘lovlar yuklanmadi',
                message: provider.errorMessage ?? 'Qayta urinib ko‘ring',
                icon: Icons.credit_card_off_rounded,
                actionLabel: 'Qayta yuklash',
                onAction: () => provider.refresh(user),
              )
            else if (provider.filteredItems.isEmpty)
              const _PaymentsEmptyState()
            else
              ...provider.filteredItems.map(
                (payment) => Padding(
                  padding: const EdgeInsets.only(bottom: AppSpacing.md),
                  child: _PaymentTile(payment: payment),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _PaymentsHeroCard extends StatelessWidget {
  const _PaymentsHeroCard({
    required this.panel,
    required this.summary,
    required this.isLoading,
  });

  final RolePanelStyle panel;
  final PaymentSummaryModel summary;
  final bool isLoading;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.xl),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppRadius.xl),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('To‘lovlar', style: AppTextStyles.headline),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.md,
                  vertical: AppSpacing.sm,
                ),
                decoration: BoxDecoration(
                  color: panel.accentSoft.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(AppRadius.pill),
                ),
                child: Text(
                  panel.panelLabel,
                  style: AppTextStyles.bodySmall.copyWith(
                    color: panel.accentSoft,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            'To‘langan summa, qarzdorlik va shu oy holati shu yerda.',
            style: AppTextStyles.subtitle,
          ),
          if (isLoading) ...[
            const SizedBox(height: AppSpacing.md),
            const LinearProgressIndicator(
              minHeight: 3,
              color: AppColors.primary,
              backgroundColor: AppColors.surfaceAlt,
            ),
          ],
          const SizedBox(height: AppSpacing.xl),
          Row(
            children: [
              Expanded(
                child: _SummaryMetric(
                  label: 'Jami to‘langan',
                  value: Formatters.currency(
                    summary.totalReceived,
                    compact: true,
                  ),
                  accent: AppColors.success,
                ),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: _SummaryMetric(
                  label: 'Qarzdorlik',
                  value: Formatters.currency(summary.openDebt, compact: true),
                  accent: AppColors.danger,
                ),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: _SummaryMetric(
                  label: 'Bu oy',
                  value: Formatters.currency(summary.thisMonth, compact: true),
                  accent: AppColors.primary,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _SummaryMetric extends StatelessWidget {
  const _SummaryMetric({
    required this.label,
    required this.value,
    required this.accent,
  });

  final String label;
  final String value;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: accent.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(AppRadius.lg),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: AppTextStyles.bodySmall),
          const SizedBox(height: AppSpacing.sm),
          Text(
            value,
            style: AppTextStyles.title.copyWith(fontSize: 16, color: accent),
          ),
        ],
      ),
    );
  }
}

class _FilterRow extends StatelessWidget {
  const _FilterRow({
    required this.currentFilter,
    required this.onFilterChanged,
  });

  final String currentFilter;
  final ValueChanged<String> onFilterChanged;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: AppSpacing.sm,
      runSpacing: AppSpacing.sm,
      children: [
        _FilterChip(
          label: 'Barchasi',
          selected: currentFilter == 'all',
          onTap: () => onFilterChanged('all'),
        ),
        _FilterChip(
          label: 'To‘langan',
          selected: currentFilter == 'received',
          onTap: () => onFilterChanged('received'),
        ),
        _FilterChip(
          label: 'Qarzlar',
          selected: currentFilter == 'debt',
          onTap: () => onFilterChanged('debt'),
        ),
      ],
    );
  }
}

class _FilterChip extends StatelessWidget {
  const _FilterChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return FilterChip(
      selected: selected,
      onSelected: (_) => onTap(),
      label: Text(label),
      backgroundColor: AppColors.surface,
      selectedColor: AppColors.primary.withValues(alpha: 0.16),
      side: const BorderSide(color: AppColors.border),
      labelStyle: AppTextStyles.bodySmall.copyWith(
        color: selected ? AppColors.textPrimary : AppColors.textMuted,
      ),
    );
  }
}

class _PaymentTile extends StatelessWidget {
  const _PaymentTile({required this.payment});

  final PaymentModel payment;

  @override
  Widget build(BuildContext context) {
    final accent = payment.isDebt ? AppColors.danger : AppColors.success;
    final title = payment.groupName.isEmpty ? 'To‘lov' : payment.groupName;

    return Container(
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppRadius.lg),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: accent.withValues(alpha: 0.14),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Icon(
              payment.isDebt
                  ? Icons.warning_amber_rounded
                  : Icons.check_circle_outline_rounded,
              color: accent,
            ),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: AppTextStyles.body),
                const SizedBox(height: 4),
                Text(
                  Formatters.date(payment.date),
                  style: AppTextStyles.bodySmall,
                ),
              ],
            ),
          ),
          const SizedBox(width: AppSpacing.md),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                Formatters.currency(payment.amount, compact: true),
                style: AppTextStyles.title.copyWith(
                  color: accent,
                  fontSize: 16,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                payment.isDebt ? 'Qarz' : 'To‘langan',
                style: AppTextStyles.bodySmall.copyWith(color: accent),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _PaymentsEmptyState extends StatelessWidget {
  const _PaymentsEmptyState();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.xl),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppRadius.xl),
        border: Border.all(color: AppColors.border),
      ),
      child: const EmptyState(
        title: 'To‘lov tarixi topilmadi',
        message: 'Hozircha bu profil uchun to‘lov yozuvlari mavjud emas.',
        icon: Icons.receipt_long_rounded,
      ),
    );
  }
}

class _PaymentsLoadingCard extends StatelessWidget {
  const _PaymentsLoadingCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 220,
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppRadius.xl),
        border: Border.all(color: AppColors.border),
      ),
      alignment: Alignment.center,
      child: const CircularProgressIndicator(),
    );
  }
}
