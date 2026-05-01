import 'package:chaqmoq_mobile/core/theme/student_colors.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/screens/auth/login_screen.dart';
import 'package:chaqmoq_mobile/widgets/app_avatar.dart';
import 'package:chaqmoq_mobile/widgets/app_badge.dart';
import 'package:chaqmoq_mobile/widgets/app_card.dart';
import 'package:chaqmoq_mobile/widgets/app_parent_app_bar.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

/// Student profile / account — dark glass theme.
/// Mirrors StudentAccount JSX hero card + info rows + settings + logout.
class StudentAccountScreen extends StatelessWidget {
  const StudentAccountScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().user;
    if (user == null) return const SizedBox.shrink();

    final centerName = user.center?.name ?? 'Markaz topilmadi';
    final joined = user.joinedDate;
    final joinedLabel = joined == null ? '—' : DateFormat('d MMM yyyy', 'uz').format(joined);

    return Scaffold(
      backgroundColor: StudentColors.bg,
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
                  decoration: const BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: RadialGradient(colors: [Color(0x2E6C63FF), Color(0x006C63FF)]),
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
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        'Profil',
                        style: GoogleFonts.inter(
                          fontSize: 19,
                          fontWeight: FontWeight.w800,
                          color: StudentColors.text,
                          letterSpacing: -0.2,
                        ),
                      ),
                    ),
                    AppStudentIconButton(icon: Icons.settings_rounded, onTap: () {}),
                  ],
                ),
                const SizedBox(height: 14),
                _Hero(
                  name: user.fullName.isEmpty ? 'O‘quvchi' : user.fullName,
                  avatarUrl: user.avatarUrl,
                  role: user.role.isEmpty ? "O‘quvchi" : 'O‘quvchi · ${user.role}',
                ),
                const SizedBox(height: 14),
                AppGCard(
                  padding: const EdgeInsets.all(4),
                  child: Column(
                    children: [
                      _InfoRow(icon: Icons.apartment_rounded, label: 'Markaz', value: centerName),
                      const _RowDivider(),
                      _InfoRow(icon: Icons.mail_outline_rounded, label: 'Email', value: user.email.isEmpty ? '—' : user.email),
                      const _RowDivider(),
                      _InfoRow(icon: Icons.phone_rounded, label: 'Telefon', value: user.phone.isEmpty ? '—' : user.phone),
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
                    color: StudentColors.textMuted,
                    letterSpacing: 1.6,
                  ),
                ),
                const SizedBox(height: 8),
                AppGCard(
                  padding: const EdgeInsets.all(4),
                  child: Column(
                    children: const [
                      _SettingRow(icon: Icons.edit_rounded, label: 'Profilni tahrirlash'),
                      _RowDivider(),
                      _SettingRow(icon: Icons.lock_outline_rounded, label: 'Xavfsizlik'),
                      _RowDivider(),
                      _SettingRow(icon: Icons.notifications_outlined, label: 'Bildirishnomalar', value: 'Yoqilgan'),
                      _RowDivider(),
                      _SettingRow(icon: Icons.translate_rounded, label: 'Til', value: "O‘zbek"),
                      _RowDivider(),
                      _SettingRow(icon: Icons.help_outline_rounded, label: 'Yordam'),
                      _RowDivider(),
                      _SettingRow(icon: Icons.info_outline_rounded, label: 'Ilova haqida', value: 'v2.4.1'),
                    ],
                  ),
                ),
                const SizedBox(height: 14),
                _LogoutButton(onTap: () => _logout(context)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _logout(BuildContext context) async {
    await context.read<AuthProvider>().logout();
    if (!context.mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute<void>(builder: (_) => const LoginScreen()),
      (_) => false,
    );
  }
}

class _Hero extends StatelessWidget {
  const _Hero({required this.name, required this.avatarUrl, required this.role});

  final String name;
  final String avatarUrl;
  final String role;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0x2E6C63FF), Color(0x1A00D4AA), Color(0x05FFFFFF)],
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0x476C63FF)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Stack(
            clipBehavior: Clip.none,
            children: [
              AppAvatar(name: name, size: 84, color: AppAvatarColor.violet, imageUrl: avatarUrl),
              Positioned(
                right: -2,
                bottom: -2,
                child: Container(
                  width: 26,
                  height: 26,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: StudentColors.primary,
                    shape: BoxShape.circle,
                    border: Border.all(color: const Color(0xFF13131A), width: 3),
                  ),
                  child: const Icon(Icons.bolt_rounded, color: StudentColors.onPrimary, size: 14),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            name,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: GoogleFonts.inter(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: StudentColors.text,
              letterSpacing: -0.2,
            ),
          ),
          const SizedBox(height: 8),
          AppBadge(label: role, tone: AppBadgeTone.violet, dark: true),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.icon, required this.label, required this.value});

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Row(
        children: [
          Container(
            width: 32,
            height: 32,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: const Color(0x2400D4AA),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, size: 16, color: StudentColors.primary),
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
                      color: StudentColors.textMuted,
                    )),
                Text(value,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: GoogleFonts.inter(
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                      color: StudentColors.text,
                    )),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SettingRow extends StatelessWidget {
  const _SettingRow({required this.icon, required this.label, this.value});

  final IconData icon;
  final String label;
  final String? value;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: () {},
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
                color: StudentColors.glassStrong,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, size: 16, color: StudentColors.primary),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w600,
                    color: StudentColors.text,
                  )),
            ),
            if (value != null)
              Padding(
                padding: const EdgeInsets.only(right: 6),
                child: Text(value!,
                    style: GoogleFonts.inter(
                      fontSize: 11.5,
                      fontWeight: FontWeight.w600,
                      color: StudentColors.textMuted,
                    )),
              ),
            const Icon(Icons.chevron_right_rounded, color: StudentColors.textDim, size: 18),
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
    return Container(height: 1, color: StudentColors.border);
  }
}

class _LogoutButton extends StatelessWidget {
  const _LogoutButton({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
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
            color: const Color(0x1AFF4757),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: const Color(0x47FF4757)),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.logout_rounded, color: StudentColors.danger, size: 20),
              const SizedBox(width: 8),
              Text('Chiqish',
                  style: GoogleFonts.inter(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w700,
                    color: StudentColors.danger,
                  )),
            ],
          ),
        ),
      ),
    );
  }
}
