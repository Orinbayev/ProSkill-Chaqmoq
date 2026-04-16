import 'package:chaqmoq_mobile/core/theme/app_colors.dart';
import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/app_text_styles.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/screens/shell/app_shell.dart';
import 'package:chaqmoq_mobile/widgets/app_button.dart';
import 'package:chaqmoq_mobile/widgets/app_input.dart';
import 'package:chaqmoq_mobile/widgets/glass_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:provider/provider.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final TextEditingController _slugController = TextEditingController();
  final TextEditingController _usernameController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();

  bool _obscureText = true;

  @override
  void initState() {
    super.initState();
    _slugController.text = 'proskill';
  }

  @override
  void dispose() {
    _slugController.dispose();
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final auth = context.read<AuthProvider>();
    final success = await auth.login(
      slug: _slugController.text.trim(),
      username: _usernameController.text.trim(),
      password: _passwordController.text,
    );
    if (!mounted || !success) {
      return;
    }
    Navigator.of(context).pushReplacement(
      MaterialPageRoute<void>(builder: (_) => const AppShell()),
    );
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    return Scaffold(
      resizeToAvoidBottomInset: true,
      body: DecoratedBox(
        decoration: const BoxDecoration(gradient: AppColors.appBackground),
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.xl),
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 420),
                child: Column(
                  children: [
                    const SizedBox(height: AppSpacing.xxl),
                    GlassCard(
                      padding: const EdgeInsets.all(AppSpacing.lg),
                      child: SizedBox(
                        width: 72,
                        height: 72,
                        child: const Icon(
                          Icons.bolt_rounded,
                          size: 42,
                          color: AppColors.primary,
                        ),
                      ),
                    ),
                    const SizedBox(height: AppSpacing.xl),
                    Text('ChaqmoqApp', style: AppTextStyles.display),
                    const SizedBox(height: AppSpacing.sm),
                    Text('CRM tizimiga kiring', style: AppTextStyles.subtitle),
                    const SizedBox(height: AppSpacing.xxl),
                    AppInput(
                      controller: _slugController,
                      label: 'Markaz slugi',
                      hint: 'proskill',
                      prefixIcon: Icons.apartment_rounded,
                      textInputAction: TextInputAction.next,
                    ),
                    const SizedBox(height: AppSpacing.lg),
                    AppInput(
                      controller: _usernameController,
                      label: 'Login / Telefon',
                      hint: '+998901234567',
                      prefixIcon: Icons.person_rounded,
                      keyboardType: TextInputType.emailAddress,
                      textInputAction: TextInputAction.next,
                    ),
                    const SizedBox(height: AppSpacing.lg),
                    AppInput(
                      controller: _passwordController,
                      label: 'Parol',
                      hint: '••••••••',
                      prefixIcon: Icons.lock_rounded,
                      obscureText: _obscureText,
                      suffixIcon: IconButton(
                        onPressed: () {
                          setState(() => _obscureText = !_obscureText);
                        },
                        icon: Icon(
                          _obscureText
                              ? Icons.visibility_rounded
                              : Icons.visibility_off_rounded,
                        ),
                      ),
                      textInputAction: TextInputAction.done,
                    ),
                    const SizedBox(height: AppSpacing.xl),
                    AppButton(
                      label: 'Tizimga kirish',
                      onPressed: _submit,
                      isLoading: auth.state == ViewState.loading,
                    ),
                    AnimatedSwitcher(
                      duration: 250.ms,
                      child: auth.errorMessage == null
                          ? const SizedBox(height: AppSpacing.lg)
                          : Padding(
                              key: ValueKey(auth.errorMessage),
                              padding: const EdgeInsets.only(top: AppSpacing.lg),
                              child: GlassCard(
                                child: Row(
                                  children: [
                                    const Icon(Icons.error_outline_rounded, color: AppColors.danger),
                                    const SizedBox(width: AppSpacing.md),
                                    Expanded(
                                      child: Text(
                                        auth.errorMessage!,
                                        style: AppTextStyles.body.copyWith(color: AppColors.danger),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                    ),
                    const SizedBox(height: AppSpacing.xl),
                    GlassCard(
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Icon(Icons.verified_user_rounded, color: AppColors.secondary),
                          const SizedBox(width: AppSpacing.md),
                          Expanded(
                            child: Text(
                              'Kirish ma\'lumotlari himoyalangan kanal orqali yuboriladi. Qurilmangiz faqat ushbu markaz sessiyasi uchun ishlatiladi.',
                              style: AppTextStyles.subtitle,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ).animate().fadeIn(duration: 450.ms).slideY(begin: 0.08, end: 0),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
