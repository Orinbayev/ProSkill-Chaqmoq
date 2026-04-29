import 'package:chaqmoq_mobile/core/theme/app_colors.dart';
import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/app_text_styles.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/core/utils/role_panel_style.dart';
import 'package:chaqmoq_mobile/core/utils/role_utils.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/dashboard_provider.dart';
import 'package:chaqmoq_mobile/screens/dashboard/widgets/chart_card.dart';
import 'package:chaqmoq_mobile/screens/dashboard/widgets/metric_card.dart';
import 'package:chaqmoq_mobile/widgets/empty_state.dart';
import 'package:chaqmoq_mobile/widgets/glass_card.dart';
import 'package:chaqmoq_mobile/widgets/role_badge.dart';
import 'package:chaqmoq_mobile/widgets/section_header.dart';
import 'package:chaqmoq_mobile/widgets/shimmer_loader.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:provider/provider.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final auth = context.read<AuthProvider>();
    final user = auth.user;
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

    return RefreshIndicator(
      onRefresh: () => dashboard.refresh(user),
      child: ListView(
        padding: const EdgeInsets.all(AppSpacing.xl),
        children: [
          GlassCard(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: AppSpacing.md,
                          vertical: AppSpacing.xs,
                        ),
                        decoration: BoxDecoration(
                          color: panel.accent.withValues(alpha: 0.14),
                          borderRadius: BorderRadius.circular(AppRadius.pill),
                        ),
                        child: Text(
                          panel.panelLabel,
                          style: AppTextStyles.bodySmall.copyWith(
                            color: panel.accent,
                          ),
                        ),
                      ),
                      const SizedBox(height: AppSpacing.md),
                      Text(
                        'Xush kelibsiz, ${Formatters.firstName(user.fullName)}!',
                        style: AppTextStyles.headline,
                      ),
                      const SizedBox(height: AppSpacing.sm),
                      Text(
                        user.center?.name ?? 'Markaz ma\'lumoti mavjud emas',
                        style: AppTextStyles.subtitle,
                      ),
                      const SizedBox(height: AppSpacing.xs),
                      Text(panel.subtitle, style: AppTextStyles.subtitle),
                    ],
                  ),
                ),
                RoleBadge(role: user.role),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.xl),
          if (dashboard.state == ViewState.loading)
            const ShimmerLoader.grid()
          else if (dashboard.state == ViewState.error)
            EmptyState(
              title: 'Dashboard yuklanmadi',
              message: dashboard.errorMessage ?? 'Qayta urinib ko\'ring',
              icon: Icons.cloud_off_rounded,
              actionLabel: 'Qayta yuklash',
              onAction: () => dashboard.refresh(user),
            )
          else ...[
            GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: dashboard.data.metrics.length,
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                crossAxisSpacing: AppSpacing.lg,
                mainAxisSpacing: AppSpacing.lg,
                childAspectRatio: 0.95,
              ),
              itemBuilder: (context, index) {
                final metric = dashboard.data.metrics[index];
                return MetricCard(
                  title: metric.title,
                  value: _formatMetric(metric),
                  subtitle: metric.subtitle,
                  icon: _iconForMetric(metric.id),
                  color: _colorForMetric(metric.colorKey),
                  trend: metric.trend,
                );
              },
            ),
            const SizedBox(height: AppSpacing.xl),
            _buildRoleSection(user.role, dashboard.data),
          ],
        ],
      ),
    ).animate().fadeIn(duration: 250.ms);
  }

  Widget _buildRoleSection(String role, DashboardData data) {
    final normalized = RoleUtils.normalize(role);
    if (normalized == 'teacher') {
      return ChartCard(
        title: 'Davomat sifati',
        subtitle: 'So\'nggi ko\'rsatkichlar bo\'yicha ustoz progressi',
        child: Center(
          child: SizedBox(
            width: 150,
            height: 150,
            child: Stack(
              alignment: Alignment.center,
              children: [
                CircularProgressIndicator(
                  value: (data.teacherAttendanceRate.clamp(0, 100)) / 100,
                  strokeWidth: 14,
                  backgroundColor: AppColors.surfaceAlt,
                ),
                Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      Formatters.percent(data.teacherAttendanceRate),
                      style: AppTextStyles.headline,
                    ),
                    Text('Davomat', style: AppTextStyles.bodySmall),
                  ],
                ),
              ],
            ),
          ),
        ),
      );
    }

    if (normalized == 'student') {
      return ChartCard(
        title: 'Chaqmoq reytingi',
        subtitle: 'Faollik va intizom bo\'yicha umumiy natija',
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 110,
                height: 110,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: AppColors.accentGradient,
                  boxShadow: const [
                    BoxShadow(
                      color: AppColors.glowPrimary,
                      blurRadius: 24,
                      offset: Offset(0, 12),
                    ),
                  ],
                ),
                alignment: Alignment.center,
                child: Text(
                  '${data.studentScore}',
                  style: AppTextStyles.headline,
                ),
              ),
              const SizedBox(height: AppSpacing.lg),
              Text(
                'Reyting badge: #${data.studentRank}',
                style: AppTextStyles.subtitle,
              ),
            ],
          ),
        ),
      );
    }

    if (normalized == 'parent') {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SectionHeader(
            title: 'Farzandlar',
            subtitle: 'Qisqa holat kartalari',
          ),
          const SizedBox(height: AppSpacing.lg),
          ...data.children.map(
            (child) => Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.lg),
              child: GlassCard(
                child: Row(
                  children: [
                    CircleAvatar(
                      backgroundColor: AppColors.primary.withValues(
                        alpha: 0.24,
                      ),
                      child: Text(
                        Formatters.initials(child.fullName),
                        style: AppTextStyles.label,
                      ),
                    ),
                    const SizedBox(width: AppSpacing.md),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            child.fullName,
                            style: AppTextStyles.title.copyWith(fontSize: 16),
                          ),
                          const SizedBox(height: AppSpacing.xs),
                          Text(
                            '${child.groupName.isEmpty ? 'Guruh yo\'q' : child.groupName} • Davomat ${Formatters.percent(child.attendanceRate)}',
                            style: AppTextStyles.bodySmall,
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      );
    }

    return ChartCard(
      title: 'Tushum trendlari',
      subtitle: 'So\'nggi 7 oy dinamikasi',
      child: data.revenueTrend.isEmpty
          ? Center(
              child: Text(
                'Trend ma\'lumoti topilmadi',
                style: AppTextStyles.subtitle,
              ),
            )
          : LineChart(
              LineChartData(
                gridData: const FlGridData(show: false),
                borderData: FlBorderData(show: false),
                titlesData: FlTitlesData(
                  topTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false),
                  ),
                  rightTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false),
                  ),
                  leftTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      reservedSize: 42,
                      getTitlesWidget: (value, _) {
                        return Text(
                          Formatters.currency(value, compact: true),
                          style: AppTextStyles.bodySmall,
                        );
                      },
                    ),
                  ),
                  bottomTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      getTitlesWidget: (value, _) {
                        final index = value.toInt();
                        if (index < 0 || index >= data.revenueTrend.length) {
                          return const SizedBox.shrink();
                        }
                        return Text(
                          data.revenueTrend[index].label,
                          style: AppTextStyles.bodySmall,
                        );
                      },
                    ),
                  ),
                ),
                lineBarsData: [
                  LineChartBarData(
                    isCurved: true,
                    color: AppColors.secondary,
                    barWidth: 3,
                    belowBarData: BarAreaData(
                      show: true,
                      color: AppColors.secondary.withValues(alpha: 0.15),
                    ),
                    dotData: const FlDotData(show: false),
                    spots: List.generate(
                      data.revenueTrend.length,
                      (index) => FlSpot(
                        index.toDouble(),
                        data.revenueTrend[index].value,
                      ),
                    ),
                  ),
                ],
              ),
            ),
    );
  }

  String _formatMetric(DashboardMetric metric) {
    if (metric.id == 'attendance') {
      return '${metric.value}%';
    }
    final parsed = int.tryParse(metric.value) ?? 0;
    if (metric.id == 'students' || metric.id == 'groups') {
      return parsed.toString();
    }
    return Formatters.currency(parsed, compact: true);
  }

  IconData _iconForMetric(String id) {
    return switch (id) {
      'revenue' || 'income' => Icons.payments_rounded,
      'students' => Icons.groups_rounded,
      'attendance' => Icons.fact_check_rounded,
      'debt' => Icons.warning_amber_rounded,
      'score' => Icons.bolt_rounded,
      'groups' => Icons.view_module_rounded,
      _ => Icons.insights_rounded,
    };
  }

  Color _colorForMetric(String key) {
    return switch (key) {
      'teal' => AppColors.secondary,
      'green' => AppColors.success,
      'red' => AppColors.danger,
      _ => AppColors.primary,
    };
  }
}
