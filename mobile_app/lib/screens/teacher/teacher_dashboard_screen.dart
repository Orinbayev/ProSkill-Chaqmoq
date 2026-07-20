import 'dart:math' as math;

import 'package:chaqmoq_mobile/core/theme/panel_tokens.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/teacher_models.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/teacher_provider.dart';
import 'package:chaqmoq_mobile/screens/teacher/teacher_attendance_screen.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class TeacherDashboardScreen extends StatefulWidget {
  const TeacherDashboardScreen({super.key, this.onGoGroups, this.onGoIncome});

  final VoidCallback? onGoGroups;
  final VoidCallback? onGoIncome;

  @override
  State<TeacherDashboardScreen> createState() => _State();
}

class _State extends State<TeacherDashboardScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      context.read<TeacherProvider>()
        ..loadGroups()
        ..loadIncome();
    });
  }

  Future<void> _refresh() async {
    final p = context.read<TeacherProvider>();
    await Future.wait([p.loadGroups(), p.forceReloadIncome()]);
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final auth = context.watch<AuthProvider>();
    final p = context.watch<TeacherProvider>();
    final name = auth.user?.firstName.isNotEmpty == true
        ? auth.user!.firstName
        : (auth.user?.fullName ?? "O'qituvchi");

    return Scaffold(
      backgroundColor: PanelTokens.bg(isDark),
      body: RefreshIndicator(
        color: PanelTokens.teacherAccent,
        onRefresh: _refresh,
        child: CustomScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          slivers: [
            _TeacherHeroBar(name: name, isDark: isDark, onRefresh: _refresh),
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 100),
              sliver: SliverList(
                delegate: SliverChildListDelegate([
                  // ── Salary prediction card ───────────────────────────────
                  _SalaryPredictionCard(p: p, isDark: isDark, onTap: widget.onGoIncome),
                  const SizedBox(height: 14),
                  // ── Stats row ────────────────────────────────────────────
                  _StatsRow(p: p, isDark: isDark),
                  const SizedBox(height: 20),
                  // ── Yearly mini-chart ────────────────────────────────────
                  if (p.income?.yearly.isNotEmpty == true) ...[
                    _MiniYearlyChart(yearly: p.income!.yearly, isDark: isDark),
                    const SizedBox(height: 20),
                  ],
                  // ── Today's groups ───────────────────────────────────────
                  _SectionHeader(
                    title: "Guruhlarim",
                    icon: Icons.groups_rounded,
                    action: p.groups.isNotEmpty
                        ? TextButton.icon(
                            onPressed: widget.onGoGroups,
                            icon: const Icon(Icons.arrow_forward_rounded, size: 14),
                            label: const Text("Barchasi"),
                            style: TextButton.styleFrom(
                              foregroundColor: PanelTokens.teacherAccent,
                              textStyle: const TextStyle(
                                  fontSize: 12, fontWeight: FontWeight.w700),
                            ),
                          )
                        : null,
                    isDark: isDark,
                  ),
                  const SizedBox(height: 10),
                  if (p.groupsState == ViewState.loading)
                    _LoadingShimmer(isDark: isDark)
                  else if (p.groupsState == ViewState.error)
                    _ErrorCard(message: p.groupsError, onRetry: p.loadGroups, isDark: isDark)
                  else if (p.groups.isEmpty)
                    _EmptyCard(
                        icon: Icons.groups_outlined,
                        message: "Hali guruh yo'q",
                        isDark: isDark)
                  else
                    ...p.groups.map((g) => _GroupCard(group: g, isDark: isDark)),
                  const SizedBox(height: 20),
                ]),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ─── Hero App Bar ──────────────────────────────────────────────────────────────

class _TeacherHeroBar extends StatelessWidget {
  const _TeacherHeroBar(
      {required this.name, required this.isDark, required this.onRefresh});

  final String name;
  final bool isDark;
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) {
    final now = DateTime.now();
    final weekdays = [
      '', 'Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba', 'Yakshanba'
    ];
    final months = [
      '', 'Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun',
      'Iyul', 'Avgust', 'Sentyabr', 'Oktyabr', 'Noyabr', 'Dekabr'
    ];
    final dateStr = '${weekdays[now.weekday]}, ${now.day} ${months[now.month]}';

    return SliverAppBar(
      backgroundColor: PanelTokens.bg(isDark),
      expandedHeight: 130,
      pinned: true,
      elevation: 0,
      scrolledUnderElevation: 0,
      flexibleSpace: FlexibleSpaceBar(
        collapseMode: CollapseMode.parallax,
        background: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: isDark
                  ? [const Color(0xFF0C4A6E), const Color(0xFF0F172A), PanelTokens.darkBg]
                  : [const Color(0xFFF0F9FF), const Color(0xFFE0F2FE), PanelTokens.lightBg],
            ),
          ),
          padding: const EdgeInsets.fromLTRB(20, 58, 20, 12),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: PanelTokens.teacherAccent.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  Icon(Icons.school_rounded,
                      size: 11,
                      color: PanelTokens.teacherAccent.withValues(alpha: 0.8)),
                  const SizedBox(width: 4),
                  Text("O'qituvchi",
                      style: TextStyle(
                          color: PanelTokens.teacherAccent,
                          fontSize: 10,
                          fontWeight: FontWeight.w700)),
                ]),
              ),
              const Spacer(),
              Text(dateStr,
                  style: TextStyle(
                      color: PanelTokens.textMuted(isDark),
                      fontSize: 11,
                      fontWeight: FontWeight.w500)),
            ]),
            const SizedBox(height: 8),
            Text("Xush kelibsiz, $name 👋",
                style: TextStyle(
                    color: PanelTokens.text(isDark),
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                    letterSpacing: -0.3)),
          ]),
        ),
      ),
      actions: [
        IconButton(
          icon: Icon(Icons.refresh_rounded,
              color: PanelTokens.textMuted(isDark), size: 22),
          onPressed: onRefresh,
        ),
        const SizedBox(width: 4),
      ],
    );
  }
}

