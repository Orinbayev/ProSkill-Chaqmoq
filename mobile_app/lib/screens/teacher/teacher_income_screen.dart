import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/teacher_models.dart';
import 'package:chaqmoq_mobile/providers/teacher_provider.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class TeacherIncomeScreen extends StatefulWidget {
  const TeacherIncomeScreen({super.key});

  @override
  State<TeacherIncomeScreen> createState() => _TeacherIncomeScreenState();
}

class _TeacherIncomeScreenState extends State<TeacherIncomeScreen> {
  late int _year;
  late int _month;

  static const _monthNames = [
    '', 'Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun',
    'Iyul', 'Avgust', 'Sentyabr', 'Oktyabr', 'Noyabr', 'Dekabr',
  ];

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

  void _prevMonth() {
    setState(() {
      if (_month == 1) { _month = 12; _year--; }
      else { _month--; }
    });
    context.read<TeacherProvider>().forceReloadIncome(year: _year, month: _month);
  }

  void _nextMonth() {
    final now = DateTime.now();
    if (_year == now.year && _month == now.month) return;
    setState(() {
      if (_month == 12) { _month = 1; _year++; }
      else { _month++; }
    });
    context.read<TeacherProvider>().forceReloadIncome(year: _year, month: _month);
  }

  @override
  Widget build(BuildContext context) {
    final p = context.watch<TeacherProvider>();
    final income = p.income;
    final now = DateTime.now();
    final isCurrentMonth = _year == now.year && _month == now.month;

    return Scaffold(
      backgroundColor: const Color(0xFF0B1220),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0F1B2A),
        title: const Text('Daromadim', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 17)),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded, color: Colors.white60),
            onPressed: () => context.read<TeacherProvider>().forceReloadIncome(year: _year, month: _month),
          ),
        ],
      ),
      body: () {
        if (p.incomeState == ViewState.loading) {
          return const Center(child: CircularProgressIndicator(color: Color(0xFF6366F1)));
        }
        if (p.incomeState == ViewState.error) {
          return Center(child: Text(p.incomeError, style: const TextStyle(color: Colors.white54)));
        }
        if (income == null) {
          return const Center(child: Text('Ma\'lumot yo\'q', style: TextStyle(color: Colors.white38)));
        }
        return _buildContent(income, isCurrentMonth);
      }(),
    );
  }

  Widget _buildContent(TeacherIncomeModel income, bool isCurrentMonth) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Month selector
        _MonthSelector(
          month: _monthNames[_month],
          year: _year,
          onPrev: _prevMonth,
          onNext: isCurrentMonth ? null : _nextMonth,
        ),
        const SizedBox(height: 16),

        // Main salary card
        _SalaryCard(income: income),
        const SizedBox(height: 16),

        // Yearly chart
        if (income.yearly.isNotEmpty) ...[
          _YearlyChart(yearly: income.yearly, currentMonth: _month),
          const SizedBox(height: 16),
        ],

        // Group breakdown
        if (income.details.isNotEmpty) ...[
          const Text('Guruhlar bo\'yicha', style: TextStyle(color: Colors.white70, fontSize: 14, fontWeight: FontWeight.w700)),
          const SizedBox(height: 10),
          ...income.details.map((d) => _GroupIncomeRow(data: d)),
        ],
        const SizedBox(height: 32),
      ],
    );
  }
}

class _MonthSelector extends StatelessWidget {
  const _MonthSelector({required this.month, required this.year, required this.onPrev, this.onNext});

  final String month;
  final int year;
  final VoidCallback onPrev;
  final VoidCallback? onNext;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        IconButton(
          icon: const Icon(Icons.chevron_left_rounded, color: Colors.white70),
          onPressed: onPrev,
        ),
        Text(
          '$month $year',
          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 16),
        ),
        IconButton(
          icon: Icon(Icons.chevron_right_rounded, color: onNext != null ? Colors.white70 : Colors.white24),
          onPressed: onNext,
        ),
      ],
    );
  }
}

class _SalaryCard extends StatelessWidget {
  const _SalaryCard({required this.income});

