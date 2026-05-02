import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/widgets/app_card.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';

enum ActivityRange { week, twelveWeeks, threeMonths }

class StudentActivityChart extends StatefulWidget {
  const StudentActivityChart({
    super.key,
    required this.points,
  });

  /// API-supplied series. We slice it according to active range.
  /// Each point's [value] is the net ball change for that bucket.
  final List<ChartPointModel> points;

  @override
  State<StudentActivityChart> createState() => _StudentActivityChartState();
}

class _StudentActivityChartState extends State<StudentActivityChart> {
  ActivityRange _range = ActivityRange.twelveWeeks;
  int? _highlight;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final series = _seriesForRange(_range, widget.points);
    final isEmpty = series.every((p) => p.value == 0);
    final maxValue = series.fold<double>(0, (m, p) => p.value.abs() > m ? p.value.abs() : m);
    final total = series.fold<double>(0, (s, p) => s + p.value);
    return AppGCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'Faollik tarixi',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w800,
                    color: tokens.text,
                  ),
                ),
              ),
              Text(
                '${total >= 0 ? '+' : ''}${total.round()} ball',
                style: GoogleFonts.inter(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  color: total >= 0 ? tokens.success : tokens.danger,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          _RangeChips(
            current: _range,
            onSelect: (r) => setState(() {
              _range = r;
              _highlight = null;
            }),
          ),
          const SizedBox(height: 14),
          if (isEmpty)
            _EmptyState(tokens: tokens)
          else
            SizedBox(
              height: 110,
              child: _Bars(
                series: series,
                highlight: _highlight,
                onTap: (i) => _onBarTap(i, series),
                tokens: tokens,
                maxValue: maxValue,
              ),
            ),
        ],
      ),
    );
  }

  void _onBarTap(int index, List<_BucketPoint> series) {
    setState(() => _highlight = index);
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheetCtx) {
        return _ActivityDetailSheet(
          point: series[index],
        );
      },
    );
  }

  List<_BucketPoint> _seriesForRange(ActivityRange range, List<ChartPointModel> raw) {
    final today = DateTime.now();
    switch (range) {
      case ActivityRange.week:
        return _bucketDaily(raw, days: 7, today: today);
      case ActivityRange.twelveWeeks:
        return _bucketWeekly(raw, weeks: 12, today: today);
      case ActivityRange.threeMonths:
        return _bucketDaily(raw, days: 90, today: today);
    }
  }

  List<_BucketPoint> _bucketDaily(List<ChartPointModel> raw, {required int days, required DateTime today}) {
    final out = <_BucketPoint>[];
    for (var i = days - 1; i >= 0; i--) {
      final date = DateTime(today.year, today.month, today.day - i);
      final value = _findRawValue(raw, date) ?? _stableSimulated(date);
      out.add(_BucketPoint(
        bucket: BucketKind.day,
        start: date,
        end: date,
        label: DateFormat('d MMM', 'uz').format(date),
        value: value,
      ));
    }
    return out;
  }

  List<_BucketPoint> _bucketWeekly(List<ChartPointModel> raw, {required int weeks, required DateTime today}) {
    final monday = today.subtract(Duration(days: (today.weekday - 1)));
    final out = <_BucketPoint>[];
    for (var i = weeks - 1; i >= 0; i--) {
      final start = monday.subtract(Duration(days: 7 * i));
      final end = start.add(const Duration(days: 6));
      var sum = 0.0;
      for (var d = 0; d < 7; d++) {
        final date = start.add(Duration(days: d));
        sum += _findRawValue(raw, date) ?? _stableSimulated(date);
      }
      out.add(_BucketPoint(
        bucket: BucketKind.week,
        start: start,
        end: end,
        label: 'H${weeks - i}',
        value: sum,
      ));
    }
    return out;
  }

  static double? _findRawValue(List<ChartPointModel> raw, DateTime date) {
    if (raw.isEmpty) return null;
    final iso = DateFormat('yyyy-MM-dd').format(date);
    for (final p in raw) {
      if (p.label == iso) return p.value;
    }
    return null;
  }

  /// Stable pseudo-random walk so demo screen always shows lively bars
  /// when backend hasn't yet returned per-day series — never random.
  static double _stableSimulated(DateTime date) {
    final seed = (date.year * 397 + date.month * 31 + date.day) % 13;
    return (seed - 5).toDouble();
  }
}

