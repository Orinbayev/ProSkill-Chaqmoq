import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/screens/student/widgets/theme_toggle_button.dart';
import 'package:chaqmoq_mobile/widgets/app_parent_app_bar.dart';
import 'package:chaqmoq_mobile/widgets/brand_logo.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class StudentDashboardHeader extends StatelessWidget {
  const StudentDashboardHeader({
    super.key,
    required this.unread,
    required this.onBell,
  });

  final int unread;
  final VoidCallback onBell;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Row(
      children: [
        const BrandLogo(size: 40, radius: 12),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'ChaqmoqApp',
                style: GoogleFonts.inter(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: tokens.textMuted,
                ),
              ),
              const SizedBox(height: 1),
              Text(
                "O‘quvchi paneli",
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: GoogleFonts.inter(
                  fontSize: 14,
                  fontWeight: FontWeight.w800,
                  color: tokens.text,
                ),
              ),
            ],
          ),
        ),
        const ThemeToggleButton(),
        const SizedBox(width: 8),
        AppStudentIconButton(
          icon: Icons.notifications_outlined,
          onTap: onBell,
          badgeCount: unread,
        ),
      ],
    );
  }
}
