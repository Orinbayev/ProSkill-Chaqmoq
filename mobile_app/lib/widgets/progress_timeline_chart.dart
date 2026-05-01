import 'package:chaqmoq_mobile/models/parent_models.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

/// Smooth gradient line chart for the per-day score timeline.
/// Tapping a point opens a bottom sheet with the day's reasons.
class ProgressTimelineChart extends StatefulWidget {
  const ProgressTimelineChart({
    super.key,
    required this.timeline,
    this.lineColor = const Color(0xFF3B82F6),
    this.height = 220,
  });

  final ProgressTimelineModel timeline;
  final Color lineColor;
  final double height;

  @override
  State<ProgressTimelineChart> createState() => _ProgressTimelineChartState();
}

class _ProgressTimelineChartState extends State<ProgressTimelineChart>
    with SingleTickerProviderStateMixin {
  late final AnimationController _animation = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 850),
  )..forward();

  @override
  void didUpdateWidget(covariant ProgressTimelineChart oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.timeline != widget.timeline) {
      _animation.forward(from: 0);
    }
  }

  @override
  void dispose() {
    _animation.dispose();
    super.dispose();
  }

  void _showReasonsForIndex(int index) {
    if (index < 0 || index >= widget.timeline.points.length) {
      return;
    }
    final point = widget.timeline.points[index];
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: false,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) => _ReasonSheet(point: point),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final points = widget.timeline.points;

    if (points.isEmpty) {
      return SizedBox(
        height: widget.height,
        child: Center(
          child: Text(
            'Hozircha statistika yo‘q',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.hintColor,
            ),
          ),
        ),
      );
    }

    final values = points.map((p) => p.score.toDouble()).toList();
    final minScore = values.reduce((a, b) => a < b ? a : b);
    final maxScore = values.reduce((a, b) => a > b ? a : b);
    final span = (maxScore - minScore).abs();
    final pad = span < 1 ? 2.0 : span * 0.25;
    final loY = (minScore - pad).clamp(-20.0, 0.0).toDouble() == 0.0
        ? minScore - pad
        : minScore - pad;
    final hiY = maxScore + pad;

    return AnimatedBuilder(
      animation: _animation,
      builder: (context, _) {
        final progress = Curves.easeOutCubic.transform(_animation.value);
        final spots = <FlSpot>[
          for (var i = 0; i < values.length; i++)
            FlSpot(i.toDouble(), values[i] * progress),
        ];

        return SizedBox(
          height: widget.height,
          child: LineChart(
            LineChartData(
              minX: 0,
              maxX: (values.length - 1).toDouble(),
              minY: loY,
              maxY: hiY,
              lineTouchData: LineTouchData(
                handleBuiltInTouches: true,
                touchTooltipData: LineTouchTooltipData(
                  getTooltipColor: (_) =>
                      theme.colorScheme.surface.withValues(alpha: 0.94),
                  tooltipRoundedRadius: 12,
                  tooltipPadding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 8,
                  ),
                  getTooltipItems: (touched) => touched.map((spot) {
                    final point = points[spot.x.toInt()];
                    final dateLabel = _formatDate(point.parsedDate);
                    return LineTooltipItem(
                      '$dateLabel\n${point.score >= 0 ? '+' : ''}${point.score} ball',
                      theme.textTheme.labelMedium!.copyWith(
                        color: theme.colorScheme.onSurface,
                        height: 1.4,
                      ),
                    );
                  }).toList(),
                ),
                touchCallback: (event, response) {
                  if (event is FlTapUpEvent &&
                      response?.lineBarSpots?.isNotEmpty == true) {
                    final index =
                        response!.lineBarSpots!.first.x.toInt();
                    _showReasonsForIndex(index);
                  }
                },
              ),
              gridData: FlGridData(
                show: true,
                drawVerticalLine: false,
                horizontalInterval: span < 4 ? 1 : (span / 4).ceilToDouble(),
                getDrawingHorizontalLine: (_) => FlLine(
                  color: theme.dividerColor.withValues(alpha: 0.18),
                  strokeWidth: 1,
                ),
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
                    reservedSize: 28,
                    interval:
                        span < 4 ? 1 : (span / 4).ceilToDouble(),
                    getTitlesWidget: (value, _) => Padding(
                      padding: const EdgeInsets.only(right: 4),
                      child: Text(
                        value.toInt().toString(),
                        style: theme.textTheme.labelSmall?.copyWith(
                          color: theme.hintColor,
                        ),
                      ),
                    ),
                  ),
                ),
                bottomTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: true,
                    reservedSize: 28,
                    interval: _xLabelInterval(values.length),
                    getTitlesWidget: (value, _) {
                      final i = value.toInt();
                      if (i < 0 || i >= points.length) {
                        return const SizedBox.shrink();
                      }
                      final date = points[i].parsedDate;
                      if (date == null) {
                        return const SizedBox.shrink();
                      }
                      return Padding(
                        padding: const EdgeInsets.only(top: 6),
                        child: Text(
                          DateFormat('d.M').format(date),
                          style: theme.textTheme.labelSmall?.copyWith(
                            color: theme.hintColor,
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ),
              lineBarsData: [
                LineChartBarData(
                  spots: spots,
                  isCurved: true,
                  curveSmoothness: 0.32,
                  preventCurveOverShooting: true,
                  barWidth: 3.2,
                  color: widget.lineColor,
                  shadow: Shadow(
                    color: widget.lineColor.withValues(alpha: 0.35),
                    blurRadius: 12,
                    offset: const Offset(0, 6),
                  ),
                  dotData: FlDotData(
                    show: true,
                    getDotPainter: (spot, _, _, _) {
                      final point = points[spot.x.toInt()];
                      final hasReasons = point.reasons.isNotEmpty;
                      return FlDotCirclePainter(
                        radius: hasReasons ? 4.5 : 2.6,
                        color: widget.lineColor,
                        strokeWidth: 2,
                        strokeColor: theme.colorScheme.surface,
                      );
                    },
                  ),
                  belowBarData: BarAreaData(
                    show: true,
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [
                        widget.lineColor.withValues(alpha: 0.32),
                        widget.lineColor.withValues(alpha: 0.02),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  double _xLabelInterval(int count) {
    if (count <= 7) return 1;
    if (count <= 14) return 2;
    if (count <= 31) return 5;
    return (count / 6).ceilToDouble();
  }

  static String _formatDate(DateTime? date) {
    if (date == null) return '';
    return DateFormat('d MMM', 'uz').format(date);
  }
}

class _ReasonSheet extends StatelessWidget {
  const _ReasonSheet({required this.point});

  final ProgressTimelinePoint point;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final date = point.parsedDate;
    final dateLabel = date == null
        ? point.date
        : DateFormat('d MMMM, EEEE', 'uz').format(date);
    final isPositive = point.score >= 0;
    final scoreColor = isPositive
        ? const Color(0xFF22C55E)
        : const Color(0xFFEF4444);
    final reasons = point.reasons;

    return SafeArea(
      top: false,
      child: Container(
        decoration: BoxDecoration(
          color: theme.colorScheme.surface,
          borderRadius: const BorderRadius.vertical(
            top: Radius.circular(24),
          ),
        ),
        padding: const EdgeInsets.fromLTRB(20, 14, 20, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: theme.dividerColor,
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text(
              dateLabel,
              style: theme.textTheme.labelLarge?.copyWith(
                color: theme.hintColor,
              ),
            ),
            const SizedBox(height: 6),
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 6,
                  ),
                  decoration: BoxDecoration(
                    color: scoreColor.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    '${isPositive ? '+' : ''}${point.score} ball',
                    style: theme.textTheme.titleMedium?.copyWith(
                      color: scoreColor,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    isPositive
                        ? 'qo‘shildi'
                        : 'ayrildi',
                    style: theme.textTheme.titleMedium,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            if (reasons.isEmpty)
              Text(
                'Bu kun uchun izoh qo‘shilmagan.',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.hintColor,
                ),
              )
            else
              ...reasons.map(
                (reason) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        margin: const EdgeInsets.only(top: 7, right: 12),
                        width: 6,
                        height: 6,
                        decoration: BoxDecoration(
                          color: scoreColor,
                          shape: BoxShape.circle,
                        ),
                      ),
                      Expanded(
                        child: Text(
                          reason,
                          style: theme.textTheme.bodyMedium,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
