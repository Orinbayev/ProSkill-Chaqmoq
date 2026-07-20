import 'dart:io';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:chaqmoq_mobile/core/config/app_config.dart';
import 'package:chaqmoq_mobile/core/design/ds_colors.dart';
import 'package:chaqmoq_mobile/core/design/ds_components.dart';
import 'package:chaqmoq_mobile/core/design/ds_tokens.dart';
import 'package:chaqmoq_mobile/core/design/ds_typography.dart';
import 'package:chaqmoq_mobile/core/utils/role_utils.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/app_preferences_provider.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/screens/profile/about_app_screen.dart';
import 'package:chaqmoq_mobile/screens/profile/help_support_screen.dart';
import 'package:chaqmoq_mobile/screens/profile/language_screen.dart';
import 'package:chaqmoq_mobile/screens/profile/notification_settings_screen.dart';
import 'package:chaqmoq_mobile/screens/profile/theme_screen.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/profile_service.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

/// Barcha rollar uchun ideal, yagona profil paneli.
///
/// - Rasm: kamera / galereya / o'chirish
/// - Ism-familya (studentdan tashqari) + telefon tahrirlash
/// - Parol o'zgartirish
/// - Mavzu, til, bildirishnoma, yordam
/// - Chiqish
class IdealProfileScreen extends StatefulWidget {
  const IdealProfileScreen({
    super.key,
    this.extraSections,
    this.showAppBar = false,
    this.title = 'Profil',
  });

  /// Parent farzandlar ro'yxati kabi qo'shimcha bloklar.
  final List<Widget>? extraSections;
  final bool showAppBar;
  final String title;

  @override
  State<IdealProfileScreen> createState() => _IdealProfileScreenState();
}

