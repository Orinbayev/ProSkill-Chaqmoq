import 'dart:math' as math;

import 'package:chaqmoq_mobile/core/utils/formatters.dart';
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

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final dashboard = context.watch<ParentDashboardProvider>();
    final childId =
        dashboard.selectedChildId ?? dashboard.data?.selectedChild.id;
    if (childId != null && childId > 0 && childId != _loadedChildId) {
      _loadedChildId = childId;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          _load(force: true);
        }
      });
    }
  }

  Future<void> _load({bool force = false}) async {
    if (_state == ViewState.loading && !force) {
      return;
    }
    setState(() {
      _state = ViewState.loading;
      _errorMessage = null;
    });

    try {
      final data = await context.read<ParentDashboardService>().fetchAttendance(
        childId: _loadedChildId,
        month: _month,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _data = data;
        _state = ViewState.success;
        _selectedDate = _normalizeSelectedDate(_selectedDate, _month);
      });
    } on ApiException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _state = ViewState.error;
        _errorMessage = error.message;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
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

  @override
  Widget build(BuildContext context) {
    final fallbackChild = context
        .watch<ParentDashboardProvider>()
        .data
        ?.selectedChild;
    final child = _data?.child ?? fallbackChild;
    final selectedItems = _itemsForDate(
      _data?.items ?? const [],
      _selectedDate,
    );

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.dark,
        statusBarBrightness: Brightness.light,
        systemNavigationBarColor: Colors.white,
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
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 32),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  AttendanceHeader(child: child),
                  const SizedBox(height: 16),
                  if (_state == ViewState.loading && _data == null)
                    const _AttendanceStateCard.loading()
                  else if (_state == ViewState.error && _data == null)
                    _AttendanceStateCard(
                      title: 'Davomat yuklanmadi',
                      message: _errorMessage ?? 'Qayta urinib ko‘ring',
                      onPressed: () => _load(force: true),
                    )
                  else ...[
                    if (_state == ViewState.loading) ...[
                      const LinearProgressIndicator(
                        minHeight: 3,
                        color: AttendanceColors.primaryBlue,
                        backgroundColor: Color(0xFFEAF4FF),
                      ),
                      const SizedBox(height: 10),
                    ],
                    CalendarCard(
                      month: _month,
                      selectedDate: _selectedDate,
                      items: _data?.items ?? const [],
                      onPreviousMonth: () => _changeMonth(-1),
                      onNextMonth: () => _changeMonth(1),
                      onSelectDate: _selectDate,
                    ),
                    const SizedBox(height: 16),
                    SelectedDateCard(
                      selectedDate: _selectedDate,
                      lessonsCount: selectedItems.length,
                      status: _statusForItems(selectedItems),
                    ),
                    const SizedBox(height: 18),
                    LessonAttendanceList(items: selectedItems),
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

class AttendanceHeader extends StatelessWidget {
  const AttendanceHeader({super.key, this.child});

  final ParentChildModel? child;

  @override
  Widget build(BuildContext context) {
    final childLine = child == null
        ? 'Farzand tanlanmoqda'
        : _childGroupLine(child!);
    return Row(
      children: [
        _RoundIconButton(
          icon: Icons.arrow_back_rounded,
          iconSize: 26,
          onTap: () {},
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              FittedBox(
                fit: BoxFit.scaleDown,
                alignment: Alignment.centerLeft,
                child: Text(
                  'Davomat',
                  maxLines: 1,
                  style: AttendanceTextStyles.title.copyWith(fontSize: 23),
                ),
              ),
              const SizedBox(height: 4),
              Text(
                childLine,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AttendanceTextStyles.body.copyWith(
                  color: AttendanceColors.grayText,
                  fontSize: 14,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(width: 12),
        const _FilterButton(),
      ],
    );
  }
}

class CalendarCard extends StatelessWidget {
  const CalendarCard({
    super.key,
    required this.month,
    required this.selectedDate,
    required this.items,
    required this.onPreviousMonth,
    required this.onNextMonth,
    required this.onSelectDate,
  });

  final DateTime month;
  final DateTime selectedDate;
  final List<ParentAttendanceItemModel> items;
  final VoidCallback onPreviousMonth;
  final VoidCallback onNextMonth;
  final ValueChanged<DateTime> onSelectDate;

  static const List<String> _weekLabels = [
    'Du',
    'Se',
    'Ch',
    'Pa',
    'Ju',
    'Sh',
    'Ya',
  ];

  @override
  Widget build(BuildContext context) {
    final days = _calendarDays(month, selectedDate, items);
    return _AttendanceCard(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 14),
      borderRadius: 20,
      child: Column(
        children: [
          Row(
            children: [
              _MonthArrowButton(
                icon: Icons.chevron_left_rounded,
                onTap: onPreviousMonth,
              ),
              Expanded(
                child: Text(
                  _monthLabel(month),
                  textAlign: TextAlign.center,
                  style: AttendanceTextStyles.title.copyWith(fontSize: 21),
                ),
              ),
              _MonthArrowButton(
                icon: Icons.chevron_right_rounded,
                onTap: onNextMonth,
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              for (final label in _weekLabels)
                Expanded(
                  child: Text(
                    label,
                    textAlign: TextAlign.center,
                    style: AttendanceTextStyles.body.copyWith(
                      color: AttendanceColors.grayText,
                      fontSize: 13,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 10),
          GridView.builder(
            itemCount: days.length,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 7,
              crossAxisSpacing: 5,
              mainAxisSpacing: 7,
              childAspectRatio: 0.86,
            ),
            itemBuilder: (context, index) {
              final day = days[index];
              return CalendarDayCell(
                data: day,
                onTap: day.status == CalendarDayStatus.disabled
                    ? null
                    : () => onSelectDate(day.date),
              );
            },
          ),
          const SizedBox(height: 12),
          const CalendarLegend(),
        ],
      ),
    );
  }
}

class CalendarDayCell extends StatelessWidget {
  const CalendarDayCell({super.key, required this.data, this.onTap});

  final CalendarDayData data;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final colors = data.status.colors;
    return LayoutBuilder(
      builder: (context, constraints) {
        final markerSize = math
            .min(constraints.maxWidth, constraints.maxHeight - 11)
            .clamp(22.0, 34.0)
            .toDouble();
        return InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: onTap,
          child: Column(
            mainAxisAlignment: MainAxisAlignment.start,
            children: [
              Container(
                width: markerSize,
                height: markerSize,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: colors.background,
                  shape: data.status == CalendarDayStatus.selected
                      ? BoxShape.circle
                      : BoxShape.rectangle,
                  borderRadius: data.status == CalendarDayStatus.selected
                      ? null
                      : BorderRadius.circular(16),
                ),
                child: Text(
                  data.day,
                  style: AttendanceTextStyles.title.copyWith(
                    color: colors.foreground,
                    fontSize: 16,
                  ),
                ),
              ),
              const SizedBox(height: 3),
              Container(
                width: 6,
                height: 6,
                decoration: BoxDecoration(
                  color: data.dot ?? Colors.transparent,
                  shape: BoxShape.circle,
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class CalendarLegend extends StatelessWidget {
  const CalendarLegend({super.key});

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 14,
      runSpacing: 8,
      alignment: WrapAlignment.spaceBetween,
      children: const [
        _LegendItem(color: AttendanceColors.green, label: 'Kelgan'),
        _LegendItem(color: AttendanceColors.red, label: 'Kelmagan'),
        _LegendItem(color: Color(0xFF8B95A1), label: 'Ta’til / Dam olish'),
        _LegendItem(
          color: AttendanceColors.primaryBlue,
          label: 'Tanlangan sana',
        ),
      ],
    );
  }
}

class SelectedDateCard extends StatelessWidget {
  const SelectedDateCard({
    super.key,
    required this.selectedDate,
    required this.lessonsCount,
    required this.status,
  });

  final DateTime selectedDate;
  final int lessonsCount;
  final AttendanceStatus status;

  @override
  Widget build(BuildContext context) {
    return _AttendanceCard(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      borderRadius: 18,
      child: Row(
        children: [
          Container(
            width: 46,
            height: 46,
            decoration: BoxDecoration(
              color: const Color(0xFFE8F1FF),
              borderRadius: BorderRadius.circular(16),
            ),
            child: const Icon(
              Icons.event_available_outlined,
              color: AttendanceColors.primaryBlue,
              size: 25,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _fullDateLabel(selectedDate),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AttendanceTextStyles.title.copyWith(fontSize: 15.5),
                ),
                const SizedBox(height: 4),
                Text(
                  'Dars kuni: $lessonsCount ta',
                  style: AttendanceTextStyles.body.copyWith(
                    color: AttendanceColors.grayText,
                    fontSize: 13.5,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          StatusPill(status: status),
        ],
      ),
    );
  }
}

class LessonAttendanceList extends StatelessWidget {
  const LessonAttendanceList({super.key, required this.items});

  final List<ParentAttendanceItemModel> items;

  @override
  Widget build(BuildContext context) {
    final lessons = [
      for (var index = 0; index < items.length; index++)
        LessonAttendanceItem(
          index + 1,
          items[index].groupName.isEmpty ? 'Dars' : items[index].groupName,
          items[index].teacherName.isEmpty
              ? 'O‘qituvchi ko‘rsatilmagan'
              : items[index].teacherName,
          items[index].present
              ? AttendanceStatus.present
              : AttendanceStatus.absent,
        ),
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Darslar bo‘yicha davomat',
          style: AttendanceTextStyles.title.copyWith(fontSize: 18),
        ),
        const SizedBox(height: 12),
        _AttendanceCard(
          padding: EdgeInsets.zero,
          borderRadius: 20,
          child: Column(
            children: [
              if (lessons.isEmpty)
                Padding(
                  padding: const EdgeInsets.all(18),
                  child: Text(
                    'Tanlangan sana uchun dars topilmadi',
                    textAlign: TextAlign.center,
                    style: AttendanceTextStyles.body.copyWith(
                      color: AttendanceColors.grayText,
                      fontSize: 13.5,
                    ),
                  ),
                )
              else
                for (int index = 0; index < lessons.length; index++)
                  LessonAttendanceRow(
                    item: lessons[index],
                    showDivider: index != lessons.length - 1,
                  ),
            ],
          ),
        ),
      ],
    );
  }
}

class LessonAttendanceRow extends StatelessWidget {
  const LessonAttendanceRow({
    super.key,
    required this.item,
    required this.showDivider,
  });

  final LessonAttendanceItem item;
  final bool showDivider;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
          child: Row(
            children: [
              Container(
                width: 40,
                height: 40,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: const Color(0xFFF3F6FB),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Text(
                  '${item.number}',
                  style: AttendanceTextStyles.title.copyWith(
                    color: const Color(0xFF374151),
                    fontSize: 17,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      item.title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AttendanceTextStyles.title.copyWith(fontSize: 16),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      item.time,
                      style: AttendanceTextStyles.body.copyWith(
                        color: AttendanceColors.grayText,
                        fontSize: 13.5,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              StatusPill(status: item.status),
            ],
          ),
        ),
        if (showDivider)
          const Padding(
            padding: EdgeInsets.only(left: 70, right: 16),
            child: Divider(height: 1, color: AttendanceColors.border),
          ),
      ],
    );
  }
}

class StatusPill extends StatelessWidget {
  const StatusPill({super.key, required this.status});

  final AttendanceStatus status;

  @override
  Widget build(BuildContext context) {
    final isPresent = status == AttendanceStatus.present;
    final isEmpty = status == AttendanceStatus.none;
    return Container(
      constraints: const BoxConstraints(minWidth: 76),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: isEmpty
            ? const Color(0xFFF3F6FB)
            : isPresent
            ? const Color(0xFFE7F8EF)
            : const Color(0xFFFDE8E8),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Text(
        isEmpty
            ? 'Dars yo‘q'
            : isPresent
            ? 'Kelgan'
            : 'Kelmagan',
        maxLines: 1,
        style: AttendanceTextStyles.body.copyWith(
          color: isEmpty
              ? AttendanceColors.grayText
              : isPresent
              ? const Color(0xFF047857)
              : const Color(0xFFDC2626),
          fontSize: 13.5,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class ParentBottomNav extends StatelessWidget {
  const ParentBottomNav({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        boxShadow: AttendanceShadows.topNav,
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
            unselectedItemColor: AttendanceColors.grayText,
            iconSize: 24,
            selectedFontSize: 11.5,
            unselectedFontSize: 11.5,
            selectedLabelStyle: AttendanceTextStyles.label.copyWith(
              fontSize: 11.5,
            ),
            unselectedLabelStyle: AttendanceTextStyles.label.copyWith(
              fontSize: 11.5,
              fontWeight: FontWeight.w600,
            ),
            items: const [
              BottomNavigationBarItem(
                icon: Icon(Icons.home_rounded),
                label: 'Bosh sahifa',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.event_available_outlined),
                label: 'Davomat',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.account_balance_wallet_outlined),
                label: 'To‘lovlar',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.bar_chart_rounded),
                label: 'Yutuqlar',
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

class _AttendanceCard extends StatelessWidget {
  const _AttendanceCard({
    required this.child,
    required this.padding,
    required this.borderRadius,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final double borderRadius;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(borderRadius),
        border: Border.all(color: AttendanceColors.border),
        boxShadow: AttendanceShadows.card,
      ),
      child: child,
    );
  }
}

class _RoundIconButton extends StatelessWidget {
  const _RoundIconButton({
    required this.icon,
    required this.onTap,
    this.iconSize = 26,
  });

  final IconData icon;
  final VoidCallback onTap;
  final double iconSize;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      shape: const CircleBorder(),
      child: InkWell(
        onTap: onTap,
        customBorder: const CircleBorder(),
        child: Container(
          width: 46,
          height: 46,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: Colors.white,
            shape: BoxShape.circle,
            border: Border.all(color: AttendanceColors.border),
            boxShadow: AttendanceShadows.soft,
          ),
          child: Icon(icon, color: AttendanceColors.text, size: iconSize),
        ),
      ),
    );
  }
}

class _MonthArrowButton extends StatelessWidget {
  const _MonthArrowButton({required this.icon, required this.onTap});

  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(14),
      onTap: onTap,
      child: Container(
        width: 40,
        height: 40,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: const Color(0xFFF2F6FF),
          borderRadius: BorderRadius.circular(14),
        ),
        child: Icon(icon, color: AttendanceColors.primaryBlue, size: 26),
      ),
    );
  }
}

class _FilterButton extends StatelessWidget {
  const _FilterButton();

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        onTap: () {},
        borderRadius: BorderRadius.circular(20),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: AttendanceColors.border),
            boxShadow: AttendanceShadows.soft,
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.filter_list_rounded,
                color: AttendanceColors.primaryBlue,
                size: 22,
              ),
              const SizedBox(width: 7),
              Text(
                'Filter',
                style: AttendanceTextStyles.body.copyWith(
                  color: AttendanceColors.text,
                  fontSize: 14,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _LegendItem extends StatelessWidget {
  const _LegendItem({required this.color, required this.label});

  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 7),
        Text(
          label,
          style: AttendanceTextStyles.body.copyWith(
            color: AttendanceColors.grayText,
            fontSize: 12.5,
          ),
        ),
      ],
    );
  }
}

class _AttendanceStateCard extends StatelessWidget {
  const _AttendanceStateCard({
    required this.title,
    required this.message,
    this.onPressed,
  }) : loading = false;

  const _AttendanceStateCard.loading()
    : title = '',
      message = '',
      onPressed = null,
      loading = true;

  final String title;
  final String message;
  final VoidCallback? onPressed;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    return _AttendanceCard(
      padding: const EdgeInsets.fromLTRB(18, 36, 18, 36),
      borderRadius: 20,
      child: loading
          ? const SizedBox(
              height: 220,
              child: Center(
                child: CircularProgressIndicator(
                  color: AttendanceColors.primaryBlue,
                ),
              ),
            )
          : Column(
              children: [
                const Icon(
                  Icons.info_outline_rounded,
                  color: AttendanceColors.primaryBlue,
                  size: 40,
                ),
                const SizedBox(height: 12),
                Text(
                  title,
                  textAlign: TextAlign.center,
                  style: AttendanceTextStyles.title.copyWith(fontSize: 19),
                ),
                const SizedBox(height: 8),
                Text(
                  message,
                  textAlign: TextAlign.center,
                  style: AttendanceTextStyles.body.copyWith(
                    color: AttendanceColors.grayText,
                    fontSize: 14,
                  ),
                ),
                if (onPressed != null) ...[
                  const SizedBox(height: 16),
                  TextButton(
                    onPressed: onPressed,
                    style: TextButton.styleFrom(
                      backgroundColor: const Color(0xFFEAF4FF),
                      foregroundColor: AttendanceColors.primaryBlue,
                    ),
                    child: const Text('Qayta urinish'),
                  ),
                ],
              ],
            ),
    );
  }
}

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

bool _isSameDay(DateTime left, DateTime right) {
  return left.year == right.year &&
      left.month == right.month &&
      left.day == right.day;
}

AttendanceStatus _statusForItems(List<ParentAttendanceItemModel> items) {
  if (items.isEmpty) {
    return AttendanceStatus.none;
  }
  if (items.any((item) => !item.present)) {
    return AttendanceStatus.absent;
  }
  return AttendanceStatus.present;
}

List<CalendarDayData> _calendarDays(
  DateTime month,
  DateTime selectedDate,
  List<ParentAttendanceItemModel> items,
) {
  final firstDay = DateTime(month.year, month.month);
  final start = firstDay.subtract(Duration(days: firstDay.weekday - 1));
  return [
    for (var index = 0; index < 42; index++)
      _calendarDay(
        start.add(Duration(days: index)),
        month,
        selectedDate,
        items,
      ),
  ];
}

CalendarDayData _calendarDay(
  DateTime date,
  DateTime month,
  DateTime selectedDate,
  List<ParentAttendanceItemModel> items,
) {
  if (_isSameDay(date, selectedDate)) {
    return CalendarDayData(
      date,
      CalendarDayStatus.selected,
      dot: AttendanceColors.primaryBlue,
    );
  }
  if (date.month != month.month || date.year != month.year) {
    return CalendarDayData(date, CalendarDayStatus.disabled);
  }

  final dayItems = _itemsForDate(items, date);
  if (dayItems.isEmpty) {
    return CalendarDayData(date, CalendarDayStatus.rest);
  }
  if (dayItems.any((item) => !item.present)) {
    return CalendarDayData(
      date,
      CalendarDayStatus.absent,
      dot: AttendanceColors.red,
    );
  }
  return CalendarDayData(
    date,
    CalendarDayStatus.present,
    dot: AttendanceColors.green,
  );
}

String _monthLabel(DateTime date) {
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

String _fullDateLabel(DateTime date) {
  const weekdays = [
    'Dushanba',
    'Seshanba',
    'Chorshanba',
    'Payshanba',
    'Juma',
    'Shanba',
    'Yakshanba',
  ];
  return '${Formatters.shortDayMonth(date)}, ${weekdays[date.weekday - 1]}';
}

String _childGroupLine(ParentChildModel child) {
  final parts = <String>[
    if (child.fullName.trim().isNotEmpty) child.fullName.trim(),
    if (child.className.trim().isNotEmpty) child.className.trim(),
    if (child.groupName.trim().isNotEmpty) child.groupName.trim(),
  ];
  return parts.isEmpty ? 'Guruh biriktirilmagan' : parts.join(' • ');
}

class CalendarDayData {
  const CalendarDayData(this.date, this.status, {this.dot});

  final DateTime date;
  final CalendarDayStatus status;
  final Color? dot;

  String get day => '${date.day}';
}

class LessonAttendanceItem {
  const LessonAttendanceItem(this.number, this.title, this.time, this.status);

  final int number;
  final String title;
  final String time;
  final AttendanceStatus status;
}

enum CalendarDayStatus { disabled, rest, present, absent, selected }

enum AttendanceStatus { present, absent, none }

extension on CalendarDayStatus {
  _CalendarCellColors get colors {
    return switch (this) {
      CalendarDayStatus.disabled => const _CalendarCellColors(
        background: Colors.transparent,
        foreground: Color(0xFFC6CCD5),
      ),
      CalendarDayStatus.rest => const _CalendarCellColors(
        background: Colors.transparent,
        foreground: Color(0xFF6B7280),
      ),
      CalendarDayStatus.present => const _CalendarCellColors(
        background: Color(0xFFDDF8E9),
        foreground: Color(0xFF027A3E),
      ),
      CalendarDayStatus.absent => const _CalendarCellColors(
        background: Color(0xFFFFE2E2),
        foreground: Color(0xFFEF4444),
      ),
      CalendarDayStatus.selected => const _CalendarCellColors(
        background: AttendanceColors.primaryBlue,
        foreground: Colors.white,
      ),
    };
  }
}

class _CalendarCellColors {
  const _CalendarCellColors({
    required this.background,
    required this.foreground,
  });

  final Color background;
  final Color foreground;
}

class AttendanceColors {
  const AttendanceColors._();

  static const Color background = Color(0xFFF7FBFF);
  static const Color primaryBlue = Color(0xFF1E73F8);
  static const Color green = Color(0xFF10B981);
  static const Color red = Color(0xFFEF4444);
  static const Color grayText = Color(0xFF6B7280);
  static const Color text = Color(0xFF111827);
  static const Color border = Color(0xFFE5EAF2);
}

class AttendanceTextStyles {
  const AttendanceTextStyles._();

  static TextStyle get title {
    return GoogleFonts.inter(
      fontSize: 18,
      height: 1.16,
      fontWeight: FontWeight.w800,
      color: AttendanceColors.text,
      letterSpacing: 0,
    );
  }

  static TextStyle get body {
    return GoogleFonts.inter(
      fontSize: 15,
      height: 1.28,
      fontWeight: FontWeight.w500,
      color: AttendanceColors.text,
      letterSpacing: 0,
    );
  }

  static TextStyle get label {
    return GoogleFonts.inter(
      fontSize: 13,
      height: 1.16,
      fontWeight: FontWeight.w800,
      color: AttendanceColors.text,
      letterSpacing: 0,
    );
  }
}

class AttendanceShadows {
  const AttendanceShadows._();

  static const List<BoxShadow> soft = [
    BoxShadow(color: Color(0x0F0B1220), blurRadius: 18, offset: Offset(0, 8)),
  ];

  static const List<BoxShadow> card = [
    BoxShadow(color: Color(0x0D0B1220), blurRadius: 18, offset: Offset(0, 8)),
  ];

  static const List<BoxShadow> topNav = [
    BoxShadow(color: Color(0x140B1220), blurRadius: 24, offset: Offset(0, -8)),
  ];
}