// ─── Salary Prediction Card ────────────────────────────────────────────────────

class _SalaryPredictionCard extends StatelessWidget {
  const _SalaryPredictionCard(
      {required this.p, required this.isDark, this.onTap});

  final TeacherProvider p;
  final bool isDark;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final loading = p.incomeState == ViewState.loading;
    final income = p.income;
    final salary = income?.salary ?? 0;
    final expected = income?.expectedIncome ?? 0;
    final pct = income?.progressPct ?? 0;

    // Prediction
    final now = DateTime.now();
    final daysInMonth = DateTime(now.year, now.month + 1, 0).day;
    final daysPassed = math.max(1, now.day);
    final projected = expected > 0 && salary > 0
        ? math.min((salary * daysInMonth / daysPassed).round(), expected)
        : salary;

    final months = [
      '', 'Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun',
      'Iyul', 'Avgust', 'Sentyabr', 'Oktyabr', 'Noyabr', 'Dekabr'
    ];

    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: PanelTokens.gradientCard(
            [const Color(0xFF0284C7), const Color(0xFF7C3AED)]),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          // Header
          Row(children: [
            const Icon(Icons.account_balance_wallet_rounded,
                color: Colors.white60, size: 15),
            const SizedBox(width: 6),
            Expanded(
              child: Text("Bu oy daromad — ${months[now.month]}",
                  style: const TextStyle(
                      color: Colors.white70,
                      fontSize: 12,
                      fontWeight: FontWeight.w600)),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Row(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.chevron_right_rounded, color: Colors.white70, size: 14),
                Text("Batafsil",
                    style: TextStyle(
                        color: Colors.white70,
                        fontSize: 10,
                        fontWeight: FontWeight.w600)),
              ]),
            ),
          ]),
          const SizedBox(height: 12),

          // Current salary
          loading
              ? const SizedBox(
                  height: 36,
                  child: LinearProgressIndicator(
                      color: Colors.white30, backgroundColor: Colors.white12))
              : Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
                  Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    const Text("Hisoblangan",
                        style:
                            TextStyle(color: Colors.white54, fontSize: 10)),
                    const SizedBox(height: 2),
                    Text(Formatters.currency(salary),
                        style: const TextStyle(
                            color: Colors.white,
                            fontSize: 26,
                            fontWeight: FontWeight.w900,
                            letterSpacing: -0.5)),
                  ]),
                  const Spacer(),
                  // Prediction badge
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 10, vertical: 8),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                          color: Colors.white.withValues(alpha: 0.2)),
                    ),
                    child: Column(children: [
                      const Icon(Icons.trending_up_rounded,
                          color: Color(0xFF86EFAC), size: 16),
                      const SizedBox(height: 2),
                      Text(Formatters.currency(projected),
                          style: const TextStyle(
                              color: Color(0xFF86EFAC),
                              fontSize: 12,
                              fontWeight: FontWeight.w800)),
                      const Text("bashorat",
                          style:
                              TextStyle(color: Colors.white38, fontSize: 9)),
                    ]),
                  ),
                ]),
          const SizedBox(height: 14),

          // Progress bar
          Row(children: [
            Text("Maksimal: ${Formatters.currency(expected)}",
                style: const TextStyle(color: Colors.white54, fontSize: 11)),
            const Spacer(),
            Text("$pct%",
                style: const TextStyle(
                    color: Colors.white,
                    fontSize: 14,
                    fontWeight: FontWeight.w800)),
          ]),
          const SizedBox(height: 6),
          Stack(children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(5),
              child: LinearProgressIndicator(
                value: (pct / 100).clamp(0.0, 1.0),
                backgroundColor: Colors.white24,
                valueColor: AlwaysStoppedAnimation<Color>(
                    pct >= 100
                        ? const Color(0xFF34D399)
                        : Colors.white),
                minHeight: 8,
              ),
            ),
            // Prediction marker
            if (expected > 0 && projected > salary)
              Positioned(
                left: (projected / expected * 1).clamp(0.0, 0.98) *
                    (MediaQuery.of(context).size.width - 72),
                top: 0,
                bottom: 0,
                child: Container(
                  width: 2,
                  decoration: BoxDecoration(
                    color: const Color(0xFF86EFAC),
                    borderRadius: BorderRadius.circular(1),
                  ),
                ),
              ),
          ]),
          const SizedBox(height: 6),
          Row(children: [
            Container(
              width: 8, height: 8,
              decoration: const BoxDecoration(
                color: Color(0xFF86EFAC), shape: BoxShape.circle),
            ),
            const SizedBox(width: 4),
            Text("Oy oxirigacha bashorat: ${Formatters.currency(projected)}",
                style: const TextStyle(
                    color: Colors.white60, fontSize: 10)),
          ]),
        ]),
      ),
    );
  }
}

