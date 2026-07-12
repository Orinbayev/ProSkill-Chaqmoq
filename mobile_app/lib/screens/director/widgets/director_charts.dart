import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../../../core/design/ds_colors.dart';
import '../../../core/design/ds_typography.dart';

/// Daromad — chiziqli grafik (soha to'ldirilgan).
class RevenueLineChart extends StatelessWidget {
  const RevenueLineChart({super.key, required this.values, required this.months});
  final List<double> values;
  final List<String> months;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    final spots = [for (final (i, v) in values.indexed) FlSpot(i.toDouble(), v)];
    final maxY = (values.reduce((a, b) => a > b ? a : b) * 1.15);

    return LineChart(
      LineChartData(
        minY: 0,
        maxY: maxY,
        gridData: const FlGridData(show: false),
        borderData: FlBorderData(show: false),
        titlesData: FlTitlesData(
          topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          leftTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              interval: 2,
              reservedSize: 22,
              getTitlesWidget: (value, meta) {
                final i = value.round();
                if (i < 0 || i >= months.length) return const SizedBox.shrink();
                return Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(months[i], style: DsType.micro(ds.textFaint)),
                );
              },
            ),
          ),
        ),
        lineTouchData: const LineTouchData(enabled: false),
        lineBarsData: [
          LineChartBarData(
            spots: spots,
            isCurved: true,
            curveSmoothness: 0.28,
            color: ds.primary,
            barWidth: 3,
            dotData: const FlDotData(show: false),
            belowBarData: BarAreaData(
              show: true,
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [ds.primary.withValues(alpha: 0.22), ds.primary.withValues(alpha: 0.0)],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Daromad vs xarajat — guruhlangan ustunli grafik.
class IncomeExpenseChart extends StatelessWidget {
  const IncomeExpenseChart({super.key, required this.data, required this.months});
  final List<(double, double)> data;
  final List<String> months;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    final maxY = data.map((e) => e.$1).reduce((a, b) => a > b ? a : b) * 1.2;

    return BarChart(
      BarChartData(
        maxY: maxY,
        alignment: BarChartAlignment.spaceAround,
        gridData: const FlGridData(show: false),
        borderData: FlBorderData(show: false),
        barTouchData: BarTouchData(enabled: false),
        titlesData: FlTitlesData(
          topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          leftTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 22,
              getTitlesWidget: (value, meta) {
                final i = value.round();
                if (i < 0 || i >= months.length) return const SizedBox.shrink();
                return Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(months[i], style: DsType.micro(ds.textFaint)),
                );
              },
            ),
          ),
        ),
        barGroups: [
          for (final (i, pair) in data.indexed)
            BarChartGroupData(
              x: i,
              barsSpace: 4,
              barRods: [
                BarChartRodData(toY: pair.$1, color: ds.primary, width: 8, borderRadius: BorderRadius.circular(3)),
                BarChartRodData(toY: pair.$2, color: ds.warning, width: 8, borderRadius: BorderRadius.circular(3)),
              ],
            ),
        ],
      ),
    );
  }
}

/// Grafik ostidagi izoh (legend) nuqtasi.
class ChartLegendDot extends StatelessWidget {
  const ChartLegendDot({super.key, required this.color, required this.label});
  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 10, height: 10, decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(3))),
        const SizedBox(width: 6),
        Text(label, style: DsType.small(ds.textMuted)),
      ],
    );
  }
}
