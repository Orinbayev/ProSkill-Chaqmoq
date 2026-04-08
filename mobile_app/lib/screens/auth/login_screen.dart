import 'package:chaqmoq_mobile/core/theme/app_foundation.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/widgets/app_button.dart';
import 'package:chaqmoq_mobile/widgets/app_input_field.dart';
import 'package:chaqmoq_mobile/widgets/chaqmoq_card.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _slugController = TextEditingController();
  final _identifierController = TextEditingController();
  final _passwordController = TextEditingController();

  bool _obscurePassword = true;
  bool _hydratedSlug = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_hydratedSlug) {
      return;
    }
    _hydratedSlug = true;
    final slug = context.read<AuthProvider>().lastUsedSlug.trim();
    if (slug.isNotEmpty) {
      _slugController.text = slug;
    }
  }

  @override
  void dispose() {
    _slugController.dispose();
    _identifierController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    FocusScope.of(context).unfocus();
    if (!_formKey.currentState!.validate()) {
      return;
    }

    final authProvider = context.read<AuthProvider>();
    final success = await authProvider.login(
      slug: _slugController.text.trim(),
      identifier: _identifierController.text.trim(),
      password: _passwordController.text,
    );

    if (!mounted || success) {
      return;
    }

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(authProvider.errorMessage ?? 'Kirish amalga oshmadi'),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      body: DecoratedBox(
        decoration: const BoxDecoration(gradient: AppGradients.darkHero),
        child: SafeArea(
          child: LayoutBuilder(
            builder: (context, constraints) {
              final isWide = constraints.maxWidth >= 900;
              return Center(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(AppSpacing.lg),
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 1040),
                    child: isWide
                        ? Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Expanded(child: _BrandPanel(textTheme: textTheme)),
                              const SizedBox(width: AppSpacing.xl),
                              SizedBox(
                                width: 430,
                                child: _LoginPanel(
                                  formKey: _formKey,
                                  slugController: _slugController,
                                  identifierController: _identifierController,
                                  passwordController: _passwordController,
                                  obscurePassword: _obscurePassword,
                                  isBusy: auth.isBusy,
                                  errorMessage: auth.errorMessage,
                                  onTogglePassword: () {
                                    setState(() {
                                      _obscurePassword = !_obscurePassword;
                                    });
                                  },
                                  onSubmit: _submit,
                                ),
                              ),
                            ],
                          )
                        : Column(
                            children: [
                              _BrandPanel(textTheme: textTheme, compact: true),
                              const SizedBox(height: AppSpacing.lg),
                              _LoginPanel(
                                formKey: _formKey,
                                slugController: _slugController,
                                identifierController: _identifierController,
                                passwordController: _passwordController,
                                obscurePassword: _obscurePassword,
                                isBusy: auth.isBusy,
                                errorMessage: auth.errorMessage,
                                onTogglePassword: () {
                                  setState(() {
                                    _obscurePassword = !_obscurePassword;
                                  });
                                },
                                onSubmit: _submit,
                              ),
                            ],
                          ),
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}

class _BrandPanel extends StatelessWidget {
  const _BrandPanel({required this.textTheme, this.compact = false});

  final TextTheme textTheme;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return ChaqmoqCard(
      gradient: const LinearGradient(
        colors: [Color(0x1FFFFFFF), Color(0x12FFFFFF)],
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
      ),
      padding: const EdgeInsets.all(AppSpacing.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 72,
            height: 72,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.14),
              borderRadius: BorderRadius.circular(AppRadius.lg),
            ),
            alignment: Alignment.center,
            child: const Icon(
              Icons.bolt_rounded,
              size: 40,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: AppSpacing.xl),
          Text(
            'ChaqmoqApp Mobile CRM',
            style: textTheme.headlineMedium?.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.w800,
              height: 1.05,
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          Text(
            'Markaz, jamoa va o\'quvchilar boshqaruvini telefon uchun tayyorlangan professional interfeysda ishlating.',
            style: textTheme.bodyLarge?.copyWith(color: Colors.white70),
          ),
          const SizedBox(height: AppSpacing.xl),
          Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.sm,
            children: const [
              _FeaturePill(label: 'Material 3', icon: Icons.layers_rounded),
              _FeaturePill(
                label: 'Role-based panel',
                icon: Icons.space_dashboard_rounded,
              ),
              _FeaturePill(
                label: 'Haqiqiy API ulanish',
                icon: Icons.sync_rounded,
              ),
            ],
          ),
          if (!compact) ...[
            const SizedBox(height: AppSpacing.xxl),
            const _ValueBlock(
              title: 'Bir kirishda',
              description:
                  'Direktor, menejer, ustoz, o\'quvchi va ota-ona rollari uchun mos oqim.',
            ),
            const SizedBox(height: AppSpacing.lg),
            const _ValueBlock(
              title: 'Qurilmaga mos',
              description:
                  'Kichik telefonlardan katta ekranlargacha xavfsiz va silliq ishlash.',
            ),
          ],
        ],
      ),
    );
  }
}

