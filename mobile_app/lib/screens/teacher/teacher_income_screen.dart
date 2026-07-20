import 'dart:math' as math;

import 'package:chaqmoq_mobile/core/theme/panel_tokens.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/teacher_models.dart';
import 'package:chaqmoq_mobile/providers/teacher_provider.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class TeacherIncomeScreen extends StatefulWidget {
  const TeacherIncomeScreen({super.key});

  @override
  State<TeacherIncomeScreen> createState() => _State();
}

class _State extends State<TeacherIncomeScreen> {
  late int _year;
  late int _month;

  static const _monthNames = [
    '', 'Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun',
    'Iyul', 'Avgust', 'Sentyabr', 'Oktyabr', 'Noyabr', 'Dekabr'
  ];
  static const _monthShorts = [
    '', 'Y', 'F', 'M', 'A', 'M', 'I', 'I', 'A', 'S', 'O', 'N', 'D'
  ];

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _year = now.year;
    _month = now.month;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        context
            .read<TeacherProvider>()
            .loadIncome(year: _year, month: _month);
      }
    });
  }

  bool get _isCurrentMonth {
    final now = DateTime.now();
    return _year == now.year && _month == now.month;
  }

  void _prevMonth() {
    setState(() {
      if (_month == 1) {
        _month = 12;
        _year--;
      } else {
        _month--;
      }
    });
    context
        .read<TeacherProvider>()
        .forceReloadIncome(year: _year, month: _month);
  }

  void _nextMonth() {
    if (_isCurrentMonth) return;
    setState(() {
      if (_month == 12) {
        _month = 1;
        _year++;
      } else {
        _month++;
      }
    });
    context
        .read<TeacherProvider>()
        .forceReloadIncome(year: _year, month: _month);
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final p = context.watch<TeacherProvider>();
    final income = p.income;

    return Scaffold(
      backgroundColor: PanelTokens.bg(isDark),
      appBar: AppBar(
        backgroundColor: PanelTokens.surface(isDark),
        elevation: 0,
        scrolledUnderElevation: 0,
        title: Text(
          "Daromadim",
          style: TextStyle(
            color: PanelTokens.text(isDark),
            fontWeight: FontWeight.w800,
            fontSize: PanelTokens.fontTitle,
          ),
        ),
        actions: [
          IconButton(
            icon: Icon(Icons.refresh_rounded,
                color: PanelTokens.textMuted(isDark)),
            onPressed: () => context
                .read<TeacherProvider>()
                .forceReloadIncome(year: _year, month: _month),
          ),
        ],
      ),
      body: Builder(builder: (context) {
        if (p.incomeState == ViewState.loading) {
          return const Center(
              child: CircularProgressIndicator(
                  color: PanelTokens.teacherAccent));
        }
        if (p.incomeState == ViewState.error) {
          return Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                const Icon(Icons.wifi_off_rounded,
                    color: PanelTokens.danger, size: 48),
                const SizedBox(height: 14),
                Text(p.incomeError,
                    style:
                        const TextStyle(color: PanelTokens.danger, fontSize: 13),
                    textAlign: TextAlign.center),
                const SizedBox(height: 16),
                ElevatedButton.icon(
                  onPressed: () => context
                      .read<TeacherProvider>()
                      .forceReloadIncome(year: _year, month: _month),
                  icon:
                      const Icon(Icons.refresh_rounded, size: 16),
                  label: const Text("Qayta urinish"),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: PanelTokens.teacherAccent,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12)),
                  ),
                ),
              ]),
            ),
          );
        }
        if (income == null) {
          return Center(
            child: Text("Ma'lumot yo'q",
                style: TextStyle(color: PanelTokens.textMuted(isDark))),
          );
        }
        return _buildContent(income, isDark);
      }),
    );
  }

  Widget _buildContent(TeacherIncomeModel income, bool isDark) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 40),
      children: [
        // ── Month selector ──────────────────────────────────────────────
        _MonthSelector(
          label: "${_monthNames[_month]} $_year",
          onPrev: _prevMonth,
          onNext: _isCurrentMonth ? null : _nextMonth,
          isDark: isDark,
        ),
        const SizedBox(height: 14),

        // ── Main salary card ─────────────────────────────────────────────
        _MainSalaryCard(income: income, isDark: isDark),
        const SizedBox(height: 14),

        // ── Prediction card (only for current month) ─────────────────────
        if (_isCurrentMonth) ...[
          _PredictionCard(income: income, isDark: isDark),
          const SizedBox(height: 14),
        ],

        // ── Yearly bar chart ─────────────────────────────────────────────
        if (income.yearly.isNotEmpty) ...[
          _YearlyBarChart(
            yearly: income.yearly,
            activeMonth: _month,
            monthShorts: _monthShorts,
            isDark: isDark,
          ),
          const SizedBox(height: 14),
        ],

        // ── Group breakdown ──────────────────────────────────────────────
        if (income.details.isNotEmpty) ...[
          _SectionHeader(title: "Guruhlar bo'yicha", isDark: isDark),
          const SizedBox(height: 10),
          _GroupBreakdownChart(details: income.details, isDark: isDark),
          const SizedBox(height: 10),
          ...income.details.map((d) => _GroupRow(data: d, isDark: isDark)),
        ],

        const SizedBox(height: 32),
      ],
    );
  }
}

