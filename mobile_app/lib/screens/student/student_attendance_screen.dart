import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/chaqmoq_history_provider.dart';
import 'package:chaqmoq_mobile/screens/student/widgets/student_atmospheric_backdrop.dart';
import 'package:chaqmoq_mobile/screens/student/widgets/student_day_detail_sheet.dart';
import 'package:chaqmoq_mobile/widgets/app_state_widgets.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

class StudentAttendanceScreen extends StatefulWidget {
  const StudentAttendanceScreen({super.key, this.standalone = false});

  final bool standalone;

  @override
  State<StudentAttendanceScreen> createState() => _StudentAttendanceScreenState();
}

class _StudentAttendanceScreenState extends State<StudentAttendanceScreen> {
  late DateTime _viewMonth;
  bool _hydrated = false;

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _viewMonth = DateTime(now.year, now.month);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_hydrated) return;
    final user = context.read<AuthProvider>().user;
    if (user == null) return;
    _hydrated = true;

    // Build fazasida provider'ni xabardor qilib bo'lmaydi — kadrdan keyin.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      context.read<ChaqmoqHistoryProvider>().load();
    });
  }

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final history = context.watch<ChaqmoqHistoryProvider>();
    final user = context.watch<AuthProvider>().user;
    if (user == null) return const SizedBox.shrink();

    return Scaffold(
      backgroundColor: tokens.bg,
      appBar: widget.standalone
          ? AppBar(
              backgroundColor: Colors.transparent,
              elevation: 0,
              foregroundColor: tokens.text,
              title: Text(
                'Davomat',
                style: GoogleFonts.inter(
                  fontSize: 17,
                  fontWeight: FontWeight.w800,
                  color: tokens.text,
                ),
              ),
            )
          : null,
      body: Stack(
        children: [
          const StudentAtmosphericBackdrop(),
          SafeArea(
            top: !widget.standalone,
            child: RefreshIndicator(
              color: tokens.primary,
              onRefresh: () => history.refresh(),
              child: _body(history, tokens),
            ),
          ),
        ],
      ),
    );
  }

  Widget _body(ChaqmoqHistoryProvider history, StudentTokens tokens) {
    if (history.state == ViewState.loading && history.items.isEmpty) {
      return AppLoadingState(dark: tokens.isDark);
    }
    if (history.state == ViewState.error && history.items.isEmpty) {
      return AppErrorState(
        title: 'Davomat yuklanmadi',
        message: history.errorMessage ?? 'Server bilan aloqa yo‘q.',
        dark: tokens.isDark,
        onRetry: () => history.refresh(),
      );
    }

    final byDate = _groupByDate(history.items);
    final summary = _MonthSummary.from(_viewMonth, byDate);

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(parent: BouncingScrollPhysics()),
      padding: EdgeInsets.fromLTRB(16, widget.standalone ? 8 : 14, 16, 110),
      children: [
        if (!widget.standalone) ...[
          Text(
            'Davomat',
            style: GoogleFonts.inter(
              fontSize: 19,
              fontWeight: FontWeight.w800,
              color: tokens.text,
              letterSpacing: -0.2,
            ),
          ),
          const SizedBox(height: 14),
        ],
        _MonthSwitcher(
          month: _viewMonth,
          onPrev: () => setState(() => _viewMonth = DateTime(_viewMonth.year, _viewMonth.month - 1)),
          onNext: _canGoNext()
              ? () => setState(() => _viewMonth = DateTime(_viewMonth.year, _viewMonth.month + 1))
              : null,
        ),
        const SizedBox(height: 14),
        _NetChaqmoqHero(netPoints: summary.netPoints),
        const SizedBox(height: 10),
        _StatsRow(summary: summary),
        const SizedBox(height: 14),
        _Calendar(
          month: _viewMonth,
          byDate: byDate,
          onDayTap: (date) => _openDay(date, byDate[date] ?? const []),
        ),
        const SizedBox(height: 10),
        const _Legend(),
        const SizedBox(height: 18),
        _DayList(
          month: _viewMonth,
          byDate: byDate,
          onTap: (date) => _openDay(date, byDate[date] ?? const []),
        ),
      ],
    );
  }

  void _openDay(DateTime date, List<ChaqmoqEntryModel> entries) {
    final events = entries
        .map((e) => StudentBallEvent(
              subject: e.groupName.isEmpty ? (e.ruleName.isEmpty ? 'Faollik' : e.ruleName) : e.groupName,
              teacher: e.giverName.isEmpty ? "O‘qituvchi / Admin" : e.giverName,
              points: e.points,
              time: e.createdAt,
              note: e.ruleName.isEmpty ? null : e.ruleName,
            ))
        .toList();
    StudentDayDetailSheet.show(
      context,
      date: date,
      events: events,
      status: _statusFor(entries),
    );
  }

  DayStatus? _statusFor(List<ChaqmoqEntryModel> entries) {
    if (entries.isEmpty) return null;
    final hasPos = entries.any((e) => e.points > 0);
    final hasNeg = entries.any((e) => e.points < 0);
    if (hasPos && !hasNeg) return DayStatus.attended;
    if (!hasPos && hasNeg) return DayStatus.absent;
    if (hasPos && hasNeg) return DayStatus.late;
    return null;
  }

  bool _canGoNext() {
    final now = DateTime.now();
    final nextMonth = DateTime(_viewMonth.year, _viewMonth.month + 1);
    return !nextMonth.isAfter(DateTime(now.year, now.month));
  }

  Map<DateTime, List<ChaqmoqEntryModel>> _groupByDate(List<ChaqmoqEntryModel> items) {
    final m = <DateTime, List<ChaqmoqEntryModel>>{};
    for (final e in items) {
      final d = DateTime(e.createdAt.year, e.createdAt.month, e.createdAt.day);
      m.putIfAbsent(d, () => <ChaqmoqEntryModel>[]).add(e);
    }
    for (final list in m.values) {
      list.sort((a, b) => a.createdAt.compareTo(b.createdAt));
    }
    return m;
  }
}

