import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class StudentHeroCard extends StatelessWidget {
  const StudentHeroCard({
    super.key,
    required this.name,
    required this.centerName,
    this.onPay,
    this.onMessages,
    this.onProfile,
  });

  final String name;
  final String centerName;
  final VoidCallback? onPay;
  final VoidCallback? onMessages;
  final VoidCallback? onProfile;

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
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(child: _QuickAction(icon: Icons.payments_rounded, label: "To‘lovlar", onTap: onPay)),
              const SizedBox(width: 8),
              Expanded(child: _QuickAction(icon: Icons.forum_rounded, label: 'Xabarlar', onTap: onMessages)),
              const SizedBox(width: 8),
              Expanded(child: _QuickAction(icon: Icons.person_rounded, label: 'Profil', onTap: onProfile)),
            ],
          ),
        ],
      ),
    );
  }
}

class _QuickAction extends StatelessWidget {
  const _QuickAction({required this.icon, required this.label, this.onTap});

  final IconData icon;
  final String label;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 6),
          decoration: BoxDecoration(
            color: tokens.isDark
                ? tokens.glassStrong
                : Colors.white.withValues(alpha: 0.65),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: tokens.borderStrong),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 18, color: tokens.primary),
              const SizedBox(height: 4),
              Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: GoogleFonts.inter(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  color: tokens.text,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