// ─── Stats Row ─────────────────────────────────────────────────────────────────

class _StatsRow extends StatelessWidget {
  const _StatsRow({required this.p, required this.isDark});

  final TeacherProvider p;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    final groups = p.groups.length;
    final students = p.groups.fold<int>(0, (s, g) => s + g.studentCount);
    final today = p.groups.fold<int>(0, (s, g) => s + g.attendedToday);
    final totalToday = p.groups.fold<int>(0, (s, g) => s + g.studentCount);
    final attendRate = totalToday > 0 ? (today / totalToday * 100).round() : 0;

    return Row(children: [
      _StatTile(
        value: '$groups',
        label: 'Guruh',
        icon: Icons.groups_rounded,
        color: PanelTokens.teacherAccent,
        isDark: isDark,
      ),
      const SizedBox(width: 10),
      _StatTile(
        value: '$students',
        label: "O'quvchi",
        icon: Icons.person_rounded,
        color: PanelTokens.info,
        isDark: isDark,
      ),
      const SizedBox(width: 10),
      _StatTile(
        value: '$attendRate%',
        label: 'Bugun davomat',
        icon: Icons.fact_check_rounded,
        color: PanelTokens.success,
        isDark: isDark,
        sub: "$today / $totalToday",
      ),
    ]);
  }
}

class _StatTile extends StatelessWidget {
  const _StatTile({
    required this.value,
    required this.label,
    required this.icon,
    required this.color,
    required this.isDark,
    this.sub,
  });

  final String value;
  final String label;
  final IconData icon;
  final Color color;
  final bool isDark;
  final String? sub;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 10),
        decoration: PanelTokens.cardDecoration(isDark),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: color, size: 18),
          ),
          const SizedBox(height: 8),
          Text(value,
              style: TextStyle(
                  color: PanelTokens.text(isDark),
                  fontSize: 17,
                  fontWeight: FontWeight.w900)),
          const SizedBox(height: 2),
          Text(label,
              style: TextStyle(
                  color: PanelTokens.textMuted(isDark),
                  fontSize: 10),
              textAlign: TextAlign.center),
          if (sub != null) ...[
            const SizedBox(height: 2),
            Text(sub!,
                style: TextStyle(
                    color: color,
                    fontSize: 9,
                    fontWeight: FontWeight.w700)),
          ],
        ]),
      ),
    );
  }
}

