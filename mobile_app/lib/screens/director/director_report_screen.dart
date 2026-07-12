import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/design/ds_colors.dart';
import '../../core/design/ds_components.dart';
import '../../core/design/ds_format.dart';
import '../../core/design/ds_tokens.dart';
import '../../core/design/ds_typography.dart';
import 'data/director_data.dart';
import 'data/director_provider.dart';
import 'widgets/director_charts.dart';
import 'widgets/director_states.dart';

const _uzMonths = [
  '', 'Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun',
  'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr',
];

class DirectorReportScreen extends StatefulWidget {
  const DirectorReportScreen({super.key, required this.data});
  final DirectorData data;

  @override
  State<DirectorReportScreen> createState() => _DirectorReportScreenState();
}

class _DirectorReportScreenState extends State<DirectorReportScreen> {
  DateTime _month = DateTime(DateTime.now().year, DateTime.now().month, 1);
  late Future<DirectorReport> _future;

  String get _value => '${_month.year}-${_month.month.toString().padLeft(2, '0')}';
  String get _label {
    final now = DateTime.now();
    if (_month.year == now.year && _month.month == now.month) return 'Joriy oy — ${_uzMonths[_month.month]}';
    return '${_uzMonths[_month.month]} ${_month.year}';
  }

  @override
  void initState() {
    super.initState();
    _future = context.read<DirectorProvider>().loadReport(_value);
  }

  void _select(DateTime m) {
    setState(() {
      _month = DateTime(m.year, m.month, 1);
      _future = context.read<DirectorProvider>().loadReport(_value);
    });
  }