// ─── Month Selector ────────────────────────────────────────────────────────────

class _MonthSelector extends StatelessWidget {
  const _MonthSelector(
      {required this.label,
      required this.onPrev,
      this.onNext,
      required this.isDark});

  final String label;
  final VoidCallback onPrev;
  final VoidCallback? onNext;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
      decoration: PanelTokens.cardDecoration(isDark),
      child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
        IconButton(
          icon: Icon(Icons.chevron_left_rounded,
              color: PanelTokens.textMuted(isDark)),
          onPressed: onPrev,
        ),
        Expanded(
          child: Center(
            child: Text(label,
                style: TextStyle(
                    color: PanelTokens.text(isDark),
                    fontWeight: FontWeight.w800,
                    fontSize: 16)),
          ),
        ),
        IconButton(
          icon: Icon(
            Icons.chevron_right_rounded,
            color: onNext != null
                ? PanelTokens.textMuted(isDark)
                : PanelTokens.textFaint(isDark),
          ),
          onPressed: onNext,
        ),
      ]),
    );
  }
}

// ─── Main Salary Card ──────────────────────────────────────────────────────────

class _MainSalaryCard extends StatelessWidget {
  const _MainSalaryCard({required this.income, required this.isDark});

  final TeacherIncomeModel income;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    final pct = income.progressPct;
    final progressColor = pct >= 100
        ? const Color(0xFF34D399)
        : pct >= 75
            ? Colors.white
            : const Color(0xFFFBBF24);

    return Container(
      padding: const EdgeInsets.all(22),
      decoration: PanelTokens.gradientCard(
          [const Color(0xFF312E81), const Color(0xFF0284C7)]),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text("Hisoblangan oylik",
                  style: TextStyle(color: Colors.white60, fontSize: 13)),
              const SizedBox(height: 6),
              Text(
                Formatters.currency(income.salary),
                style: const TextStyle(
                    color: Colors.white,
                    fontSize: 28,
                    fontWeight: FontWeight.w900,
                    letterSpacing: -0.5),
              ),
            ]),
          ),
          if (income.isLocked)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(
                  color: Colors.white24,
                  borderRadius: BorderRadius.circular(10)),
              child: const Row(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.lock_rounded, size: 12, color: Colors.white70),
                SizedBox(width: 4),
                Text("Yopilgan",
                    style: TextStyle(
                        color: Colors.white70,
                        fontSize: 11,
                        fontWeight: FontWeight.w600)),
              ]),
            ),
        ]),
        const SizedBox(height: 18),
        // Stats row
        Row(children: [
          _InlineStatItem(
            label: "Maksimal",
            value: Formatters.currency(income.expectedIncome),
          ),
          const SizedBox(width: 16),
          _InlineStatItem(
            label: "Guruhlar",
            value: "${income.details.length} ta",
          ),
          const Spacer(),
          Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
            Text("$pct%",
                style: const TextStyle(
                    color: Colors.white,
                    fontSize: 26,
                    fontWeight: FontWeight.w900)),
            const Text("yig'ildi",
                style: TextStyle(color: Colors.white60, fontSize: 10)),
          ]),
        ]),
        const SizedBox(height: 12),
        ClipRRect(
          borderRadius: BorderRadius.circular(6),
          child: LinearProgressIndicator(
            value: (pct / 100).clamp(0.0, 1.0),
            backgroundColor: Colors.white24,
            valueColor: AlwaysStoppedAnimation<Color>(progressColor),
            minHeight: 8,
          ),
        ),
        const SizedBox(height: 8),
        // Milestone labels
        Row(children: [
          const Text("0%",
              style: TextStyle(color: Colors.white38, fontSize: 10)),
          const Spacer(),
          Text("50%",
              style: TextStyle(
                  color: pct >= 50 ? Colors.white70 : Colors.white30,
                  fontSize: 10)),
          const Spacer(),
          Text("100%",
              style: TextStyle(
                  color: pct >= 100 ? const Color(0xFF34D399) : Colors.white30,
                  fontSize: 10)),
        ]),
      ]),
    );
  }
}

