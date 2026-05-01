import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

/// Mini line chart matching primitives.jsx `MiniLine`.
/// Gradient fill (28%→0%), 2.5px stroke, end-point dot.
class AppMiniLineChart extends StatelessWidget {
  const AppMiniLineChart({
    super.key,
    required this.values,
    this.color = const Color(0xFF3B82F6),
    this.height = 80,
    this.fill = true,
    this.minY,
    this.maxY,
  });

  final List<double> values;
  final Color color;
  final double height;
  final bool fill;
  final double? minY;
  final double? maxY;

  @override
  Widget build(BuildContext context) {
    if (values.isEmpty) {
      return SizedBox(height: height);
    }

    final spots = <FlSpot>[
      for (var i = 0; i < values.length; i++) FlSpot(i.toDouble(), values[i]),
    ];

    final autoMin = values.reduce((a, b) => a < b ? a : b);
    final autoMax = values.reduce((a, b) => a > b ? a : b);
    final span = (autoMax - autoMin).abs();
    final padding = span < 0.0001 ? 1.0 : span * 0.18;
    final loY = minY ?? autoMin - padding;
    final hiY = maxY ?? autoMax + padding;

    return SizedBox(
      height: height,
      child: LineChart(
        LineChartData(
          minX: 0,
          maxX: (values.length - 1).toDouble(),
          minY: loY,
          maxY: hiY,
          clipData: const FlClipData.all(),
          lineTouchData: const LineTouchData(enabled: false),
          gridData: const FlGridData(show: false),
          borderData: FlBorderData(show: false),
          titlesData: const FlTitlesData(show: false),
          lineBarsData: [
            LineChartBarData(
              spots: spots,
              isCurved: true,
              preventCurveOverShooting: true,
              color: color,
              barWidth: 2.5,
              isStrokeCapRound: true,
              isStrokeJoinRound: true,
              dotData: FlDotData(
                show: true,
                checkToShowDot: (spot, _) => spot.x == spots.last.x,
                getDotPainter: (spot, percent, barData, index) {
                  return FlDotCirclePainter(
                    radius: 3.5,
                    color: color,
                    strokeWidth: 2,
                    strokeColor: Colors.white,
                  );
                },
              ),
              belowBarData: BarAreaData(
                show: fill,
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [color.withAlpha((0.28 * 255).round()), color.withAlpha(0)],
                ),
              ),
            ),
          ],
        ),
        duration: const Duration(milliseconds: 750),
      ),
    );
  }
}
