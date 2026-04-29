import 'dart:math' as math;

import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/parent_models.dart';
import 'package:chaqmoq_mobile/providers/parent_dashboard_provider.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/parent_dashboard_service.dart';
import 'package:chaqmoq_mobile/widgets/adaptive_avatar.dart';
import 'package:fl_chart/fl_chart.dart';
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

  void _showSubjectsSheet() {
    final subjects = _data?.subjects ?? const <ParentSubjectProgressModel>[];
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (sheetContext) {
        return _ProgressBottomSheet(
          title: 'Fanlar bo‘yicha progress',
          child: subjects.isEmpty
              ? const _ProgressSheetEmptyState(
                  message: 'Fanlar bo‘yicha ma’lumot mavjud emas',
                )
              : ListView.separated(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: subjects.length,
                  separatorBuilder: (_, _) =>
                      const Divider(height: 1, color: ProgressColors.border),
                  itemBuilder: (context, index) {
                    final row = _subjectData(subjects[index], index);
                    return Padding(
                      padding: const EdgeInsets.symmetric(vertical: 10),
                      child: SubjectProgressRow(
                        data: row,
                        showDivider: false,
                      ),
                    );
                  },
                ),
        );
      },
    );
  }

  void _showCommentsSheet() {
    final comments = _data?.teacherComments ?? const <ParentTeacherCommentModel>[];
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (sheetContext) {
        return _ProgressBottomSheet(
          title: 'O‘qituvchilarning izohlari',
          child: comments.isEmpty
              ? const _ProgressSheetEmptyState(
                  message: 'O‘qituvchi izohlari hozircha mavjud emas',
                )
              : ListView.separated(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: comments.length,
                  separatorBuilder: (_, _) =>
                      const Divider(height: 1, color: ProgressColors.border),
                  itemBuilder: (context, index) {
                    final comment = comments[index];
                    return Padding(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      child: _TeacherCommentTile(comment: comment),
                    );
                  },
                ),
        );
      },
    );
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
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 32),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  ProgressHeader(
                    child: child,
                    periodLabel:
                        _data?.selectedPeriodLabel ?? 'Joriy davr',
                    onSelectPeriod: () => _showPeriodMenu(context),
                  ),
                  const SizedBox(height: 16),
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
                      const SizedBox(height: 10),
                    ],
                    OverallProgressCard(data: _data),
                    const SizedBox(height: 18),
                    SubjectProgressSection(
                      subjects: _data?.subjects ?? const [],
                      onShowAll: _showSubjectsSheet,
                    ),
                    const SizedBox(height: 18),
                    TeacherCommentCard(
                      comments: _data?.teacherComments ?? const [],
                      onShowAll: _showCommentsSheet,
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
                'Progress',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: ProgressTextStyles.title.copyWith(fontSize: 23),
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

class OverallProgressCard extends StatelessWidget {
  const OverallProgressCard({super.key, this.data});

  final ParentProgressModel? data;

  @override
  Widget build(BuildContext context) {
    return ProgressCard(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 16),
      child: Column(
        children: [
          LayoutBuilder(
            builder: (context, constraints) {
              final stacked = constraints.maxWidth < 270;
              if (stacked) {
                return Column(
                  children: [
                    CircularProgressBlock(data: data),
                    const SizedBox(height: 16),
                    const Divider(color: ProgressColors.border),
                    const SizedBox(height: 14),
                    ProgressLineChart(series: data?.progressChart ?? const []),
                  ],
                );
              }

              return SizedBox(
                height: 204,
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Expanded(child: CircularProgressBlock(data: data)),
                    const VerticalDivider(
                      width: 22,
                      thickness: 1,
                      color: ProgressColors.border,
                    ),
                    Expanded(
                      child: ProgressLineChart(
                        series: data?.progressChart ?? const [],
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              _ProgressMetricChip(
                label: 'Joriy davr',
                value: data?.selectedPeriodLabel ?? 'Joriy davr',
                icon: Icons.event_note_rounded,
              ),
              _ProgressMetricChip(
                label: 'Davomatga ta’siri',
                value: '${data?.attendancePercent ?? 0}%',
                icon: Icons.event_available_outlined,
                accentColor: ProgressColors.green,
                backgroundColor: const Color(0xFFEAFBF2),
              ),
              _ProgressMetricChip(
                label: 'Fanlar o‘rtachasi',
                value: '${data?.subjectAveragePercent ?? 0}%',
                icon: Icons.auto_graph_rounded,
                accentColor: ProgressColors.purple,
                backgroundColor: const Color(0xFFF1ECFF),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class CircularProgressBlock extends StatelessWidget {
  const CircularProgressBlock({super.key, this.data});

  final ParentProgressModel? data;

  @override
  Widget build(BuildContext context) {
    final percent = data?.overallPercent ?? 0;
    final normalized = (percent / 100).clamp(0, 1).toDouble();
    return LayoutBuilder(
      builder: (context, constraints) {
        final size = constraints.maxWidth.clamp(96.0, 112.0).toDouble();
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Umumiy progress',
              style: ProgressTextStyles.title.copyWith(fontSize: 16),
            ),
            const SizedBox(height: 14),
            Center(
              child: SizedBox(
                width: size,
                height: size,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    SizedBox.expand(
                      child: CircularProgressIndicator(
                        value: normalized,
                        strokeWidth: 10,
                        strokeCap: StrokeCap.round,
                        backgroundColor: const Color(0xFFEFF2F6),
                        color: ProgressColors.primaryBlue,
                      ),
                    ),
                    Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          '$percent%',
                          style: ProgressTextStyles.title.copyWith(
                            fontSize: 32,
                            height: 0.98,
                          ),
                        ),
                        const SizedBox(height: 5),
                        Text(
                          _progressStatus(percent),
                          style: ProgressTextStyles.link.copyWith(fontSize: 15),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 14),
            Row(
              children: [
                const Icon(
                  Icons.trending_up_rounded,
                  color: ProgressColors.green,
                  size: 18,
                ),
                const SizedBox(width: 5),
                Text(
                  '${percent.clamp(0, 100)}%',
                  style: ProgressTextStyles.body.copyWith(
                    color: ProgressColors.green,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(width: 5),
                Expanded(
                  child: Text(
                    'umumiy o‘zlashtirish',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: ProgressTextStyles.body.copyWith(
                      color: ProgressColors.secondaryText,
                      fontSize: 13,
                    ),
                  ),
                ),
              ],
            ),
          ],
        );
      },
    );
  }
}

class ProgressLineChart extends StatelessWidget {
  const ProgressLineChart({super.key, required this.series});

  final List<ParentProgressSeries> series;

  @override
  Widget build(BuildContext context) {
    final chart = _averageProgressSeries(series);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Progress dinamikasi',
          style: ProgressTextStyles.title.copyWith(fontSize: 16),
        ),
        const SizedBox(height: 10),
        SizedBox(
          height: 144,
          width: double.infinity,
          child: chart.points.length < 2
              ? Center(
                  child: Text(
                    'Progress ma’lumoti yo‘q',
                    style: ProgressTextStyles.body.copyWith(
                      color: ProgressColors.secondaryText,
                      fontSize: 13,
                    ),
                  ),
                )
              : LineChart(
                  LineChartData(
                    minX: 0,
                    maxX: (chart.points.length - 1).toDouble(),
                    minY: 0,
                    maxY: 100,
                    clipData: const FlClipData.all(),
                    lineTouchData: LineTouchData(
                      touchTooltipData: LineTouchTooltipData(
                        getTooltipColor: (_) => ProgressColors.text,
                        getTooltipItems: (spots) => spots
                            .map(
                              (spot) => LineTooltipItem(
                                '${spot.y.toStringAsFixed(0)}%',
                                ProgressTextStyles.label.copyWith(
                                  color: Colors.white,
                                ),
                              ),
                            )
                            .toList(growable: false),
                      ),
                    ),
                    gridData: FlGridData(
                      show: true,
                      drawVerticalLine: false,
                      horizontalInterval: 25,
                      getDrawingHorizontalLine: (_) {
                        return const FlLine(
                          color: ProgressColors.border,
                          strokeWidth: 1,
                        );
                      },
                    ),
                    borderData: FlBorderData(show: false),
                    titlesData: FlTitlesData(
                      topTitles: const AxisTitles(
                        sideTitles: SideTitles(showTitles: false),
                      ),
                      rightTitles: const AxisTitles(
                        sideTitles: SideTitles(showTitles: false),
                      ),
                      leftTitles: AxisTitles(
                        sideTitles: SideTitles(
                          showTitles: true,
                          reservedSize: 34,
                          interval: 25,
                          getTitlesWidget: (value, meta) {
                            return Text(
                              '${value.toInt()}%',
                              style: ProgressTextStyles.body.copyWith(
                                color: ProgressColors.secondaryText,
                                fontSize: 11,
                              ),
                            );
                          },
                        ),
                      ),
                      bottomTitles: AxisTitles(
                        sideTitles: SideTitles(
                          showTitles: true,
                          reservedSize: 22,
                          interval: 1,
                          getTitlesWidget: (value, meta) {
                            final index = value.round();
                            if (index < 0 || index >= chart.points.length) {
                              return const SizedBox.shrink();
                            }
                            final label = index < chart.months.length
                                ? chart.months[index]
                                : '${index + 1}';
                            return Padding(
                              padding: const EdgeInsets.only(top: 5),
                              child: Text(
                                label,
                                style: ProgressTextStyles.body.copyWith(
                                  color: ProgressColors.secondaryText,
                                  fontSize: 11,
                                ),
                              ),
                            );
                          },
                        ),
                      ),
                    ),
                    lineBarsData: [
                      LineChartBarData(
                        spots: [
                          for (
                            var index = 0;
                            index < chart.points.length;
                            index++
                          )
                            FlSpot(index.toDouble(), chart.points[index]),
                        ],
                        isCurved: true,
                        preventCurveOverShooting: true,
                        color: ProgressColors.primaryBlue,
                        barWidth: 2.6,
                        isStrokeCapRound: true,
                        dotData: FlDotData(
                          show: true,
                          getDotPainter: (spot, percent, barData, index) {
                            return FlDotCirclePainter(
                              radius: 3.2,
                              color: Colors.white,
                              strokeWidth: 2,
                              strokeColor: ProgressColors.primaryBlue,
                            );
                          },
                        ),
                        belowBarData: BarAreaData(
                          show: true,
                          color: ProgressColors.primaryBlue.withValues(
                            alpha: 0.08,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
        ),
      ],
    );
  }
}

class SubjectProgressSection extends StatelessWidget {
  const SubjectProgressSection({
    super.key,
    required this.subjects,
    required this.onShowAll,
  });

  final List<ParentSubjectProgressModel> subjects;
  final VoidCallback onShowAll;

  @override
  Widget build(BuildContext context) {
    final preview = subjects.take(4).toList(growable: false);
    final rows = [
      for (var index = 0; index < preview.length; index++)
        _subjectData(preview[index], index),
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _SectionHeader(
          title: 'Fanlar bo‘yicha progress',
          actionText: 'Barchasi',
          onTap: onShowAll,
        ),
        const SizedBox(height: 12),
        ProgressCard(
          padding: EdgeInsets.zero,
          child: Column(
            children: [
              if (rows.isEmpty)
                Padding(
                  padding: const EdgeInsets.all(18),
                  child: Text(
                    'Progress ma’lumoti yo‘q',
                    textAlign: TextAlign.center,
                    style: ProgressTextStyles.body.copyWith(
                      color: ProgressColors.secondaryText,
                      fontSize: 13.5,
                    ),
                  ),
                )
              else
                for (int index = 0; index < rows.length; index++)
                  SubjectProgressRow(
                    data: rows[index],
                    showDivider: index != rows.length - 1,
                  ),
            ],
          ),
        ),
      ],
    );
  }
}

class SubjectProgressRow extends StatelessWidget {
  const SubjectProgressRow({
    super.key,
    required this.data,
    required this.showDivider,
  });

  final SubjectProgressData data;
  final bool showDivider;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final compact = constraints.maxWidth < 330;
        return Column(
          children: [
            Padding(
              padding: EdgeInsets.fromLTRB(
                compact ? 12 : 16,
                14,
                compact ? 10 : 14,
                14,
              ),
              child: Row(
                children: [
                  _SubjectIconTile(data: data, compact: compact),
                  SizedBox(width: compact ? 10 : 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          data.title,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: ProgressTextStyles.title.copyWith(
                            fontSize: compact ? 14.2 : 15.5,
                            height: 1.18,
                          ),
                        ),
                        const SizedBox(height: 5),
                        Text(
                          data.teacher,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: ProgressTextStyles.body.copyWith(
                            color: ProgressColors.secondaryText,
                            fontSize: compact ? 12 : 13,
                          ),
                        ),
                        if (data.detailLine.isNotEmpty) ...[
                          const SizedBox(height: 4),
                          Text(
                            data.detailLine,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: ProgressTextStyles.body.copyWith(
                              color: ProgressColors.secondaryText,
                              fontSize: compact ? 11.5 : 12.2,
                            ),
                          ),
                        ],
                        const SizedBox(height: 10),
                        ClipRRect(
                          borderRadius: BorderRadius.circular(999),
                          child: LinearProgressIndicator(
                            value: data.percent / 100,
                            minHeight: 5,
                            backgroundColor: const Color(0xFFEFF2F6),
                            valueColor: AlwaysStoppedAnimation<Color>(
                              data.color,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  SizedBox(width: compact ? 6 : 10),
                  SizedBox(
                    width: compact ? 46 : 54,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        FittedBox(
                          fit: BoxFit.scaleDown,
                          alignment: Alignment.centerRight,
                          child: Text(
                            '${data.percent}%',
                            style: ProgressTextStyles.title.copyWith(
                              color: data.color,
                              fontSize: compact ? 20 : 22,
                            ),
                          ),
                        ),
                        const SizedBox(height: 5),
                        Text(
                          data.status,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: ProgressTextStyles.body.copyWith(
                            color: data.status == 'O‘rta'
                                ? ProgressColors.orange
                                : ProgressColors.green,
                            fontSize: compact ? 11.5 : 12.5,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 4),
                  const Icon(
                    Icons.chevron_right_rounded,
                    color: Color(0xFF9AA4B2),
                    size: 20,
                  ),
                ],
              ),
            ),
            if (showDivider)
              const Divider(height: 1, color: ProgressColors.border),
          ],
        );
      },
    );
  }
}

class TeacherCommentCard extends StatelessWidget {
  const TeacherCommentCard({
    super.key,
    required this.comments,
    required this.onShowAll,
  });

  final List<ParentTeacherCommentModel> comments;
  final VoidCallback onShowAll;

  @override
  Widget build(BuildContext context) {
    final data = comments.isEmpty ? null : comments.first;
    return ProgressCard(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _SectionHeader(
            title: 'O‘qituvchilarning izohi',
            actionText: 'Barchasi',
            onTap: onShowAll,
          ),
          const SizedBox(height: 16),
          if (data == null)
            const _ProgressSheetEmptyState(
              message: 'O‘qituvchi izohlari hozircha mavjud emas',
            )
          else
            _TeacherCommentTile(comment: data),
        ],
      ),
    );
  }
}

class _TeacherCommentTile extends StatelessWidget {
  const _TeacherCommentTile({required this.comment});

  final ParentTeacherCommentModel comment;

  @override
  Widget build(BuildContext context) {
    final teacherName = comment.teacherName.isEmpty
        ? 'O‘qituvchi'
        : comment.teacherName;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        AdaptiveAvatar(
          name: teacherName,
          size: 48,
          icon: Icons.person_outline_rounded,
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          teacherName,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: ProgressTextStyles.title.copyWith(fontSize: 16),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          comment.teacherRole.isEmpty
                              ? 'O‘qituvchi'
                              : comment.teacherRole,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: ProgressTextStyles.link.copyWith(
                            fontSize: 13.5,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    Formatters.date(comment.date),
                    style: ProgressTextStyles.body.copyWith(
                      color: ProgressColors.secondaryText,
                      fontSize: 12.5,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Text(
                comment.comment,
                style: ProgressTextStyles.body.copyWith(
                  color: const Color(0xFF374151),
                  fontSize: 13.5,
                  height: 1.45,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _ProgressMetricChip extends StatelessWidget {
  const _ProgressMetricChip({
    required this.label,
    required this.value,
    required this.icon,
    this.accentColor = ProgressColors.primaryBlue,
    this.backgroundColor = const Color(0xFFEAF4FF),
  });

  final String label;
  final String value;
  final IconData icon;
  final Color accentColor;
  final Color backgroundColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minWidth: 148),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
      decoration: BoxDecoration(
        color: backgroundColor,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 34,
            height: 34,
            decoration: BoxDecoration(
              color: accentColor.withValues(alpha: 0.14),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, color: accentColor, size: 18),
          ),
          const SizedBox(width: 10),
          Flexible(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: ProgressTextStyles.body.copyWith(
                    color: ProgressColors.secondaryText,
                    fontSize: 12,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  value,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: ProgressTextStyles.title.copyWith(fontSize: 14.5),
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

class _ProgressSheetEmptyState extends StatelessWidget {
  const _ProgressSheetEmptyState({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(18, 20, 18, 20),
      decoration: BoxDecoration(
        color: const Color(0xFFF7FBFF),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: ProgressColors.border),
      ),
      child: Column(
        children: [
          Container(
            width: 52,
            height: 52,
            decoration: const BoxDecoration(
              color: Color(0xFFEAF4FF),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.info_outline_rounded,
              color: ProgressColors.primaryBlue,
              size: 24,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            message,
            textAlign: TextAlign.center,
            style: ProgressTextStyles.body.copyWith(
              color: ProgressColors.secondaryText,
              fontSize: 13.5,
            ),
          ),
        ],
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
              fontSize: 11.5,
            ),
            unselectedLabelStyle: ProgressTextStyles.label.copyWith(
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

class ProgressCard extends StatelessWidget {
  const ProgressCard({super.key, required this.child, required this.padding});

  final Widget child;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: ProgressColors.border),
        boxShadow: ProgressShadows.card,
      ),
      child: child,
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({
    required this.title,
    required this.actionText,
    required this.onTap,
  });

  final String title;
  final String actionText;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(
            title,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: ProgressTextStyles.title.copyWith(fontSize: 18),
          ),
        ),
        TextButton(
          onPressed: onTap,
          style: TextButton.styleFrom(
            foregroundColor: ProgressColors.primaryBlue,
            padding: EdgeInsets.zero,
            minimumSize: const Size(0, 30),
            tapTargetSize: MaterialTapTargetSize.shrinkWrap,
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                actionText,
                style: ProgressTextStyles.link.copyWith(fontSize: 14),
              ),
              const SizedBox(width: 4),
              const Icon(Icons.chevron_right_rounded, size: 20),
            ],
          ),
        ),
      ],
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
        padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 10),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
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
              fontSize: 13.5,
            ),
          ),
          const SizedBox(width: 5),
          const Icon(Icons.keyboard_arrow_down_rounded, size: 19),
        ],
      ),
    );
  }
}

class _SubjectIconTile extends StatelessWidget {
  const _SubjectIconTile({required this.data, required this.compact});

  final SubjectProgressData data;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final size = compact ? 42.0 : 48.0;
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: data.background,
        borderRadius: BorderRadius.circular(13),
      ),
      child: _SubjectIcon(kind: data.iconKind, color: data.color),
    );
  }
}

class _SubjectIcon extends StatelessWidget {
  const _SubjectIcon({required this.kind, required this.color});

  final SubjectIconKind kind;
  final Color color;

  @override
  Widget build(BuildContext context) {
    if (kind == SubjectIconKind.math) {
      return Text(
        '√x',
        style: GoogleFonts.inter(
          color: color,
          fontSize: 22,
          fontWeight: FontWeight.w800,
          fontStyle: FontStyle.italic,
        ),
      );
    }

    final icon = switch (kind) {
      SubjectIconKind.book => Icons.menu_book_outlined,
      SubjectIconKind.atom => Icons.scatter_plot_outlined,
      SubjectIconKind.code => Icons.code_rounded,
      SubjectIconKind.flask => Icons.science_outlined,
      SubjectIconKind.history => Icons.account_balance_outlined,
      SubjectIconKind.math => Icons.functions_rounded,
    };
    return Icon(icon, color: color, size: 26);
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
    return ProgressCard(
      padding: const EdgeInsets.fromLTRB(18, 36, 18, 36),
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

class _AverageChartData {
  const _AverageChartData({required this.points, required this.months});

  final List<double> points;
  final List<String> months;
}

_AverageChartData _averageProgressSeries(List<ParentProgressSeries> series) {
  if (series.isEmpty) {
    return const _AverageChartData(points: [], months: []);
  }
  final pointCount = series.fold<int>(
    0,
    (previous, item) => math.max(previous, item.points.length),
  );
  if (pointCount == 0) {
    return const _AverageChartData(points: [], months: []);
  }

  final points = <double>[];
  for (var index = 0; index < pointCount; index++) {
    final values = [
      for (final item in series)
        if (index < item.points.length) item.points[index].clamp(0, 100),
    ];
    if (values.isEmpty) {
      points.add(0);
    } else {
      points.add(values.reduce((a, b) => a + b) / values.length);
    }
  }

  final months = series
      .firstWhere((item) => item.months.isNotEmpty, orElse: () => series.first)
      .months;
  return _AverageChartData(points: points, months: months);
}

SubjectProgressData _subjectData(
  ParentSubjectProgressModel subject,
  int index,
) {
  const colors = [
    Color(0xFF6D5DF6),
    ProgressColors.green,
    ProgressColors.orange,
    ProgressColors.purple,
    ProgressColors.primaryBlue,
    ProgressColors.pink,
  ];
  const backgrounds = [
    Color(0xFFEDE5FF),
    Color(0xFFE4F8EC),
    Color(0xFFFFF1D8),
    Color(0xFFEDE2FF),
    Color(0xFFE2F1FF),
    Color(0xFFFFE1F0),
  ];
  final color = colors[index % colors.length];
  final teacher = subject.teacherName.trim().isEmpty
      ? 'O‘qituvchi biriktirilmagan'
      : 'O‘qituvchi: ${subject.teacherName}';
  final details = <String>[
    if (subject.examPercent > 0) 'Topshiriq va baholar: ${subject.examPercent}%',
    if (subject.attendancePercent > 0) 'Davomat ta’siri: ${subject.attendancePercent}%',
  ];
  return SubjectProgressData(
    title: subject.subject.isEmpty ? 'Fan' : subject.subject,
    teacher: teacher,
    detailLine: details.join(' • '),
    percent: subject.percent.clamp(0, 100),
    status: subject.status.isEmpty
        ? _progressStatus(subject.percent)
        : subject.status,
    iconKind: _subjectIcon(subject.subject),
    color: color,
    background: backgrounds[index % backgrounds.length],
  );
}

SubjectIconKind _subjectIcon(String subject) {
  final normalized = subject.toLowerCase();
  if (normalized.contains('mat')) {
    return SubjectIconKind.math;
  }
  if (normalized.contains('ingliz') || normalized.contains('til')) {
    return SubjectIconKind.book;
  }
  if (normalized.contains('fiz')) {
    return SubjectIconKind.atom;
  }
  if (normalized.contains('info') || normalized.contains('it')) {
    return SubjectIconKind.code;
  }
  if (normalized.contains('kim')) {
    return SubjectIconKind.flask;
  }
  return SubjectIconKind.history;
}

String _progressStatus(int percent) {
  if (percent >= 90) {
    return 'A’lo';
  }
  if (percent >= 65) {
    return 'Yaxshi';
  }
  return 'O‘rta';
}

String _childGroupLine(ParentChildModel child) {
  final parts = <String>[
    if (child.fullName.trim().isNotEmpty) child.fullName.trim(),
    if (child.className.trim().isNotEmpty) child.className.trim(),
    if (child.groupName.trim().isNotEmpty) child.groupName.trim(),
  ];
  return parts.isEmpty ? 'Guruh biriktirilmagan' : parts.join(' • ');
}

class SubjectProgressData {
  const SubjectProgressData({
    required this.title,
    required this.teacher,
    required this.detailLine,
    required this.percent,
    required this.status,
    required this.iconKind,
    required this.color,
    required this.background,
  });

  final String title;
  final String teacher;
  final String detailLine;
  final int percent;
  final String status;
  final SubjectIconKind iconKind;
  final Color color;
  final Color background;
}

enum SubjectIconKind { math, book, atom, code, flask, history }

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
      fontSize: 18,
      height: 1.16,
      fontWeight: FontWeight.w800,
      color: ProgressColors.text,
      letterSpacing: 0,
    );
  }

  static TextStyle get body {
    return GoogleFonts.inter(
      fontSize: 15,
      height: 1.28,
      fontWeight: FontWeight.w500,
      color: ProgressColors.text,
      letterSpacing: 0,
    );
  }

  static TextStyle get label {
    return GoogleFonts.inter(
      fontSize: 13,
      height: 1.16,
      fontWeight: FontWeight.w800,
      color: ProgressColors.text,
      letterSpacing: 0,
    );
  }

  static TextStyle get link {
    return GoogleFonts.inter(
      fontSize: 15,
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
