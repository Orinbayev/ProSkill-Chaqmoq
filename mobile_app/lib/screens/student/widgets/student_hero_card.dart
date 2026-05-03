import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class StudentHeroCard extends StatelessWidget {
  const StudentHeroCard({
    super.key,
    required this.name,
    required this.centerName,
  });

  final String name;
  final String centerName;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final firstName = name.split(RegExp(r'\s+')).first;
    final subtitle = centerName.isEmpty ? 'Markaz topilmadi' : centerName;
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: tokens.heroGradient,
        borderRadius: BorderRadius.circular(AppRadius.xxl),
        border: Border.all(color: tokens.primary.withValues(alpha: 0.28)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            "O‘QUVCHI PANELI",
            style: GoogleFonts.inter(
              fontSize: 11,
              fontWeight: FontWeight.w700,
              color: tokens.primary,
              letterSpacing: 1.6,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'Salom, $firstName 👋',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: GoogleFonts.inter(
              fontSize: 22,
              fontWeight: FontWeight.w800,
              color: tokens.text,
              letterSpacing: -0.4,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            subtitle,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: GoogleFonts.inter(
              fontSize: 12.5,
              fontWeight: FontWeight.w500,
              color: tokens.textMuted,
            ),
          ),
        ],
      ),
    );
  }
}
