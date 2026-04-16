import 'package:chaqmoq_mobile/core/theme/app_colors.dart';
import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/app_text_styles.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/screens/auth/login_screen.dart';
import 'package:chaqmoq_mobile/widgets/app_button.dart';
import 'package:chaqmoq_mobile/widgets/glass_card.dart';
import 'package:chaqmoq_mobile/widgets/role_badge.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  String _language = 'UZ';

  Future<void> _logout() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text('Chiqishni tasdiqlang'),
          content: const Text('Hisobdan chiqishni xohlaysizmi?'),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: const Text('Bekor qilish'),
            ),
            TextButton(
              onPressed: () => Navigator.of(context).pop(true),
              child: const Text('Chiqish'),
            ),
          ],
        );
      },
    );
    if (confirmed != true || !mounted) {
      return;
    }
    await context.read<AuthProvider>().logout();
    if (!mounted) {
      return;
    }
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute<void>(builder: (_) => const LoginScreen()),
      (route) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().user;
    if (user == null) {
      return const SizedBox.shrink();
    }
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.xl),
      children: [
        GlassCard(
          child: Column(
            children: [
              CircleAvatar(
                radius: 40,
                backgroundColor: AppColors.primary.withValues(alpha: 0.18),
                child: Text(Formatters.initials(user.fullName), style: AppTextStyles.title),
              ),
              const SizedBox(height: AppSpacing.lg),
              Text(user.fullName, style: AppTextStyles.headline, textAlign: TextAlign.center),
              const SizedBox(height: AppSpacing.sm),
              RoleBadge(role: user.role),
              const SizedBox(height: AppSpacing.sm),
              Text(user.center?.name ?? 'Markaz nomi yo\'q', style: AppTextStyles.subtitle),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.xl),
        _InfoTile(label: 'Telefon', value: user.phone.isEmpty ? 'Mavjud emas' : user.phone),
        _InfoTile(label: 'Email', value: user.email.isEmpty ? 'Mavjud emas' : user.email),
        _InfoTile(label: 'Joined date', value: Formatters.date(user.joinedDate)),
        const SizedBox(height: AppSpacing.xl),
        GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Sozlamalar', style: AppTextStyles.title),
              const SizedBox(height: AppSpacing.lg),
              Row(
                children: [
                  Expanded(child: Text('Language (UZ/RU/EN)', style: AppTextStyles.body)),
                  DropdownButton<String>(
                    value: _language,
                    items: const [
                      DropdownMenuItem(value: 'UZ', child: Text('UZ')),
                      DropdownMenuItem(value: 'RU', child: Text('RU')),
                      DropdownMenuItem(value: 'EN', child: Text('EN')),
                    ],
                    onChanged: (value) {
                      if (value != null) {
                        setState(() => _language = value);
                      }
                    },
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.lg),
              Row(
                children: [
                  Expanded(child: Text('Dark mode', style: AppTextStyles.body)),
                  const Switch(value: true, onChanged: null),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.xl),
        AppButton(
          label: 'Logout',
          onPressed: _logout,
          isDestructive: true,
        ),
      ],
    );
  }
}

class _InfoTile extends StatelessWidget {
  const _InfoTile({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.lg),
      child: GlassCard(
        child: Row(
          children: [
            Expanded(child: Text(label, style: AppTextStyles.subtitle)),
            Expanded(child: Text(value, style: AppTextStyles.body, textAlign: TextAlign.right)),
          ],
        ),
      ),
    );
  }
}
