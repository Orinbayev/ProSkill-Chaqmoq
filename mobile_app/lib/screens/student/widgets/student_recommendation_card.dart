import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/widgets/app_card.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Local AI-style summary derived from the student's metrics —
/// no remote call, just heuristic so the card never blocks on network.
class StudentRecommendationCard extends StatelessWidget {
  const StudentRecommendationCard({
    super.key,
    required this.attendancePct,
    required this.score,
    required this.openDebt,
    required this.streakDays,
  });

  final double attendancePct;
  final int score;
  final int openDebt;
  final int streakDays;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final insights = _build(tokens);
    return AppGCard(
      borderColor: tokens.secondary.withValues(alpha: 0.28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Container(
                width: 36,
                height: 36,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  gradient: tokens.violetTealGradient,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.auto_awesome_rounded, color: Colors.white, size: 20),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      'Tavsiya',
                      style: GoogleFonts.inter(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        color: tokens.textMuted,
                        letterSpacing: 1.4,
                      ),
                    ),
                    Text(
                      'Sizning bugungi yo‘riqnomangiz',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: GoogleFonts.inter(
                        fontSize: 13,
                        fontWeight: FontWeight.w800,
                        color: tokens.text,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          for (final i in insights) ...[
            _InsightRow(insight: i),
            const SizedBox(height: 6),
          ],
        ],
      ),
    );
  }

  List<_Insight> _build(StudentTokens tokens) {
    final out = <_Insight>[];
    if (attendancePct >= 0.9) {
      out.add(_Insight(
        icon: Icons.thumb_up_rounded,
        color: tokens.success,
        kind: 'Kuchli tomon',
        text: 'Davomat ${(attendancePct * 100).round()}% — barqaror.',
      ));
    } else if (attendancePct < 0.7 && attendancePct > 0) {
      out.add(_Insight(
        icon: Icons.warning_amber_rounded,
        color: tokens.warning,
        kind: "E'tibor kerak",
        text: 'Davomat ${(attendancePct * 100).round()}% ga tushdi. Darslarni qoldirmang.',
      ));
    }

    if (score >= 200) {
      out.add(_Insight(
        icon: Icons.local_fire_department_rounded,
        color: tokens.primary,
        kind: 'Kuchli tomon',
        text: 'Sizda $score chaqmoq. Reytingda yuqorilashda davom eting.',
      ));
    } else if (score < 50) {
      out.add(_Insight(
        icon: Icons.tips_and_updates_rounded,
        color: tokens.info,
        kind: 'Tavsiya',
        text: "Vazifalarni o‘z vaqtida bajarsangiz, ball tezroq oshadi.",
      ));
    }

    if (openDebt > 0) {
      out.add(_Insight(
        icon: Icons.account_balance_wallet_rounded,
        color: tokens.danger,
        kind: "E'tibor kerak",
        text: "Qarzdorlik bor. To‘lovni vaqtida amalga oshiring.",
      ));
    }

    if (streakDays >= 7) {
      out.add(_Insight(
        icon: Icons.bolt_rounded,
        color: tokens.warning,
        kind: 'Kuchli tomon',
        text: '$streakDays kun ketma-ket faol — ajoyib seriya!',
      ));
    }

    if (out.isEmpty) {
      out.add(_Insight(
        icon: Icons.menu_book_rounded,
        color: tokens.info,
        kind: 'Tavsiya',
        text: 'Bugun bitta yangi mavzuni mustaqil ko‘rib chiqing.',
      ));
    }
    return out.take(3).toList();
  }
}

class _InsightRow extends StatelessWidget {
  const _InsightRow({required this.insight});

  final _Insight insight;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: tokens.tonedSurface(insight.color),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: tokens.tonedBorder(insight.color)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(insight.icon, size: 18, color: insight.color),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  insight.kind,
                  style: GoogleFonts.inter(
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    color: insight.color,
                    letterSpacing: 0.6,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  insight.text,
                  style: GoogleFonts.inter(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: tokens.text,
                    height: 1.35,
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

class _Insight {
  const _Insight({
    required this.icon,
    required this.color,
    required this.kind,
    required this.text,
  });

  final IconData icon;
  final Color color;
  final String kind;
  final String text;
}