  Future<void> _openMonthPicker() async {
    final picked = await showModalBottomSheet<DateTime>(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (_) => _MonthPickerSheet(initial: _month),
    );
    if (picked != null) _select(picked);
  }

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return SafeArea(
      bottom: false,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(DsSpace.screen, DsSpace.x3, DsSpace.screen, 0),
            child: Text('Hisobot', style: DsType.h1(ds.textPrimary)),
          ),
          const SizedBox(height: 12),
          // Oy tanlagich (bosib tanlaysiz)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: DsSpace.screen),
            child: Material(
              color: ds.card,
              borderRadius: DsRadius.all(DsRadius.md),
              child: InkWell(
                onTap: _openMonthPicker,
                borderRadius: DsRadius.all(DsRadius.md),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
                  decoration: BoxDecoration(
                    borderRadius: DsRadius.all(DsRadius.md),
                    border: Border.all(color: ds.border),
                  ),
                  child: Row(children: [
                    Icon(Icons.calendar_month_rounded, size: 20, color: ds.primary),
                    const SizedBox(width: 10),
                    Text(_label, style: DsType.bodyStrong(ds.textPrimary)),
                    const Spacer(),
                    Text('O\'zgartirish', style: DsType.small(ds.primary)),
                    Icon(Icons.keyboard_arrow_down_rounded, size: 20, color: ds.textMuted),
                  ]),
                ),
              ),
            ),
          ),
          const SizedBox(height: DsSpace.x5),
          Expanded(
            child: FutureBuilder<DirectorReport>(
              future: _future,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const DirectorLoading();
                }
                if (snapshot.hasError || !snapshot.hasData) {
                  return DirectorErrorView(
                    onRetry: () => setState(() => _future = context.read<DirectorProvider>().loadReport(_value)),
                  );
                }
                return _ReportBody(report: snapshot.data!);
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _ReportBody extends StatelessWidget {
  const _ReportBody({required this.report});
  final DirectorReport report;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    final r = report;
    return ListView(
      padding: const EdgeInsets.fromLTRB(DsSpace.screen, 0, DsSpace.screen, DsSpace.x8),
      children: [
        // Sof foyda
        DsCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Sof foyda — ${r.monthLabel}', style: DsType.caption(ds.textMuted)),
              const SizedBox(height: 4),
              Text(dsSom(r.netProfit, withSuffix: true),
                  style: DsType.display(r.netProfit >= 0 ? ds.success : ds.danger)),
              const SizedBox(height: 14),
              Row(children: [
                Expanded(child: _MiniStat(label: 'Daromad', value: dsSom(r.revenue), color: ds.primary)),
                Container(width: 1, height: 34, color: ds.border),
                Expanded(child: _MiniStat(label: 'Xarajat', value: dsSom(r.expenses + r.teacherSalary), color: ds.warning)),
              ]),
            ],
          ),
        ),
        const SizedBox(height: DsSpace.section),
        if (r.incomeVsExpense.isNotEmpty) ...[
          DsCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Daromad vs xarajat — 6 oy (mln)', style: DsType.bodyStrong(ds.textPrimary)),
                const SizedBox(height: 16),
                SizedBox(
                  height: 150,
                  child: IncomeExpenseChart(
                    data: [for (final p in r.incomeVsExpense) (p.income, p.expense)],
                    months: [for (final p in r.incomeVsExpense) p.label],
                  ),
                ),
                const SizedBox(height: 14),
                Row(children: [
                  ChartLegendDot(color: ds.primary, label: 'Daromad'),
                  const SizedBox(width: 18),
                  ChartLegendDot(color: ds.warning, label: 'Xarajat'),
                ]),
              ],
            ),
          ),
          const SizedBox(height: DsSpace.section),
        ],
        // O'qituvchi maoshlari — kimga qancha
        if (r.teacherSalaries.isNotEmpty) ...[
          DsSectionHeader('O\'qituvchi maoshlari'),
          const SizedBox(height: 8),
          _ItemListCard(items: r.teacherSalaries, icon: Icons.school_rounded, tone: DsStatus.info),
          const SizedBox(height: DsSpace.section),
        ],
        // Xarajatlar
        if (r.expensesList.isNotEmpty) ...[
          DsSectionHeader('Xarajatlar'),
          const SizedBox(height: 8),
          _ItemListCard(items: r.expensesList, icon: Icons.receipt_long_rounded, tone: DsStatus.warning),
          const SizedBox(height: DsSpace.section),
        ],
        // Qabul qilingan to'lovlar
        DsSectionHeader('Qabul qilingan to\'lovlar'),
        const SizedBox(height: 8),
        if (r.payments.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 22),
            child: Center(child: Text('Bu oyда to\'lov qabul qilinmagan', style: DsType.caption(ds.textMuted))),
          )
        else
          DsCard(
            padding: const EdgeInsets.symmetric(horizontal: DsSpace.x5, vertical: DsSpace.x2),
            child: Column(children: [
              for (final (i, p) in r.payments.indexed) ...[
                if (i > 0) Container(height: 1, color: ds.border),
                DsListRow(
                  leading: DsAvatar(p.name, tone: p.tone),
                  title: p.name,
                  subtitle: '${p.subtitle}${p.time.isNotEmpty ? ' · ${p.time}' : ''}',
                  trailing: Text(dsSom(p.amount, sign: true), style: DsType.bodyStrong(ds.success)),
                ),
              ],
            ]),
          ),
        // Agar bu oyда hech narsa bo'lmasa
        if (r.teacherSalaries.isEmpty && r.expensesList.isEmpty && r.payments.isEmpty && r.revenue == 0)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Center(child: Text('Bu oy uchun ma\'lumot yo\'q', style: DsType.small(ds.textFaint))),
          ),
      ],
    );
  }
}

