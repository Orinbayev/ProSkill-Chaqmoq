import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/widgets/app_badge.dart';
import 'package:chaqmoq_mobile/widgets/app_card.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class StudentRatingCard extends StatelessWidget {
  const StudentRatingCard({
    super.key,
    required this.score,
    required this.rank,
    this.nextTarget,
  });

  final int score;
  final int rank;
  final int? nextTarget;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final hasData = score > 0 || rank > 0;
    final target = nextTarget ?? _suggestNextTarget(score);
    final remaining = (target - score).clamp(0, 1 << 30);
    return AppGCard(
      borderColor: tokens.secondary.withValues(alpha: 0.32),
      child: Stack(
        clipBehavior: Clip.hardEdge,
        children: [
          Positioned(
            top: -30,
            right: -30,
            child: IgnorePointer(
              child: Container(
                width: 110,
                height: 110,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [
                      tokens.secondary.withValues(alpha: 0.32),
                      tokens.secondary.withValues(alpha: 0),
                    ],
                  ),
                ),
              ),
            ),
          ),
          Row(
            children: [
              Container(
                width: 64,
                height: 64,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: tokens.violetTealGradient,
                  boxShadow: [
                    BoxShadow(
                      color: tokens.secondary.withValues(alpha: 0.35),
                      blurRadius: 24,
                      offset: const Offset(0, 10),
                    ),
                  ],
                ),
                child: const Icon(Icons.bolt_rounded, color: Colors.white, size: 32),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      'CHAQMOQ REYTING',
                      style: GoogleFonts.inter(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        color: tokens.textMuted,
                        letterSpacing: 1.6,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.baseline,
                      textBaseline: TextBaseline.alphabetic,
                      children: [
                        Text(
                          hasData ? '$score' : '—',
                          style: GoogleFonts.inter(
                            fontSize: 26,
                            fontWeight: FontWeight.w800,
                            color: tokens.text,
                            letterSpacing: -0.6,
                          ),
                        ),
                        const SizedBox(width: 6),
                        Text(
                          'ball',
                          style: GoogleFonts.inter(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: tokens.textMuted,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Wrap(
                      spacing: 6,
                      runSpacing: 4,
                      children: [
                        if (rank > 0)
                          AppBadge(
                            label: '#$rank reyting',
                            tone: AppBadgeTone.success,
                            dark: tokens.isDark,
                          )
                        else
                          AppBadge(
                            label: 'Reyting tayyor emas',
                            tone: AppBadgeTone.neutral,
                            dark: tokens.isDark,
                          ),
                        if (hasData && remaining > 0)
                          AppBadge(
                            label: '+$remaining → $target',
                            tone: AppBadgeTone.violet,
                            dark: tokens.isDark,
                          ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  static int _suggestNextTarget(int score) {
    if (score < 100) return 100;
    if (score < 250) return 250;
    if (score < 500) return 500;
    if (score < 1000) return 1000;
    return ((score ~/ 500) + 1) * 500;
  }
}