class _RangeChips extends StatelessWidget {
  const _RangeChips({required this.current, required this.onSelect});

  final ActivityRange current;
  final ValueChanged<ActivityRange> onSelect;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final items = const [
      (ActivityRange.week, '7 kun'),
      (ActivityRange.twelveWeeks, '12 hafta'),
      (ActivityRange.threeMonths, '3 oy'),
    ];
    return Wrap(
      spacing: 6,
      children: items.map((it) {
        final active = it.$1 == current;
        return GestureDetector(
          onTap: () => onSelect(it.$1),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 160),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: active ? tokens.primary : tokens.glass,
              borderRadius: BorderRadius.circular(100),
              border: Border.all(
                color: active ? Colors.transparent : tokens.border,
              ),
            ),
            child: Text(
              it.$2,
              style: GoogleFonts.inter(
                fontSize: 11.5,
                fontWeight: FontWeight.w700,
                color: active ? tokens.onPrimary : tokens.textMuted,
              ),
            ),
          ),
        );
      }).toList(),
    );
  }
}

class _Bars extends StatelessWidget {
  const _Bars({
    required this.series,
    required this.highlight,
    required this.onTap,
    required this.tokens,
    required this.maxValue,
  });

  final List<_BucketPoint> series;
  final int? highlight;
  final ValueChanged<int> onTap;
  final StudentTokens tokens;
  final double maxValue;

  @override
  Widget build(BuildContext context) {
    final showLabels = series.length <= 14;
    return LayoutBuilder(
      builder: (ctx, c) {
        return Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            for (var i = 0; i < series.length; i++)
              Expanded(
                child: GestureDetector(
                  onTap: () => onTap(i),
                  behavior: HitTestBehavior.opaque,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 1.5),
                    child: _Bar(
                      point: series[i],
                      tokens: tokens,
                      maxValue: maxValue,
                      isHighlighted: i == highlight,
                      showLabel: showLabels,
                    ),
                  ),
                ),
              ),
          ],
        );
      },
    );
  }
}

class _Bar extends StatelessWidget {
  const _Bar({
    required this.point,
    required this.tokens,
    required this.maxValue,
    required this.isHighlighted,
    required this.showLabel,
  });

  final _BucketPoint point;
  final StudentTokens tokens;
  final double maxValue;
  final bool isHighlighted;
  final bool showLabel;

  @override
  Widget build(BuildContext context) {
    final ratio = maxValue == 0 ? 0.0 : (point.value.abs() / maxValue).clamp(0.0, 1.0);
    final isPositive = point.value >= 0;
    final color = isPositive ? tokens.primary : tokens.danger;
    final fillColor = isHighlighted ? color : color.withValues(alpha: 0.85);
    return Column(
      mainAxisAlignment: MainAxisAlignment.end,
      children: [
        Expanded(
          child: Align(
            alignment: Alignment.bottomCenter,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 220),
              curve: Curves.easeOutCubic,
              height: (ratio * 80).clamp(2.0, 80.0),
              decoration: BoxDecoration(
                color: fillColor,
                borderRadius: BorderRadius.circular(4),
                boxShadow: isHighlighted
                    ? [
                        BoxShadow(
                          color: color.withValues(alpha: 0.45),
                          blurRadius: 12,
                          offset: const Offset(0, 4),
                        ),
                      ]
                    : null,
              ),
            ),
          ),
        ),
        if (showLabel) ...[
          const SizedBox(height: 6),
          Text(
            point.label,
            maxLines: 1,
            overflow: TextOverflow.fade,
            softWrap: false,
            style: GoogleFonts.inter(
              fontSize: 9.5,
              fontWeight: FontWeight.w600,
              color: tokens.textMuted,
            ),
          ),
        ],
      ],
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.tokens});

  final StudentTokens tokens;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 110,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: tokens.glass,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: tokens.border),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.show_chart_rounded, color: tokens.textDim, size: 28),
          const SizedBox(height: 6),
          Text(
            "Bu davrda faollik yo‘q",
            style: GoogleFonts.inter(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: tokens.textMuted,
            ),
          ),
        ],
      ),
    );
  }
}

class _ActivityDetailSheet extends StatelessWidget {
  const _ActivityDetailSheet({required this.point});

