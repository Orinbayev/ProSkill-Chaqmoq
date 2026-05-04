import 'dart:math' as math;

import 'package:chaqmoq_mobile/core/theme/parent_colors.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/parent_models.dart';
import 'package:chaqmoq_mobile/providers/parent_dashboard_provider.dart';
import 'package:chaqmoq_mobile/screens/parent/parent_ui.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/parent_dashboard_service.dart';
import 'package:chaqmoq_mobile/widgets/adaptive_avatar.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
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

  String _currentMonthLabel() {
    const months = <String>[
      'Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun',
      'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr',
    ];
    final now = DateTime.now();
    return '${months[now.month - 1]} ${now.year}';
  }

  @override
  Widget build(BuildContext context) {
    ParentColors.update(Theme.of(context).brightness);
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
                    _ProgressHeroCard(
                      child: child,
                      data: _data,
                      periodLabel: _currentMonthLabel(),
                      onSelectPeriod: () {},
                    ),
                    const SizedBox(height: 12),
                    _BreakdownCard(data: _data),
                    const SizedBox(height: 12),
                    _RecentActivityList(
                      timeline: _data?.progressTimeline,
                      totalChaqmoq: _data?.totalChaqmoq ?? 0,
                      currentPeriod: _selectedPeriod ?? _data?.selectedPeriod,
                      onChangePeriod: _changePeriod,
                    ),
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

// =====================================================================
// Simplified parent-facing progress widgets
// =====================================================================

({String label, Color color, IconData icon}) _trendMeta(String trend) {
  switch (trend) {
    case 'yaxshilandi':
      return (
        label: 'Yaxshilandi',
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

class _ProgressHeroCard extends StatelessWidget {
  const _ProgressHeroCard({
    required this.child,
    required this.data,
    required this.periodLabel,
    required this.onSelectPeriod,
  });

  final ParentChildModel? child;
  final ParentProgressModel? data;
  final String periodLabel;
  final VoidCallback onSelectPeriod;

  @override
  Widget build(BuildContext context) {
    final hasMin = data?.hasMinimumData ?? false;
    final score = data?.currentLevel ?? 0;
    final maxLevel = data?.maxLevel ?? 5;
    final rawLabel = (data?.levelLabel ?? '').trim();
    final levelLabel = hasMin
        ? (rawLabel.isNotEmpty ? rawLabel : '—')
        : 'Kutilmoqda';
    final trend = _trendMeta(data?.trend ?? '');
    final scoreText = hasMin ? score.toStringAsFixed(1) : '—';

    final childName = child?.fullName.trim().isNotEmpty == true
        ? child!.fullName
        : 'Farzand tanlanmoqda';
    final groupParts = <String>[
      if (child?.className.trim().isNotEmpty == true) child!.className.trim(),
      if (child?.groupName.trim().isNotEmpty == true) child!.groupName.trim(),
    ];
    final groupLine =
        groupParts.isEmpty ? 'Guruh biriktirilmagan' : groupParts.join(' · ');

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(16, 14, 14, 16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: <Color>[Color(0xFF1E73F8), Color(0xFF4F8FFA)],
        ),
        boxShadow: const <BoxShadow>[
          BoxShadow(
            color: Color(0x331E73F8),
            blurRadius: 22,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 5,
                ),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.18),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  'O‘zlashtirish',
                  style: ProgressTextStyles.label.copyWith(
                    color: Colors.white,
                    fontSize: 11,
                  ),
                ),
              ),
              const Spacer(),
              InkWell(
                onTap: () => _showInsightInfoSheet(context),
                customBorder: const CircleBorder(),
                child: Container(
                  width: 30,
                  height: 30,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.18),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(
                    Icons.info_outline_rounded,
                    color: Colors.white,
                    size: 15,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Container(
                width: 38,
                height: 38,
                clipBehavior: Clip.antiAlias,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: Colors.white.withValues(alpha: 0.18),
                  border: Border.all(
                    color: Colors.white.withValues(alpha: 0.45),
                  ),
                ),
                child: AdaptiveAvatar(
                  name: childName,
                  imageUrl: child?.avatarUrl ?? '',
                  size: 38,
                  icon: Icons.school_outlined,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      childName,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: ProgressTextStyles.title.copyWith(
                        color: Colors.white,
                        fontSize: 14.5,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      groupLine,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: ProgressTextStyles.body.copyWith(
                        color: const Color(0xFFE0EBFF),
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              SizedBox(
                width: 110,
                height: 110,
                child: _ScoreGauge(
                  value: hasMin ? score : 0,
                  maxValue: maxLevel,
                  centerText: scoreText,
                  bottomText: '/ ${maxLevel.toStringAsFixed(0)} ball',
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 10,
                        vertical: 5,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.22),
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Text(
                        levelLabel,
                        style: ProgressTextStyles.label.copyWith(
                          color: Colors.white,
                          fontSize: 11.5,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                    const SizedBox(height: 10),
                    if (!hasMin)
                      Text(
                        'Bu davrda hali faoliyat ma’lumotlari yo‘q.',
                        style: ProgressTextStyles.body.copyWith(
                          color: const Color(0xFFE0EBFF),
                          fontSize: 11.5,
                          height: 1.35,
                        ),
                      )
                    else ...[
                      Row(
                        children: [
                          Icon(trend.icon, size: 15, color: Colors.white),
                          const SizedBox(width: 6),
                          Flexible(
                            child: Text(
                              trend.label,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: ProgressTextStyles.body.copyWith(
                                color: Colors.white,
                                fontWeight: FontWeight.w700,
                                fontSize: 12,
                                height: 1.3,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '$periodLabel asosida',
                        style: ProgressTextStyles.body.copyWith(
                          color: const Color(0xFFC2DDFF),
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}


class _ScoreGauge extends StatelessWidget {
  const _ScoreGauge({
    required this.value,
    required this.maxValue,
    required this.centerText,
    required this.bottomText,
  });

  final double value;
  final double maxValue;
  final String centerText;
  final String bottomText;

  @override
  Widget build(BuildContext context) {
    final ratio = maxValue <= 0
        ? 0.0
        : (value / maxValue).clamp(0.0, 1.0).toDouble();
    return CustomPaint(
      painter: _GaugePainter(progress: ratio),
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              centerText,
              style: GoogleFonts.inter(
                fontSize: 26,
                fontWeight: FontWeight.w800,
                color: Colors.white,
                letterSpacing: -0.4,
                height: 1,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              bottomText,
              style: GoogleFonts.inter(
                fontSize: 10.5,
                fontWeight: FontWeight.w600,
                color: const Color(0xFFC2DDFF),
                height: 1,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _GaugePainter extends CustomPainter {
  _GaugePainter({required this.progress});

  final double progress;

  @override
  void paint(Canvas canvas, Size size) {
    final stroke = 8.0;
    final center = Offset(size.width / 2, size.height / 2);
    final radius = (size.shortestSide / 2) - (stroke / 2);
    final rect = Rect.fromCircle(center: center, radius: radius);

    final track = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round
      ..color = Colors.white.withValues(alpha: 0.22);
    canvas.drawArc(rect, 0, math.pi * 2, false, track);

    if (progress <= 0) return;

    final arc = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round
      ..color = Colors.white;
    final start = -math.pi / 2;
    final sweep = math.pi * 2 * progress;
    canvas.drawArc(rect, start, sweep, false, arc);
  }

  @override
  bool shouldRepaint(covariant _GaugePainter oldDelegate) {
    return oldDelegate.progress != progress;
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

  Color _colorForRatio(double ratio) {
    if (ratio >= 0.75) return ProgressColors.green;
    if (ratio >= 0.4) return ProgressColors.orange;
    if (ratio > 0) return const Color(0xFFEF4444);
    return ProgressColors.secondaryText;
  }

  @override
  Widget build(BuildContext context) {
    final breakdown = data?.breakdown ?? const <ProgressBreakdownItem>[];
    final total = data?.currentLevel ?? 0;
    final maxLevel = data?.maxLevel ?? 5;
    final hasMin = data?.hasMinimumData ?? false;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        boxShadow: ProgressShadows.card,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.insights_rounded,
                size: 16,
                color: ProgressColors.primaryBlue,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Natija nimaga asoslangan?',
                  style: ProgressTextStyles.title.copyWith(fontSize: 13.5),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          if (!hasMin || breakdown.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Text(
                'Bu davrda hali faoliyat ma’lumotlari yo‘q.',
                style: ProgressTextStyles.body.copyWith(
                  color: ProgressColors.secondaryText,
                  fontSize: 12.5,
                  height: 1.35,
                ),
              ),
            )
          else ...[
            for (var i = 0; i < breakdown.length; i++) ...[
              if (i > 0) const SizedBox(height: 8),
              _BreakdownRow(
                item: breakdown[i],
                color: _colorForRatio(
                  breakdown[i].maxScore > 0
                      ? breakdown[i].score / breakdown[i].maxScore
                      : 0,
                ),
                formatScore: _formatScore,
              ),
            ],
            const SizedBox(height: 10),
            Divider(height: 1, color: ProgressColors.border),
            Padding(
              padding: const EdgeInsets.only(top: 10),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      'Jami',
                      style: ProgressTextStyles.title.copyWith(
                        color: ProgressColors.text,
                        fontSize: 12.5,
                      ),
                    ),
                  ),
                  Text(
                    '${_formatScore(total)} / ${maxLevel.toStringAsFixed(0)} ball',
                    style: ProgressTextStyles.title.copyWith(
                      color: ProgressColors.primaryBlue,
                      fontSize: 12.5,
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

class _BreakdownRow extends StatelessWidget {
  const _BreakdownRow({
    required this.item,
    required this.color,
    required this.formatScore,
  });

  final ProgressBreakdownItem item;
  final Color color;
  final String Function(double) formatScore;

  @override
  Widget build(BuildContext context) {
    final hasValue = item.hasValue;
    final ratio = item.maxScore > 0
        ? (item.score / item.maxScore).clamp(0.0, 1.0).toDouble()
        : 0.0;
    final scoreText = '+${formatScore(item.score)} ball';
    final pillColor = hasValue ? color : ProgressColors.secondaryText;
    return Container(
      padding: const EdgeInsets.fromLTRB(10, 8, 10, 10),
      decoration: BoxDecoration(
        color: const Color(0xFFFAFBFC),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  item.title.isNotEmpty ? item.title : item.label,
                  style: ProgressTextStyles.body.copyWith(
                    color: ProgressColors.text,
                    fontSize: 12.5,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              Text(
                hasValue ? item.value : '—',
                style: ProgressTextStyles.body.copyWith(
                  color: ProgressColors.secondaryText,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 8,
                  vertical: 3,
                ),
                decoration: BoxDecoration(
                  color: pillColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  scoreText,
                  style: ProgressTextStyles.label.copyWith(
                    color: pillColor,
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              value: ratio,
              minHeight: 5,
              backgroundColor: const Color(0xFFEFF2F6),
              valueColor: AlwaysStoppedAnimation<Color>(pillColor),
            ),
          ),
        ],
      ),
    );
  }
}


enum _ReasonKind { attendance, attendanceMissed, homework, test, activity, other }

class _ReasonMeta {
  const _ReasonMeta({
    required this.label,
    required this.icon,
    required this.color,
    required this.kind,
  });

  final String label;
  final IconData icon;
  final Color color;
  final _ReasonKind kind;
}

_ReasonMeta _classifyReason(String reason) {
  final lower = reason.toLowerCase();
  if (lower.contains('vazifa')) {
    return _ReasonMeta(
      label: reason,
      icon: Icons.menu_book_rounded,
      color: ProgressColors.primaryBlue,
      kind: _ReasonKind.homework,
    );
  }
  if (lower.contains('test') || lower.contains('imtihon')) {
    return _ReasonMeta(
      label: reason,
      icon: Icons.assignment_turned_in_rounded,
      color: ProgressColors.purple,
      kind: _ReasonKind.test,
    );
  }
  if (lower.contains('kelmadi') || lower.contains('qoldir')) {
    return _ReasonMeta(
      label: reason,
      icon: Icons.cancel_rounded,
      color: const Color(0xFFEF4444),
      kind: _ReasonKind.attendanceMissed,
    );
  }
  if (lower.contains('keldi') || lower.contains('qatnash')) {
    return _ReasonMeta(
      label: reason,
      icon: Icons.check_circle_rounded,
      color: ProgressColors.green,
      kind: _ReasonKind.attendance,
    );
  }
  if (lower.contains('faol') || lower.contains('chaqmoq')) {
    return _ReasonMeta(
      label: reason,
      icon: Icons.bolt_rounded,
      color: ProgressColors.orange,
      kind: _ReasonKind.activity,
    );
  }
  return _ReasonMeta(
    label: reason,
    icon: Icons.check_circle_outline_rounded,
    color: ProgressColors.primaryBlue,
    kind: _ReasonKind.other,
  );
}



class _RecentActivityList extends StatefulWidget {
  const _RecentActivityList({
    required this.timeline,
    required this.totalChaqmoq,
    required this.currentPeriod,
    required this.onChangePeriod,
  });

  final ProgressTimelineModel? timeline;
  final int totalChaqmoq;
  final String? currentPeriod;
  final Future<void> Function(String periodKey) onChangePeriod;

  @override
  State<_RecentActivityList> createState() => _RecentActivityListState();
}

class _RecentActivityListState extends State<_RecentActivityList> {
  late DateTime _viewMonth;

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _viewMonth = DateTime(now.year, now.month);
  }

  /// Tanlangan oydagi har bir chaqmoq/yozuv — yassi (flat) ro'yxat.
  /// Vaqt bo'yicha kamayuvchi tartibda saralangan, har bir element o'z
  /// sanasi va soati bilan qaytadi.
  List<_FlatEntry> _entriesForMonth() {
    final result = <_FlatEntry>[];
    final points = widget.timeline?.points ?? const <ProgressTimelinePoint>[];
    for (final point in points) {
      final dayDate = point.parsedDate;
      if (dayDate == null) continue;
      if (dayDate.year != _viewMonth.year || dayDate.month != _viewMonth.month) {
        continue;
      }
      for (final entry in point.entries) {
        final text = entry.text.trim();
        if (text.isEmpty && entry.score == 0) continue;
        final ts = entry.parsedCreatedAt ?? dayDate;
        result.add(_FlatEntry(
          timestamp: ts,
          text: text.isEmpty ? 'Faollik' : text,
          score: entry.score,
          meta: _classifyReason(text),
          entry: entry,
        ));
      }
    }
    result.sort((a, b) => b.timestamp.compareTo(a.timestamp));
    return result;
  }

  bool _canGoNext() {
    final now = DateTime.now();
    final next = DateTime(_viewMonth.year, _viewMonth.month + 1);
    return !next.isAfter(DateTime(now.year, now.month));
  }

  void _shiftMonth(int delta) {
    setState(() {
      _viewMonth = DateTime(_viewMonth.year, _viewMonth.month + delta);
    });
    final now = DateTime.now();
    if (_viewMonth.year == now.year && _viewMonth.month == now.month) {
      widget.onChangePeriod('current');
    } else if (_viewMonth.year == now.year && _viewMonth.month == now.month - 1) {
      widget.onChangePeriod('last_month');
    } else {
      // 3 oylik radius — backenddan timeline'ni keng oraliqda olamiz.
      widget.onChangePeriod('last_3_months');
    }
  }

  String _monthLabel() {
    const months = [
      'Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun',
      'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr',
    ];
    return '${months[_viewMonth.month - 1]} ${_viewMonth.year}';
  }

  @override
  Widget build(BuildContext context) {
    final entries = _entriesForMonth();
    var totalChaqmoqMonth = 0;
    for (final e in entries) {
      totalChaqmoqMonth += e.score;
    }

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        boxShadow: ProgressShadows.card,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                'Faol kunlar',
                style: ProgressTextStyles.title.copyWith(fontSize: 13.5),
              ),
              const Spacer(),
              if (totalChaqmoqMonth != 0) ...[
                Icon(
                  Icons.bolt_rounded,
                  size: 13,
                  color: totalChaqmoqMonth > 0
                      ? ProgressColors.orange
                      : const Color(0xFFEF4444),
                ),
                const SizedBox(width: 2),
                Text(
                  '${totalChaqmoqMonth > 0 ? '+' : ''}$totalChaqmoqMonth',
                  style: ProgressTextStyles.label.copyWith(
                    color: totalChaqmoqMonth > 0
                        ? ProgressColors.orange
                        : const Color(0xFFEF4444),
                    fontSize: 11.5,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(width: 8),
              ],
              Text(
                '${entries.length} ta yozuv',
                style: ProgressTextStyles.body.copyWith(
                  color: ProgressColors.secondaryText,
                  fontSize: 11.5,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          // Oy tanlash paneli (chap/o'ng o'qlar + oy nomi)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
            decoration: BoxDecoration(
              color: const Color(0xFFF5F8FC),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: ProgressColors.border),
            ),
            child: Row(
              children: [
                _MonthArrowBtn(
                  icon: Icons.chevron_left_rounded,
                  enabled: true,
                  onTap: () => _shiftMonth(-1),
                ),
                Expanded(
                  child: Center(
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(
                          Icons.calendar_month_rounded,
                          size: 15,
                          color: ProgressColors.primaryBlue,
                        ),
                        const SizedBox(width: 6),
                        Text(
                          _monthLabel(),
                          style: ProgressTextStyles.title.copyWith(
                            fontSize: 13,
                            color: ProgressColors.text,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                _MonthArrowBtn(
                  icon: Icons.chevron_right_rounded,
                  enabled: _canGoNext(),
                  onTap: () => _shiftMonth(1),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          if (entries.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 18),
              child: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.event_busy_rounded,
                      color: ProgressColors.secondaryText.withValues(alpha: 0.6),
                      size: 28,
                    ),
                    const SizedBox(height: 6),
                    Text(
                      "Bu oyda yozuv yo‘q",
                      style: ProgressTextStyles.body.copyWith(
                        color: ProgressColors.secondaryText,
                        fontSize: 12.5,
                      ),
                    ),
                  ],
                ),
              ),
            )
          else
            for (var i = 0; i < entries.length; i++) ...[
              if (i > 0) const SizedBox(height: 6),
              _ActivityRow(entry: entries[i]),
            ],
        ],
      ),
    );
  }
}

class _FlatEntry {
  const _FlatEntry({
    required this.timestamp,
    required this.text,
    required this.score,
    required this.meta,
    required this.entry,
  });

  final DateTime timestamp;
  final String text;
  final int score;
  final _ReasonMeta meta;
  final ProgressReasonEntry entry;
}

class _MonthArrowBtn extends StatelessWidget {
  const _MonthArrowBtn({
    required this.icon,
    required this.enabled,
    required this.onTap,
  });

  final IconData icon;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Opacity(
      opacity: enabled ? 1 : 0.4,
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(8),
        child: InkWell(
          onTap: enabled ? onTap : null,
          borderRadius: BorderRadius.circular(8),
          child: Container(
            width: 32,
            height: 30,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: ProgressColors.border),
            ),
            child: Icon(icon, size: 16, color: ProgressColors.text),
          ),
        ),
      ),
    );
  }
}

class _ActivityRow extends StatelessWidget {
  const _ActivityRow({required this.entry});

  final _FlatEntry entry;

  String _shortDate(DateTime d) {
    const m = ['yan', 'fev', 'mar', 'apr', 'may', 'iyn',
               'iyl', 'avg', 'sen', 'okt', 'noy', 'dek'];
    return '${d.day} ${m[d.month - 1]}';
  }

  String _shortTime(DateTime d) {
    final hh = d.hour.toString().padLeft(2, '0');
    final mm = d.minute.toString().padLeft(2, '0');
    return '$hh:$mm';
  }

  @override
  Widget build(BuildContext context) {
    final positive = entry.score >= 0;
    final pillColor = positive ? ProgressColors.green : const Color(0xFFEF4444);
    final pillBg = positive
        ? const Color(0xFFDCFCE7)
        : const Color(0xFFFEE2E2);
    final iconBg = entry.meta.color.withValues(alpha: 0.12);
    final subtitleParts = <String>[];
    if (entry.entry.group.trim().isNotEmpty) {
      subtitleParts.add(entry.entry.group.trim());
    }
    final teacher = (entry.entry.awardedBy.trim().isNotEmpty
            ? entry.entry.awardedBy
            : entry.entry.teacher)
        .trim();
    if (teacher.isNotEmpty) subtitleParts.add(teacher);
    final subtitle = subtitleParts.join(' · ');
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
      decoration: BoxDecoration(
        color: const Color(0xFFFAFCFF),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: ProgressColors.border),
      ),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: iconBg,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(entry.meta.icon, size: 18, color: entry.meta.color),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  entry.text,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: ProgressTextStyles.title.copyWith(fontSize: 12.5),
                ),
                const SizedBox(height: 2),
                Text(
                  '${_shortDate(entry.timestamp)} · ${_shortTime(entry.timestamp)}'
                  '${subtitle.isEmpty ? '' : ' · $subtitle'}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: ProgressTextStyles.body.copyWith(
                    color: ProgressColors.secondaryText,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: pillBg,
              borderRadius: BorderRadius.circular(100),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.bolt_rounded, size: 12, color: pillColor),
                const SizedBox(width: 2),
                Text(
                  '${positive ? '+' : ''}${entry.score}',
                  style: ProgressTextStyles.label.copyWith(
                    color: pillColor,
                    fontSize: 11.5,
                    fontWeight: FontWeight.w800,
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

  static bool get _isDark =>
      ParentColors.bg == const Color(0xFF0B0F17);
  static Color get background => _isDark
      ? const Color(0xFF0B0F17) : const Color(0xFFF7FBFF);
  static Color get card => _isDark
      ? const Color(0xFF141926) : const Color(0xFFFFFFFF);
  static Color get text => _isDark
      ? const Color(0xFFEAF1FB) : const Color(0xFF111827);
  static Color get secondaryText => _isDark
      ? const Color(0xFF94A3B8) : const Color(0xFF6B7280);
  static Color get border => _isDark
      ? const Color(0xFF24304A) : const Color(0xFFE5EAF2);
  static const Color primaryBlue = Color(0xFF1E73F8);
  static const Color green = Color(0xFF10B981);
  static const Color orange = Color(0xFFF59E0B);
  static const Color purple = Color(0xFF7C3AED);
  static const Color pink = Color(0xFFEC4899);
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
