import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/teacher_models.dart';
import 'package:chaqmoq_mobile/providers/teacher_provider.dart';
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

  static const _m = ['', 'Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun',
      'Iyul', 'Avgust', 'Sentyabr', 'Oktyabr', 'Noyabr', 'Dekabr'];
  static const _ms = ['', 'Y', 'F', 'M', 'A', 'M', 'I', 'I', 'A', 'S', 'O', 'N', 'D'];

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _year = now.year;
    _month = now.month;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) context.read<TeacherProvider>().loadIncome(year: _year, month: _month);
    });
  }

  bool get _isCurrentMonth {
    final now = DateTime.now();
    return _year == now.year && _month == now.month;
  }

  void _prevMonth() {
    setState(() {
      if (_month == 1) { _month = 12; _year--; } else { _month--; }
    });
    context.read<TeacherProvider>().forceReloadIncome(year: _year, month: _month);
  }

  void _nextMonth() {
    if (_isCurrentMonth) return;
    setState(() {
      if (_month == 12) { _month = 1; _year++; } else { _month++; }
    });
    context.read<TeacherProvider>().forceReloadIncome(year: _year, month: _month);
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final p = context.watch<TeacherProvider>();
    final income = p.income;

    return Scaffold(
      backgroundColor: isDark ? const Color(0xFF0B1220) : const Color(0xFFF5F7FB),
      appBar: AppBar(
        backgroundColor: isDark ? const Color(0xFF0F1B2A) : Colors.white,
        elevation: 0,
        title: Text("Daromadim",
            style: TextStyle(
                color: isDark ? Colors.white : const Color(0xFF0F172A),
                fontWeight: FontWeight.w800, fontSize: 17)),
        actions: [
          IconButton(
            icon: Icon(Icons.refresh_rounded, color: isDark ? Colors.white60 : Colors.black45),
            onPressed: () => context.read<TeacherProvider>().forceReloadIncome(year: _year, month: _month),
          ),
        ],
      ),
      body: () {
        if (p.incomeState == ViewState.loading) {
          return const Center(child: CircularProgressIndicator(color: Color(0xFF6366F1)));
        }
        if (p.incomeState == ViewState.error) {
          return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.wifi_off_rounded, color: Colors.red, size: 40),
            const SizedBox(height: 12),
            Text(p.incomeError, style: const TextStyle(color: Colors.red, fontSize: 13)),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () => context.read<TeacherProvider>().forceReloadIncome(year: _year, month: _month),
              child: const Text("Qayta urinish"),
            ),
          ]));
        }
        if (income == null) {
          return const Center(child: Text("Ma'lumot yo'q", style: TextStyle(color: Colors.white38)));
        }
        return _buildContent(income, isDark);
      }(),
    );
  }

  Widget _buildContent(TeacherIncomeModel income, bool isDark) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Month selector
        _MonthSelector(
          label: "${_m[_month]} $_year",
          onPrev: _prevMonth,
          onNext: _isCurrentMonth ? null : _nextMonth,
          isDark: isDark,
        ),
        const SizedBox(height: 14),

        // Main card
        _MainCard(income: income, isDark: isDark),
        const SizedBox(height: 16),

        // Yearly chart
        if (income.yearly.isNotEmpty) _YearlyChart(yearly: income.yearly, activeMonth: _month, monthShorts: _ms, isDark: isDark),
        const SizedBox(height: 16),

        // Group breakdown
        if (income.details.isNotEmpty) ...[
          Text("Guruhlar bo'yicha",
              style: TextStyle(
                  color: isDark ? Colors.white70 : const Color(0xFF374151),
                  fontSize: 15, fontWeight: FontWeight.w800)),
          const SizedBox(height: 10),
          ...income.details.map((d) => _GroupRow(data: d, isDark: isDark)),
        ],

        const SizedBox(height: 32),
      ],
    );
  }
}

class _MonthSelector extends StatelessWidget {
  const _MonthSelector({required this.label, required this.onPrev, this.onNext, required this.isDark});

  final String label;
  final VoidCallback onPrev;
  final VoidCallback? onNext;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Row(mainAxisAlignment: MainAxisAlignment.center, children: [
      IconButton(
        icon: Icon(Icons.chevron_left_rounded, color: isDark ? Colors.white70 : Colors.black54),
        onPressed: onPrev,
      ),
      Text(label,
          style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A),
              fontWeight: FontWeight.w800, fontSize: 16)),
      IconButton(
        icon: Icon(Icons.chevron_right_rounded,
            color: onNext != null ? (isDark ? Colors.white70 : Colors.black54) : Colors.grey.withValues(alpha: 0.3)),
        onPressed: onNext,
      ),
    ]);
  }
}

class _MainCard extends StatelessWidget {
  const _MainCard({required this.income, required this.isDark});

