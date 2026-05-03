import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/widgets/app_card.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class StudentRatingCard extends StatelessWidget {
  const StudentRatingCard({
    super.key,
    required this.score,
    required this.rank,
    this.totalRanked = 0,
    this.onTap,
  });

  final int score;
  final int rank;
  final int totalRanked;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final hasData = score > 0 || rank > 0;
    return AppGCard(
      onTap: onTap,
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
                      crossAxisAlignment: CrossAxisAlignment.center,
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
                        const SizedBox(width: 4),
                        Icon(Icons.bolt_rounded, color: tokens.primary, size: 20),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        Flexible(
                          child: Text(
                            _rankLabel(),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: GoogleFonts.inter(
                              fontSize: 12.5,
                              fontWeight: FontWeight.w800,
                              color: rank > 0 ? tokens.primary : tokens.textMuted,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    _DetailHint(tokens: tokens),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  String _rankLabel() {
    if (rank <= 0) return 'Reyting tayyor emas';
    return 'Umumiy reyting: $rank-o‘rin';
  }
}

class _DetailHint extends StatelessWidget {
  const _DetailHint({required this.tokens});

  final StudentTokens tokens;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: tokens.tonedSurface(tokens.primary),
        borderRadius: BorderRadius.circular(100),
        border: Border.all(color: tokens.primary.withValues(alpha: 0.4)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            'Batafsil',
            style: GoogleFonts.inter(
              fontSize: 10.5,
              fontWeight: FontWeight.w800,
              color: tokens.primary,
              letterSpacing: 0.4,
            ),
          ),
          const SizedBox(width: 2),
          Icon(Icons.chevron_right_rounded, size: 14, color: tokens.primary),
        ],
      ),
    );
  }
}
