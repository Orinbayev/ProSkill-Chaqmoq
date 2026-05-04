import 'dart:math' as math;

import 'package:chaqmoq_mobile/core/theme/parent_colors.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/parent_models.dart';
import 'package:chaqmoq_mobile/providers/parent_dashboard_provider.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/parent_dashboard_service.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

class AttendanceScreen extends StatefulWidget {
  const AttendanceScreen({super.key, this.showBottomNav = true});

  final bool showBottomNav;

  @override
  State<AttendanceScreen> createState() => _AttendanceScreenState();
}

class _AttendanceScreenState extends State<AttendanceScreen> {
  ParentAttendanceModel? _data;
  ViewState _state = ViewState.idle;
  String? _errorMessage;
  DateTime _month = DateTime(DateTime.now().year, DateTime.now().month);
  DateTime _selectedDate = DateTime.now();
  int? _loadedChildId;
  int? _selectedGroupId;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final dashboard = context.watch<ParentDashboardProvider>();
    final childId =
        dashboard.selectedChildId ?? dashboard.data?.selectedChild.id;
    if (childId != null && childId > 0 && childId != _loadedChildId) {
      _loadedChildId = childId;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _load(force: true);
      });
    }
  }

  Future<void> _load({bool force = false}) async {
    if (_state == ViewState.loading && !force) return;
    setState(() {
      _state = ViewState.loading;
      _errorMessage = null;
    });
    try {
      final data = await context.read<ParentDashboardService>().fetchAttendance(
        childId: _loadedChildId,
        month: _month,
        groupId: _selectedGroupId,
      );
      if (!mounted) return;
      setState(() {
        _data = data;
        _state = ViewState.success;
        _selectedDate = _normalizeSelectedDate(_selectedDate, _month);
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _state = ViewState.error;
        _errorMessage = error.message;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _state = ViewState.error;
        _errorMessage = 'Davomat ma’lumotlari yuklanmadi';
      });
    }
  }

  void _changeMonth(int offset) {
    setState(() {
      _month = DateTime(_month.year, _month.month + offset);
      _selectedDate = _normalizeSelectedDate(_selectedDate, _month);
    });
    _load(force: true);
  }

  void _selectDate(DateTime date) {
    setState(() => _selectedDate = date);
  }

  Future<void> _openFilterSheet() async {
    final groups = _data?.groups ?? const <ParentAttendanceGroupOption>[];
    final result = await showModalBottomSheet<int?>(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (sheetContext) => _FilterSheet(
        groups: groups,
        selectedGroupId: _selectedGroupId,
      ),
    );
    if (!mounted || result == null) return;
    final next = result == -1 ? null : result;
    if (next == _selectedGroupId) return;
    setState(() => _selectedGroupId = next);
    await _load(force: true);
  }

  @override
  Widget build(BuildContext context) {
    ParentColors.update(Theme.of(context).brightness);
    final fallbackChild = context
        .watch<ParentDashboardProvider>()
        .data
        ?.selectedChild;
    final child = _data?.child ?? fallbackChild;
    final summary = _data?.summary;
    final monthItems = _itemsForMonth(_data?.items ?? const [], _month);

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.dark,
        statusBarBrightness: Brightness.light,
        systemNavigationBarColor: AttendanceColors.background,
        systemNavigationBarIconBrightness: Brightness.dark,
      ),
      child: Scaffold(
        backgroundColor: AttendanceColors.background,
        bottomNavigationBar: widget.showBottomNav
            ? const ParentBottomNav()
            : null,
        body: SafeArea(
          child: RefreshIndicator(
            color: AttendanceColors.primaryBlue,
            onRefresh: () => _load(force: true),
            child: SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(
                parent: BouncingScrollPhysics(),
              ),
              padding: const EdgeInsets.fromLTRB(18, 8, 18, 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _Header(
                    onFilter: _openFilterSheet,
                    activeFilter: _selectedGroupId != null,
                  ),
                  const SizedBox(height: 14),
                  if (_state == ViewState.loading && _data == null)
                    const _LoadingCard()
                  else if (_state == ViewState.error && _data == null)
                    _ErrorCard(
                      message: _errorMessage ?? 'Qayta urinib ko‘ring',
                      onRetry: () => _load(force: true),
                    )
                  else ...[
                    if (_state == ViewState.loading)
                      const Padding(
                        padding: EdgeInsets.only(bottom: 10),
                        child: LinearProgressIndicator(
                          minHeight: 3,
                          color: AttendanceColors.primaryBlue,
                          backgroundColor: Color(0xFFEAF4FF),
                        ),
                      ),
                    _SummaryHero(
                      child: child,
                      month: _month,
                      summary: summary,
                    ),
                    const SizedBox(height: 16),
                    _MonthNav(
                      label: _monthYearLabel(_month),
                      onPrev: () => _changeMonth(-1),
                      onNext: () => _changeMonth(1),
                    ),
                    const SizedBox(height: 12),
                    _CalendarCard(
                      month: _month,
                      selectedDate: _selectedDate,
                      items: _data?.items ?? const [],
                      onSelect: _selectDate,
                    ),
                    const SizedBox(height: 18),
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            "${_monthYearLabel(_month)} davomati",
                            style: GoogleFonts.inter(
                              fontSize: 15,
                              fontWeight: FontWeight.w800,
                              color: AttendanceColors.text,
                              letterSpacing: -0.2,
                            ),
                          ),
                        ),
                        if (monthItems.isNotEmpty)
                          Text(
                            '${monthItems.length} ta yozuv',
                            style: GoogleFonts.inter(
                              fontSize: 11.5,
                              fontWeight: FontWeight.w700,
                              color: AttendanceColors.textMuted,
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    if (monthItems.isEmpty)
                      _EmptyMonthCard()
                    else
                      for (final item in monthItems) ...[
                        _LessonCard(item: item),
                        const SizedBox(height: 8),
                      ],
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.onFilter, required this.activeFilter});

  final VoidCallback onFilter;
  final bool activeFilter;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(
            'Davomat',
            style: GoogleFonts.inter(
              fontSize: 26,
              fontWeight: FontWeight.w800,
              color: AttendanceColors.text,
              letterSpacing: -0.5,
            ),
          ),
        ),
        Material(
          color: Colors.white,
          borderRadius: BorderRadius.circular(13),
          child: InkWell(
            onTap: onFilter,
            borderRadius: BorderRadius.circular(13),
            child: Container(
              width: 42,
              height: 42,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(13),
                border: Border.all(
                  color: activeFilter
                      ? AttendanceColors.primaryBlue
                      : AttendanceColors.line,
                  width: activeFilter ? 1.5 : 1,
                ),
              ),
              alignment: Alignment.center,
              child: Stack(
                clipBehavior: Clip.none,
                alignment: Alignment.center,
                children: [
                  Icon(
                    Icons.tune_rounded,
                    size: 22,
                    color: activeFilter
                        ? AttendanceColors.primaryBlue
                        : AttendanceColors.text,
                  ),
                  if (activeFilter)
                    Positioned(
                      top: -2,
                      right: -2,
                      child: Container(
                        width: 8,
                        height: 8,
                        decoration: BoxDecoration(
                          color: AttendanceColors.primaryBlue,
                          shape: BoxShape.circle,
                        ),
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
}

class _FilterSheet extends StatelessWidget {
  const _FilterSheet({required this.groups, required this.selectedGroupId});

  final List<ParentAttendanceGroupOption> groups;
  final int? selectedGroupId;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 22),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: AttendanceColors.line,
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
            ),
            const SizedBox(height: 14),
            Text(
              'Guruh bo‘yicha filter',
              style: GoogleFonts.inter(
                fontSize: 16,
                fontWeight: FontWeight.w800,
                color: AttendanceColors.text,
              ),
            ),
            const SizedBox(height: 14),
            _FilterTile(
              label: 'Hammasi',
              selected: selectedGroupId == null,
              onTap: () => Navigator.of(context).pop(-1),
            ),
            for (final g in groups)
              _FilterTile(
                label: g.name,
                selected: selectedGroupId == g.id,
                onTap: () => Navigator.of(context).pop(g.id),
              ),
            if (groups.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 18),
                child: Text(
                  'Hozircha guruhlar yo‘q',
                  textAlign: TextAlign.center,
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                    color: AttendanceColors.textMuted,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _FilterTile extends StatelessWidget {
  const _FilterTile({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
        margin: const EdgeInsets.only(bottom: 8),
        decoration: BoxDecoration(
          color: selected
              ? AttendanceColors.primaryBlue.withValues(alpha: 0.08)
              : Colors.white,
          border: Border.all(
            color:
                selected ? AttendanceColors.primaryBlue : AttendanceColors.line,
            width: selected ? 1.4 : 1,
          ),
          borderRadius: BorderRadius.circular(14),
        ),
        child: Row(
          children: [
            Icon(
              selected
                  ? Icons.radio_button_checked_rounded
                  : Icons.radio_button_unchecked_rounded,
              size: 20,
              color: selected
                  ? AttendanceColors.primaryBlue
                  : AttendanceColors.textMuted,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                label,
                style: GoogleFonts.inter(
                  fontSize: 14,
                  fontWeight:
                      selected ? FontWeight.w700 : FontWeight.w600,
                  color: AttendanceColors.text,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SummaryHero extends StatelessWidget {
  const _SummaryHero({this.child, required this.month, this.summary});

  final ParentChildModel? child;
  final DateTime month;
  final ParentAttendanceSummaryModel? summary;

  @override
  Widget build(BuildContext context) {
    final s = summary;
    final total = s?.totalLessons ?? 0;
    final attended = s?.attendedLessons ?? 0;
    final percent = s == null
        ? 0
        : (s.attendancePercent > 0
            ? s.attendancePercent
            : (total > 0
                ? ((attended / total) * 100).round()
                : 0));
    final hasLessons = total > 0;
    final name = (child?.fullName ?? '').trim().isEmpty
        ? 'Farzand'
        : child!.fullName.trim();
    final detailLine = hasLessons
        ? '$total dan $attended dars qatnashgan'
        : 'Bu oyda dars topilmadi';

    return Container(
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 18),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF10B981), Color(0xFF059669)],
        ),
        borderRadius: BorderRadius.circular(22),
        boxShadow: const [
          BoxShadow(
            color: Color(0x4710B981),
            blurRadius: 28,
            offset: Offset(0, 12),
          ),
        ],
      ),
      child: Row(
        children: [
          SizedBox(
            width: 64,
            height: 64,
            child: Stack(
              alignment: Alignment.center,
              children: [
                CustomPaint(
                  size: const Size(64, 64),
                  painter: _RingPainter(hasLessons ? percent / 100 : 0),
                ),
                Text(
                  hasLessons ? '$percent%' : '—',
                  style: GoogleFonts.inter(
                    fontSize: hasLessons ? 16 : 18,
                    fontWeight: FontWeight.w800,
                    color: Colors.white,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  _monthYearUpper(month),
                  style: GoogleFonts.inter(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    color: Colors.white.withValues(alpha: 0.92),
                    letterSpacing: 1.4,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 17,
                    fontWeight: FontWeight.w800,
                    color: Colors.white,
                    letterSpacing: -0.2,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  detailLine,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w500,
                    color: Colors.white.withValues(alpha: 0.92),
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

class _RingPainter extends CustomPainter {
  _RingPainter(this.progress);
  final double progress;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = (size.width / 2) - 4;
    final track = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 6
      ..color = Colors.white.withValues(alpha: 0.22);
    final arc = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 6
      ..strokeCap = StrokeCap.round
      ..color = Colors.white;
    canvas.drawCircle(center, radius, track);
    final rect = Rect.fromCircle(center: center, radius: radius);
    canvas.drawArc(rect, -math.pi / 2, 2 * math.pi * progress, false, arc);
  }

  @override
  bool shouldRepaint(covariant _RingPainter oldDelegate) =>
      oldDelegate.progress != progress;
}

class _MonthNav extends StatelessWidget {
  const _MonthNav({
    required this.label,
    required this.onPrev,
    required this.onNext,
  });

  final String label;
  final VoidCallback onPrev;
  final VoidCallback onNext;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        _MonthArrow(icon: Icons.chevron_left_rounded, onTap: onPrev),
        Text(
          label,
          style: GoogleFonts.inter(
            fontSize: 15,
            fontWeight: FontWeight.w800,
            color: AttendanceColors.text,
            letterSpacing: -0.2,
          ),
        ),
        _MonthArrow(icon: Icons.chevron_right_rounded, onTap: onNext),
      ],
    );
  }
}

class _MonthArrow extends StatelessWidget {
  const _MonthArrow({required this.icon, required this.onTap});
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(11),
        side: BorderSide(color: AttendanceColors.line),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(11),
        onTap: onTap,
        child: SizedBox(
          width: 36,
          height: 36,
          child: Icon(icon, size: 20, color: AttendanceColors.text),
        ),
      ),
    );
  }
}

class _CalendarCard extends StatelessWidget {
  const _CalendarCard({
    required this.month,
    required this.selectedDate,
    required this.items,
    required this.onSelect,
  });

  final DateTime month;
  final DateTime selectedDate;
  final List<ParentAttendanceItemModel> items;
  final ValueChanged<DateTime> onSelect;

  static const _labels = ['D', 'S', 'C', 'P', 'J', 'S', 'Y'];

  @override
  Widget build(BuildContext context) {
    final firstDay = DateTime(month.year, month.month);
    final daysInMonth = DateTime(month.year, month.month + 1, 0).day;
    // weekday: Monday=1..Sunday=7. Our header is Du Se Cho Pa Ju Sh Ya — index 0..6
    final leading = firstDay.weekday - 1;

    final cells = <Widget>[];
    for (var i = 0; i < leading; i++) {
      cells.add(const SizedBox.shrink());
    }
    for (var d = 1; d <= daysInMonth; d++) {
      final date = DateTime(month.year, month.month, d);
      final dayItems = _itemsForDate(items, date);
      final isSelected = _isSameDay(date, selectedDate);
      final status = _dayStatus(dayItems);
      cells.add(_DayCell(
        day: d,
        selected: isSelected,
        status: status,
        onTap: () => onSelect(date),
      ));
    }

    return Container(
      padding: const EdgeInsets.fromLTRB(14, 14, 14, 14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AttendanceColors.line),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0D0B1220),
            blurRadius: 18,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        children: [
          Row(
            children: [
              for (final l in _labels)
                Expanded(
                  child: Text(
                    l,
                    textAlign: TextAlign.center,
                    style: GoogleFonts.inter(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      color: AttendanceColors.textMuted,
                      letterSpacing: 0.2,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 8),
          GridView.count(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            crossAxisCount: 7,
            mainAxisSpacing: 4,
            crossAxisSpacing: 4,
            childAspectRatio: 0.95,
            children: cells,
          ),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.only(top: 10),
            decoration: BoxDecoration(
              border: Border(top: BorderSide(color: AttendanceColors.line)),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: const [
                _Legend(color: Color(0xFF10B981), label: 'Kelgan'),
                _Legend(color: Color(0xFFEF4444), label: 'Kelmagan'),
                _Legend(color: Color(0xFFF59E0B), label: 'Sababli'),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _DayCell extends StatelessWidget {
  const _DayCell({
    required this.day,
    required this.selected,
    required this.status,
    required this.onTap,
  });

  final int day;
  final bool selected;
  final _DayStatus status;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = _DayCellTheme.of(status, selected: selected);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        decoration: BoxDecoration(
          color: theme.background,
          borderRadius: BorderRadius.circular(12),
          border: theme.border,
        ),
        alignment: Alignment.center,
        child: Text(
          '$day',
          style: GoogleFonts.inter(
            fontSize: 13,
            fontWeight: FontWeight.w800,
            color: theme.foreground,
            letterSpacing: -0.2,
          ),
        ),
      ),
    );
  }
}

enum _DayStatus { none, present, absent, excused }

class _DayCellTheme {
  const _DayCellTheme({
    required this.background,
    required this.foreground,
  });

  final Color background;
  final Color foreground;
  BoxBorder? get border => null;

  static _DayCellTheme of(_DayStatus status, {required bool selected}) {
    if (selected) {
      return const _DayCellTheme(
        background: AttendanceColors.primaryBlue,
        foreground: Colors.white,
      );
    }
    switch (status) {
      case _DayStatus.present:
        return const _DayCellTheme(
          background: Color(0xFFDCFCE7),
          foreground: Color(0xFF047857),
        );
      case _DayStatus.absent:
        return const _DayCellTheme(
          background: Color(0xFFFEE2E2),
          foreground: Color(0xFFB91C1C),
        );
      case _DayStatus.excused:
        return const _DayCellTheme(
          background: Color(0xFFFEF3C7),
          foreground: Color(0xFFB45309),
        );
      case _DayStatus.none:
        return _DayCellTheme(
          background: Colors.transparent,
          foreground: AttendanceColors.text,
        );
    }
  }
}

class _Legend extends StatelessWidget {
  const _Legend({required this.color, required this.label});
  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 6,
          height: 6,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 6),
        Text(
          label,
          style: GoogleFonts.inter(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: AttendanceColors.textSoft,
          ),
        ),
      ],
    );
  }
}

class _LessonCard extends StatelessWidget {
  const _LessonCard({required this.item});
  final ParentAttendanceItemModel item;

  @override
  Widget build(BuildContext context) {
    final present = item.present;
    final statusLower = item.status.toLowerCase();
    final isExcused = !present &&
        (statusLower.contains('excused') ||
            statusLower.contains('late') ||
            statusLower.contains('sababli'));
    final barColor = present
        ? AttendanceColors.green
        : isExcused
            ? AttendanceColors.amber
            : AttendanceColors.red;

    final title = item.groupName.trim().isEmpty
        ? 'Dars'
        : item.groupName.trim();
    final teacher = item.teacherName.trim().isEmpty
        ? 'O‘qituvchi'
        : item.teacherName.trim();
    final dateLabel = _shortDate(item.date);
    final timeLabel = item.createdAt != null
        ? _shortTime(item.createdAt!)
        : '';
    final subtitle = timeLabel.isEmpty
        ? '$dateLabel · $teacher'
        : '$dateLabel · $timeLabel · $teacher';

    final pillBg = present
        ? const Color(0xFFDCFCE7)
        : isExcused
            ? const Color(0xFFFEF3C7)
            : const Color(0xFFFEE2E2);
    final pillFg = present
        ? const Color(0xFF047857)
        : isExcused
            ? const Color(0xFFB45309)
            : const Color(0xFFB91C1C);
    final pillLabel = present
        ? 'Kelgan'
        : (isExcused ? 'Sababli' : 'Kelmagan');

    return Container(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AttendanceColors.line),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0A0B1220),
            blurRadius: 14,
            offset: Offset(0, 6),
          ),
        ],
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Container(
            width: 4,
            height: 38,
            decoration: BoxDecoration(
              color: barColor,
              borderRadius: BorderRadius.circular(4),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w800,
                    color: AttendanceColors.text,
                    letterSpacing: -0.1,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 11.5,
                    fontWeight: FontWeight.w600,
                    color: AttendanceColors.textMuted,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(
              color: pillBg,
              borderRadius: BorderRadius.circular(100),
            ),
            child: Text(
              pillLabel,
              style: GoogleFonts.inter(
                fontSize: 11,
                fontWeight: FontWeight.w800,
                color: pillFg,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyMonthCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(14, 18, 14, 18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AttendanceColors.line),
      ),
      alignment: Alignment.center,
      child: Text(
        "Bu oyda hali davomat yozuvi yo‘q",
        textAlign: TextAlign.center,
        style: GoogleFonts.inter(
          fontSize: 13,
          fontWeight: FontWeight.w600,
          color: AttendanceColors.textMuted,
        ),
      ),
    );
  }
}

class _LoadingCard extends StatelessWidget {
  const _LoadingCard();
  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 60),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AttendanceColors.line),
      ),
      alignment: Alignment.center,
      child: const CircularProgressIndicator(
        color: AttendanceColors.primaryBlue,
      ),
    );
  }
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(18, 28, 18, 24),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AttendanceColors.line),
      ),
      child: Column(
        children: [
          const Icon(
            Icons.info_outline_rounded,
            color: AttendanceColors.primaryBlue,
            size: 36,
          ),
          const SizedBox(height: 10),
          Text(
            message,
            textAlign: TextAlign.center,
            style: GoogleFonts.inter(
              fontSize: 13.5,
              fontWeight: FontWeight.w600,
              color: AttendanceColors.textSoft,
            ),
          ),
          const SizedBox(height: 14),
          TextButton(
            onPressed: onRetry,
            style: TextButton.styleFrom(
              backgroundColor: const Color(0xFFEFF6FF),
              foregroundColor: AttendanceColors.primaryBlue,
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
            ),
            child: const Text('Qayta urinish'),
          ),
        ],
      ),
    );
  }
}

class ParentBottomNav extends StatelessWidget {
  const ParentBottomNav({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        boxShadow: [
          BoxShadow(
            color: Color(0x140B1220),
            blurRadius: 24,
            offset: Offset(0, -8),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: ClipRRect(
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
          child: BottomNavigationBar(
            currentIndex: 1,
            onTap: (_) {},
            type: BottomNavigationBarType.fixed,
            backgroundColor: Colors.white,
            elevation: 0,
            selectedItemColor: AttendanceColors.primaryBlue,
            unselectedItemColor: AttendanceColors.textMuted,
            iconSize: 24,
            selectedFontSize: 11,
            unselectedFontSize: 11,
            items: const [
              BottomNavigationBarItem(
                icon: Icon(Icons.home_rounded),
                label: 'Bosh',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.fact_check_outlined),
                label: 'Davomat',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.account_balance_wallet_outlined),
                label: 'To‘lovlar',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.auto_graph_rounded),
                label: 'Progress',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.person_rounded),
                label: 'Profil',
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ---- Helpers ----
DateTime _normalizeSelectedDate(DateTime selectedDate, DateTime month) {
  final lastDay = DateTime(month.year, month.month + 1, 0).day;
  final day =
      selectedDate.month == month.month && selectedDate.year == month.year
      ? selectedDate.day.clamp(1, lastDay)
      : DateTime.now().day.clamp(1, lastDay);
  return DateTime(month.year, month.month, day);
}

List<ParentAttendanceItemModel> _itemsForDate(
  List<ParentAttendanceItemModel> items,
  DateTime date,
) {
  return items.where((item) => _isSameDay(item.date, date)).toList();
}

List<ParentAttendanceItemModel> _itemsForMonth(
  List<ParentAttendanceItemModel> items,
  DateTime month,
) {
  final filtered = items
      .where((item) =>
          item.date.year == month.year && item.date.month == month.month)
      .toList();
  filtered.sort((a, b) {
    final byDate = b.date.compareTo(a.date);
    if (byDate != 0) return byDate;
    final aTs = a.createdAt ?? a.date;
    final bTs = b.createdAt ?? b.date;
    return bTs.compareTo(aTs);
  });
  return filtered;
}

String _shortDate(DateTime date) {
  const m = [
    'yan', 'fev', 'mar', 'apr', 'may', 'iyn',
    'iyl', 'avg', 'sen', 'okt', 'noy', 'dek',
  ];
  return '${date.day} ${m[date.month - 1]}';
}

String _shortTime(DateTime ts) {
  final hh = ts.hour.toString().padLeft(2, '0');
  final mm = ts.minute.toString().padLeft(2, '0');
  return '$hh:$mm';
}

bool _isSameDay(DateTime a, DateTime b) =>
    a.year == b.year && a.month == b.month && a.day == b.day;

_DayStatus _dayStatus(List<ParentAttendanceItemModel> items) {
  if (items.isEmpty) return _DayStatus.none;
  final hasPresent = items.any((i) => i.present);
  final hasExcused = items.any(
    (i) =>
        i.status.toLowerCase().contains('excused') ||
        i.status.toLowerCase().contains('late') ||
        i.status.toLowerCase().contains('sababli'),
  );
  final hasUnexcused = items.any(
    (i) => !i.present &&
        (i.status.toLowerCase().contains('unexcused') ||
            i.status.toLowerCase() == 'absent'),
  );
  if (hasPresent) return _DayStatus.present;
  if (hasUnexcused) return _DayStatus.absent;
  if (hasExcused) return _DayStatus.excused;
  return _DayStatus.absent;
}

String _monthYearLabel(DateTime date) {
  const months = [
    'Yanvar',
    'Fevral',
    'Mart',
    'Aprel',
    'May',
    'Iyun',
    'Iyul',
    'Avgust',
    'Sentabr',
    'Oktabr',
    'Noyabr',
    'Dekabr',
  ];
  return '${months[date.month - 1]} ${date.year}';
}

String _monthYearUpper(DateTime date) {
  const m = [
    'YAN',
    'FEV',
    'MAR',
    'APR',
    'MAY',
    'IYUN',
    'IYUL',
    'AVG',
    'SEN',
    'OKT',
    'NOY',
    'DEK',
  ];
  return '${m[date.month - 1]} ${date.year}';
}


class AttendanceColors {
  const AttendanceColors._();
  static bool get _isDark =>
      ParentColors.bg == const Color(0xFF0B0F17);
  static Color get background => _isDark
      ? const Color(0xFF0B0F17)
      : const Color(0xFFF4F7FB);
  static Color get card => _isDark
      ? const Color(0xFF141926)
      : const Color(0xFFFFFFFF);
  static Color get text => _isDark
      ? const Color(0xFFEAF1FB)
      : const Color(0xFF0F1E33);
  static Color get textSoft => _isDark
      ? const Color(0xFFB6C2D6)
      : const Color(0xFF4B5B72);
  static Color get textMuted => _isDark
      ? const Color(0xFF94A3B8)
      : const Color(0xFF8090A8);
  static Color get line => _isDark
      ? const Color(0xFF24304A)
      : const Color(0xFFE4ECF5);
  static const Color primaryBlue = Color(0xFF3B82F6);
  static const Color green = Color(0xFF10B981);
  static const Color red = Color(0xFFEF4444);
  static const Color amber = Color(0xFFF59E0B);
}

// Backwards-compat aliases to avoid breaking other imports if they reach this
// file. Kept lean on purpose.
class AttendanceTextStyles {
  const AttendanceTextStyles._();
  static TextStyle get title => GoogleFonts.inter(
        fontSize: 18,
        fontWeight: FontWeight.w800,
        color: AttendanceColors.text,
      );
  static TextStyle get body => GoogleFonts.inter(
        fontSize: 14,
        fontWeight: FontWeight.w500,
        color: AttendanceColors.text,
      );
  static TextStyle get label => GoogleFonts.inter(
        fontSize: 12,
        fontWeight: FontWeight.w800,
        color: AttendanceColors.text,
      );
}
