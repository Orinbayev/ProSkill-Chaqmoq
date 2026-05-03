import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class StudentHeroCard extends StatelessWidget {
  const StudentHeroCard({
    super.key,
    required this.name,
    required this.centerName,
    this.isActive = false,
    this.isArchived = false,
  });

  final String name;
  final String centerName;
  final bool isActive;
  final bool isArchived;

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
          Row(
            children: [
              Expanded(
                child: Text(
                  "O‘QUVCHI PANELI",
                  style: GoogleFonts.inter(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    color: tokens.primary,
                    letterSpacing: 1.6,
                  ),
                ),
              ),
              _StatusBadge(isActive: isActive, isArchived: isArchived),
            ],
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

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.isActive, required this.isArchived});

  final bool isActive;
  final bool isArchived;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final active = isActive && !isArchived;
    final color = active ? tokens.success : tokens.danger;
    final label = active ? 'Faol' : 'Nofaol';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: tokens.tonedSurface(color),
        borderRadius: BorderRadius.circular(100),
        border: Border.all(color: color.withValues(alpha: 0.55), width: 1),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 7,
            height: 7,
            decoration: BoxDecoration(
              color: color,
              shape: BoxShape.circle,
              boxShadow: active
                  ? [
                      BoxShadow(
                        color: color.withValues(alpha: 0.6),
                        blurRadius: 6,
                      ),
                    ]
                  : null,
            ),
          ),
          const SizedBox(width: 6),
          Text(
            label,
            style: GoogleFonts.inter(
              fontSize: 11,
              fontWeight: FontWeight.w800,
              color: color,
              letterSpacing: 0.3,
            ),
          ),
        ],
      ),
    );
  }
}
