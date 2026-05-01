import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/parent_models.dart';
import 'package:chaqmoq_mobile/providers/parent_dashboard_provider.dart';
import 'package:chaqmoq_mobile/screens/parent/parent_ui.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/parent_dashboard_service.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

class ProgressScreen extends StatefulWidget {
  const ProgressScreen({super.key, this.showBottomNav = true});

  final bool showBottomNav;

  @override
  State<ProgressScreen> createState() => _ProgressScreenState();
}

class _ProgressScreenState extends State<ProgressScreen> {
  ParentProgressModel? _data;
  ViewState _state = ViewState.idle;
  String? _errorMessage;
  int? _loadedChildId;
  String? _selectedPeriod;

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

  Future<void> _load({bool force = false, String? period}) async {
    if (_state == ViewState.loading && !force) {
      return;
    }
    final requestedPeriod = (period ?? _selectedPeriod)?.trim();
    setState(() {
      _state = ViewState.loading;
      _errorMessage = null;
    });
    try {
      final data = await context.read<ParentDashboardService>().fetchProgress(
        childId: _loadedChildId,
        period: requestedPeriod?.isEmpty == true ? null : requestedPeriod,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _data = data;
        _selectedPeriod = data.selectedPeriod;
        _state = ViewState.success;
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
        _errorMessage = 'Progress ma’lumotlari yuklanmadi';
      });
    }
  }

  Future<void> _changePeriod(String periodKey) async {
    if (periodKey == _selectedPeriod && _data != null) {
      return;
    }
    await _load(force: true, period: periodKey);
  }

  @override
  Widget build(BuildContext context) {
    final fallbackChild = context
        .watch<ParentDashboardProvider>()
        .data
        ?.selectedChild;
    final child = _data?.child ?? fallbackChild;

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.dark,
        statusBarBrightness: Brightness.light,
        systemNavigationBarColor: Colors.white,
        systemNavigationBarIconBrightness: Brightness.dark,
      ),
      child: Scaffold(
        backgroundColor: ProgressColors.background,
        bottomNavigationBar: widget.showBottomNav
            ? const ParentBottomNav()
            : null,
        body: SafeArea(
          child: RefreshIndicator(
            color: ProgressColors.primaryBlue,
            onRefresh: () => _load(force: true),
            child: SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(
                parent: BouncingScrollPhysics(),
              ),
              padding: ParentUi.screenPadding,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  ProgressHeader(
                    child: child,
                    periodLabel:
                        _data?.selectedPeriodLabel ?? 'Joriy davr',
                    onSelectPeriod: () => _showPeriodMenu(context),
                  ),
                  const SizedBox(height: 14),
                  if (_state == ViewState.loading && _data == null)
                    const _ProgressStateCard.loading()
                  else if (_state == ViewState.error && _data == null)
                    _ProgressStateCard(
                      title: 'Progress yuklanmadi',
                      message: _errorMessage ?? 'Qayta urinib ko‘ring',
                      onPressed: () => _load(force: true),
                    )
                  else ...[
                    if (_state == ViewState.loading) ...[
                      const LinearProgressIndicator(
                        minHeight: 3,
                        color: ProgressColors.primaryBlue,
                        backgroundColor: Color(0xFFEAF4FF),
                      ),
                      const SizedBox(height: 8),
                    ],
                    _OverviewCard(data: _data),
                    const SizedBox(height: 12),
                    _BreakdownCard(data: _data),
                    const SizedBox(height: 12),
                    _QuickStatsRow(data: _data),
                    const SizedBox(height: 12),
                    _RecentActivityList(timeline: _data?.progressTimeline),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _showPeriodMenu(BuildContext anchorContext) async {
    final periods = _data?.availablePeriods ?? const <ParentProgressPeriodModel>[];
    if (periods.isEmpty) {
      return;
    }
    final selected = await showModalBottomSheet<String>(
      context: anchorContext,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) {
        return _ProgressBottomSheet(
          title: 'Davrni tanlang',
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (final period in periods)
                _PeriodOptionTile(
                  label: period.label,
                  selected: period.key == (_selectedPeriod ?? _data?.selectedPeriod),
                  onTap: () => Navigator.of(sheetContext).pop(period.key),
                ),
            ],
          ),
        );
      },
    );
    if (!mounted || selected == null) {
      return;
    }
    await _changePeriod(selected);
  }
}