class _InlineStatItem extends StatelessWidget {
  const _InlineStatItem({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(label,
          style: const TextStyle(color: Colors.white54, fontSize: 10)),
      const SizedBox(height: 2),
      Text(value,
          style: const TextStyle(
              color: Colors.white70,
              fontSize: 13,
              fontWeight: FontWeight.w700)),
    ]);
  }
}

// ─── Prediction Card ───────────────────────────────────────────────────────────

class _PredictionCard extends StatelessWidget {
  const _PredictionCard({required this.income, required this.isDark});

  final TeacherIncomeModel income;
  final bool isDark;

  int get _predicted {
    final now = DateTime.now();
    final daysInMonth = DateTime(now.year, now.month + 1, 0).day;
    final daysPassed = math.max(1, now.day);
    if (income.salary == 0) return income.expectedIncome;
    return math
        .min((income.salary * daysInMonth / daysPassed).round(), income.expectedIncome);
  }

  int get _gap => income.expectedIncome - _predicted;

  double get _completionPct =>
      income.expectedIncome > 0 ? _predicted / income.expectedIncome : 0;

  @override
  Widget build(BuildContext context) {
    final predicted = _predicted;
    final gap = _gap;
    final now = DateTime.now();
    final daysInMonth = DateTime(now.year, now.month + 1, 0).day;
    final remaining = daysInMonth - now.day;
    final confidence = math.min(100, (now.day / daysInMonth * 100).round());

    final isGood = _completionPct >= 0.85;
    final color = isGood ? PanelTokens.success : PanelTokens.warning;

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: PanelTokens.card(isDark),
        borderRadius: BorderRadius.circular(PanelTokens.cardRadius),
        border: Border.all(color: color.withValues(alpha: 0.3)),
        boxShadow: [
          BoxShadow(
            color: color.withValues(alpha: 0.08),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        // Header
        Row(children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(Icons.auto_graph_rounded, color: color, size: 18),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text("Oy oxirigacha bashorat",
                  style: TextStyle(
                      color: PanelTokens.text(isDark),
                      fontSize: 14,
                      fontWeight: FontWeight.w800)),
              Text("$remaining kun qoldi · $confidence% aniqlik",
                  style: TextStyle(
                      color: PanelTokens.textMuted(isDark), fontSize: 11)),
            ]),
          ),
          // Confidence badge
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text("~$confidence%",
                style: TextStyle(
                    color: color, fontSize: 11, fontWeight: FontWeight.w700)),
          ),
        ]),
        const SizedBox(height: 16),
        const Divider(height: 1),
        const SizedBox(height: 16),

        // Prediction amount
        Row(children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text("Bashorat qilingan maosh",
                  style: TextStyle(
                      color: PanelTokens.textMuted(isDark), fontSize: 11)),
              const SizedBox(height: 4),
              Text(Formatters.currency(predicted),
                  style: TextStyle(
                      color: color,
                      fontSize: 22,
                      fontWeight: FontWeight.w900,
                      letterSpacing: -0.3)),
            ]),
          ),
          // Gap indicator
          Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
            Text(gap > 0 ? "Yetishmaydi" : "To'liq!",
                style: TextStyle(
                    color: PanelTokens.textMuted(isDark), fontSize: 10)),
            const SizedBox(height: 2),
            Text(
              gap > 0 ? "-${Formatters.currency(gap)}" : "+${Formatters.currency((-gap).abs())}",
              style: TextStyle(
                  color: gap > 0 ? PanelTokens.warning : PanelTokens.success,
                  fontSize: 13,
                  fontWeight: FontWeight.w800),
            ),
          ]),
        ]),
        const SizedBox(height: 14),

        // Comparison bar
        Stack(children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: LinearProgressIndicator(
              value: _completionPct.clamp(0.0, 1.0),
              backgroundColor: PanelTokens.border(isDark),
              valueColor: AlwaysStoppedAnimation<Color>(color),
              minHeight: 10,
            ),
          ),
          // Current salary marker
          if (income.expectedIncome > 0)
            Positioned(
              left: (income.salary / income.expectedIncome)
                      .clamp(0.0, 0.97) *
                  (MediaQuery.of(context).size.width - 68),
              top: 1,
              bottom: 1,
              child: Container(
                width: 3,
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(2),
                  boxShadow: [
                    BoxShadow(
                        color: Colors.black.withValues(alpha: 0.2),
                        blurRadius: 2)
                  ],
                ),
              ),
            ),
        ]),
        const SizedBox(height: 8),

        // Legend
        Row(children: [
          _LegendDot(color: color, label: "Bashorat"),
          const SizedBox(width: 14),
          _LegendDot(color: Colors.white, label: "Hozirgi"),
        ]),
        const SizedBox(height: 12),

        // Tip
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.07),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Row(children: [
            Icon(Icons.lightbulb_outline_rounded, color: color, size: 14),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                gap > 0
                    ? "Davomatni oshiring — oylik oshadi. Maksimum: ${Formatters.currency(income.expectedIncome)}"
                    : "Ajoyib! Hozirgi davomat saqlanib qolsa, maksimal maosh olishingiz mumkin.",
                style: TextStyle(
                    color: PanelTokens.textMuted(isDark),
                    fontSize: 11,
                    height: 1.4),
              ),
            ),
          ]),
        ),
      ]),
    );
  }
}