class _MonthSwitcher extends StatelessWidget {
  const _MonthSwitcher({required this.month, required this.onPrev, this.onNext});

  final DateTime month;
  final VoidCallback onPrev;
  final VoidCallback? onNext;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final label = DateFormat('MMMM yyyy', 'uz').format(month);
    final pretty = label.isEmpty
        ? label
        : '${label[0].toUpperCase()}${label.substring(1)}';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 6),
      decoration: BoxDecoration(
        color: tokens.glass,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: tokens.border),
      ),
      child: Row(
        children: [
          _NavButton(icon: Icons.chevron_left_rounded, onTap: onPrev),
          Expanded(
            child: Center(
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.calendar_month_rounded, size: 16, color: tokens.primary),
                  const SizedBox(width: 6),
                  Text(
                    pretty,
                    style: GoogleFonts.inter(
                      fontSize: 14,
                      fontWeight: FontWeight.w800,
                      color: tokens.text,
                    ),
                  ),
                ],
              ),
            ),
          ),
          _NavButton(icon: Icons.chevron_right_rounded, onTap: onNext),
        ],
      ),
    );
  }
}

class _NavButton extends StatelessWidget {
  const _NavButton({required this.icon, required this.onTap});

  final IconData icon;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final disabled = onTap == null;
    return Opacity(
      opacity: disabled ? 0.4 : 1,
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(10),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(10),
          child: Container(
            width: 36,
            height: 36,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: tokens.glassStrong,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: tokens.border),
            ),
            child: Icon(icon, size: 18, color: tokens.text),
          ),
        ),
      ),
    );
  }
}

class _NetChaqmoqHero extends StatelessWidget {
  const _NetChaqmoqHero({required this.netPoints});

