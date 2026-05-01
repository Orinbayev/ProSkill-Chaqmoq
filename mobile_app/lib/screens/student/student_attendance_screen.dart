import 'package:chaqmoq_mobile/core/theme/student_colors.dart';
import 'package:chaqmoq_mobile/widgets/app_state_widgets.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Student Davomat — placeholder while a dedicated student-facing
/// attendance API is not yet wired. Renders the dark-glass surface so
/// the bottom nav navigation feels consistent.
class StudentAttendanceScreen extends StatelessWidget {
  const StudentAttendanceScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: StudentColors.bg,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(18, 8, 18, 110),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Davomat',
                style: GoogleFonts.inter(
                  fontSize: 19,
                  fontWeight: FontWeight.w800,
                  color: StudentColors.text,
                  letterSpacing: -0.2,
                ),
              ),
              const SizedBox(height: 14),
              const Expanded(
                child: AppEmptyState(
                  dark: true,
                  title: 'Davomat tez orada',
                  subtitle:
                      'Kunlik darslar va kelmagan kunlar shu yerda jonli ko‘rsatiladi.',
                  icon: Icons.fact_check_outlined,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