  final TeacherIncomeModel income;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    final pct = income.progressPct;
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF312E81), Color(0xFF4F46E5)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
        boxShadow: [BoxShadow(color: const Color(0xFF6366F1).withValues(alpha: 0.3), blurRadius: 24, offset: const Offset(0, 8))],
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text("Hisoblangan oylik", style: TextStyle(color: Colors.white60, fontSize: 13)),
            const SizedBox(height: 6),
            Text(Formatters.currency(income.salary),
                style: const TextStyle(color: Colors.white, fontSize: 26, fontWeight: FontWeight.w900, letterSpacing: -0.5)),
          ])),
          if (income.isLocked)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(color: Colors.white24, borderRadius: BorderRadius.circular(10)),
              child: const Row(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.lock_rounded, size: 12, color: Colors.white70),
                SizedBox(width: 4),
                Text("Yopilgan", style: TextStyle(color: Colors.white70, fontSize: 11, fontWeight: FontWeight.w600)),
              ]),
            ),
        ]),
        const SizedBox(height: 16),
        Row(children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text("Maksimal", style: TextStyle(color: Colors.white54, fontSize: 11)),
              const SizedBox(height: 2),
              Text(Formatters.currency(income.expectedIncome),
                  style: const TextStyle(color: Colors.white70, fontSize: 13, fontWeight: FontWeight.w700)),
            ]),
          ),
          Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
            Text("$pct%", style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w900)),
            const Text("yig'ildi", style: TextStyle(color: Colors.white60, fontSize: 10)),
          ]),
        ]),
        const SizedBox(height: 10),
        ClipRRect(
          borderRadius: BorderRadius.circular(5),
          child: LinearProgressIndicator(
            value: (pct / 100).clamp(0.0, 1.0),
            backgroundColor: Colors.white24,
            valueColor: AlwaysStoppedAnimation<Color>(pct >= 100 ? const Color(0xFF34D399) : Colors.white),
            minHeight: 7,
          ),
        ),
      ]),
    );
  }
}

class _YearlyChart extends StatelessWidget {
  const _YearlyChart({required this.yearly, required this.activeMonth, required this.monthShorts, required this.isDark});

  final List<int> yearly;
  final int activeMonth;
  final List<String> monthShorts;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    final maxVal = yearly.isEmpty ? 1 : yearly.reduce((a, b) => a > b ? a : b);
    final cardColor = isDark ? const Color(0xFF162436) : Colors.white;
    final borderColor = isDark ? Colors.white.withValues(alpha: 0.06) : Colors.black.withValues(alpha: 0.05);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: cardColor,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: borderColor),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text("Yillik daromad",
            style: TextStyle(color: isDark ? Colors.white70 : const Color(0xFF374151),
                fontSize: 14, fontWeight: FontWeight.w700)),
        const SizedBox(height: 16),
        SizedBox(
          height: 90,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: List.generate(12, (i) {
              final val = i < yearly.length ? yearly[i] : 0;
              final frac = maxVal > 0 ? val / maxVal : 0.0;
              final active = (i + 1) == activeMonth;
              return Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 2),
                  child: Column(mainAxisAlignment: MainAxisAlignment.end, children: [
                    AnimatedContainer(
                      duration: const Duration(milliseconds: 400),
                      height: (frac * 70).clamp(3.0, 70.0),
                      decoration: BoxDecoration(
                        gradient: active
                            ? const LinearGradient(
                                colors: [Color(0xFF818CF8), Color(0xFF6366F1)],
                                begin: Alignment.topCenter,
                                end: Alignment.bottomCenter,
                              )
                            : null,
                        color: active ? null : (isDark ? const Color(0xFF6366F1).withValues(alpha: 0.25) : const Color(0xFF6366F1).withValues(alpha: 0.2)),
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      i < monthShorts.length ? monthShorts[i + 1] : '',
                      style: TextStyle(
                        fontSize: 9,
                        color: active ? const Color(0xFF818CF8) : (isDark ? Colors.white38 : Colors.black38),
                        fontWeight: active ? FontWeight.w800 : FontWeight.w500,
                      ),
                    ),
                  ]),
                ),
              );
            }),
          ),
        ),
      ]),
    );
  }
}

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
    final cardColor = isDark ? const Color(0xFF162436) : Colors.white;
    final borderColor = isDark ? Colors.white.withValues(alpha: 0.06) : Colors.black.withValues(alpha: 0.05);

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: cardColor,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: borderColor),
      ),
      child: Row(children: [
        Container(
          width: 36, height: 36,
          decoration: BoxDecoration(
            color: const Color(0xFF6366F1).withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(10),
          ),
          child: const Icon(Icons.groups_rounded, color: Color(0xFF6366F1), size: 18),
        ),
        const SizedBox(width: 12),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(name, style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontWeight: FontWeight.w700, fontSize: 13)),
          Text("$att dars · $pct%",
              style: TextStyle(color: isDark ? Colors.white38 : Colors.black38, fontSize: 11)),
        ])),
        Text(Formatters.currency(salary),
            style: const TextStyle(color: Color(0xFF10B981), fontWeight: FontWeight.w800, fontSize: 13)),
      ]),
    );
  }
}