// ─── Mini Yearly Chart ─────────────────────────────────────────────────────────

class _MiniYearlyChart extends StatelessWidget {
  const _MiniYearlyChart({required this.yearly, required this.isDark});

  final List<int> yearly;
  final bool isDark;

  static const _ms = ['Y', 'F', 'M', 'A', 'M', 'I', 'I', 'A', 'S', 'O', 'N', 'D'];

  @override
  Widget build(BuildContext context) {
    final now = DateTime.now();
    final maxVal =
        yearly.isEmpty ? 1.0 : yearly.reduce(math.max).toDouble();
    if (maxVal == 0) return const SizedBox.shrink();

    final bars = List.generate(12, (i) {
      final val = i < yearly.length ? yearly[i].toDouble() : 0.0;
      final isActive = (i + 1) == now.month;
      return BarChartGroupData(
        x: i,
        barRods: [
          BarChartRodData(
            toY: val,
            width: 14,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(5)),
            gradient: isActive
                ? const LinearGradient(
                    colors: [Color(0xFF38BDF8), Color(0xFF0EA5E9)],
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                  )
                : LinearGradient(
                    colors: [
                      PanelTokens.teacherAccent.withValues(alpha: 0.4),
                      PanelTokens.teacherAccent.withValues(alpha: 0.2),
                    ],
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                  ),
          ),
        ],
      );
    });

    return Container(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 10),
      decoration: PanelTokens.cardDecoration(isDark),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(Icons.bar_chart_rounded,
              size: 16,
              color: PanelTokens.teacherAccent),
          const SizedBox(width: 8),
          Text("Yillik daromad grafigi",
              style: TextStyle(
                  color: PanelTokens.text(isDark),
                  fontSize: 14,
                  fontWeight: FontWeight.w800)),
        ]),
        const SizedBox(height: 16),
        SizedBox(
          height: 100,
          child: BarChart(
            BarChartData(
              maxY: maxVal * 1.2,
              minY: 0,
              gridData: FlGridData(
                show: true,
                horizontalInterval: maxVal / 3,
                getDrawingHorizontalLine: (v) => FlLine(
                  color: PanelTokens.border(isDark),
                  strokeWidth: 1,
                ),
                drawVerticalLine: false,
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
                    reservedSize: 22,
                    getTitlesWidget: (val, _) {
                      final i = val.toInt();
                      if (i < 0 || i >= _ms.length) return const SizedBox();
                      final isActive = (i + 1) == now.month;
                      return Text(
                        _ms[i],
                        style: TextStyle(
                          fontSize: 9,
                          fontWeight: isActive ? FontWeight.w800 : FontWeight.w500,
                          color: isActive
                              ? PanelTokens.teacherAccent
                              : PanelTokens.textMuted(isDark),
                        ),
                      );
                    },
                  ),
                ),
              ),
              barGroups: bars,
              barTouchData: BarTouchData(
                touchTooltipData: BarTouchTooltipData(
                  getTooltipColor: (_) => isDark
                      ? const Color(0xFF1E2A3A)
                      : const Color(0xFF1E293B),
                  tooltipRoundedRadius: 8,
                  getTooltipItem: (group, gi, rod, ri) => BarTooltipItem(
                    Formatters.currency(rod.toY.round()),
                    const TextStyle(
                        color: Colors.white,
                        fontSize: 10,
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

// ─── Section Header ────────────────────────────────────────────────────────────

class _SectionHeader extends StatelessWidget {
  const _SectionHeader(
      {required this.title, required this.icon, this.action, required this.isDark});

  final String title;
  final IconData icon;
  final Widget? action;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Row(children: [
      Icon(icon, size: 16, color: PanelTokens.teacherAccent),
      const SizedBox(width: 8),
      Text(title,
          style: TextStyle(
              color: PanelTokens.text(isDark),
              fontSize: PanelTokens.fontSection,
              fontWeight: FontWeight.w800)),
      const Spacer(),
      if (action != null) action!,
    ]);
  }
}

// ─── Group Card ────────────────────────────────────────────────────────────────

class _GroupCard extends StatelessWidget {
  const _GroupCard({required this.group, required this.isDark});

  final TeacherGroupModel group;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    final pct = group.studentCount > 0
        ? group.attendedToday / group.studentCount
        : 0.0;
    final pctColor = pct >= 0.9
        ? PanelTokens.success
        : pct >= 0.6
            ? PanelTokens.warning
            : PanelTokens.danger;

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: PanelTokens.cardDecoration(isDark),
      child: InkWell(
        borderRadius: BorderRadius.circular(PanelTokens.cardRadius),
        onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(
            builder: (_) => TeacherAttendanceScreen(group: group))),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(children: [
            // Icon
            Container(
              width: 46,
              height: 46,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                    colors: [Color(0xFF38BDF8), Color(0xFF0EA5E9)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight),
                borderRadius: BorderRadius.circular(13),
              ),
              child:
                  const Icon(Icons.groups_rounded, color: Colors.white, size: 22),
            ),
            const SizedBox(width: 12),
            // Info
            Expanded(
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(group.name,
                        style: TextStyle(
                            color: PanelTokens.text(isDark),
                            fontSize: 14,
                            fontWeight: FontWeight.w800)),
                    if (group.category.isNotEmpty)
                      Text(group.category,
                          style: TextStyle(
                              color: PanelTokens.textMuted(isDark),
                              fontSize: 11)),
                    const SizedBox(height: 6),
                    Row(children: [
                      Expanded(
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(3),
                          child: LinearProgressIndicator(
                            value: pct,
                            backgroundColor: PanelTokens.border(isDark),
                            valueColor:
                                AlwaysStoppedAnimation<Color>(pctColor),
                            minHeight: 5,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text("${group.attendedToday}/${group.studentCount}",
                          style: TextStyle(
                              color: pctColor,
                              fontSize: 11,
                              fontWeight: FontWeight.w800)),
                    ]),
                  ]),
            ),
            const SizedBox(width: 10),
            // Davomat button
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              decoration: BoxDecoration(
                color: PanelTokens.teacherAccent.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.fact_check_rounded,
                    size: 18, color: PanelTokens.teacherAccent),
                const SizedBox(height: 2),
                Text("Davomat",
                    style: TextStyle(
                        color: PanelTokens.teacherAccent,
                        fontSize: 9,
                        fontWeight: FontWeight.w700)),
              ]),
            ),
          ]),
        ),
      ),
    );
  }
}