class _LegendDot extends StatelessWidget {
  const _LegendDot({required this.color, required this.label});

  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Row(mainAxisSize: MainAxisSize.min, children: [
      Container(
          width: 8, height: 8,
          decoration: BoxDecoration(
              color: color, shape: BoxShape.circle)),
      const SizedBox(width: 4),
      Text(label,
          style: TextStyle(
              color: PanelTokens.textMuted(isDark),
              fontSize: 10)),
    ]);
  }
}

// ─── Yearly Bar Chart ──────────────────────────────────────────────────────────

class _YearlyBarChart extends StatefulWidget {
  const _YearlyBarChart({
    required this.yearly,
    required this.activeMonth,
    required this.monthShorts,
    required this.isDark,
  });

  final List<int> yearly;
  final int activeMonth;
  final List<String> monthShorts;
  final bool isDark;

  @override
  State<_YearlyBarChart> createState() => _YearlyBarChartState();
}

class _YearlyBarChartState extends State<_YearlyBarChart> {
  int _touchedIndex = -1;

  @override
  Widget build(BuildContext context) {
    final maxVal = widget.yearly.isEmpty
        ? 1.0
        : widget.yearly.reduce(math.max).toDouble();

    final bars = List.generate(12, (i) {
      final val = i < widget.yearly.length ? widget.yearly[i].toDouble() : 0.0;
      final isActive = (i + 1) == widget.activeMonth;
      final isTouched = i == _touchedIndex;

      final bool dark = widget.isDark;
      Color barColor;
      if (isTouched) {
        barColor = Colors.white.withValues(alpha: 0.9);
      } else if (isActive) {
        barColor = PanelTokens.teacherAccent;
      } else {
        barColor = PanelTokens.teacherAccent.withValues(alpha: dark ? 0.3 : 0.25);
      }

      return BarChartGroupData(
        x: i,
        showingTooltipIndicators: isTouched ? [0] : [],
        barRods: [
          BarChartRodData(
            toY: val,
            width: 16,
            color: barColor,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(6)),
          ),
        ],
      );
    });

