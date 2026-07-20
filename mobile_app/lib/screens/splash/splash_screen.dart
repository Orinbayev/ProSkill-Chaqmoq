import 'package:chaqmoq_mobile/core/design/ds_colors.dart';
import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/app_text_styles.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/screens/auth/login_screen.dart';
import 'package:chaqmoq_mobile/screens/shell/app_shell.dart';
import 'package:chaqmoq_mobile/widgets/brand_logo.dart';
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
    if (!mounted) return;
    await context.read<AuthProvider>().restoreSession();
    if (!mounted) return;
    final auth = context.read<AuthProvider>();
    final target = auth.isAuthenticated ? const AppShell() : const LoginScreen();
    Navigator.of(context).pushReplacement(
      MaterialPageRoute<void>(builder: (_) => target),
    );
  }

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Scaffold(
      backgroundColor: ds.bg,
      body: SafeArea(
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const BrandLogoHero(size: 120)
                  .animate(onPlay: (c) => c.repeat())
                  .scale(
                    begin: const Offset(0.96, 0.96),
                    end: const Offset(1.03, 1.03),
                    duration: 1200.ms,
                    curve: Curves.easeInOut,
                  ),
              const SizedBox(height: AppSpacing.xl),
              Text(
                'ChaqmoqApp',
                style: AppTextStyles.display.copyWith(
                  fontSize: 28,
                  color: ds.textPrimary,
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              Text(
                'Ta’lim boshqaruvi platformasi',
                style: AppTextStyles.subtitle.copyWith(color: ds.textMuted),
              ),
            ],
          )
              .animate()
              .fadeIn(duration: 450.ms)
              .scale(begin: const Offset(0.96, 0.96), end: const Offset(1, 1)),
        ),
      ),
    );
  }
}