// ─── Utility Widgets ──────────────────────────────────────────────────────────

class _LoadingShimmer extends StatelessWidget {
  const _LoadingShimmer({required this.isDark});

  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 80,
      decoration: PanelTokens.cardDecoration(isDark),
      child: const Center(
          child: CircularProgressIndicator(
              color: PanelTokens.teacherAccent, strokeWidth: 2)),
    );
  }
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard(
      {required this.message, required this.onRetry, required this.isDark});

  final String message;
  final VoidCallback onRetry;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: PanelTokens.danger.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(PanelTokens.cardRadius),
        border: Border.all(color: PanelTokens.danger.withValues(alpha: 0.2)),
      ),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        const Icon(Icons.wifi_off_rounded, color: PanelTokens.danger, size: 32),
        const SizedBox(height: 8),
        Text(message,
            style: const TextStyle(color: PanelTokens.danger, fontSize: 12),
            textAlign: TextAlign.center),
        const SizedBox(height: 10),
        TextButton.icon(
          onPressed: onRetry,
          icon: const Icon(Icons.refresh_rounded, size: 14),
          label: const Text("Qayta urinish"),
          style:
              TextButton.styleFrom(foregroundColor: PanelTokens.teacherAccent),
        ),
      ]),
    );
  }
}

class _EmptyCard extends StatelessWidget {
  const _EmptyCard(
      {required this.icon, required this.message, required this.isDark});

  final IconData icon;
  final String message;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(32),
      decoration: PanelTokens.cardDecoration(isDark),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon,
            color: PanelTokens.textFaint(isDark), size: 40),
        const SizedBox(height: 10),
        Text(message,
            style: TextStyle(
                color: PanelTokens.textMuted(isDark), fontSize: 13)),
      ]),
    );
  }
}
