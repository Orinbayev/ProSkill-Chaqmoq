import 'package:chaqmoq_mobile/core/theme/app_colors.dart';
import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/app_text_styles.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/screens/auth/login_screen.dart';
import 'package:chaqmoq_mobile/screens/shell/app_shell.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:provider/provider.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    await Future<void>.delayed(const Duration(seconds: 2));
    if (!mounted) {
      return;
    }
    await context.read<AuthProvider>().restoreSession();
    if (!mounted) {
      return;
    }
    final auth = context.read<AuthProvider>();
    final target = auth.isAuthenticated ? const AppShell() : const LoginScreen();
    Navigator.of(context).pushReplacement(
      MaterialPageRoute<void>(builder: (_) => target),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: DecoratedBox(
        decoration: const BoxDecoration(color: AppColors.background),
        child: SafeArea(
          child: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 112,
                  height: 112,
                  decoration: BoxDecoration(
                    color: AppColors.glassStrong,
                    borderRadius: BorderRadius.circular(AppRadius.xl),
                    border: Border.all(color: AppColors.border),
                    boxShadow: const [
                      BoxShadow(
                        color: AppColors.glowPrimary,
                        blurRadius: 28,
                        offset: Offset(0, 12),
                      ),
                    ],
                  ),
                  alignment: Alignment.center,
                  child: const Icon(
                    Icons.bolt_rounded,
                    size: 80,
                    color: AppColors.primary,
                  )
                      .animate(onPlay: (controller) => controller.repeat())
                      .scale(
                        begin: const Offset(0.94, 0.94),
                        end: const Offset(1.04, 1.04),
                        duration: 1200.ms,
                        curve: Curves.easeInOut,
                      )
                      .fade(
                        begin: 0.6,
                        end: 1,
                        duration: 1200.ms,
                      ),
                ),
                const SizedBox(height: AppSpacing.xl),
                Text('ChaqmoqApp', style: AppTextStyles.display.copyWith(fontSize: 28)),
                const SizedBox(height: AppSpacing.sm),
                Text('CRM Platform', style: AppTextStyles.subtitle),
              ],
            )
                .animate()
                .fadeIn(duration: 450.ms)
                .scale(begin: const Offset(0.96, 0.96), end: const Offset(1, 1)),
          ),
        ),
      ),
    );
  }
}
