import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/chaqmoq_history_provider.dart';
import 'package:chaqmoq_mobile/screens/student/widgets/student_atmospheric_backdrop.dart';
import 'package:chaqmoq_mobile/screens/student/widgets/student_day_detail_sheet.dart';
import 'package:chaqmoq_mobile/widgets/app_badge.dart';
import 'package:chaqmoq_mobile/widgets/app_card.dart';
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
    if (user != null) {
      _hydrated = true;
      context.read<ChaqmoqHistoryProvider>().load();
    }
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
      padding: EdgeInsets.fromLTRB(18, widget.standalone ? 8 : 14, 18, 110),
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
          const SizedBox(height: 12),
        ],
        _MonthSwitcher(
          month: _viewMonth,
          onPrev: () => setState(() => _viewMonth = DateTime(_viewMonth.year, _viewMonth.month - 1)),
          onNext: _canGoNext()
              ? () => setState(() => _viewMonth = DateTime(_viewMonth.year, _viewMonth.month + 1))
              : null,
        ),
        const SizedBox(height: 12),
        _SummaryCard(summary: summary),
        const SizedBox(height: 12),
        _Legend(),
        const SizedBox(height: 12),
        _Calendar(
          month: _viewMonth,
          byDate: byDate,
          onDayTap: (date) => _openDay(date, byDate[date] ?? const []),
        ),
        const SizedBox(height: 14),
        _MonthDayList(
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
    return AppGCard(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
      child: Row(
        children: [
          _NavButton(icon: Icons.chevron_left_rounded, onTap: onPrev, tokens: tokens),
          Expanded(
            child: Center(
              child: Text(
                DateFormat('MMMM yyyy', 'uz').format(month),
                style: GoogleFonts.inter(
                  fontSize: 14,
                  fontWeight: FontWeight.w800,
                  color: tokens.text,
                ),
              ),
            ),
          ),
          _NavButton(icon: Icons.chevron_right_rounded, onTap: onNext, tokens: tokens),
        ],
      ),
    );
  }
}

class _NavButton extends StatelessWidget {
  const _NavButton({required this.icon, required this.onTap, required this.tokens});

  final IconData icon;
  final VoidCallback? onTap;
  final StudentTokens tokens;

  @override
  Widget build(BuildContext context) {
    final disabled = onTap == null;
    return Material(
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
            color: tokens.glass,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: tokens.border),
          ),
          child: Icon(
            icon,
            size: 20,
            color: disabled ? tokens.textDim : tokens.text,
          ),
        ),
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({required this.summary});

  final _MonthSummary summary;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return AppGCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            summary.attendedDays + summary.absentDays == 0
                ? 'Bu oyda hali yozuv yo‘q'
                : '${summary.totalRecorded} kundan ${summary.attendedDays} tasiga kelgan',
            style: GoogleFonts.inter(
              fontSize: 13,
              fontWeight: FontWeight.w800,
              color: tokens.text,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(child: _SummaryStat(label: 'Kelgan', value: '${summary.attendedDays}', color: tokens.success)),
              Container(width: 1, height: 36, color: tokens.border),
              Expanded(child: _SummaryStat(label: 'Kelmagan', value: '${summary.absentDays}', color: tokens.danger)),
              Container(width: 1, height: 36, color: tokens.border),
              Expanded(
                child: _SummaryStat(
                  label: 'Sof ball',
                  value: '${summary.netBall >= 0 ? '+' : ''}${summary.netBall}',
                  color: summary.netBall >= 0 ? tokens.primary : tokens.danger,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _SummaryStat extends StatelessWidget {
  const _SummaryStat({required this.label, required this.value, required this.color});

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            value,
            style: GoogleFonts.inter(
              fontSize: 17,
              fontWeight: FontWeight.w800,
              color: color,
              letterSpacing: -0.3,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: GoogleFonts.inter(
              fontSize: 10.5,
              fontWeight: FontWeight.w600,
              color: tokens.textMuted,
            ),
          ),
        ],
      ),
    );
  }
}

class _Legend extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    Widget chip(Color color, String label) {
      return Padding(
        padding: const EdgeInsets.only(right: 10),
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
      runSpacing: 6,
      children: [
        chip(tokens.success, 'Kelgan'),
        chip(tokens.danger, 'Kelmagan'),
        chip(tokens.warning, 'Aralash'),
        chip(tokens.glassStrong, 'Yozuv yo‘q'),
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
        netBall: entries.fold<int>(0, (s, e) => s + e.points),
        isToday: isToday,
        isFuture: isFuture,
        onTap: isFuture ? null : () => onDayTap(date),
      ));
    }

    return AppGCard(
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
              _Weekday(label: 'Sh'),
              _Weekday(label: 'Ya'),
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
            childAspectRatio: 0.85,
            children: cells,
          ),
        ],
      ),
    );
  }
}

