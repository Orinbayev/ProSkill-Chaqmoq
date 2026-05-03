import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/providers/app_preferences_provider.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/screens/auth/login_screen.dart';
import 'package:chaqmoq_mobile/screens/profile/about_app_screen.dart';
import 'package:chaqmoq_mobile/screens/profile/edit_profile_screen.dart';
import 'package:chaqmoq_mobile/screens/profile/help_support_screen.dart';
import 'package:chaqmoq_mobile/screens/profile/language_screen.dart';
import 'package:chaqmoq_mobile/screens/profile/notification_settings_screen.dart';
import 'package:chaqmoq_mobile/screens/profile/security_screen.dart';
import 'package:chaqmoq_mobile/screens/profile/theme_screen.dart';
import 'package:chaqmoq_mobile/services/parent_dashboard_service.dart';
import 'package:chaqmoq_mobile/widgets/app_avatar.dart';
import 'package:chaqmoq_mobile/widgets/app_badge.dart';
import 'package:chaqmoq_mobile/widgets/app_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

/// Student profile / account — dark glass theme.
class StudentAccountScreen extends StatelessWidget {
  const StudentAccountScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().user;
    final prefs = context.watch<AppPreferencesProvider>();
    final tokens = StudentTokens.of(context);
    if (user == null) return const SizedBox.shrink();

    final centerName = user.center?.name ?? 'Markaz topilmadi';
    final joined = user.joinedDate;
    final joinedLabel = joined == null ? '—' : DateFormat('d MMM yyyy', 'uz').format(joined);
    final notifEnabledCount = _enabledNotificationCount(prefs.notificationSettings);
    final notifLabel = notifEnabledCount == 0
        ? "O‘chirilgan"
        : (notifEnabledCount == 4 ? 'Yoqilgan' : '$notifEnabledCount/4');

