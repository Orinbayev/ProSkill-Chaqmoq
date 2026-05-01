import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Mini bar chart matching primitives.jsx `MiniBars`.
/// Rounded top corners, 6px label below, simple custom paint.
class AppMiniBarChart extends StatelessWidget {
  const AppMiniBarChart({
    super.key,
    required this.values,
    required this.labels,
    this.color = const Color(0xFF3B82F6),
    this.height = 110,
    this.max,
    this.labelColor = const Color(0xFF8090A8),
  });

  final List<double> values;
  final List<String> labels;
  final Color color;
  final double height;
  final double? max;
  final Color labelColor;

  @override
  Widget build(BuildContext context) {
    if (values.isEmpty) return SizedBox(height: height);
    final maxVal = max ?? values.reduce((a, b) => a > b ? a : b);
    final safeMax = maxVal <= 0 ? 1.0 : maxVal;

    return SizedBox(
      height: height,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          for (var i = 0; i < values.length; i++) ...[
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  Expanded(
                    child: LayoutBuilder(
                      builder: (_, constraints) {
                        final ratio = (values[i] / safeMax).clamp(0.0, 1.0);
                        final barHeight = (constraints.maxHeight * ratio).clamp(4.0, constraints.maxHeight);
                        return Align(
                          alignment: Alignment.bottomCenter,
                          child: AnimatedContainer(
                            duration: const Duration(milliseconds: 600),
                            curve: Curves.easeOut,
                            height: barHeight,
                            decoration: BoxDecoration(
                              color: color.withAlpha((0.85 * 255).round()),
                              borderRadius: const BorderRadius.only(
                                topLeft: Radius.circular(6),
                                topRight: Radius.circular(6),
                                bottomLeft: Radius.circular(2),
                                bottomRight: Radius.circular(2),
                              ),
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                  const SizedBox(height: 6),
                  if (i < labels.length)
                    Text(
                      labels[i],
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: GoogleFonts.inter(
                        fontSize: 10,
                        fontWeight: FontWeight.w600,
                        color: labelColor,
                      ),
                    ),
                ],
              ),
            ),
            if (i < values.length - 1) const SizedBox(width: 8),
          ],
        ],
      ),
    );
  }
}
