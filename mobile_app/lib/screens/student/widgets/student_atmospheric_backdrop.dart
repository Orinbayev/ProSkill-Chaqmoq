import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:flutter/material.dart';

class StudentAtmosphericBackdrop extends StatelessWidget {
  const StudentAtmosphericBackdrop({super.key});

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final tealAlpha = tokens.isDark ? 0.22 : 0.10;
    final violetAlpha = tokens.isDark ? 0.18 : 0.08;
    return IgnorePointer(
      child: Stack(
        children: [
          Positioned(
            top: 70,
            right: -60,
            child: Container(
              width: 220,
              height: 220,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: [
                    tokens.primary.withValues(alpha: tealAlpha),
                    tokens.primary.withValues(alpha: 0),
                  ],
                ),
              ),
            ),
          ),
          Positioned(
            top: 220,
            left: -60,
            child: Container(
              width: 200,
              height: 200,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: [
                    tokens.secondary.withValues(alpha: violetAlpha),
                    tokens.secondary.withValues(alpha: 0),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
