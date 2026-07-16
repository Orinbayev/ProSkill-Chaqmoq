import 'package:chaqmoq_mobile/core/theme/app_colors.dart';
import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/app_text_styles.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/core/utils/role_panel_style.dart';
import 'package:chaqmoq_mobile/providers/app_preferences_provider.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/screens/profile/about_app_screen.dart';
import 'package:chaqmoq_mobile/screens/profile/help_support_screen.dart';
import 'package:chaqmoq_mobile/screens/profile/language_screen.dart';
import 'package:chaqmoq_mobile/screens/profile/notification_settings_screen.dart';
import 'package:chaqmoq_mobile/screens/profile/theme_screen.dart';
import 'package:chaqmoq_mobile/widgets/role_badge.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class AccountScreen extends StatelessWidget {
  const AccountScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final preferences = context.watch<AppPreferencesProvider>();
    final user = auth.user;
    if (user == null) {
      return const SizedBox.shrink();
    }

    final panel = RolePanelStyles.of(user.role);

    return DecoratedBox(
      decoration: const BoxDecoration(gradient: AppColors.appBackground),
      child: RefreshIndicator(
        onRefresh: () async {},
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(
            parent: BouncingScrollPhysics(),
          ),
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.xl,
            AppSpacing.xl,
            AppSpacing.xl,
            32,
          ),
          children: [
            _AccountHeroCard(
              fullName: user.fullName,
              role: user.role,
              phone: user.phone,
              panel: panel,
              isOffline: auth.isOfflineMode,
            ),
            const SizedBox(height: AppSpacing.xl),
            _AccountInfoCard(
              centerName: user.center?.name ?? 'Markaz belgilanmagan',
              email: user.email,
              phone: user.phone,
              joinedDate: user.joinedDate,
            ),
            const SizedBox(height: AppSpacing.xl),
            _ActionSection(
              title: 'Sozlamalar',
              children: [
                _ActionTile(
                  icon: Icons.language_rounded,
                  title: 'Til',
                  subtitle: preferences.languageLabel,
                  onTap: () => _push(context, const LanguageScreen()),
                ),
                _ActionTile(
                  icon: Icons.palette_outlined,
                  title: 'Mavzu',
                  subtitle: preferences.themeLabel,
                  onTap: () => _push(context, const ThemeScreen()),
                ),
                _ActionTile(
                  icon: Icons.notifications_none_rounded,
                  title: 'Bildirishnomalar',
                  subtitle: 'Shaxsiy xabar sozlamalari',
                  onTap: () =>
                      _push(context, const NotificationSettingsScreen()),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.lg),
            _ActionSection(
              title: 'Yordam',
              children: [
                _ActionTile(
                  icon: Icons.help_outline_rounded,
                  title: 'Yordam va qo‘llab-quvvatlash',
                  subtitle: 'Savollar va tezkor yordam',
                  onTap: () => _push(context, const HelpSupportScreen()),
                ),
                _ActionTile(
                  icon: Icons.info_outline_rounded,
                  title: 'Ilova haqida',
                  subtitle: 'Versiya va umumiy ma’lumot',
                  onTap: () => _push(context, const AboutAppScreen()),
                ),
                _ActionTile(
                  icon: Icons.logout_rounded,
                  title: 'Hisobdan chiqish',
                  subtitle: 'Joriy sessiyani yakunlash',
                  iconColor: AppColors.danger,
                  onTap: () => _logout(context),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  static Future<void> _push(BuildContext context, Widget screen) {
    return Navigator.of(
      context,
    ).push(MaterialPageRoute<void>(builder: (_) => screen));
  }

  static Future<void> _logout(BuildContext context) async {
    final shouldLogout = await showDialog<bool>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('Hisobdan chiqish'),
          content: const Text(
            'Joriy qurilmadagi sessiya yakunlanadi. Davom etilsinmi?',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              child: const Text('Bekor qilish'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(dialogContext).pop(true),
              child: const Text('Chiqish'),
            ),
          ],
        );
      },
    );

    if (shouldLogout != true || !context.mounted) {
      return;
    }

    await context.read<AuthProvider>().logout();
    if (!context.mounted) {
      return;
    }

    // AuthGate (ildiz route) reaktiv ravishda logindan keyin bosh sahifaga
    // o'tkazadi. pushAndRemoveUntil AuthGate'ni yo'q qilib yuborardi — natijada
    // qayta login qilinganda dasturga kirmasdi (faqat restartda kirardi).
    Navigator.of(context).popUntil((route) => route.isFirst);
  }
}

class _AccountHeroCard extends StatelessWidget {
  const _AccountHeroCard({
    required this.fullName,
    required this.role,
    required this.phone,
    required this.panel,
    required this.isOffline,
  });

  final String fullName;
  final String role;
  final String phone;
  final RolePanelStyle panel;
  final bool isOffline;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.xl),
      decoration: BoxDecoration(
        gradient: panel.heroGradient,
        borderRadius: BorderRadius.circular(AppRadius.xl),
        border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
        boxShadow: const [
          BoxShadow(
            color: AppColors.shadow,
            blurRadius: 28,
            offset: Offset(0, 14),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  color: panel.accentSoft,
                  borderRadius: BorderRadius.circular(18),
                ),
                child: Icon(panel.icon, color: panel.accent, size: 28),
              ),
              const Spacer(),
              RoleBadge(role: role),
            ],
          ),
          const SizedBox(height: AppSpacing.xl),
          Text(
            panel.panelLabel,
            style: AppTextStyles.label.copyWith(color: panel.accentSoft),
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(fullName, style: AppTextStyles.headline),
          const SizedBox(height: AppSpacing.sm),
          Text(
            phone.trim().isEmpty ? 'Telefon raqam kiritilmagan' : phone,
            style: AppTextStyles.subtitle,
          ),
          if (isOffline) ...[
            const SizedBox(height: AppSpacing.lg),
            Container(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.md,
                vertical: AppSpacing.sm,
              ),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(AppRadius.lg),
              ),
              child: Row(
                children: [
                  const Icon(
                    Icons.cloud_off_rounded,
                    color: Color(0xFFFAC858),
                    size: 18,
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Text(
                      'Hozir ilova offline rejimda ishlayapti. Saqlangan ma’lumotlar ko‘rsatilmoqda.',
                      style: AppTextStyles.bodySmall.copyWith(
                        color: AppColors.textPrimary,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _AccountInfoCard extends StatelessWidget {
  const _AccountInfoCard({
    required this.centerName,
    required this.email,
    required this.phone,
    required this.joinedDate,
  });

  final String centerName;
  final String email;
  final String phone;
  final DateTime? joinedDate;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.xl),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppRadius.xl),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Profil ma’lumotlari', style: AppTextStyles.title),
          const SizedBox(height: AppSpacing.lg),
          _InfoRow(label: 'Markaz', value: centerName),
          _InfoRow(
            label: 'Email',
            value: email.trim().isEmpty ? 'Kiritilmagan' : email,
          ),
          _InfoRow(
            label: 'Telefon',
            value: phone.trim().isEmpty ? 'Kiritilmagan' : phone,
          ),
          _InfoRow(
            label: 'Ro‘yxatdan o‘tgan sana',
            value: joinedDate == null
                ? 'Mavjud emas'
                : Formatters.date(joinedDate),
            isLast: true,
          ),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({
    required this.label,
    required this.value,
    this.isLast = false,
  });

  final String label;
  final String value;
  final bool isLast;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: isLast ? 0 : AppSpacing.md),
      child: Row(
        children: [
          Expanded(
            child: Text(
              label,
              style: AppTextStyles.bodySmall.copyWith(
                color: AppColors.textMuted,
              ),
            ),
          ),
          const SizedBox(width: AppSpacing.md),
          Flexible(
            child: Text(
              value,
              textAlign: TextAlign.right,
              style: AppTextStyles.body,
            ),
          ),
        ],
      ),
    );
  }
}

class _ActionSection extends StatelessWidget {
  const _ActionSection({required this.title, required this.children});

  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.xl),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppRadius.xl),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: AppTextStyles.title),
          const SizedBox(height: AppSpacing.md),
          ...children,
        ],
      ),
    );
  }
}

class _ActionTile extends StatelessWidget {
  const _ActionTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
    this.iconColor = AppColors.primary,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  final Color iconColor;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppRadius.lg),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
          child: Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: iconColor.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(icon, color: iconColor, size: 22),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: AppTextStyles.body),
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      style: AppTextStyles.bodySmall.copyWith(
                        color: AppColors.textMuted,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: AppSpacing.md),
              const Icon(
                Icons.chevron_right_rounded,
                color: AppColors.textMuted,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
