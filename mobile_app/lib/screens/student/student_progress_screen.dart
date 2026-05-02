import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/widgets/app_state_widgets.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class StudentProgressScreen extends StatelessWidget {
  const StudentProgressScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Scaffold(
      backgroundColor: tokens.bg,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(18, 8, 18, 110),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Progress',
                style: GoogleFonts.inter(
                  fontSize: 19,
                  fontWeight: FontWeight.w800,
                  color: tokens.text,
                  letterSpacing: -0.2,
                ),
              ),
              const SizedBox(height: 14),
              Expanded(
                child: AppEmptyState(
                  dark: tokens.isDark,
                  title: 'Statistika tayyorlanmoqda',
                  subtitle:
                      'O‘qituvchi izohlari va fanlar bo‘yicha o‘sish dinamikasi shu yerga keladi.',
                  icon: Icons.insights_outlined,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