  final int netPoints;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final positive = netPoints >= 0;
    final accent = positive ? tokens.primary : tokens.danger;
    final accent2 = positive ? tokens.secondary : tokens.warning;
    return Container(
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            accent.withValues(alpha: 0.22),
            accent2.withValues(alpha: 0.18),
          ],
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: accent.withValues(alpha: 0.4)),
        boxShadow: [
          BoxShadow(
            color: accent.withValues(alpha: 0.18),
            blurRadius: 22,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            width: 56,
            height: 56,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [accent, accent2],
              ),
              boxShadow: [
                BoxShadow(
                  color: accent.withValues(alpha: 0.5),
                  blurRadius: 16,
                  offset: const Offset(0, 6),
                ),
              ],
            ),
            child: const Icon(Icons.bolt_rounded, color: Colors.white, size: 28),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  "SOF CHAQMOQ",
                  style: GoogleFonts.inter(
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    color: accent,
                    letterSpacing: 1.6,
                  ),
                ),
                const SizedBox(height: 4),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    Text(
                      '${positive ? '+' : ''}${Formatters.number(netPoints)}',
                      style: GoogleFonts.inter(
                        fontSize: 30,
                        fontWeight: FontWeight.w800,
                        color: tokens.text,
                        letterSpacing: -0.6,
                      ),
                    ),
                    const SizedBox(width: 5),
                    Icon(Icons.bolt_rounded, color: accent, size: 22),
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  positive
                      ? 'Bu oydagi natija — ajoyib!'
                      : 'Bu oydagi balansingiz manfiy',
                  style: GoogleFonts.inter(
                    fontSize: 11.5,
                    fontWeight: FontWeight.w600,
                    color: tokens.textMuted,
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

class _StatsRow extends StatelessWidget {
  const _StatsRow({required this.summary});

  final _MonthSummary summary;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Row(
      children: [
        Expanded(
          child: _StatCard(
            icon: Icons.check_circle_outline_rounded,
            label: 'Kelgan',
            value: '${summary.attendedDays}',
            color: tokens.success,
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: _StatCard(
            icon: Icons.highlight_off_rounded,
            label: 'Kelmagan',
            value: '${summary.absentDays}',
            color: tokens.danger,
          ),
        ),
      ],
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
  });

  final IconData icon;
  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12),
      decoration: BoxDecoration(
        color: tokens.tonedSurface(color),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Icon(icon, size: 16, color: color),
              const SizedBox(width: 6),
              Text(
                label,
                style: GoogleFonts.inter(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  color: tokens.textMuted,
                  letterSpacing: 0.3,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            value,
            style: GoogleFonts.inter(
              fontSize: 22,
              fontWeight: FontWeight.w800,
              color: color,
              letterSpacing: -0.4,
            ),
          ),
        ],
      ),
    );
  }
}

class _Legend extends StatelessWidget {
  const _Legend();

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    Widget chip(Color color, String label) {
      return Padding(
        padding: const EdgeInsets.only(right: 12, top: 2, bottom: 2),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 10,
              height: 10,
              decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(3)),
            ),
            const SizedBox(width: 6),
            Text(
              label,
              style: GoogleFonts.inter(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: tokens.textMuted,
              ),
            ),
          ],
        ),
      );
    }

    return Wrap(
      spacing: 0,
      runSpacing: 4,
      children: [
        chip(tokens.success, 'Kelgan'),
        chip(tokens.danger, 'Kelmagan'),
        chip(tokens.glassStrong, "Yozuv yo‘q"),
      ],
    );
  }
}

class _Calendar extends StatelessWidget {
  const _Calendar({required this.month, required this.byDate, required this.onDayTap});

  final DateTime month;
  final Map<DateTime, List<ChaqmoqEntryModel>> byDate;
  final void Function(DateTime) onDayTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final firstDay = DateTime(month.year, month.month);
    final daysInMonth = DateTime(month.year, month.month + 1, 0).day;
    final firstWeekday = firstDay.weekday;
    final cells = <Widget>[];
    final today = DateTime.now();
    final todayKey = DateTime(today.year, today.month, today.day);

    for (var i = 1; i < firstWeekday; i++) {
      cells.add(const SizedBox.shrink());
    }
    for (var d = 1; d <= daysInMonth; d++) {
      final date = DateTime(month.year, month.month, d);
      final entries = byDate[date] ?? const <ChaqmoqEntryModel>[];
      final status = _classifyDay(entries);
      final isFuture = date.isAfter(todayKey);
      final isToday = date == todayKey;
      cells.add(_DayCell(
        date: date,
        status: status,
        netPoints: entries.fold<int>(0, (s, e) => s + e.points),
        isToday: isToday,
        isFuture: isFuture,
        onTap: isFuture ? null : () => onDayTap(date),
      ));
    }

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: tokens.glass,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: tokens.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: const [
              _Weekday(label: 'Du'),
              _Weekday(label: 'Se'),
              _Weekday(label: 'Cho'),
              _Weekday(label: 'Pa'),
              _Weekday(label: 'Ju'),
              _Weekday(label: 'Sh', highlight: true),
              _Weekday(label: 'Ya', highlight: true),
            ],
          ),
          const SizedBox(height: 8),
          Container(height: 1, color: tokens.border),
          const SizedBox(height: 8),
          GridView.count(
            crossAxisCount: 7,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: 6,
            crossAxisSpacing: 6,
            childAspectRatio: 0.92,
            children: cells,
          ),
        ],
      ),
    );
  }
}

class _Weekday extends StatelessWidget {
  const _Weekday({required this.label, this.highlight = false});

  final String label;
  final bool highlight;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Expanded(
      child: Center(
        child: Text(
          label,
          style: GoogleFonts.inter(
            fontSize: 10.5,
            fontWeight: FontWeight.w800,
            color: highlight ? tokens.danger.withValues(alpha: 0.7) : tokens.textMuted,
            letterSpacing: 0.6,
          ),
        ),
      ),
    );
  }
}