class _ItemListCard extends StatelessWidget {
  const _ItemListCard({required this.items, required this.icon, required this.tone});
  final List<(String, int)> items;
  final IconData icon;
  final DsStatus tone;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    final (bg, fg) = tone == DsStatus.warning ? (ds.warningBg, ds.warningFg) : (ds.primarySoft, ds.primarySoftFg);
    return DsCard(
      padding: const EdgeInsets.symmetric(horizontal: DsSpace.x5, vertical: DsSpace.x2),
      child: Column(
        children: [
          for (final (i, e) in items.indexed) ...[
            if (i > 0) Container(height: 1, color: ds.border),
            DsListRow(
              leading: Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(color: bg, borderRadius: DsRadius.all(DsRadius.sm)),
                child: Icon(icon, size: 18, color: fg),
              ),
              title: e.$1,
              trailing: Text(dsSom(e.$2), style: DsType.bodyStrong(ds.textPrimary)),
            ),
          ],
        ],
      ),
    );
  }
}

class _MiniStat extends StatelessWidget {
  const _MiniStat({required this.label, required this.value, required this.color});
  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Column(
      children: [
        Text(value, style: DsType.bodyStrong(ds.textPrimary)),
        const SizedBox(height: 2),
        Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          Container(width: 8, height: 8, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
          const SizedBox(width: 6),
          Text(label, style: DsType.small(ds.textMuted)),
        ]),
      ],
    );
  }
}

/// Oy tanlash bottom-sheet: yil navigatsiyasi + oy tarmog'i (kelajak o'chirilgan).
class _MonthPickerSheet extends StatefulWidget {
  const _MonthPickerSheet({required this.initial});
  final DateTime initial;

  @override
  State<_MonthPickerSheet> createState() => _MonthPickerSheetState();
}

class _MonthPickerSheetState extends State<_MonthPickerSheet> {
  late int _year = widget.initial.year;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    final now = DateTime.now();
    return Container(
      decoration: BoxDecoration(
        color: ds.card,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(DsRadius.xl)),
        boxShadow: DsShadow.raised(ds.isDark),
      ),
      padding: const EdgeInsets.fromLTRB(DsSpace.x5, DsSpace.x3, DsSpace.x5, DsSpace.x6),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Center(
            child: Container(width: 40, height: 4, decoration: BoxDecoration(color: ds.border, borderRadius: DsRadius.all(DsRadius.pill))),
          ),
          const SizedBox(height: 16),
          // Yil navigatsiyasi
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              IconButton(
                onPressed: () => setState(() => _year--),
                icon: Icon(Icons.chevron_left_rounded, color: ds.textSecondary),
              ),
              const SizedBox(width: 8),
              Text('$_year', style: DsType.h2(ds.textPrimary)),
              const SizedBox(width: 8),
              IconButton(
                onPressed: _year >= now.year ? null : () => setState(() => _year++),
                icon: Icon(Icons.chevron_right_rounded, color: _year >= now.year ? ds.textFaint : ds.textSecondary),
              ),
            ],
          ),
          const SizedBox(height: 12),
          // Oylar tarmog'i
          GridView.count(
            crossAxisCount: 3,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            childAspectRatio: 2.2,
            mainAxisSpacing: 10,
            crossAxisSpacing: 10,
            children: [
              for (var m = 1; m <= 12; m++)
                _MonthCell(
                  label: _uzMonths[m],
                  selected: widget.initial.year == _year && widget.initial.month == m,
                  disabled: _year > now.year || (_year == now.year && m > now.month),
                  onTap: () => Navigator.pop(context, DateTime(_year, m, 1)),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MonthCell extends StatelessWidget {
  const _MonthCell({required this.label, required this.selected, required this.disabled, required this.onTap});
  final String label;
  final bool selected;
  final bool disabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    final bg = selected ? ds.primary : ds.cardAlt;
    final fg = selected ? ds.primaryFg : (disabled ? ds.textFaint : ds.textPrimary);
    return Opacity(
      opacity: disabled ? 0.4 : 1,
      child: Material(
        color: bg,
        borderRadius: DsRadius.all(DsRadius.md),
        child: InkWell(
          onTap: disabled ? null : onTap,
          borderRadius: DsRadius.all(DsRadius.md),
          child: Center(child: Text(label, style: DsType.bodyStrong(fg))),
        ),
      ),
    );
  }
}