    return Container(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
      decoration: PanelTokens.cardDecoration(widget.isDark),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(Icons.bar_chart_rounded,
              size: 16, color: PanelTokens.teacherAccent),
          const SizedBox(width: 8),
          Text("Yillik ko'rsatkich",
              style: TextStyle(
                  color: PanelTokens.text(widget.isDark),
                  fontSize: 14,
                  fontWeight: FontWeight.w800)),
          const Spacer(),
          Text("${widget.yearly.where((v) => v > 0).length} / 12 oy",
              style: TextStyle(
                  color: PanelTokens.textMuted(widget.isDark), fontSize: 11)),
        ]),
        const SizedBox(height: 18),
        SizedBox(
          height: 120,
          child: BarChart(
            BarChartData(
              maxY: maxVal > 0 ? maxVal * 1.25 : 1,
              minY: 0,
              gridData: FlGridData(
                show: true,
                drawVerticalLine: false,
                horizontalInterval: maxVal > 0 ? maxVal / 4 : 1,
                getDrawingHorizontalLine: (v) => FlLine(
                  color: PanelTokens.border(widget.isDark),
                  strokeWidth: 1,
                ),
              ),
              borderData: FlBorderData(show: false),
              titlesData: FlTitlesData(
                topTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false)),
                rightTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false)),
                leftTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false)),
                bottomTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: true,
                    reservedSize: 24,
                    getTitlesWidget: (val, _) {
                      final i = val.toInt();
                      if (i < 1 || i >= widget.monthShorts.length) {
                        return const SizedBox();
                      }
                      final isActive = (i) == widget.activeMonth;
                      return Text(
                        widget.monthShorts[i],
                        style: TextStyle(
                          fontSize: 9,
                          fontWeight:
                              isActive ? FontWeight.w900 : FontWeight.w500,
                          color: isActive
                              ? PanelTokens.teacherAccent
                              : PanelTokens.textMuted(widget.isDark),
                        ),
                      );
                    },
                  ),
                ),
              ),
              barGroups: bars,
              barTouchData: BarTouchData(
                touchCallback: (event, response) {
                  if (event is FlTapUpEvent || event is FlPanEndEvent) {
                    setState(() => _touchedIndex = -1);
                  } else if (response?.spot != null) {
                    setState(
                        () => _touchedIndex = response!.spot!.touchedBarGroupIndex);
                  }
                },
                touchTooltipData: BarTouchTooltipData(
                  getTooltipColor: (_) =>
                      widget.isDark
                          ? const Color(0xFF1E2A3A)
                          : const Color(0xFF1E293B),
                  tooltipRoundedRadius: 8,
                  tooltipPadding: const EdgeInsets.symmetric(
                      horizontal: 10, vertical: 6),
                  getTooltipItem: (group, gi, rod, ri) => BarTooltipItem(
                    Formatters.currency(rod.toY.round()),
                    const TextStyle(
                        color: Colors.white,
                        fontSize: 11,
                        fontWeight: FontWeight.w700),
                  ),
                ),
              ),
            ),
          ),
        ),
      ]),
    );
  }
}

// ─── Group Breakdown Chart ─────────────────────────────────────────────────────

class _GroupBreakdownChart extends StatelessWidget {
  const _GroupBreakdownChart(
      {required this.details, required this.isDark});

  final List<Map<String, dynamic>> details;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    final total = details.fold<int>(
        0, (s, d) => s + ((d['salary'] as num?)?.toInt() ?? 0));
    if (total == 0) return const SizedBox.shrink();