class _IdealProfileScreenState extends State<IdealProfileScreen> {
  late final ProfileService _service;
  File? _localAvatar;
  bool _avatarBusy = false;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _service = ProfileService(context.read<ApiClient>());
  }

  String _resolveAvatarUrl(String raw) {
    if (raw.isEmpty) return '';
    if (raw.startsWith('http')) return raw;
    return '${AppConfig.baseUrl}$raw';
  }

  Future<void> _openAvatarPicker(UserModel user) async {
    final hasAvatar =
        _localAvatar != null || user.avatarUrl.trim().isNotEmpty;
    final action = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (ctx) {
        final ds = ctx.ds;
        return Container(
          decoration: BoxDecoration(
            color: ds.card,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
          ),
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
          child: SafeArea(
            top: false,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: ds.borderStrong,
                    borderRadius: BorderRadius.circular(99),
                  ),
                ),
                const SizedBox(height: 14),
                Text('Profil rasmi', style: DsType.h3(ds.textPrimary)),
                const SizedBox(height: 6),
                Text(
                  'Kameradan oling yoki galereyadan tanlang',
                  style: DsType.small(ds.textMuted),
                ),
                const SizedBox(height: 16),
                _sheetTile(
                  ds,
                  icon: Icons.photo_camera_rounded,
                  title: 'Kameradan olish',
                  onTap: () => Navigator.pop(ctx, 'camera'),
                ),
                _sheetTile(
                  ds,
                  icon: Icons.photo_library_rounded,
                  title: 'Galereyadan tanlash',
                  onTap: () => Navigator.pop(ctx, 'gallery'),
                ),
                if (hasAvatar)
                  _sheetTile(
                    ds,
                    icon: Icons.delete_outline_rounded,
                    title: 'Rasmni o‘chirish',
                    danger: true,
                    onTap: () => Navigator.pop(ctx, 'clear'),
                  ),
                _sheetTile(
                  ds,
                  icon: Icons.close_rounded,
                  title: 'Bekor qilish',
                  onTap: () => Navigator.pop(ctx, 'cancel'),
                ),
              ],
            ),
          ),
        );
      },
    );
    if (!mounted || action == null || action == 'cancel') return;
    if (action == 'clear') {
      await _clearAvatar();
      return;
    }
    final source =
        action == 'camera' ? ImageSource.camera : ImageSource.gallery;
    await _pickAndUpload(source);
  }

  Widget _sheetTile(
    DsColors ds, {
    required IconData icon,
    required String title,
    required VoidCallback onTap,
    bool danger = false,
  }) {
    final fg = danger ? ds.danger : ds.textPrimary;
    return ListTile(
      onTap: onTap,
      leading: Icon(icon, color: fg),
      title: Text(title, style: DsType.bodyStrong(fg)),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
    );
  }

  Future<void> _pickAndUpload(ImageSource source) async {
    final picked = await ImagePicker().pickImage(
      source: source,
      maxWidth: 1080,
      imageQuality: 85,
    );
    if (picked == null || !mounted) return;
    setState(() {
      _localAvatar = File(picked.path);
      _avatarBusy = true;
    });
    try {
      final updated = await _service.uploadAvatar(picked);
      if (!mounted) return;
      context.read<AuthProvider>().updateUser(updated);
      _toast('Profil rasmi yangilandi');
    } on ApiException catch (e) {
      _toast(e.message);
    } catch (_) {
      _toast('Rasmni yuklab bo‘lmadi');
    } finally {
      if (mounted) setState(() => _avatarBusy = false);
    }
  }

  Future<void> _clearAvatar() async {
    setState(() => _avatarBusy = true);
    try {
      final updated = await _service.removeAvatar();
      if (!mounted) return;
      setState(() => _localAvatar = null);
      context.read<AuthProvider>().updateUser(updated);
      _toast('Profil rasmi o‘chirildi');
    } on ApiException catch (e) {
      _toast(e.message);
    } catch (_) {
      _toast('Rasmni o‘chirib bo‘lmadi');
    } finally {
      if (mounted) setState(() => _avatarBusy = false);
    }
  }

  Future<void> _openEditSheet(UserModel user) async {
    final isStudent = RoleUtils.normalize(user.role) == 'student';
    final ismCtrl = TextEditingController(text: user.firstName);
    final famCtrl = TextEditingController(text: user.lastName);
    final phoneCtrl = TextEditingController(text: user.phone);

    final saved = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) {
        final ds = ctx.ds;
        final bottom = MediaQuery.viewInsetsOf(ctx).bottom;
        return Padding(
          padding: EdgeInsets.only(bottom: bottom),
          child: Container(
            decoration: BoxDecoration(
              color: ds.card,
              borderRadius:
                  const BorderRadius.vertical(top: Radius.circular(22)),
            ),
            padding: const EdgeInsets.fromLTRB(18, 12, 18, 20),
            child: SafeArea(
              top: false,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Center(
                    child: Container(
                      width: 40,
                      height: 4,
                      decoration: BoxDecoration(
                        color: ds.borderStrong,
                        borderRadius: BorderRadius.circular(99),
                      ),
                    ),
                  ),
                  const SizedBox(height: 14),
                  Text('Ma’lumotlarni tahrirlash',
                      style: DsType.h3(ds.textPrimary)),
                  if (isStudent) ...[
                    const SizedBox(height: 8),
                    Text(
                      'Ism va familyani markaz o‘zgartiradi. Faqat telefonni tahrirlashingiz mumkin.',
                      style: DsType.small(ds.textMuted),
                    ),
                  ],
                  const SizedBox(height: 16),
                  if (!isStudent) ...[
                    DsTextField(
                      label: 'Ism',
                      controller: ismCtrl,
                      hint: 'Ismingiz',
                    ),
                    const SizedBox(height: 12),
                    DsTextField(
                      label: 'Familya',
                      controller: famCtrl,
                      hint: 'Familyangiz',
                    ),
                    const SizedBox(height: 12),
                  ],
                  DsTextField(
                    label: 'Telefon',
                    controller: phoneCtrl,
                    hint: '+998 90 123 45 67',
                    keyboardType: TextInputType.phone,
                  ),
                  const SizedBox(height: 18),
                  DsButton(
                    label: 'Saqlash',
                    onPressed: () => Navigator.pop(ctx, true),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );

    if (saved != true || !mounted) {
      ismCtrl.dispose();
      famCtrl.dispose();
      phoneCtrl.dispose();
      return;
    }

    setState(() => _saving = true);
    try {
      final updated = await _service.updateProfile(
        ism: isStudent ? null : ismCtrl.text.trim(),
        familya: isStudent ? null : famCtrl.text.trim(),
        phone: phoneCtrl.text.trim(),
      );
      if (!mounted) return;
      context.read<AuthProvider>().updateUser(updated);
      _toast('Profil saqlandi');
    } on ApiException catch (e) {
      _toast(e.message);
    } catch (_) {
      _toast('Saqlashda xatolik');
    } finally {
      ismCtrl.dispose();
      famCtrl.dispose();
      phoneCtrl.dispose();
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _openPasswordSheet() async {
    final cur = TextEditingController();
    final neu = TextEditingController();
    final conf = TextEditingController();
    var obscure = true;

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) {
        final ds = ctx.ds;
        final bottom = MediaQuery.viewInsetsOf(ctx).bottom;
        return StatefulBuilder(
          builder: (ctx, setLocal) {
            return Padding(
              padding: EdgeInsets.only(bottom: bottom),
              child: Container(
                decoration: BoxDecoration(
                  color: ds.card,
                  borderRadius:
                      const BorderRadius.vertical(top: Radius.circular(22)),
                ),
                padding: const EdgeInsets.fromLTRB(18, 12, 18, 20),
                child: SafeArea(
                  top: false,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Center(
                        child: Container(
                          width: 40,
                          height: 4,
                          decoration: BoxDecoration(
                            color: ds.borderStrong,
                            borderRadius: BorderRadius.circular(99),
                          ),
                        ),
                      ),
                      const SizedBox(height: 14),
                      Text('Parolni o‘zgartirish',
                          style: DsType.h3(ds.textPrimary)),
                      const SizedBox(height: 16),
                      DsTextField(
                        label: 'Joriy parol',
                        controller: cur,
                        obscureText: obscure,
                        hint: '••••••••',
                      ),
                      const SizedBox(height: 12),
                      DsTextField(
                        label: 'Yangi parol',
                        controller: neu,
                        obscureText: obscure,
                        hint: 'Kamida 8 belgi',
                      ),
                      const SizedBox(height: 12),
                      DsTextField(
                        label: 'Tasdiqlash',
                        controller: conf,
                        obscureText: obscure,
                        hint: 'Yangi parolni takrorlang',
                      ),
                      const SizedBox(height: 8),
                      TextButton(
                        onPressed: () => setLocal(() => obscure = !obscure),
                        child: Text(
                          obscure ? 'Parolni ko‘rsatish' : 'Parolni yashirish',
                          style: DsType.small(ds.primary),
                        ),
                      ),
                      const SizedBox(height: 8),
                      DsButton(
                        label: 'Yangilash',
                        onPressed: () async {
                          try {
                            await _service.changePassword(
                              currentPassword: cur.text.trim(),
                              newPassword: neu.text.trim(),
                              confirmPassword: conf.text.trim(),
                            );
                            if (ctx.mounted) Navigator.pop(ctx);
                            _toast('Parol muvaffaqiyatli yangilandi');
                          } on ApiException catch (e) {
                            _toast(e.message);
                          } catch (_) {
                            _toast('Parolni o‘zgartirib bo‘lmadi');
                          }
                        },
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        );
      },
    );

    cur.dispose();
    neu.dispose();
    conf.dispose();
  }

  Future<void> _logout() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) {
        final ds = ctx.ds;
        return AlertDialog(
          backgroundColor: ds.card,
          title: Text('Chiqish', style: DsType.h3(ds.textPrimary)),
          content: Text(
            'Hisobingizdan chiqmoqchimisiz?',
            style: DsType.body(ds.textSecondary),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: Text('Bekor', style: DsType.bodyStrong(ds.textMuted)),
            ),
            TextButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: Text('Chiqish', style: DsType.bodyStrong(ds.danger)),
            ),
          ],
        );
      },
    );
    if (ok == true && mounted) {
      await context.read<AuthProvider>().logout();
    }
  }

  void _toast(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    final auth = context.watch<AuthProvider>();
    final prefs = context.watch<AppPreferencesProvider>();
    final user = auth.user;
    if (user == null) {
      return Scaffold(
        backgroundColor: ds.bg,
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    final role = RoleUtils.normalize(user.role);
    final roleLabel = RoleUtils.roleLabel(user.role);
    final avatarUrl = _resolveAvatarUrl(user.avatarUrl);
    final joined = user.joinedDate;
    final joinedLabel = joined == null
        ? '—'
        : DateFormat('d MMM yyyy', 'uz').format(joined);

    final body = ListView(
      physics: const BouncingScrollPhysics(),
      padding: EdgeInsets.fromLTRB(
        DsSpace.screen,
        widget.showAppBar ? DsSpace.x4 : DsSpace.x5,
        DsSpace.screen,
        110,
      ),
      children: [
        // ── Hero ────────────────────────────────────────────────
        DsCard(
          padding: const EdgeInsets.fromLTRB(18, 22, 18, 20),
          child: Column(
            children: [
              GestureDetector(
                onTap: _avatarBusy ? null : () => _openAvatarPicker(user),
                child: Stack(
                  children: [
                    Container(
                      width: 108,
                      height: 108,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: avatarUrl.isEmpty && _localAvatar == null
                            ? LinearGradient(colors: ds.primaryGradient)
                            : null,
                        border: Border.all(
                          color: ds.primary.withValues(alpha: 0.35),
                          width: 3,
                        ),
                        boxShadow: DsShadow.primaryGlow(ds.primary),
                      ),
                      clipBehavior: Clip.antiAlias,
                      child: _avatarBusy
                          ? const Center(
                              child: CircularProgressIndicator(
                                strokeWidth: 2.4,
                                color: Colors.white,
                              ),
                            )
                          : _localAvatar != null
                              ? Image.file(_localAvatar!, fit: BoxFit.cover)
                              : avatarUrl.isNotEmpty
                                  ? CachedNetworkImage(
                                      imageUrl: avatarUrl,
                                      fit: BoxFit.cover,
                                      errorWidget: (_, __, ___) =>
                                          _Initials(name: user.fullName, ds: ds),
                                    )
                                  : _Initials(name: user.fullName, ds: ds),
                    ),
                    Positioned(
                      right: 2,
                      bottom: 2,
                      child: Container(
                        width: 34,
                        height: 34,
                        decoration: BoxDecoration(
                          color: ds.primary,
                          shape: BoxShape.circle,
                          border: Border.all(color: ds.card, width: 2.5),
                        ),
                        child: const Icon(
                          Icons.camera_alt_rounded,
                          size: 16,
                          color: Colors.white,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 14),
              Text(
                user.fullName.isNotEmpty ? user.fullName : roleLabel,
                textAlign: TextAlign.center,
                style: DsType.h2(ds.textPrimary),
              ),
              const SizedBox(height: 6),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
                decoration: BoxDecoration(
                  color: ds.primarySoft,
                  borderRadius: BorderRadius.circular(99),
                ),
                child: Text(roleLabel, style: DsType.small(ds.primarySoftFg)),
              ),
              if ((user.center?.name ?? '').isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(
                  user.center!.name,
                  style: DsType.small(ds.textMuted),
                ),
              ],
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: DsButton(
                      label: 'Tahrirlash',
                      icon: Icons.edit_rounded,
                      height: 46,
                      onPressed: _saving ? null : () => _openEditSheet(user),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: DsButton(
                      label: 'Rasm',
                      icon: Icons.photo_camera_outlined,
                      variant: DsButtonVariant.secondary,
                      height: 46,
                      onPressed:
                          _avatarBusy ? null : () => _openAvatarPicker(user),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 14),

        // ── Ma'lumotlar ─────────────────────────────────────────
        _SectionLabel('Shaxsiy ma’lumotlar'),
        const SizedBox(height: 8),
        DsCard(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Column(
            children: [
              _InfoRow(
                icon: Icons.mail_outline_rounded,
                label: 'Email',
                value: user.email.isEmpty ? '—' : user.email,
                onLongPress: user.email.isEmpty
                    ? null
                    : () => _copy(user.email, 'Email'),
              ),
              Divider(height: 1, color: ds.border),
              _InfoRow(
                icon: Icons.phone_rounded,
                label: 'Telefon',
                value: user.phone.isEmpty ? '—' : user.phone,
                onLongPress: user.phone.isEmpty
                    ? null
                    : () => _copy(user.phone, 'Telefon'),
              ),
              Divider(height: 1, color: ds.border),
              _InfoRow(
                icon: Icons.business_rounded,
                label: 'Markaz',
                value: user.center?.name ?? '—',
              ),
              Divider(height: 1, color: ds.border),
              _InfoRow(
                icon: Icons.event_rounded,
                label: 'Qo‘shilgan',
                value: joinedLabel,
              ),
              if (role == 'student') ...[
                Divider(height: 1, color: ds.border),
                _InfoRow(
                  icon: Icons.info_outline_rounded,
                  label: 'Eslatma',
                  value: 'Ismni faqat markaz o‘zgartiradi',
                ),
              ],
            ],
          ),
        ),

        if (widget.extraSections != null) ...[
          const SizedBox(height: 14),
          ...widget.extraSections!,
        ],

        const SizedBox(height: 14),
        _SectionLabel('Xavfsizlik va sozlamalar'),
        const SizedBox(height: 8),
        DsCard(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Column(
            children: [
              _ActionRow(
                icon: Icons.lock_outline_rounded,
                title: 'Parolni o‘zgartirish',
                onTap: _openPasswordSheet,
              ),
              Divider(height: 1, color: ds.border),
              _ActionRow(
                icon: Icons.notifications_none_rounded,
                title: 'Bildirishnomalar',
                subtitle: _notifLabel(prefs),
                onTap: () => _push(const NotificationSettingsScreen()),
              ),
              Divider(height: 1, color: ds.border),
              _ActionRow(
                icon: Icons.palette_outlined,
                title: 'Mavzu',
                subtitle: prefs.themeLabel,
                onTap: () => _push(const ThemeScreen()),
              ),
              Divider(height: 1, color: ds.border),
              _ActionRow(
                icon: Icons.translate_rounded,
                title: 'Til',
                subtitle: prefs.languageLabel,
                onTap: () => _push(const LanguageScreen()),
              ),
            ],
          ),
        ),

        const SizedBox(height: 14),
        _SectionLabel('Yordam'),
        const SizedBox(height: 8),
        DsCard(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Column(
            children: [
              _ActionRow(
                icon: Icons.help_outline_rounded,
                title: 'Yordam va qo‘llab-quvvatlash',
                onTap: () => _push(const HelpSupportScreen()),
              ),
              Divider(height: 1, color: ds.border),
              _ActionRow(
                icon: Icons.info_outline_rounded,
                title: 'Ilova haqida',
                subtitle: 'v${AppConfig.appName.contains('Mobile') ? '1.0.4' : '1.0'}',
                onTap: () => _push(const AboutAppScreen()),
              ),
            ],
          ),
        ),

        const SizedBox(height: 20),
        DsButton(
          label: 'Chiqish',
          variant: DsButtonVariant.danger,
          icon: Icons.logout_rounded,
          onPressed: _logout,
        ),
        if (auth.isOfflineMode) ...[
          const SizedBox(height: 10),
          Text(
            'Offline rejim — ba’zi o‘zgarishlar sinxronlanmasligi mumkin',
            textAlign: TextAlign.center,
            style: DsType.small(ds.warningFg),
          ),
        ],
      ],
    );

    return Scaffold(
      backgroundColor: ds.bg,
      appBar: widget.showAppBar
          ? AppBar(
              title: Text(widget.title),
              backgroundColor: ds.surface,
              surfaceTintColor: Colors.transparent,
            )
          : null,
      body: SafeArea(
        bottom: false,
        child: body,
      ),
    );
  }

  String _notifLabel(AppPreferencesProvider prefs) {
    final s = prefs.notificationSettings;
    final n = (s.attendance ? 1 : 0) +
        (s.payments ? 1 : 0) +
        (s.progress ? 1 : 0) +
        (s.general ? 1 : 0);
    if (n == 0) return 'O‘chirilgan';
    if (n == 4) return 'Yoqilgan';
    return '$n/4';
  }

  Future<void> _push(Widget page) async {
    await Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => page));
  }

  Future<void> _copy(String value, String label) async {
    await Clipboard.setData(ClipboardData(text: value));
    _toast('$label nusxalandi');
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.text);
  final String text;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Text(
      text.toUpperCase(),
      style: DsType.micro(ds.textMuted).copyWith(letterSpacing: 1.2),
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
    final ds = context.ds;
    return InkWell(
      onLongPress: onLongPress,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: ds.primarySoft,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, size: 18, color: ds.primarySoftFg),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(label, style: DsType.small(ds.textMuted)),
                  const SizedBox(height: 2),
                  Text(value, style: DsType.bodyStrong(ds.textPrimary)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ActionRow extends StatelessWidget {
  const _ActionRow({
    required this.icon,
    required this.title,
    this.subtitle,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String? subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Material(
      color: Colors.transparent,
      child: ListTile(
        onTap: onTap,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 2),
        leading: Container(
          width: 36,
          height: 36,
          decoration: BoxDecoration(
            color: ds.cardAlt,
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(icon, size: 18, color: ds.textSecondary),
        ),
        title: Text(title, style: DsType.bodyStrong(ds.textPrimary)),
        subtitle: subtitle == null
            ? null
            : Text(subtitle!, style: DsType.small(ds.textMuted)),
        trailing: Icon(Icons.chevron_right_rounded, color: ds.textFaint),
      ),
    );
  }
}

class _Initials extends StatelessWidget {
  const _Initials({required this.name, required this.ds});
  final String name;
  final DsColors ds;

  @override
  Widget build(BuildContext context) {
    final parts =
        name.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty).toList();
    final ini = parts.isEmpty
        ? '?'
        : (parts.length == 1
                ? parts[0].characters.first
                : parts[0].characters.first + parts[1].characters.first)
            .toUpperCase();
    return ColoredBox(
      color: ds.primary,
      child: Center(
        child: Text(ini, style: DsType.display(Colors.white)),
      ),
    );
  }
}