  final TeacherIncomeModel income;

  @override
  Widget build(BuildContext context) {
    final pct = income.progressPct;
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF312E81), Color(0xFF4F46E5)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(18),
        boxShadow: [
          BoxShadow(color: const Color(0xFF6366F1).withOpacity(0.3), blurRadius: 20, offset: const Offset(0, 6)),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('Hisoblangan oylik', style: TextStyle(color: Colors.white60, fontSize: 13)),
              if (income.isLocked)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: Colors.white24,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Row(mainAxisSize: MainAxisSize.min, children: [
                    Icon(Icons.lock_rounded, size: 11, color: Colors.white70),
                    SizedBox(width: 4),
                    Text('Yopilgan', style: TextStyle(color: Colors.white70, fontSize: 11)),
                  ]),
                ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            Formatters.currency(income.salary),
            style: const TextStyle(color: Colors.white, fontSize: 28, fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 14),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Maksimal: ${Formatters.currency(income.expectedIncome)}',
                style: const TextStyle(color: Colors.white54, fontSize: 12),
              ),
              Text('$pct%', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 14)),
            ],
          ),
          const SizedBox(height: 6),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: (pct / 100).clamp(0.0, 1.0),
              backgroundColor: Colors.white24,
              valueColor: AlwaysStoppedAnimation<Color>(
                pct >= 100 ? const Color(0xFF10B981) : Colors.white,
              ),
              minHeight: 6,
            ),
          ),
        ],
      ),
    );
  }
}

class _YearlyChart extends StatelessWidget {
  const _YearlyChart({required this.yearly, required this.currentMonth});

  final List<int> yearly;
  final int currentMonth;

  static const _months = ['Y', 'F', 'M', 'A', 'M', 'I', 'I', 'A', 'S', 'O', 'N', 'D'];

  @override
  Widget build(BuildContext context) {
    final maxVal = yearly.isEmpty ? 1 : yearly.reduce((a, b) => a > b ? a : b);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF162436),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white.withOpacity(0.06)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('${0 + 0}-yil oylik daromad', style: TextStyle(color: Colors.white70, fontSize: 13, fontWeight: FontWeight.w700)),
          const SizedBox(height: 16),
          SizedBox(
            height: 100,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: List.generate(12, (i) {
                final val = i < yearly.length ? yearly[i] : 0;
                final frac = maxVal > 0 ? val / maxVal : 0.0;
                final isActive = (i + 1) == currentMonth;
                return Expanded(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 2),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: [
                        AnimatedContainer(
                          duration: const Duration(milliseconds: 400),
                          height: (frac * 80).clamp(3.0, 80.0),
                          decoration: BoxDecoration(
                            color: isActive ? const Color(0xFF6366F1) : const Color(0xFF6366F1).withOpacity(0.3),
                            borderRadius: BorderRadius.circular(4),
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          _months[i],
                          style: TextStyle(
                            fontSize: 9,
                            color: isActive ? const Color(0xFF818CF8) : Colors.white38,
                            fontWeight: isActive ? FontWeight.w800 : FontWeight.w500,
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              }),
            ),
          ),
        ],
      ),
    );
  }
}

class _GroupIncomeRow extends StatelessWidget {
  const _GroupIncomeRow({required this.data});

  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    final name = '${data['group_name'] ?? ''}';
    final salary = (data['salary'] as num? ?? 0).toInt();
    final att = (data['attendance'] as num? ?? 0).toInt();
    final pct = (data['fi'] as num? ?? 0).toInt();
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: const Color(0xFF162436),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white.withOpacity(0.06)),
      ),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: const Color(0xFF6366F1).withOpacity(0.15),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(Icons.groups_rounded, color: Color(0xFF6366F1), size: 18),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(name, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 13)),
              Text('$att dars · $pct%', style: const TextStyle(color: Colors.white38, fontSize: 11)),
            ]),
          ),
          Text(
            Formatters.currency(salary),
            style: const TextStyle(color: Color(0xFF10B981), fontWeight: FontWeight.w800, fontSize: 13),
          ),
        ],
      ),
    );
  }
}