    final colors = [
      PanelTokens.teacherAccent,
      PanelTokens.info,
      PanelTokens.success,
      PanelTokens.warning,
      PanelTokens.danger,
      const Color(0xFFA855F7),
    ];

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: PanelTokens.cardDecoration(isDark),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text("Daromad taqsimoti",
            style: TextStyle(
                color: PanelTokens.text(isDark),
                fontSize: 13,
                fontWeight: FontWeight.w700)),
        const SizedBox(height: 14),
        ...List.generate(details.length, (i) {
          final d = details[i];
          final sal = (d['salary'] as num?)?.toInt() ?? 0;
          final frac = total > 0 ? sal / total : 0.0;
          final color = colors[i % colors.length];
          return Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Row(children: [
              Container(
                  width: 10,
                  height: 10,
                  decoration: BoxDecoration(
                      color: color, shape: BoxShape.circle)),
              const SizedBox(width: 8),
              Expanded(
                flex: 2,
                child: Text(
                  '${d['group_name'] ?? ''}',
                  style: TextStyle(
                      color: PanelTokens.text(isDark),
                      fontSize: 11,
                      fontWeight: FontWeight.w600),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              Expanded(
                flex: 3,
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(3),
                    child: LinearProgressIndicator(
                      value: frac,
                      backgroundColor: PanelTokens.border(isDark),
                      valueColor: AlwaysStoppedAnimation<Color>(color),
                      minHeight: 6,
                    ),
                  ),
                ),
              ),
              Text(
                "${(frac * 100).round()}%",
                style: TextStyle(
                    color: color,
                    fontSize: 11,
                    fontWeight: FontWeight.w700),
              ),
            ]),
          );
        }),
      ]),
    );
  }
}

// ─── Section Header ────────────────────────────────────────────────────────────

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title, required this.isDark});

  final String title;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Row(children: [
      Container(
        width: 4,
        height: 16,
        decoration: BoxDecoration(
          color: PanelTokens.teacherAccent,
          borderRadius: BorderRadius.circular(2),
        ),
      ),
      const SizedBox(width: 8),
      Text(title,
          style: TextStyle(
              color: PanelTokens.text(isDark),
              fontSize: PanelTokens.fontSection,
              fontWeight: FontWeight.w800)),
    ]);
  }
}

// ─── Group Row ─────────────────────────────────────────────────────────────────

class _GroupRow extends StatelessWidget {
  const _GroupRow({required this.data, required this.isDark});

  final Map<String, dynamic> data;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    final name = '${data['group_name'] ?? ''}';
    final salary = (data['salary'] as num? ?? 0).toInt();
    final att = (data['attendance'] as num? ?? 0).toInt();
    final pct = (data['fi'] as num? ?? 0).toInt();

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: PanelTokens.cardDecoration(isDark),
      child: Row(children: [
        Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: PanelTokens.teacherAccent.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(11),
          ),
          child: const Icon(Icons.groups_rounded,
              color: PanelTokens.teacherAccent, size: 20),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(name,
                style: TextStyle(
                    color: PanelTokens.text(isDark),
                    fontWeight: FontWeight.w700,
                    fontSize: 13)),
            const SizedBox(height: 3),
            Row(children: [
              Icon(Icons.fact_check_outlined,
                  size: 11, color: PanelTokens.textMuted(isDark)),
              const SizedBox(width: 3),
              Text("$att dars",
                  style: TextStyle(
                      color: PanelTokens.textMuted(isDark), fontSize: 11)),
              const SizedBox(width: 8),
              Icon(Icons.percent_rounded,
                  size: 11, color: PanelTokens.textMuted(isDark)),
              const SizedBox(width: 3),
              Text("$pct% davomat",
                  style: TextStyle(
                      color: PanelTokens.textMuted(isDark), fontSize: 11)),
            ]),
          ]),
        ),
        Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Text(Formatters.currency(salary),
              style: const TextStyle(
                  color: PanelTokens.success,
                  fontWeight: FontWeight.w800,
                  fontSize: 13)),
          const SizedBox(height: 2),
          Text("bu guruhdan",
              style: TextStyle(
                  color: PanelTokens.textMuted(isDark), fontSize: 9)),
        ]),
      ]),
    );
  }
}