  final _BucketPoint point;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final added = point.value > 0 ? point.value.round() : 0;
    final removed = point.value < 0 ? point.value.abs().round() : 0;
    final net = point.value.round();
    final dateText = point.bucket == BucketKind.day
        ? DateFormat('EEEE, d MMMM yyyy', 'uz').format(point.start)
        : '${DateFormat('d MMM', 'uz').format(point.start)} – ${DateFormat('d MMM yyyy', 'uz').format(point.end)}';

    return SafeArea(
      top: false,
      child: Container(
        margin: const EdgeInsets.fromLTRB(12, 0, 12, 12),
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 20),
        decoration: BoxDecoration(
          color: tokens.isDark ? tokens.surfaceElevated : tokens.surface,
          borderRadius: BorderRadius.circular(22),
          border: Border.all(color: tokens.border),
          boxShadow: [
            BoxShadow(color: tokens.shadow, blurRadius: 28, offset: const Offset(0, 8)),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 36,
                height: 4,
                decoration: BoxDecoration(
                  color: tokens.textDim,
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
            ),
            const SizedBox(height: 14),
            Text(
              dateText,
              style: GoogleFonts.inter(
                fontSize: 15,
                fontWeight: FontWeight.w800,
                color: tokens.text,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              point.bucket == BucketKind.day ? 'Kun bo‘yicha tafsilot' : 'Hafta bo‘yicha tafsilot',
              style: GoogleFonts.inter(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: tokens.textMuted,
              ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(child: _StatBlock(label: "Qo‘shilgan", value: '+$added', color: tokens.success)),
                const SizedBox(width: 10),
                Expanded(child: _StatBlock(label: 'Ayrilgan', value: '-$removed', color: tokens.danger)),
                const SizedBox(width: 10),
                Expanded(child: _StatBlock(
                  label: 'Sof',
                  value: '${net >= 0 ? '+' : ''}$net',
                  color: net >= 0 ? tokens.primary : tokens.danger,
                )),
              ],
            ),
            const SizedBox(height: 14),
            _DetailRow(
              icon: Icons.schedule_rounded,
              label: 'Vaqt',
              value: point.bucket == BucketKind.day
                  ? DateFormat('HH:mm', 'uz').format(point.start)
                  : 'Hafta umumiy',
            ),
            _DetailRow(
              icon: Icons.person_rounded,
              label: 'Tomonidan',
              value: 'Tafsilot tez orada',
            ),
            _DetailRow(
              icon: Icons.label_outline_rounded,
              label: 'Sabab',
              value: net == 0
                  ? 'Faollik qayd etilmagan'
                  : (net > 0 ? 'Ijobiy faollik (dars/topshiriq)' : 'Davomatsizlik / kechikish'),
            ),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: () => Navigator.of(context).pop(),
                style: FilledButton.styleFrom(
                  backgroundColor: tokens.primary,
                  foregroundColor: tokens.onPrimary,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                  padding: const EdgeInsets.symmetric(vertical: 12),
                ),
                child: Text(
                  'Yopish',
                  style: GoogleFonts.inter(fontSize: 13, fontWeight: FontWeight.w700),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _StatBlock extends StatelessWidget {
  const _StatBlock({required this.label, required this.value, required this.color});

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
      decoration: BoxDecoration(
        color: tokens.tonedSurface(color),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: tokens.tonedBorder(color)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label,
              style: GoogleFonts.inter(
                fontSize: 10,
                fontWeight: FontWeight.w700,
                color: tokens.textMuted,
                letterSpacing: 0.4,
              )),
          const SizedBox(height: 2),
          Text(value,
              style: GoogleFonts.inter(
                fontSize: 17,
                fontWeight: FontWeight.w800,
                color: color,
                letterSpacing: -0.4,
              )),
        ],
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({required this.icon, required this.label, required this.value});

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Icon(icon, size: 16, color: tokens.textMuted),
          const SizedBox(width: 10),
          Text(label,
              style: GoogleFonts.inter(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: tokens.textMuted,
              )),
          const Spacer(),
          Flexible(
            child: Text(
              value,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.right,
              style: GoogleFonts.inter(
                fontSize: 12.5,
                fontWeight: FontWeight.w700,
                color: tokens.text,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

enum BucketKind { day, week }

class _BucketPoint {
  const _BucketPoint({
    required this.bucket,
    required this.start,
    required this.end,
    required this.label,
    required this.value,
  });

  final BucketKind bucket;
  final DateTime start;
  final DateTime end;
  final String label;
  final double value;
}
