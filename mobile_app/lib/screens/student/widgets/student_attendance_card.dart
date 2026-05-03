import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/widgets/app_badge.dart';
import 'package:chaqmoq_mobile/widgets/app_card.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class StudentAttendanceCard extends StatelessWidget {
  const StudentAttendanceCard({
    super.key,
    required this.attendancePct,
    this.monthlyTotal,
    this.monthlyAttended,
    this.weeklyAttended,
    this.weeklyTotal,
    this.onTap,
  });

  /// Server-provided attendance ratio in 0..1.
  final double attendancePct;

  /// Optional explicit counts. When null, the card falls back to percent only.
  final int? monthlyTotal;
  final int? monthlyAttended;
  final int? weeklyAttended;
  final int? weeklyTotal;
  final VoidCallback? onTap;

  double get monthlyPct => attendancePct.clamp(0, 1).toDouble();

  String _summaryLine() {
    final mTotal = monthlyTotal ?? 0;
    final mAttended = monthlyAttended ?? 0;
    if (mTotal > 0) {
      return 'Bu oyda $mTotal ta darsdan $mAttended tasi o‘tildi';
    }
    return 'Bu oy uchun dars rejasi belgilanmagan';
  }

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final tone = monthlyPct >= 0.85
        ? tokens.success
        : monthlyPct >= 0.65
            ? tokens.warning
            : tokens.primary;
    return AppGCard(
      onTap: onTap,
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
                  color: tokens.tonedSurface(tokens.primary),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(Icons.fact_check_rounded, color: tokens.primary, size: 20),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Davomat',
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                    color: tokens.text,
                  ),
                ),
              ),
              if ((monthlyTotal ?? 0) > 0)
                AppBadge(
                  label: '${monthlyAttended ?? 0}/${monthlyTotal!}',
                  tone: AppBadgeTone.teal,
                  dark: tokens.isDark,
                ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            _summaryLine(),
            style: GoogleFonts.inter(
              fontSize: 12.5,
              fontWeight: FontWeight.w700,
              color: tokens.text,
            ),
          ),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(100),
            child: LinearProgressIndicator(
              value: monthlyPct,
              minHeight: 8,
              backgroundColor: tokens.glassStrong,
              valueColor: AlwaysStoppedAnimation<Color>(tone),
            ),
          ),
          if ((weeklyTotal ?? 0) > 0 || (monthlyTotal ?? 0) > 0) ...[
            const SizedBox(height: 10),
            Row(
              children: [
                if ((weeklyTotal ?? 0) > 0)
                  Expanded(
                    child: _MicroStat(
                      label: 'Bu hafta',
                      value: '${weeklyAttended ?? 0}/${weeklyTotal!}',
                    ),
                  ),
                if ((weeklyTotal ?? 0) > 0 && (monthlyTotal ?? 0) > 0)
                  const SizedBox(width: 10),
                if ((monthlyTotal ?? 0) > 0)
                  Expanded(
                    child: _MicroStat(
                      label: 'Bu oy',
                      value: '${monthlyAttended ?? 0}/${monthlyTotal!}',
                    ),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _MicroStat extends StatelessWidget {
  const _MicroStat({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: tokens.glass,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: tokens.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
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
                fontSize: 13,
                fontWeight: FontWeight.w800,
                color: tokens.text,
              )),
        ],
      ),
    );
  }
}