class _LoginPanel extends StatelessWidget {
  const _LoginPanel({
    required this.formKey,
    required this.slugController,
    required this.identifierController,
    required this.passwordController,
    required this.obscurePassword,
    required this.isBusy,
    required this.errorMessage,
    required this.onTogglePassword,
    required this.onSubmit,
  });

  final GlobalKey<FormState> formKey;
  final TextEditingController slugController;
  final TextEditingController identifierController;
  final TextEditingController passwordController;
  final bool obscurePassword;
  final bool isBusy;
  final String? errorMessage;
  final VoidCallback onTogglePassword;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    return ChaqmoqCard(
      padding: const EdgeInsets.all(AppSpacing.xxl),
      child: Form(
        key: formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Kirish', style: textTheme.headlineSmall),
            const SizedBox(height: AppSpacing.xs),
            Text(
              'Slug, login va parol orqali markazingiz ish maydoniga kiring.',
              style: textTheme.bodyMedium?.copyWith(color: AppColors.muted),
            ),
            const SizedBox(height: AppSpacing.xl),
            AppInputField(
              controller: slugController,
              label: 'Markaz slugi',
              hint: 'masalan: proskill',
              prefixIcon: Icons.apartment_rounded,
              textInputAction: TextInputAction.next,
              validator: (value) {
                if (value == null || value.trim().isEmpty) {
                  return 'Markaz slugi kiritilsin';
                }
                return null;
              },
            ),
            const SizedBox(height: AppSpacing.md),
            AppInputField(
              controller: identifierController,
              label: 'Login / telefon / elektron pochta',
              hint: '+998901234567 yoki user@example.com',
              prefixIcon: Icons.person_outline_rounded,
              textInputAction: TextInputAction.next,
              validator: (value) {
                if (value == null || value.trim().isEmpty) {
                  return 'Login yoki telefon kiriting';
                }
                return null;
              },
            ),
            const SizedBox(height: AppSpacing.md),
            AppInputField(
              controller: passwordController,
              label: 'Parol',
              hint: 'Parolingizni kiriting',
              prefixIcon: Icons.lock_outline_rounded,
              obscureText: obscurePassword,
              onFieldSubmitted: (_) => onSubmit(),
              suffixIcon: IconButton(
                onPressed: onTogglePassword,
                icon: Icon(
                  obscurePassword
                      ? Icons.visibility_off_rounded
                      : Icons.visibility_rounded,
                ),
              ),
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Parolni kiriting';
                }
                return null;
              },
            ),
            if (errorMessage != null) ...[
              const SizedBox(height: AppSpacing.md),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(AppSpacing.md),
                decoration: BoxDecoration(
                  color: AppColors.danger.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(AppRadius.md),
                  border: Border.all(
                    color: AppColors.danger.withValues(alpha: 0.18),
                  ),
                ),
                child: Text(
                  errorMessage!,
                  style: textTheme.bodyMedium?.copyWith(
                    color: AppColors.danger,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
            const SizedBox(height: AppSpacing.xl),
            AppButton(
              label: isBusy ? 'Kirilmoqda...' : 'Tizimga kirish',
              icon: Icons.arrow_forward_rounded,
              loading: isBusy,
              onPressed: onSubmit,
            ),
            const SizedBox(height: AppSpacing.lg),
            Container(
              padding: const EdgeInsets.all(AppSpacing.md),
              decoration: BoxDecoration(
                color: AppColors.surfaceAlt,
                borderRadius: BorderRadius.circular(AppRadius.md),
                border: Border.all(color: AppColors.border),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(
                    Icons.verified_user_rounded,
                    color: AppColors.primary,
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Text(
                      'Tokenlar qurilmada shifrlangan holatda saqlanadi va rolga mos panel avtomatik ochiladi.',
                      style: textTheme.bodySmall?.copyWith(
                        color: AppColors.muted,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _FeaturePill extends StatelessWidget {
  const _FeaturePill({required this.label, required this.icon});

  final String label;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm,
        vertical: AppSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(AppRadius.pill),
        border: Border.all(color: Colors.white24),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: Colors.white),
          const SizedBox(width: AppSpacing.xs),
          Text(
            label,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _ValueBlock extends StatelessWidget {
  const _ValueBlock({required this.title, required this.description});

  final String title;
  final String description;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(AppRadius.lg),
        border: Border.all(color: Colors.white12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              color: Colors.white,
            ),
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            description,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Colors.white70,
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }
}