    return Scaffold(
      backgroundColor: tokens.bg,
      body: Stack(
        children: [
          IgnorePointer(
            child: Stack(children: [
              Positioned(
                top: 80,
                left: -50,
                child: Container(
                  width: 180,
                  height: 180,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: RadialGradient(colors: [
                      tokens.secondary.withValues(alpha: 0.18),
                      tokens.secondary.withValues(alpha: 0),
                    ]),
                  ),
                ),
              ),
            ]),
          ),
          SafeArea(
            child: ListView(
              physics: const BouncingScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(18, 8, 18, 110),
              children: [
                Text(
                  'Profil',
                  style: GoogleFonts.inter(
                    fontSize: 19,
                    fontWeight: FontWeight.w800,
                    color: tokens.text,
                    letterSpacing: -0.2,
                  ),
                ),
                const SizedBox(height: 14),
                _Hero(
                  name: user.fullName.isEmpty ? 'O‘quvchi' : user.fullName,
                  avatarUrl: user.avatarUrl,
                  role: user.role.isEmpty ? "O‘quvchi" : 'O‘quvchi · ${user.role}',
                  onEdit: () => _openEditProfile(context),
                ),
                const SizedBox(height: 14),
                AppGCard(
                  padding: const EdgeInsets.all(4),
                  child: Column(
                    children: [
                      _InfoRow(icon: Icons.apartment_rounded, label: 'Markaz', value: centerName),
                      const _RowDivider(),
                      _InfoRow(
                        icon: Icons.mail_outline_rounded,
                        label: 'Email',
                        value: user.email.isEmpty ? '—' : user.email,
                        onLongPress: user.email.isEmpty ? null : () => _copy(context, user.email, 'Email'),
                      ),
                      const _RowDivider(),
                      _InfoRow(
                        icon: Icons.phone_rounded,
                        label: 'Telefon',
                        value: user.phone.isEmpty ? '—' : user.phone,
                        onLongPress: user.phone.isEmpty ? null : () => _copy(context, user.phone, 'Telefon raqami'),
                      ),
                      const _RowDivider(),
                      _InfoRow(icon: Icons.event_rounded, label: "Qo‘shilgan", value: joinedLabel),
                    ],
                  ),
                ),
                const SizedBox(height: 14),
                Text(
                  'SOZLAMALAR',
                  style: GoogleFonts.inter(
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    color: tokens.textMuted,
                    letterSpacing: 1.6,
                  ),
                ),
                const SizedBox(height: 8),
                AppGCard(
                  padding: const EdgeInsets.all(4),
                  child: Column(
                    children: [
                      _SettingRow(
                        icon: Icons.lock_outline_rounded,
                        label: 'Xavfsizlik',
                        onTap: () => _openSecurity(context),
                      ),
                      const _RowDivider(),
                      _SettingRow(
                        icon: Icons.notifications_outlined,
                        label: 'Bildirishnomalar',
                        value: notifLabel,
                        onTap: () => _openNotificationSettings(context),
                      ),
                      const _RowDivider(),
                      _SettingRow(
                        icon: Icons.translate_rounded,
                        label: 'Til',
                        value: prefs.languageLabel,
                        onTap: () => _openLanguage(context),
                      ),
                      const _RowDivider(),
                      _SettingRow(
                        icon: Icons.dark_mode_outlined,
                        label: 'Mavzu',
                        value: prefs.themeLabel,
                        onTap: () => _openTheme(context),
                      ),
                      const _RowDivider(),
                      _SettingRow(
                        icon: Icons.help_outline_rounded,
                        label: 'Yordam',
                        onTap: () => _openHelp(context),
                      ),
                      const _RowDivider(),
                      _SettingRow(
                        icon: Icons.info_outline_rounded,
                        label: 'Ilova haqida',
                        value: 'v1.0.0',
                        onTap: () => _openAbout(context),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 14),
                _LogoutButton(onTap: () => _confirmLogout(context)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  static int _enabledNotificationCount(NotificationPreferenceSettings s) {
    return (s.attendance ? 1 : 0) +
        (s.payments ? 1 : 0) +
        (s.progress ? 1 : 0) +
        (s.general ? 1 : 0);
  }

  Future<void> _openEditProfile(BuildContext context) async {
    final user = context.read<AuthProvider>().user;
    if (user == null) return;
    final service = context.read<ParentDashboardService>();
    final result = await Navigator.of(context).push(
      MaterialPageRoute<dynamic>(
        builder: (_) => EditProfileScreen(
          initialUser: user,
          profileService: service,
        ),
      ),
    );
    if (!context.mounted) return;
    if (result != null) {
      try {
        final updatedUser = (result as dynamic).parent;
        if (updatedUser != null) {
          context.read<AuthProvider>().updateUser(updatedUser);
        }
      } catch (_) {}
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Profil ma’lumotlari saqlandi')),
      );
    }
  }

  void _openSecurity(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<bool>(
        builder: (_) => SecurityScreen(
          profileService: context.read<ParentDashboardService>(),
        ),
      ),
    );
  }

  void _openNotificationSettings(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<bool>(
        builder: (_) => const NotificationSettingsScreen(),
      ),
    );
  }

  void _openLanguage(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<bool>(builder: (_) => const LanguageScreen()),
    );
  }

  void _openTheme(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<bool>(builder: (_) => const ThemeScreen()),
    );
  }

  void _openHelp(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => const HelpSupportScreen()),
    );
  }

  void _openAbout(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => const AboutAppScreen()),
    );
  }

  void _copy(BuildContext context, String value, String label) {
    Clipboard.setData(ClipboardData(text: value));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('$label nusxalandi'), duration: const Duration(seconds: 1)),
    );
  }

  Future<void> _confirmLogout(BuildContext context) async {
    final tokens = StudentTokens.of(context);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: tokens.isDark ? tokens.surfaceElevated : tokens.surface,
        title: Text('Chiqish', style: GoogleFonts.inter(color: tokens.text, fontWeight: FontWeight.w700)),
        content: Text('Hisobdan chiqishni xohlaysizmi?', style: GoogleFonts.inter(color: tokens.textMuted)),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: Text('Bekor', style: GoogleFonts.inter(color: tokens.textMuted)),
          ),
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: Text('Chiqish', style: GoogleFonts.inter(color: tokens.danger, fontWeight: FontWeight.w700)),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    if (!context.mounted) return;
    await context.read<AuthProvider>().logout();
    if (!context.mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute<void>(builder: (_) => const LoginScreen()),
      (_) => false,
    );
  }
}

