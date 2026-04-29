import 'package:chaqmoq_mobile/core/theme/app_colors.dart';
import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/app_text_styles.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/core/utils/role_panel_style.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/dashboard_provider.dart';
import 'package:chaqmoq_mobile/widgets/empty_state.dart';
import 'package:chaqmoq_mobile/widgets/role_badge.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class StudentDashboardScreen extends StatefulWidget {
  const StudentDashboardScreen({
    super.key,
    this.onOpenPayments,
    this.onOpenNotifications,
    this.onOpenProfile,
  });

  final VoidCallback? onOpenPayments;
  final VoidCallback? onOpenNotifications;
  final VoidCallback? onOpenProfile;

  @override
  State<StudentDashboardScreen> createState() => _StudentDashboardScreenState();
}

class _StudentDashboardScreenState extends State<StudentDashboardScreen> {
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final user = context.read<AuthProvider>().user;
    if (user != null) {
      context.read<DashboardProvider>().load(user);
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final dashboard = context.watch<DashboardProvider>();
    final user = auth.user;
    if (user == null) {
      return const SizedBox.shrink();
    }

    final panel = RolePanelStyles.of(user.role);
    final metrics = dashboard.data.metrics;

    return DecoratedBox(
      decoration: BoxDecoration(gradient: panel.heroGradient),
      child: RefreshIndicator(
        onRefresh: () => dashboard.refresh(user),
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
            _StudentHeroCard(
              fullName: user.fullName,
              centerName: user.center?.name ?? 'Markaz biriktirilmagan',
              panel: panel,
              isOffline: auth.isOfflineMode,
            ),
            const SizedBox(height: AppSpacing.xl),
            _QuickActionsRow(
              onOpenPayments: widget.onOpenPayments,
              onOpenNotifications: widget.onOpenNotifications,
              onOpenProfile: widget.onOpenProfile,
            ),
            const SizedBox(height: AppSpacing.xl),
            if (dashboard.state == ViewState.loading && metrics.isEmpty)
              const _LoadingCard()
            else if (dashboard.state == ViewState.error && metrics.isEmpty)
              EmptyState(
                title: 'Student paneli yuklanmadi',
                message: dashboard.errorMessage ?? 'Qayta urinib ko‘ring',
                icon: Icons.cloud_off_rounded,
                actionLabel: 'Qayta yuklash',
                onAction: () => dashboard.refresh(user),
              )
            else ...[
              if (dashboard.state == ViewState.loading) ...[
                const LinearProgressIndicator(
                  minHeight: 3,
                  color: AppColors.secondary,
                  backgroundColor: Color(0x1AFFFFFF),
                ),
                const SizedBox(height: AppSpacing.md),
              ],
              _StudentHighlights(
                score: dashboard.data.studentScore,
                rank: dashboard.data.studentRank,
              ),
              const SizedBox(height: AppSpacing.lg),
              Wrap(
                spacing: AppSpacing.lg,
                runSpacing: AppSpacing.lg,
                children: metrics
                    .map((metric) => _StudentMetricCard(metric: metric))
                    .toList(),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _StudentHeroCard extends StatelessWidget {
  const _StudentHeroCard({
    required this.fullName,
    required this.centerName,
    required this.panel,
    required this.isOffline,
  });

  final String fullName;
  final String centerName;
  final RolePanelStyle panel;
  final bool isOffline;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.xl),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(AppRadius.xl),
        border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  color: panel.accentSoft.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(18),
                ),
                child: Icon(panel.icon, color: panel.accentSoft, size: 28),
              ),
              const Spacer(),
              const RoleBadge(role: 'student'),
            ],
          ),
          const SizedBox(height: AppSpacing.xl),
          Text(
            panel.panelLabel,
            style: AppTextStyles.label.copyWith(color: panel.accentSoft),
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            'Salom, ${Formatters.firstName(fullName)}',
            style: AppTextStyles.headline,
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(centerName, style: AppTextStyles.subtitle),
          const SizedBox(height: AppSpacing.md),
          Text(
            panel.subtitle,
            style: AppTextStyles.body.copyWith(
              color: AppColors.textPrimary.withValues(alpha: 0.88),
            ),
          ),
          if (isOffline) ...[
            const SizedBox(height: AppSpacing.lg),
            Container(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.md,
                vertical: AppSpacing.sm,
              ),
              decoration: BoxDecoration(
                color: const Color(0x1AFAC858),
                borderRadius: BorderRadius.circular(AppRadius.lg),
              ),
              child: Row(
                children: [
                  const Icon(
                    Icons.cloud_off_rounded,
                    color: Color(0xFFFAC858),
                    size: 18,
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Text(
                      'Tarmoq bilan aloqa cheklangan. Oxirgi saqlangan ma’lumotlar ko‘rsatilmoqda.',
                      style: AppTextStyles.bodySmall.copyWith(
                        color: AppColors.textPrimary,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _QuickActionsRow extends StatelessWidget {
  const _QuickActionsRow({
    this.onOpenPayments,
    this.onOpenNotifications,
    this.onOpenProfile,
  });

  final VoidCallback? onOpenPayments;
  final VoidCallback? onOpenNotifications;
  final VoidCallback? onOpenProfile;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _ActionButton(
            icon: Icons.credit_card_rounded,
            label: 'To‘lovlar',
            onTap: onOpenPayments,
          ),
        ),
        const SizedBox(width: AppSpacing.md),
        Expanded(
          child: _ActionButton(
            icon: Icons.notifications_none_rounded,
            label: 'Xabarlar',
            onTap: onOpenNotifications,
          ),
        ),
        const SizedBox(width: AppSpacing.md),
        Expanded(
          child: _ActionButton(
            icon: Icons.person_outline_rounded,
            label: 'Profil',
            onTap: onOpenProfile,
          ),
        ),
      ],
    );
  }
}

class _ActionButton extends StatelessWidget {
  const _ActionButton({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppRadius.lg),
        child: Container(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.md,
            vertical: AppSpacing.lg,
          ),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.08),
            borderRadius: BorderRadius.circular(AppRadius.lg),
            border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
          ),
          child: Column(
            children: [
              Icon(icon, color: AppColors.textPrimary),
              const SizedBox(height: AppSpacing.sm),
              Text(
                label,
                style: AppTextStyles.bodySmall.copyWith(
                  color: AppColors.textPrimary,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StudentHighlights extends StatelessWidget {
  const _StudentHighlights({required this.score, required this.rank});

  final int score;
  final int rank;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.xl),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppRadius.xl),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        children: [
          Container(
            width: 92,
            height: 92,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: AppColors.accentGradient,
              boxShadow: const [
                BoxShadow(
                  color: AppColors.glowSecondary,
                  blurRadius: 20,
                  offset: Offset(0, 10),
                ),
              ],
            ),
            alignment: Alignment.center,
            child: Text(
              '$score',
              style: AppTextStyles.headline.copyWith(fontSize: 28),
            ),
          ),
          const SizedBox(width: AppSpacing.xl),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Chaqmoq reytingi', style: AppTextStyles.title),
                const SizedBox(height: AppSpacing.sm),
                Text(
                  rank > 0
                      ? 'Reytingdagi o‘rningiz: #$rank'
                      : 'Reyting ma’lumoti yangilanmoqda',
                  style: AppTextStyles.subtitle,
                ),
                const SizedBox(height: AppSpacing.md),
                Text(
                  'Faollik, davomat va intizom ko‘rsatkichlaringiz shu bo‘limda jamlangan.',
                  style: AppTextStyles.bodySmall.copyWith(
                    color: AppColors.textMuted,
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

class _StudentMetricCard extends StatelessWidget {
  const _StudentMetricCard({required this.metric});

  final DashboardMetric metric;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width:
          (MediaQuery.sizeOf(context).width -
              (AppSpacing.xl * 2) -
              AppSpacing.lg) /
          2,
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.lg),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(AppRadius.lg),
          border: Border.all(color: AppColors.border),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(metric.title, style: AppTextStyles.bodySmall),
            const SizedBox(height: AppSpacing.md),
            Text(
              _valueFor(metric),
              style: AppTextStyles.title.copyWith(fontSize: 20),
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(metric.subtitle, style: AppTextStyles.bodySmall),
          ],
        ),
      ),
    );
  }

  String _valueFor(DashboardMetric metric) {
    if (metric.id == 'debt') {
      final amount = int.tryParse(metric.value) ?? 0;
      return Formatters.currency(amount, compact: true);
    }
    if (metric.id == 'attendance') {
      return '${metric.value}%';
    }
    return metric.value;
  }
}

class _LoadingCard extends StatelessWidget {
  const _LoadingCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 240,
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppRadius.xl),
        border: Border.all(color: AppColors.border),
      ),
      alignment: Alignment.center,
      child: const CircularProgressIndicator(color: AppColors.secondary),
    );
  }
}