// =====================================================================
// Simplified parent-facing progress widgets
// =====================================================================

Color _colorForLevelLabel(String label) {
  switch (label) {
    case 'Yaxshi':
      return ProgressColors.green;
    case 'O‘rtacha':
      return ProgressColors.orange;
    case 'E’tibor kerak':
      return const Color(0xFFEF4444);
    default:
      return ProgressColors.secondaryText;
  }
}

({String label, Color color, IconData icon}) _trendMeta(String trend) {
  switch (trend) {
    case 'yaxshilandi':
      return (
        label: 'Oxirgi 30 kunda yaxshilandi',
        color: ProgressColors.green,
        icon: Icons.trending_up_rounded,
      );
    case 'pasaydi':
      return (
        label: 'Pasaydi',
        color: const Color(0xFFEF4444),
        icon: Icons.trending_down_rounded,
      );
    case 'barqaror':
      return (
        label: 'Barqaror',
        color: ProgressColors.primaryBlue,
        icon: Icons.trending_flat_rounded,
      );
    default:
      return (
        label: 'Ma’lumot kutilmoqda',
        color: ProgressColors.secondaryText,
        icon: Icons.timelapse_rounded,
      );
  }
}

void _showInsightInfoSheet(BuildContext context) {
  showModalBottomSheet<void>(
    context: context,
    backgroundColor: Colors.transparent,
    isScrollControlled: false,
    builder: (sheetContext) => _ProgressBottomSheet(
      title: 'Natija qanday hisoblanadi?',
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Natija oxirgi 30 kun asosida hisoblangan.',
              style: ProgressTextStyles.body.copyWith(
                color: ProgressColors.text,
                fontSize: 14,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 10),
            Text(
              'Davomat (max 2 ball), Vazifalar (max 1 ball) va Faollik '
              '(max 2 ball) — jami 5 ballgacha jamlanadi.',
              style: ProgressTextStyles.body.copyWith(
                color: ProgressColors.secondaryText,
                fontSize: 13,
                height: 1.4,
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

class _OverviewCard extends StatelessWidget {
  const _OverviewCard({required this.data});

  final ParentProgressModel? data;

  @override
  Widget build(BuildContext context) {
    final score = data?.currentLevel ?? 0;
    final maxLevel = data?.maxLevel ?? 5;
    final levelLabel = (data?.levelLabel ?? '').isNotEmpty
        ? data!.levelLabel
        : '—';
    final levelColor = _colorForLevelLabel(levelLabel);
    final trend = _trendMeta(data?.trend ?? '');
    final scoreText = score == 0 ? '—' : score.toStringAsFixed(1);

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: ProgressShadows.card,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'Farzandingizning natijasi',
                  style: ProgressTextStyles.title.copyWith(fontSize: 16),
                ),
              ),
              InkWell(
                onTap: () => _showInsightInfoSheet(context),
                customBorder: const CircleBorder(),
                child: const Padding(
                  padding: EdgeInsets.all(4),
                  child: Icon(
                    Icons.info_outline_rounded,
                    size: 18,
                    color: ProgressColors.secondaryText,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 6,
                ),
                decoration: BoxDecoration(
                  color: levelColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  levelLabel,
                  style: ProgressTextStyles.label.copyWith(
                    color: levelColor,
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              const Spacer(),
              Text.rich(
                TextSpan(
                  children: [
                    TextSpan(
                      text: scoreText,
                      style: GoogleFonts.inter(
                        fontSize: 26,
                        fontWeight: FontWeight.w800,
                        color: ProgressColors.text,
                        letterSpacing: -0.4,
                      ),
                    ),
                    TextSpan(
                      text: ' / ${maxLevel.toStringAsFixed(0)}',
                      style: GoogleFonts.inter(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: ProgressColors.secondaryText,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          _LevelProgressBar(score: score, color: levelColor),
          const SizedBox(height: 4),
          Text(
            'Umumiy daraja',
            style: ProgressTextStyles.body.copyWith(
              color: ProgressColors.secondaryText,
              fontSize: 12,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Icon(trend.icon, size: 16, color: trend.color),
              const SizedBox(width: 6),
              Flexible(
                child: Text(
                  trend.label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: ProgressTextStyles.body.copyWith(
                    color: trend.color,
                    fontWeight: FontWeight.w700,
                    fontSize: 13,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            'Oxirgi 30 kun asosida',
            style: ProgressTextStyles.body.copyWith(
              color: ProgressColors.secondaryText,
              fontSize: 11.5,
            ),
          ),
        ],
      ),
    );
  }
}

class _BreakdownCard extends StatelessWidget {
  const _BreakdownCard({required this.data});

  final ParentProgressModel? data;

  String _formatScore(double score) {
    if (score == score.roundToDouble()) {
      return score.toStringAsFixed(0);
    }
    return score.toStringAsFixed(1);
  }

  Color _colorForScore(double score) {
    if (score >= 1.5) return ProgressColors.green;
    if (score >= 0.5) return ProgressColors.orange;
    if (score > 0) return const Color(0xFFEF4444);
    return ProgressColors.secondaryText;
  }

  @override
  Widget build(BuildContext context) {
    final breakdown = data?.breakdown ?? const <ProgressBreakdownItem>[];
    final hasData = (data?.hasBreakdownData ?? false) && breakdown.isNotEmpty;
    final total = data?.currentLevel ?? 0;
    final maxLevel = data?.maxLevel ?? 5;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: ProgressShadows.card,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.insights_rounded,
                size: 18,
                color: ProgressColors.primaryBlue,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Natija nimaga asoslangan?',
                  style: ProgressTextStyles.title.copyWith(fontSize: 15),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (!hasData)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Text(
                'Ma’lumot yetarli emas',
                style: ProgressTextStyles.body.copyWith(
                  color: ProgressColors.secondaryText,
                  fontSize: 13,
                ),
              ),
            )
          else ...[
            for (var i = 0; i < breakdown.length; i++) ...[
              if (i > 0) const Divider(height: 1, color: ProgressColors.border),
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 10),
                child: Row(
                  children: [
                    Expanded(
                      flex: 5,
                      child: Text(
                        breakdown[i].label,
                        style: ProgressTextStyles.body.copyWith(
                          color: ProgressColors.text,
                          fontSize: 13.5,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    Expanded(
                      flex: 4,
                      child: Text(
                        breakdown[i].value,
                        textAlign: TextAlign.center,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: ProgressTextStyles.body.copyWith(
                          color: ProgressColors.secondaryText,
                          fontSize: 13,
                        ),
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 10,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: _colorForScore(breakdown[i].score)
                            .withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Text(
                        '+${_formatScore(breakdown[i].score)}',
                        style: ProgressTextStyles.label.copyWith(
                          color: _colorForScore(breakdown[i].score),
                          fontSize: 12.5,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
            const Divider(height: 1, color: ProgressColors.border),
            Padding(
              padding: const EdgeInsets.only(top: 10),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      'Jami',
                      style: ProgressTextStyles.title.copyWith(
                        color: ProgressColors.text,
                        fontSize: 14,
                      ),
                    ),
                  ),
                  Text(
                    '${_formatScore(total)} / ${maxLevel.toStringAsFixed(0)} ball',
                    style: ProgressTextStyles.title.copyWith(
                      color: ProgressColors.primaryBlue,
                      fontSize: 14,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _LevelProgressBar extends StatelessWidget {
  const _LevelProgressBar({required this.score, required this.color});

  final double score;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final ratio = (score / 5).clamp(0.0, 1.0).toDouble();
    return Stack(
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(999),
          child: LinearProgressIndicator(
            value: ratio,
            minHeight: 12,
            backgroundColor: const Color(0xFFEFF2F6),
            valueColor: AlwaysStoppedAnimation<Color>(color),
          ),
        ),
        Positioned.fill(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                for (var i = 0; i <= 5; i++)
                  Container(
                    width: 2,
                    height: 12,
                    color: i == 0 || i == 5
                        ? Colors.transparent
                        : Colors.white.withValues(alpha: 0.55),
                  ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _QuickStatsRow extends StatelessWidget {
  const _QuickStatsRow({required this.data});

  final ParentProgressModel? data;

  int _homeworkPercent() {
    final points = data?.progressTimeline.points ?? const <ProgressTimelinePoint>[];
    if (points.isEmpty) return 0;
    final activeDays = points
        .where((p) => p.score != 0 || p.reasons.isNotEmpty)
        .length;
    if (activeDays == 0) return 0;
    final homeworkDays = points
        .where(
          (p) => p.reasons.any(
            (r) => r.toLowerCase().contains('vazifa'),
          ),
        )
        .length;
    return ((homeworkDays / activeDays) * 100).round().clamp(0, 100);
  }

  Color _statColor(int percent) {
    if (percent >= 75) return ProgressColors.green;
    if (percent >= 50) return ProgressColors.orange;
    if (percent > 0) return const Color(0xFFEF4444);
    return ProgressColors.secondaryText;
  }

  @override
  Widget build(BuildContext context) {
    final attendance = data?.attendancePercent ?? 0;
    final homework = _homeworkPercent();
    return Row(
      children: [
        Expanded(
          child: _StatPill(
            icon: Icons.event_available_rounded,
            title: 'Davomat',
            value: data == null ? '—' : '$attendance%',
            color: _statColor(attendance),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: _StatPill(
            icon: Icons.menu_book_rounded,
            title: 'Vazifalar',
            value: data == null ? '—' : '$homework% bajarilgan',
            color: _statColor(homework),
          ),
        ),
      ],
    );
  }
}

class _StatPill extends StatelessWidget {
  const _StatPill({
    required this.icon,
    required this.title,
    required this.value,
    required this.color,
  });

  final IconData icon;
  final String title;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: ProgressShadows.card,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Container(
                width: 28,
                height: 28,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(icon, size: 16, color: color),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: ProgressTextStyles.body.copyWith(
                    color: ProgressColors.secondaryText,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(
              value,
              maxLines: 1,
              style: ProgressTextStyles.title.copyWith(
                color: color,
                fontSize: 16,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _RecentActivityList extends StatelessWidget {
  const _RecentActivityList({required this.timeline});

  final ProgressTimelineModel? timeline;

  List<({String label, IconData icon, Color color, DateTime? date})>
  _buildItems() {
    final result =
        <({String label, IconData icon, Color color, DateTime? date})>[];
    final points = timeline?.points ?? const <ProgressTimelinePoint>[];
    for (final point in points.reversed) {
      if (point.score == 0 && point.reasons.isEmpty) continue;
      final date = point.parsedDate;
      if (point.reasons.isEmpty) {
        result.add((
          label: point.score >= 0 ? 'Yaxshi natija' : 'E’tibor kerak',
          icon: point.score >= 0
              ? Icons.check_circle_rounded
              : Icons.cancel_rounded,
          color: point.score >= 0
              ? ProgressColors.green
              : const Color(0xFFEF4444),
          date: date,
        ));
      } else {
        for (final reason in point.reasons) {
          result.add(_metaForReason(reason, point.score, date));
        }
      }
      if (result.length >= 5) break;
    }
    return result.take(5).toList();
  }

  ({String label, IconData icon, Color color, DateTime? date}) _metaForReason(
    String reason,
    int score,
    DateTime? date,
  ) {
    final lower = reason.toLowerCase();
    if (lower.contains('vazifa')) {
      return (
        label: reason,
        icon: Icons.menu_book_rounded,
        color: ProgressColors.primaryBlue,
        date: date,
      );
    }
    if (lower.contains('faol')) {
      return (
        label: reason,
        icon: Icons.star_rounded,
        color: ProgressColors.orange,
        date: date,
      );
    }
    if (lower.contains('test')) {
      return (
        label: reason,
        icon: Icons.assignment_turned_in_rounded,
        color: ProgressColors.purple,
        date: date,
      );
    }
    if (lower.contains('kelmadi') || lower.contains('qoldir')) {
      return (
        label: reason,
        icon: Icons.cancel_rounded,
        color: const Color(0xFFEF4444),
        date: date,
      );
    }
    if (score >= 0) {
      return (
        label: reason,
        icon: Icons.check_circle_rounded,
        color: ProgressColors.green,
        date: date,
      );
    }
    return (
      label: reason,
      icon: Icons.cancel_rounded,
      color: const Color(0xFFEF4444),
      date: date,
    );
  }

  static String _shortDate(DateTime? date) {
    if (date == null) return '';
    return DateFormat('d MMM', 'uz').format(date);
  }

  @override
  Widget build(BuildContext context) {
    final items = _buildItems();
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: ProgressShadows.card,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Oxirgi faoliyat',
            style: ProgressTextStyles.title.copyWith(fontSize: 15),
          ),
          const SizedBox(height: 12),
          if (items.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Progress ma’lumotlari hali mavjud emas',
                    style: ProgressTextStyles.body.copyWith(
                      color: ProgressColors.text,
                      fontSize: 13.5,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'O‘qituvchi hali ma’lumot kiritmagan',
                    style: ProgressTextStyles.body.copyWith(
                      color: ProgressColors.secondaryText,
                      fontSize: 12.5,
                    ),
                  ),
                ],
              ),
            )
          else
            for (var i = 0; i < items.length; i++) ...[
              if (i > 0) const Divider(height: 1, color: ProgressColors.border),
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 10),
                child: Row(
                  children: [
                    Container(
                      width: 34,
                      height: 34,
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        color: items[i].color.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Icon(items[i].icon, size: 18, color: items[i].color),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        items[i].label,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: ProgressTextStyles.body.copyWith(
                          color: ProgressColors.text,
                          fontSize: 13.5,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      _shortDate(items[i].date),
                      style: ProgressTextStyles.body.copyWith(
                        color: ProgressColors.secondaryText,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
            ],
        ],
      ),
    );
  }
}

String _childGroupLine(ParentChildModel child) {
  final parts = <String>[];
  final groupName = child.groupName.trim();
  final className = child.className.trim();
  if (groupName.isNotEmpty) parts.add(groupName);
  if (className.isNotEmpty && className != groupName) parts.add(className);
  return parts.isEmpty ? 'Guruh biriktirilmagan' : parts.join(' • ');
}

class ProgressHeader extends StatelessWidget {
  const ProgressHeader({
    super.key,
    this.child,
    required this.periodLabel,
    required this.onSelectPeriod,
  });

  final ParentChildModel? child;
  final String periodLabel;
  final VoidCallback onSelectPeriod;

  @override
  Widget build(BuildContext context) {
    final childLine = child == null
        ? 'Farzand tanlanmoqda'
        : _childGroupLine(child!);
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 6,
                ),
                decoration: BoxDecoration(
                  color: const Color(0xFFEAF4FF),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  'Ota-ona paneli',
                  style: ProgressTextStyles.label.copyWith(
                    color: ProgressColors.primaryBlue,
                    fontSize: 11.5,
                  ),
                ),
              ),
              const SizedBox(height: 10),
              Text(
                'O‘zlashtirish',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: ProgressTextStyles.title.copyWith(fontSize: 22),
              ),
              const SizedBox(height: 5),
              Text(
                childLine,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: ProgressTextStyles.body.copyWith(
                  color: ProgressColors.secondaryText,
                  fontSize: 14,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(width: 8),
        _TermDropdownButton(
          label: periodLabel,
          onTap: onSelectPeriod,
        ),
      ],
    );
  }
}

class _ProgressBottomSheet extends StatelessWidget {
  const _ProgressBottomSheet({
    required this.title,
    required this.child,
  });

  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Container(
        margin: const EdgeInsets.all(12),
        padding: const EdgeInsets.fromLTRB(18, 12, 18, 18),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(24),
          boxShadow: ProgressShadows.card,
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 44,
                  height: 5,
                  margin: const EdgeInsets.only(bottom: 16),
                  decoration: BoxDecoration(
                    color: const Color(0xFFD8E0EC),
                    borderRadius: BorderRadius.circular(999),
                  ),
                ),
              ),
              Text(
                title,
                style: ProgressTextStyles.title.copyWith(fontSize: 18),
              ),
              const SizedBox(height: 14),
              child,
            ],
          ),
        ),
      ),
    );
  }
}

class _PeriodOptionTile extends StatelessWidget {
  const _PeriodOptionTile({
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
      borderRadius: BorderRadius.circular(16),
      onTap: onTap,
      child: Container(
        width: double.infinity,
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        decoration: BoxDecoration(
          color: selected ? const Color(0xFFEAF4FF) : Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: selected
                ? ProgressColors.primaryBlue
                : ProgressColors.border,
          ),
        ),
        child: Row(
          children: [
            Expanded(
              child: Text(
                label,
                style: ProgressTextStyles.body.copyWith(
                  color: ProgressColors.text,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
            Icon(
              selected
                  ? Icons.check_circle_rounded
                  : Icons.chevron_right_rounded,
              color: selected
                  ? ProgressColors.primaryBlue
                  : const Color(0xFF9AA4B2),
            ),
          ],
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
        boxShadow: ProgressShadows.topNav,
      ),
      child: SafeArea(
        top: false,
        child: ClipRRect(
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
          child: BottomNavigationBar(
            currentIndex: 3,
            onTap: (_) {},
            type: BottomNavigationBarType.fixed,
            backgroundColor: Colors.white,
            elevation: 0,
            iconSize: 24,
            selectedItemColor: ProgressColors.primaryBlue,
            unselectedItemColor: ProgressColors.secondaryText,
            selectedLabelStyle: ProgressTextStyles.label.copyWith(
              fontSize: 11,
            ),
            unselectedLabelStyle: ProgressTextStyles.label.copyWith(
              fontSize: 11,
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

class _TermDropdownButton extends StatelessWidget {
  const _TermDropdownButton({
    required this.label,
    required this.onTap,
  });

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return TextButton(
      onPressed: onTap,
      style: TextButton.styleFrom(
        backgroundColor: Colors.white,
        foregroundColor: ProgressColors.secondaryText,
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(ParentUi.cardRadius),
          side: const BorderSide(color: ProgressColors.border),
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.event_available_outlined, size: 19),
          const SizedBox(width: 6),
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: ProgressTextStyles.body.copyWith(
              color: const Color(0xFF374151),
              fontSize: 12.8,
            ),
          ),
          const SizedBox(width: 4),
          const Icon(Icons.keyboard_arrow_down_rounded, size: 18),
        ],
      ),
    );
  }
}

class _ProgressStateCard extends StatelessWidget {
  const _ProgressStateCard({
    required this.title,
    required this.message,
    this.onPressed,
  }) : loading = false;

  const _ProgressStateCard.loading()
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
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(18, 36, 18, 36),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: ProgressShadows.card,
      ),
      child: loading
          ? const SizedBox(
              height: 220,
              child: Center(
                child: CircularProgressIndicator(
                  color: ProgressColors.primaryBlue,
                ),
              ),
            )
          : Column(
              children: [
                const Icon(
                  Icons.info_outline_rounded,
                  color: ProgressColors.primaryBlue,
                  size: 40,
                ),
                const SizedBox(height: 12),
                Text(
                  title,
                  textAlign: TextAlign.center,
                  style: ProgressTextStyles.title.copyWith(fontSize: 19),
                ),
                const SizedBox(height: 8),
                Text(
                  message,
                  textAlign: TextAlign.center,
                  style: ProgressTextStyles.body.copyWith(
                    color: ProgressColors.secondaryText,
                    fontSize: 14,
                  ),
                ),
                if (onPressed != null) ...[
                  const SizedBox(height: 16),
                  TextButton(
                    onPressed: onPressed,
                    style: TextButton.styleFrom(
                      backgroundColor: const Color(0xFFEAF4FF),
                      foregroundColor: ProgressColors.primaryBlue,
                    ),
                    child: const Text('Qayta urinish'),
                  ),
                ],
              ],
            ),
    );
  }
}

class ProgressColors {
  const ProgressColors._();

  static const Color background = Color(0xFFF7FBFF);
  static const Color primaryBlue = Color(0xFF1E73F8);
  static const Color green = Color(0xFF10B981);
  static const Color orange = Color(0xFFF59E0B);
  static const Color purple = Color(0xFF7C3AED);
  static const Color pink = Color(0xFFEC4899);
  static const Color text = Color(0xFF111827);
  static const Color secondaryText = Color(0xFF6B7280);
  static const Color border = Color(0xFFE5EAF2);
}

class ProgressTextStyles {
  const ProgressTextStyles._();

  static TextStyle get title {
    return GoogleFonts.inter(
      fontSize: 17,
      height: 1.16,
      fontWeight: FontWeight.w800,
      color: ProgressColors.text,
      letterSpacing: 0,
    );
  }

  static TextStyle get body {
    return GoogleFonts.inter(
      fontSize: 14,
      height: 1.28,
      fontWeight: FontWeight.w500,
      color: ProgressColors.text,
      letterSpacing: 0,
    );
  }

  static TextStyle get label {
    return GoogleFonts.inter(
      fontSize: 12.5,
      height: 1.16,
      fontWeight: FontWeight.w800,
      color: ProgressColors.text,
      letterSpacing: 0,
    );
  }

  static TextStyle get link {
    return GoogleFonts.inter(
      fontSize: 14,
      height: 1.16,
      fontWeight: FontWeight.w800,
      color: ProgressColors.primaryBlue,
      letterSpacing: 0,
    );
  }
}

class ProgressShadows {
  const ProgressShadows._();

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
