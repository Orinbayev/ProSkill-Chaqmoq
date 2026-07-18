import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/design/ds_colors.dart';
import '../../core/design/ds_components.dart';
import '../../core/design/ds_format.dart';
import '../../core/design/ds_tokens.dart';
import '../../core/design/ds_typography.dart';
import 'data/director_data.dart';
import 'data/director_provider.dart';
import 'director_debtors_screen.dart';
import 'widgets/director_attendance_card.dart';
import 'widgets/director_charts.dart';
import 'widgets/director_header.dart';
import 'widgets/director_payment_sheet.dart';

class DirectorDashboardScreen extends StatelessWidget {
  const DirectorDashboardScreen({super.key, required this.data, this.onRefresh, this.onProfileTap, this.onBellTap});
  final DirectorData data;
  final Future<void> Function()? onRefresh;
  final VoidCallback? onProfileTap;
  final VoidCallback? onBellTap;

  @override
  Widget build(BuildContext context) {
    final list = ListView(
      padding: const EdgeInsets.fromLTRB(DsSpace.screen, DsSpace.x3, DsSpace.screen, DsSpace.x8),
      children: [
        DirectorHeader(
          subtitle: '${data.centerName.isEmpty ? 'Markaz' : data.centerName} · Boshqaruv',
          name: data.directorName.isEmpty ? 'Direktor' : data.directorName,
          onProfileTap: onProfileTap,
          onBellTap: onBellTap,
        ),
        const SizedBox(height: DsSpace.x5),
        DirectorHeroCard(
          label: 'Davr tushumi, so\'m',
          value: dsSom(data.periodRevenue),
          caption: '${data.revenueChange >= 0 ? '▲' : '▼'} ${data.revenueChange.abs().toStringAsFixed(0)}% · oldingi davrga nisbatan',
        ),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(
            child: DsKpiTile(
              icon: Icons.groups_rounded,
              value: '${data.activeStudents}',
              label: 'Faol o\'quvchilar',
              tone: DsStatus.info,
              delta: data.studentsChange != 0 ? '${data.studentsChange.abs().toStringAsFixed(0)}%' : null,
              deltaUp: data.studentsChange >= 0,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: DsKpiTile(
              icon: Icons.check_circle_rounded,
              value: '${data.avgAttendance}%',
              label: 'O\'rtacha davomat',
              tone: DsStatus.success,
            ),
          ),
        ]),
        const SizedBox(height: 12),
        _DebtSummaryCard(
          totalDebt: data.totalDebt,
          debtors: data.totalDebtors,
          onTap: () => _openDebtors(context),
        ),
        if (!data.attendanceMonitor.isEmpty) ...[
          const SizedBox(height: DsSpace.section),
          DirectorAttendanceCard(monitor: data.attendanceMonitor),
        ],
        const SizedBox(height: DsSpace.section),
        if (data.revenueTrend.isNotEmpty)
          DsCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                DsSectionHeader('Daromad — oxirgi 12 oy (mln)', actionLabel: 'Hisobot', onAction: () {}),
                const SizedBox(height: 16),
                SizedBox(
                  height: 150,
                  child: RevenueLineChart(
                    values: data.revenueTrend.map((p) => p.value).toList(),
                    months: data.revenueTrend.map((p) => p.label).toList(),
                  ),
                ),
              ],
            ),
          ),
        const SizedBox(height: DsSpace.section),
        DsCard(
          padding: const EdgeInsets.fromLTRB(DsSpace.x5, DsSpace.x5, DsSpace.x5, DsSpace.x3),
          child: Column(
            children: [
              DsSectionHeader(
                'Qarzdorlar — TOP',
                actionLabel: data.totalDebtors > 0 ? 'Barchasi · ${data.totalDebtors}' : null,
                onAction: () => _openDebtors(context),
              ),
              const SizedBox(height: 6),
              if (data.debtors.isEmpty)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 18),
                  child: Text('Qarzdorlar yo\'q — barcha to\'lovlar joyida', style: DsType.small(context.ds.textMuted)),
                )
              else
                for (final (i, d) in data.debtors.take(3).indexed) ...[
                  if (i > 0) Container(height: 1, color: context.ds.border),
                  _DebtorTopRow(debtor: d, methods: data.paymentMethods),
                ],
            ],
          ),
        ),
      ],
    );

    final body = SafeArea(bottom: false, child: list);
    if (onRefresh == null) return body;
    return SafeArea(
      bottom: false,
      child: RefreshIndicator(onRefresh: onRefresh!, color: context.ds.primary, child: list),
    );
  }

  void _openDebtors(BuildContext context) {
    final provider = context.read<DirectorProvider>();
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ChangeNotifierProvider<DirectorProvider>.value(
          value: provider,
          child: const DirectorDebtorsScreen(),
        ),
      ),
    );
  }
}

class _DebtSummaryCard extends StatelessWidget {
  const _DebtSummaryCard({required this.totalDebt, required this.debtors, required this.onTap});
  final int totalDebt;
  final int debtors;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return DsCard(
      onTap: onTap,
      padding: const EdgeInsets.all(DsSpace.x4),
      child: Row(
        children: [
          Container(
            width: 34,
            height: 34,
            decoration: BoxDecoration(color: ds.dangerBg, borderRadius: DsRadius.all(DsRadius.sm)),
            child: Icon(Icons.account_balance_wallet_rounded, size: 18, color: ds.dangerFg),
          ),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(dsSom(totalDebt), style: DsType.h2(ds.textPrimary)),
              Text('Jami qarzdorlik, so\'m', style: DsType.small(ds.textMuted)),
            ],
          ),
          const Spacer(),
          DsBadge('$debtors ta', status: DsStatus.danger),
          const SizedBox(width: 4),
          Icon(Icons.chevron_right, color: ds.textFaint),
        ],
      ),
    );
  }
}

class _DebtorTopRow extends StatelessWidget {
  const _DebtorTopRow({required this.debtor, this.methods = const []});
  final DirectorDebtor debtor;
  final List<String> methods;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return DsListRow(
      leading: DsAvatar(debtor.name, tone: debtor.tone),
      title: debtor.name,
      subtitle: [debtor.group, if (debtor.months.isNotEmpty) '${debtor.months.length} oy']
          .where((e) => e.isNotEmpty)
          .join(' · '),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(dsSom(-debtor.totalDebt), style: DsType.bodyStrong(ds.danger)),
          const SizedBox(width: 10),
          DsButton(
            label: 'To\'lov',
            expand: false,
            height: 36,
            onPressed: () async {
              final ok = await showDirectorPaymentSheet(context, debtor, methods: methods);
              if (ok == true && context.mounted) context.read<DirectorProvider>().refresh();
            },
          ),
        ],
      ),
    );
  }
}