enum _CellStatus { attended, absent, mixed, none }

_CellStatus _classifyDay(List<ChaqmoqEntryModel> entries) {
  if (entries.isEmpty) return _CellStatus.none;
  final hasPos = entries.any((e) => e.points > 0);
  final hasNeg = entries.any((e) => e.points < 0);
  if (hasPos && hasNeg) return _CellStatus.mixed;
  if (hasPos) return _CellStatus.attended;
  if (hasNeg) return _CellStatus.absent;
  return _CellStatus.none;
}

class _DayCell extends StatelessWidget {
  const _DayCell({
    required this.date,
    required this.status,
    required this.netPoints,
    required this.isToday,
    required this.isFuture,
    this.onTap,
  });

  final DateTime date;
  final _CellStatus status;
  final int netPoints;
  final bool isToday;
  final bool isFuture;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final accent = switch (status) {
      _CellStatus.attended => tokens.success,
      _CellStatus.absent => tokens.danger,
      _CellStatus.mixed => tokens.warning,
      _CellStatus.none => tokens.textMuted,
    };
    final hasData = status != _CellStatus.none && !isFuture;
    final filled = status == _CellStatus.attended || status == _CellStatus.absent;
    final cellBg = hasData
        ? (filled ? accent : tokens.tonedSurface(accent))
        : (isFuture ? Colors.transparent : tokens.glassStrong);
    final dayColor = hasData
        ? (filled ? Colors.white : accent)
        : (isFuture ? tokens.textDim : tokens.text);
    final ballColor = hasData
        ? (filled ? Colors.white.withValues(alpha: 0.95) : accent)
        : tokens.textDim;
    final borderColor = isToday
        ? tokens.primary
        : (hasData ? accent.withValues(alpha: 0.5) : tokens.border);
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(10),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(10),
        child: Container(
          decoration: BoxDecoration(
            color: cellBg,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: borderColor, width: isToday ? 1.6 : 1),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                '${date.day}',
                style: GoogleFonts.inter(
                  fontSize: 13,
                  fontWeight: FontWeight.w800,
                  color: dayColor,
                ),
              ),
              if (hasData && netPoints != 0) ...[
                const SizedBox(height: 2),
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      '${netPoints > 0 ? '+' : ''}$netPoints',
                      style: GoogleFonts.inter(
                        fontSize: 9.5,
                        fontWeight: FontWeight.w800,
                        color: ballColor,
                      ),
                    ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _DayList extends StatelessWidget {
  const _DayList({required this.month, required this.byDate, required this.onTap});

  final DateTime month;
  final Map<DateTime, List<ChaqmoqEntryModel>> byDate;
  final void Function(DateTime) onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final today = DateTime.now();
    final todayKey = DateTime(today.year, today.month, today.day);
    final daysInMonth = DateTime(month.year, month.month + 1, 0).day;
    final rows = <_DayRowData>[];
    for (var d = 1; d <= daysInMonth; d++) {
      final date = DateTime(month.year, month.month, d);
      if (date.isAfter(todayKey)) continue;
      final entries = byDate[date] ?? const <ChaqmoqEntryModel>[];
      if (entries.isEmpty) continue;
      rows.add(_DayRowData(
        date: date,
        status: _classifyDay(entries),
        netPoints: entries.fold<int>(0, (s, e) => s + e.points),
        entryCount: entries.length,
      ));
    }
    rows.sort((a, b) => b.date.compareTo(a.date));

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(
              "BU OYDAGI YOZUVLAR",
              style: GoogleFonts.inter(
                fontSize: 11,
                fontWeight: FontWeight.w800,
                color: tokens.textMuted,
                letterSpacing: 1.6,
              ),
            ),
            const Spacer(),
            if (rows.isNotEmpty)
              Text(
                '${rows.length} kun',
                style: GoogleFonts.inter(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  color: tokens.textMuted,
                ),
              ),
          ],
        ),
        const SizedBox(height: 8),
        if (rows.isEmpty)
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: tokens.glass,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: tokens.border),
            ),
            child: Row(
              children: [
                Icon(Icons.event_busy_rounded, color: tokens.textDim, size: 20),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    "Bu oyda hech qanday yozuv yo‘q",
                    style: GoogleFonts.inter(
                      fontSize: 12.5,
                      fontWeight: FontWeight.w600,
                      color: tokens.textMuted,
                    ),
                  ),
                ),
              ],
            ),
          )
        else
          ...rows.map((r) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: _DayRow(data: r, onTap: () => onTap(r.date)),
              )),
      ],
    );
  }
}