class _Weekday extends StatelessWidget {
  const _Weekday({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Expanded(
      child: Center(
        child: Text(
          label,
          style: GoogleFonts.inter(
            fontSize: 10.5,
            fontWeight: FontWeight.w700,
            color: tokens.textMuted,
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
    required this.netBall,
    required this.isToday,
    required this.isFuture,
    this.onTap,
  });

  final DateTime date;
  final _CellStatus status;
  final int netBall;
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
    final cellBg = hasData
        ? tokens.tonedSurface(accent)
        : (isFuture ? Colors.transparent : tokens.glass);
    final borderColor = isToday
        ? tokens.primary
        : (hasData ? tokens.tonedBorder(accent) : tokens.border);
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
            border: Border.all(color: borderColor, width: isToday ? 1.5 : 1),
          ),
          padding: const EdgeInsets.all(4),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                '${date.day}',
                style: GoogleFonts.inter(
                  fontSize: 13,
                  fontWeight: FontWeight.w800,
                  color: isFuture ? tokens.textDim : tokens.text,
                ),
              ),
              if (hasData) ...[
                const SizedBox(height: 2),
                Text(
                  '${netBall > 0 ? '+' : ''}$netBall',
                  style: GoogleFonts.inter(
                    fontSize: 9.5,
                    fontWeight: FontWeight.w800,
                    color: accent,
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _MonthDayList extends StatelessWidget {
  const _MonthDayList({required this.month, required this.byDate, required this.onTap});

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
      rows.add(_DayRowData(
        date: date,
        status: _classifyDay(entries),
        netBall: entries.fold<int>(0, (s, e) => s + e.points),
        entryCount: entries.length,
      ));
    }
    rows.sort((a, b) => b.date.compareTo(a.date));

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'BU OYDAGI KUNLAR',
          style: GoogleFonts.inter(
            fontSize: 11,
            fontWeight: FontWeight.w800,
            color: tokens.textMuted,
            letterSpacing: 1.6,
          ),
        ),
        const SizedBox(height: 8),
        if (rows.isEmpty)
          AppGCard(
            child: Row(
              children: [
                Icon(Icons.event_busy_rounded, color: tokens.textDim, size: 20),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    'Bu oyda hech qanday yozuv yo‘q',
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
          AppGCard(
            padding: const EdgeInsets.all(4),
            child: Column(
              children: [
                for (var i = 0; i < rows.length; i++) ...[
                  _DayRow(data: rows[i], onTap: () => onTap(rows[i].date)),
                  if (i < rows.length - 1)
                    Container(height: 1, color: tokens.border),
                ],
              ],
            ),
          ),
      ],
    );
  }
}

class _DayRowData {
  const _DayRowData({
    required this.date,
    required this.status,
    required this.netBall,
    required this.entryCount,
  });

  final DateTime date;
  final _CellStatus status;
  final int netBall;
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
      _CellStatus.none => 'Yozuv yo‘q',
    };
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Row(
          children: [
            Container(
              width: 38,
              height: 38,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: tokens.tonedSurface(color),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, color: color, size: 20),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    DateFormat('EEEE, d MMM', 'uz').format(data.date),
                    style: GoogleFonts.inter(
                      fontSize: 12.5,
                      fontWeight: FontWeight.w700,
                      color: tokens.text,
                    ),
                  ),
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
            ),
            if (data.netBall != 0)
              AppBadge(
                label: '${data.netBall > 0 ? '+' : ''}${data.netBall} ball',
                tone: data.netBall > 0
                    ? AppBadgeTone.success
                    : (data.netBall < 0 ? AppBadgeTone.danger : AppBadgeTone.neutral),
                dark: tokens.isDark,
              ),
            const SizedBox(width: 6),
            Icon(Icons.chevron_right_rounded, color: tokens.textDim, size: 18),
          ],
        ),
      ),
    );
  }
}

class _MonthSummary {
  const _MonthSummary({
    required this.attendedDays,
    required this.absentDays,
    required this.netBall,
  });

  final int attendedDays;
  final int absentDays;
  final int netBall;

  int get totalRecorded => attendedDays + absentDays;

  static _MonthSummary from(DateTime month, Map<DateTime, List<ChaqmoqEntryModel>> byDate) {
    var attended = 0;
    var absent = 0;
    var net = 0;
    final lastDay = DateTime(month.year, month.month + 1, 0).day;
    for (var d = 1; d <= lastDay; d++) {
      final date = DateTime(month.year, month.month, d);
      final entries = byDate[date];
      if (entries == null || entries.isEmpty) continue;
      final hasPos = entries.any((e) => e.points > 0);
      final hasNeg = entries.any((e) => e.points < 0);
      if (hasPos) attended++;
      if (!hasPos && hasNeg) absent++;
      for (final e in entries) {
        net += e.points;
      }
    }
    return _MonthSummary(attendedDays: attended, absentDays: absent, netBall: net);
  }
}