class _Hero extends StatelessWidget {
  const _Hero({
    required this.name,
    required this.avatarUrl,
    required this.role,
    required this.onEdit,
  });

  final String name;
  final String avatarUrl;
  final String role;
  final VoidCallback onEdit;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: tokens.heroGradient,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: tokens.secondary.withValues(alpha: 0.28)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          GestureDetector(
            onTap: onEdit,
            behavior: HitTestBehavior.opaque,
            child: Stack(
              clipBehavior: Clip.none,
              children: [
                AppAvatar(name: name, size: 84, color: AppAvatarColor.violet, imageUrl: avatarUrl),
                Positioned(
                  right: -2,
                  bottom: -2,
                  child: Material(
                    color: Colors.transparent,
                    shape: const CircleBorder(),
                    child: InkWell(
                      onTap: onEdit,
                      customBorder: const CircleBorder(),
                      child: Container(
                        width: 28,
                        height: 28,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          color: tokens.primary,
                          shape: BoxShape.circle,
                          border: Border.all(color: tokens.bg, width: 3),
                        ),
                        child: Icon(Icons.edit_rounded, color: tokens.onPrimary, size: 14),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 10),
          Text(
            name,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: GoogleFonts.inter(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: tokens.text,
              letterSpacing: -0.2,
            ),
          ),
          const SizedBox(height: 8),
          AppBadge(label: role, tone: AppBadgeTone.violet, dark: tokens.isDark),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({
    required this.icon,
    required this.label,
    required this.value,
    this.onLongPress,
  });

  final IconData icon;
  final String label;
  final String value;
  final VoidCallback? onLongPress;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return InkWell(
      onTap: onLongPress,
      onLongPress: onLongPress,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            Container(
              width: 32,
              height: 32,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: tokens.tonedSurface(tokens.primary),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, size: 16, color: tokens.primary),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(label,
                      style: GoogleFonts.inter(
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        color: tokens.textMuted,
                      )),
                  Text(value,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: GoogleFonts.inter(
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                        color: tokens.text,
                      )),
                ],
              ),
            ),
            if (onLongPress != null)
              Icon(Icons.copy_rounded, size: 14, color: tokens.textDim),
          ],
        ),
      ),
    );
  }
}

class _SettingRow extends StatelessWidget {
  const _SettingRow({required this.icon, required this.label, this.value, this.onTap});

  final IconData icon;
  final String label;
  final String? value;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            Container(
              width: 32,
              height: 32,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: tokens.glassStrong,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, size: 16, color: tokens.primary),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w600,
                    color: tokens.text,
                  )),
            ),
            if (value != null)
              Padding(
                padding: const EdgeInsets.only(right: 6),
                child: Text(value!,
                    style: GoogleFonts.inter(
                      fontSize: 11.5,
                      fontWeight: FontWeight.w600,
                      color: tokens.textMuted,
                    )),
              ),
            Icon(Icons.chevron_right_rounded, color: tokens.textDim, size: 18),
          ],
        ),
      ),
    );
  }
}

class _RowDivider extends StatelessWidget {
  const _RowDivider();

  @override
  Widget build(BuildContext context) {
    return Container(height: 1, color: StudentTokens.of(context).border);
  }
}

class _LogoutButton extends StatelessWidget {
  const _LogoutButton({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: tokens.tonedSurface(tokens.danger),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: tokens.tonedBorder(tokens.danger)),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.logout_rounded, color: tokens.danger, size: 20),
              const SizedBox(width: 8),
              Text('Chiqish',
                  style: GoogleFonts.inter(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w700,
                    color: tokens.danger,
                  )),
            ],
          ),
        ),
      ),
    );
  }
}