class _DayRowData {
  const _DayRowData({
    required this.date,
    required this.status,
    required this.netPoints,
    required this.entryCount,
  });

  final DateTime date;
  final _CellStatus status;
  final int netPoints;
  final int entryCount;
}

class _DayRow extends StatelessWidget {
  const _DayRow({required this.data, required this.onTap});

  final _DayRowData data;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final color = switch (data.status) {
      _CellStatus.attended => tokens.success,
      _CellStatus.absent => tokens.danger,
      _CellStatus.mixed => tokens.warning,
      _CellStatus.none => tokens.textDim,
    };
    final icon = switch (data.status) {
      _CellStatus.attended => Icons.check_circle_outline_rounded,
      _CellStatus.absent => Icons.highlight_off_rounded,
      _CellStatus.mixed => Icons.compare_arrows_rounded,
      _CellStatus.none => Icons.remove_rounded,
    };
    final label = switch (data.status) {
      _CellStatus.attended => 'Kelgan',
      _CellStatus.absent => 'Kelmagan',
      _CellStatus.mixed => 'Aralash',
      _CellStatus.none => "Yozuv yo‘q",
    };
    final dayName = DateFormat('EEEE', 'uz').format(data.date);
    final prettyDay = dayName.isEmpty
        ? dayName
        : '${dayName[0].toUpperCase()}${dayName.substring(1)}';
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
          decoration: BoxDecoration(
            color: tokens.glass,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: tokens.border),
          ),
          child: Row(
            children: [
              Container(
                width: 46,
                height: 46,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: tokens.tonedSurface(color),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      '${data.date.day}',
                      style: GoogleFonts.inter(
                        fontSize: 16,
                        fontWeight: FontWeight.w800,
                        color: color,
                        height: 1,
                      ),
                    ),
                    const SizedBox(height: 1),
                    Text(
                      DateFormat('MMM', 'uz').format(data.date).toUpperCase(),
                      style: GoogleFonts.inter(
                        fontSize: 8.5,
                        fontWeight: FontWeight.w700,
                        color: color.withValues(alpha: 0.85),
                        letterSpacing: 0.5,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      prettyDay,
                      style: GoogleFonts.inter(
                        fontSize: 13.5,
                        fontWeight: FontWeight.w800,
                        color: tokens.text,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Row(
                      children: [
                        Icon(icon, size: 12, color: color),
                        const SizedBox(width: 4),
                        Text(
                          data.entryCount > 0
                              ? '$label · ${data.entryCount} ta yozuv'
                              : label,
                          style: GoogleFonts.inter(
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                            color: tokens.textMuted,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              if (data.netPoints != 0) ...[
                Text(
                  '${data.netPoints > 0 ? '+' : ''}${data.netPoints}',
                  style: GoogleFonts.inter(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w800,
                    color: data.netPoints > 0 ? tokens.success : tokens.danger,
                  ),
                ),
                const SizedBox(width: 3),
                Icon(
                  Icons.bolt_rounded,
                  size: 14,
                  color: data.netPoints > 0 ? tokens.success : tokens.danger,
                ),
              ],
              const SizedBox(width: 6),
              Icon(Icons.chevron_right_rounded, color: tokens.textDim, size: 18),
            ],
          ),
        ),
      ),
    );
  }
}

class _MonthSummary {
  const _MonthSummary({
    required this.attendedDays,
    required this.absentDays,
    required this.mixedDays,
    required this.netPoints,
  });

  final int attendedDays;
  final int absentDays;
  final int mixedDays;
  final int netPoints;

  static _MonthSummary from(DateTime month, Map<DateTime, List<ChaqmoqEntryModel>> byDate) {
    var attended = 0;
    var absent = 0;
    var mixed = 0;
    var net = 0;
    final lastDay = DateTime(month.year, month.month + 1, 0).day;
    for (var d = 1; d <= lastDay; d++) {
      final date = DateTime(month.year, month.month, d);
      final entries = byDate[date];
      if (entries == null || entries.isEmpty) continue;
      final hasPos = entries.any((e) => e.points > 0);
      final hasNeg = entries.any((e) => e.points < 0);
      if (hasPos && hasNeg) {
        mixed++;
      } else if (hasPos) {
        attended++;
      } else if (hasNeg) {
        absent++;
      }
      for (final e in entries) {
        net += e.points;
      }
    }
    return _MonthSummary(
      attendedDays: attended,
      absentDays: absent,
      mixedDays: mixed,
      netPoints: net,
    );
  }
}
