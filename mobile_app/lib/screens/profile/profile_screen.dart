import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/parent_models.dart';
import 'package:chaqmoq_mobile/providers/app_preferences_provider.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/parent_dashboard_provider.dart';
import 'package:chaqmoq_mobile/screens/notifications/notifications_screen.dart';
import 'package:chaqmoq_mobile/screens/parent/add_child_screen.dart';
import 'package:chaqmoq_mobile/screens/parent/parent_ui.dart';
import 'package:chaqmoq_mobile/screens/profile/about_app_screen.dart';
import 'package:chaqmoq_mobile/screens/profile/edit_profile_screen.dart';
import 'package:chaqmoq_mobile/screens/profile/help_support_screen.dart';
import 'package:chaqmoq_mobile/screens/profile/language_screen.dart';
import 'package:chaqmoq_mobile/screens/profile/notification_settings_screen.dart';
import 'package:chaqmoq_mobile/screens/profile/security_screen.dart';
import 'package:chaqmoq_mobile/screens/profile/theme_screen.dart';
import 'package:chaqmoq_mobile/screens/settings/settings_screen.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/parent_dashboard_service.dart';
import 'package:chaqmoq_mobile/widgets/adaptive_avatar.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key, this.showBottomNav = true});

  final bool showBottomNav;

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  ParentProfileModel? _data;
  ViewState _state = ViewState.idle;
  String? _errorMessage;
  bool _loaded = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_loaded) {
      _loaded = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          _load();
        }
      });
    }
  }

  Future<void> _load({bool force = false}) async {
    if (_state == ViewState.loading && !force) {
      return;
    }
    setState(() {
      _state = ViewState.loading;
      _errorMessage = null;
    });
    try {
      final ParentProfileModel data = await context
          .read<ParentDashboardService>()
          .fetchProfile();
      if (!mounted) {
        return;
      }
      setState(() {
        _data = data;
        _state = ViewState.success;
      });
      context.read<AuthProvider>().updateUser(data.parent);
    } on ApiException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _state = ViewState.error;
        _errorMessage = error.message;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _state = ViewState.error;
        _errorMessage = 'Profil ma’lumotlari yuklanmadi';
      });
    }
  }

  void _openNotifications() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => const Scaffold(
          backgroundColor: Color(0xFFF7FBFF),
          body: SafeArea(child: NotificationsScreen()),
        ),
      ),
    );
  }

  void _openSettingsScreen() {
    Navigator.of(
      context,
    ).push(MaterialPageRoute<void>(builder: (_) => const SettingsScreen()));
  }

  Future<void> _openEditProfile() async {
    final UserModel? parent =
        _data?.parent ?? context.read<AuthProvider>().user;
    if (parent == null) {
      return;
    }
    final ParentProfileModel? profile = await Navigator.of(context)
        .push<ParentProfileModel>(
          MaterialPageRoute<ParentProfileModel>(
            builder: (_) => EditProfileScreen(
              initialUser: parent,
              profileService: context.read<ParentDashboardService>(),
            ),
          ),
        );
    if (profile == null || !mounted) {
      return;
    }
    setState(() => _data = profile);
    context.read<AuthProvider>().updateUser(profile.parent);
    await context.read<ParentDashboardProvider>().refresh();
    if (!mounted) {
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Profil ma’lumotlari saqlandi')),
    );
  }

  Future<void> _openSecurity() async {
    await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(
        builder: (_) => SecurityScreen(
          profileService: context.read<ParentDashboardService>(),
        ),
      ),
    );
  }

  Future<void> _openNotificationSettings() async {
    await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(
        builder: (_) => const NotificationSettingsScreen(),
      ),
    );
  }

  Future<void> _openLanguage() async {
    await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(builder: (_) => const LanguageScreen()),
    );
  }

  Future<void> _openTheme() async {
    await Navigator.of(
      context,
    ).push<bool>(MaterialPageRoute<bool>(builder: (_) => const ThemeScreen()));
  }

  Future<void> _openHelp() async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(builder: (_) => const HelpSupportScreen()),
    );
  }

  Future<void> _openAbout() async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(builder: (_) => const AboutAppScreen()),
    );
  }

  Future<void> _openAddChild() async {
    final ParentChildModel? child = await Navigator.of(context)
        .push<ParentChildModel>(
          MaterialPageRoute<ParentChildModel>(
            builder: (_) => const AddChildScreen(),
          ),
        );
    if (child != null && mounted) {
      await context.read<ParentDashboardProvider>().selectChild(child.id);
      await _load(force: true);
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Farzand muvaffaqiyatli qo‘shildi')),
      );
    }
  }

  Future<void> _logoutFromProfile() async {
    final bool? confirmed = await showDialog<bool>(
      context: context,
      builder: (BuildContext dialogContext) {
        final c = ProfileColors.of(dialogContext);
        return AlertDialog(
          backgroundColor: c.surface,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
          ),
          title: Text(
            'Hisobdan chiqish',
            style: ProfileTextStyles.title.copyWith(
              fontSize: 20,
              color: c.text,
            ),
          ),
          content: Text(
            'Rostdan ham hisobdan chiqmoqchimisiz?',
            style: ProfileTextStyles.body.copyWith(
              color: c.secondaryText,
            ),
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              child: Text(
                'Bekor qilish',
                style: ProfileTextStyles.link.copyWith(
                  fontSize: 14,
                  color: c.primaryBlue,
                ),
              ),
            ),
            FilledButton(
              onPressed: () => Navigator.of(dialogContext).pop(true),
              style: FilledButton.styleFrom(
                backgroundColor: c.red,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14),
                ),
              ),
              child: const Text('Chiqish'),
            ),
          ],
        );
      },
    );

    if (confirmed != true || !mounted) {
      return;
    }

    context.read<ParentDashboardProvider>().clear();
    await context.read<AuthProvider>().logout();
    if (!mounted) {
      return;
    }
    // AuthGate (ildiz route) reaktiv ravishda logindan keyin bosh sahifaga
    // o'tkazadi. pushAndRemoveUntil AuthGate'ni yo'q qilib yuborardi — natijada
    // qayta login qilinganda dasturga kirmasdi (faqat restartda kirardi).
    Navigator.of(context).popUntil((route) => route.isFirst);
  }

  Future<void> _handleSettingAction(ProfileAction action) async {
    switch (action) {
      case ProfileAction.editProfile:
        await _openEditProfile();
        return;
      case ProfileAction.security:
        await _openSecurity();
        return;
      case ProfileAction.notifications:
        await _openNotificationSettings();
        return;
      case ProfileAction.language:
        await _openLanguage();
        return;
      case ProfileAction.theme:
        await _openTheme();
        return;
      case ProfileAction.help:
        await _openHelp();
        return;
      case ProfileAction.about:
        await _openAbout();
        return;
      case ProfileAction.logout:
        await _logoutFromProfile();
        return;
    }
  }

  @override
  Widget build(BuildContext context) {
    final UserModel? parent =
        _data?.parent ?? context.watch<AuthProvider>().user;
    final List<ParentChildModel> children =
        _data?.children ?? const <ParentChildModel>[];
    final AppPreferencesProvider preferences = context
        .watch<AppPreferencesProvider>();

    final c = ProfileColors.of(context);
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: c.isDark ? Brightness.light : Brightness.dark,
        statusBarBrightness: c.isDark ? Brightness.dark : Brightness.light,
        systemNavigationBarColor: c.surface,
        systemNavigationBarIconBrightness:
            c.isDark ? Brightness.light : Brightness.dark,
      ),
      child: Scaffold(
        backgroundColor: c.background,
        bottomNavigationBar: widget.showBottomNav
            ? const ParentBottomNav()
            : null,
        body: SafeArea(
          child: RefreshIndicator(
            color: ProfileColors.of(context).primaryBlue,
            onRefresh: () => _load(force: true),
            child: SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(
                parent: BouncingScrollPhysics(),
              ),
              padding: ParentUi.screenPadding,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  if (_state == ViewState.loading && _data == null)
                    const _ProfileStateCard.loading()
                  else if (_state == ViewState.error && _data == null)
                    _ProfileStateCard(
                      title: 'Profil yuklanmadi',
                      message: _errorMessage ?? 'Qayta urinib ko‘ring',
                      onPressed: () => _load(force: true),
                    )
                  else ...<Widget>[
                    if (_state == ViewState.loading) ...<Widget>[
                      LinearProgressIndicator(
                        minHeight: 3,
                        color: ProfileColors.of(context).primaryBlue,
                        backgroundColor: const Color(0xFFEAF4FF),
                      ),
                      const SizedBox(height: 8),
                    ],
                    _HeroCard(
                      parent: parent,
                      onEdit: _openEditProfile,
                      onNotifications: _openNotifications,
                      onSettings: _openSettingsScreen,
                    ),
                    const SizedBox(height: 12),
                    _StatsRow(
                      parent: parent,
                      childrenCount: children.length,
                    ),
                    const SizedBox(height: ParentUi.sectionGap),
                    _AddChildCta(onTap: _openAddChild),
                    const SizedBox(height: ParentUi.sectionGap),
                    _SettingsGroup(
                      title: '',
                      rows: <SettingsRowData>[
                        SettingsRowData(
                          action: ProfileAction.security,
                          icon: Icons.lock_outline_rounded,
                          iconColor: ProfileColors.of(context).purple,
                          iconBackground: const Color(0xFFEDE2FF),
                          title: 'Hisob xavfsizligi',
                          subtitle: 'Parolni yangilash',
                        ),
                        SettingsRowData(
                          action: ProfileAction.notifications,
                          icon: Icons.notifications_none_rounded,
                          iconColor: ProfileColors.of(context).green,
                          iconBackground: const Color(0xFFE4F8EC),
                          title: 'Bildirishnomalar',
                          subtitle:
                              'Davomat, to‘lov va progress xabarlarini boshqarish',
                        ),
                        SettingsRowData(
                          action: ProfileAction.language,
                          icon: Icons.language_rounded,
                          iconColor: ProfileColors.of(context).orange,
                          iconBackground: const Color(0xFFFFF1D8),
                          title: 'Til',
                          value: preferences.languageLabel,
                        ),
                        SettingsRowData(
                          action: ProfileAction.theme,
                          icon: Icons.dark_mode_outlined,
                          iconColor: ProfileColors.of(context).primaryBlue,
                          iconBackground: const Color(0xFFE8F1FF),
                          title: 'Mavzu',
                          value: preferences.themeLabel,
                        ),
                        const SettingsRowData(
                          action: ProfileAction.about,
                          icon: Icons.info_outline_rounded,
                          iconColor: Color(0xFF6B7280),
                          iconBackground: Color(0xFFF0F2F6),
                          title: 'Ilova haqida',
                          value: 'Versiya 1.0.0',
                        ),
                      ],
                      onActionTap: _handleSettingAction,
                    ),
                    const SizedBox(height: 14),
                    _LogoutButton(onTap: _logoutFromProfile),
                    const SizedBox(height: 8),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _HeroCard extends StatelessWidget {
  const _HeroCard({
    required this.parent,
    required this.onEdit,
    required this.onNotifications,
    required this.onSettings,
  });

  final UserModel? parent;
  final VoidCallback onEdit;
  final VoidCallback onNotifications;
  final VoidCallback onSettings;

  @override
  Widget build(BuildContext context) {
    final String name = parent?.fullName.trim().isNotEmpty == true
        ? parent!.fullName
        : 'Ota-ona';
    final String centerName = parent?.center?.name.trim() ?? '';
    final String phone = parent?.phone.trim() ?? '';
    final String email = parent?.email.trim() ?? '';

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(16, 14, 14, 18),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: <Color>[Color(0xFF1E73F8), Color(0xFF4F8FFA)],
        ),
        boxShadow: const <BoxShadow>[
          BoxShadow(
            color: Color(0x331E73F8),
            blurRadius: 22,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 5,
                ),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.18),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  'Ota-ona paneli',
                  style: ProfileTextStyles.label.copyWith(
                    color: Colors.white,
                    fontSize: 11,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: <Widget>[
              Stack(
                clipBehavior: Clip.none,
                children: <Widget>[
                  Container(
                    width: 76,
                    height: 76,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: Colors.white.withValues(alpha: 0.16),
                      border: Border.all(
                        color: Colors.white.withValues(alpha: 0.45),
                        width: 2,
                      ),
                    ),
                    clipBehavior: Clip.antiAlias,
                    child: AdaptiveAvatar(
                      name: name,
                      imageUrl: parent?.avatarUrl ?? '',
                      size: 76,
                      icon: Icons.person_outline_rounded,
                    ),
                  ),
                  Positioned(
                    right: -2,
                    bottom: -2,
                    child: GestureDetector(
                      onTap: onEdit,
                      child: Container(
                        width: 26,
                        height: 26,
                        decoration: BoxDecoration(
                          color: Colors.white,
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: const Color(0xFF1E73F8),
                            width: 1.4,
                          ),
                        ),
                        child: const Icon(
                          Icons.edit_outlined,
                          color: Color(0xFF1E73F8),
                          size: 14,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      name,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: ProfileTextStyles.title.copyWith(
                        color: Colors.white,
                        fontSize: 18,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: <Widget>[
                        const Icon(
                          Icons.verified_rounded,
                          size: 14,
                          color: Color(0xFFC2DDFF),
                        ),
                        const SizedBox(width: 4),
                        Flexible(
                          child: Text(
                            centerName.isEmpty
                                ? 'Ota-ona'
                                : 'Ota-ona · $centerName',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: ProfileTextStyles.body.copyWith(
                              color: const Color(0xFFE0EBFF),
                              fontSize: 12.4,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          if (phone.isNotEmpty || email.isNotEmpty)
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: <Widget>[
                if (phone.isNotEmpty)
                  _HeroChip(icon: Icons.phone_outlined, text: phone),
                if (email.isNotEmpty)
                  _HeroChip(icon: Icons.mail_outline_rounded, text: email),
              ],
            ),
        ],
      ),
    );
  }
}

class _HeroChip extends StatelessWidget {
  const _HeroChip({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      constraints: const BoxConstraints(maxWidth: 220),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.16),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Icon(icon, color: const Color(0xFFE0EBFF), size: 13),
          const SizedBox(width: 6),
          Flexible(
            child: Text(
              text,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: ProfileTextStyles.body.copyWith(
                color: Colors.white,
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}


class _AddChildCta extends StatelessWidget {
  const _AddChildCta({required this.onTap});

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
          padding: const EdgeInsets.fromLTRB(14, 14, 14, 14),
          decoration: BoxDecoration(
            color: const Color(0xFFEAF4FF),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: ProfileColors.of(context).primaryBlue.withValues(alpha: 0.25),
            ),
          ),
          child: Row(
            children: <Widget>[
              Container(
                width: 38,
                height: 38,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: ProfileColors.of(context).primaryBlue,
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.person_add_alt_1_rounded,
                  color: Colors.white,
                  size: 19,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      'Farzand qo‘shish',
                      style: ProfileTextStyles.title.copyWith(
                        color: ProfileColors.of(context).text,
                        fontSize: 14,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'Yangi farzand kodini kiriting va profilga ulang',
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: ProfileTextStyles.body.copyWith(
                        color: ProfileColors.of(context).secondaryText,
                        fontSize: 11.8,
                        height: 1.3,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 6),
              Icon(
                Icons.chevron_right_rounded,
                color: ProfileColors.of(context).primaryBlue,
                size: 22,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SettingsGroup extends StatelessWidget {
  const _SettingsGroup({
    required this.title,
    required this.rows,
    required this.onActionTap,
  });

  final String title;
  final List<SettingsRowData> rows;
  final Future<void> Function(ProfileAction action) onActionTap;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        if (title.trim().isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(left: 4, bottom: 8),
            child: Text(
              title.toUpperCase(),
              style: ProfileTextStyles.label.copyWith(
                color: ProfileColors.of(context).secondaryText,
                fontSize: 10.5,
                letterSpacing: 0.6,
              ),
            ),
          ),
        ProfileCard(
          padding: EdgeInsets.zero,
          child: Column(
            children: <Widget>[
              for (int index = 0; index < rows.length; index++)
                SettingsRow(
                  data: rows[index],
                  showDivider: index != rows.length - 1,
                  onTap: () => onActionTap(rows[index].action),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

class _StatsRow extends StatelessWidget {
  const _StatsRow({required this.parent, required this.childrenCount});

  final UserModel? parent;
  final int childrenCount;

  String _formatJoined(DateTime? date) {
    if (date == null) return '—';
    const months = <String>[
      'Yan', 'Fev', 'Mar', 'Apr', 'May', 'Iyn',
      'Iyl', 'Avg', 'Sen', 'Okt', 'Noy', 'Dek',
    ];
    return '${months[date.month - 1]} ${date.year}';
  }

  @override
  Widget build(BuildContext context) {
    final centerName = parent?.center?.name.trim() ?? '';
    final joinedLabel = _formatJoined(parent?.joinedDate);

    return Row(
      children: <Widget>[
        Expanded(
          child: _StatCard(
            icon: Icons.family_restroom_rounded,
            color: ProfileColors.of(context).primaryBlue,
            value: '$childrenCount',
            label: childrenCount == 1 ? 'Farzand' : 'Farzandlar',
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _StatCard(
            icon: Icons.shield_outlined,
            color: ProfileColors.of(context).green,
            value: 'Faol',
            label: 'Hisob',
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _StatCard(
            icon: Icons.school_outlined,
            color: ProfileColors.of(context).purple,
            value: centerName.isEmpty ? joinedLabel : centerName,
            label: centerName.isEmpty ? 'Qo‘shilgan' : 'Markaz',
          ),
        ),
      ],
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({
    required this.icon,
    required this.color,
    required this.value,
    required this.label,
  });

  final IconData icon;
  final Color color;
  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    final c = ProfileColors.of(context);
    return Container(
      padding: const EdgeInsets.fromLTRB(10, 10, 10, 10),
      decoration: BoxDecoration(
        color: c.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: c.border),
        boxShadow: c.isDark ? null : ProfileShadows.card,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Container(
            width: 26,
            height: 26,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, size: 14, color: color),
          ),
          const SizedBox(height: 8),
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: ProfileTextStyles.title.copyWith(
              color: c.text,
              fontSize: 13,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: ProfileTextStyles.body.copyWith(
              color: c.secondaryText,
              fontSize: 11,
            ),
          ),
        ],
      ),
    );
  }
}

class _LogoutButton extends StatelessWidget {
  const _LogoutButton({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: ProfileColors.of(context).red.withValues(alpha: 0.4),
            ),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: <Widget>[
              Icon(
                Icons.logout_rounded,
                color: ProfileColors.of(context).red,
                size: 18,
              ),
              const SizedBox(width: 8),
              Text(
                'Hisobdan chiqish',
                style: ProfileTextStyles.title.copyWith(
                  color: ProfileColors.of(context).red,
                  fontSize: 14,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class SettingsRow extends StatelessWidget {
  const SettingsRow({
    super.key,
    required this.data,
    required this.showDivider,
    required this.onTap,
  });

  final SettingsRowData data;
  final bool showDivider;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = ProfileColors.of(context);
    return Column(
      children: <Widget>[
        InkWell(
          onTap: onTap,
          child: Padding(
            padding: ParentUi.denseCardPadding,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: <Widget>[
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: data.iconBackground,
                    shape: BoxShape.circle,
                  ),
                  child: Icon(data.icon, color: data.iconColor, size: 20),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        data.title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: ProfileTextStyles.title.copyWith(
                          color: data.destructive ? c.red : c.text,
                          fontSize: 14.4,
                        ),
                      ),
                      if (data.subtitle != null) ...<Widget>[
                        const SizedBox(height: 4),
                        Text(
                          data.subtitle!,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: ProfileTextStyles.body.copyWith(
                            color: data.destructive ? c.red : c.secondaryText,
                            fontSize: 12.4,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
                if (data.value != null) ...<Widget>[
                  const SizedBox(width: 10),
                  Text(
                    data.value!,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    textAlign: TextAlign.right,
                    style: ProfileTextStyles.body.copyWith(
                      color: c.text,
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
                if (!data.destructive) ...<Widget>[
                  const SizedBox(width: 4),
                  Icon(
                    Icons.chevron_right_rounded,
                    color: c.secondaryText,
                    size: 18,
                  ),
                ],
              ],
            ),
          ),
        ),
        if (showDivider)
          Padding(
            padding: const EdgeInsets.only(left: 68),
            child: Divider(height: 1, color: c.border),
          ),
      ],
    );
  }
}

class ParentBottomNav extends StatelessWidget {
  const ParentBottomNav({super.key});

  @override
  Widget build(BuildContext context) {
    final c = ProfileColors.of(context);
    return Container(
      decoration: BoxDecoration(
        color: c.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
        boxShadow: ProfileShadows.topNav,
      ),
      child: SafeArea(
        top: false,
        child: ClipRRect(
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
          child: BottomNavigationBar(
            currentIndex: 4,
            onTap: (_) {},
            type: BottomNavigationBarType.fixed,
            backgroundColor: c.surface,
            elevation: 0,
            iconSize: 24,
            selectedItemColor: ProfileColors.of(context).primaryBlue,
            unselectedItemColor: ProfileColors.of(context).secondaryText,
            selectedLabelStyle: ProfileTextStyles.label.copyWith(
              fontSize: 11,
            ),
            unselectedLabelStyle: ProfileTextStyles.label.copyWith(
              fontSize: 11,
              fontWeight: FontWeight.w600,
            ),
            items: const <BottomNavigationBarItem>[
              BottomNavigationBarItem(
                icon: Icon(Icons.home_rounded),
                label: 'Bosh sahifa',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.event_available_outlined),
                label: 'Davomat',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.account_balance_wallet_outlined),
                label: 'To‘lovlar',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.bar_chart_rounded),
                label: 'Progress',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.person_rounded),
                label: 'Profil',
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class ProfileCard extends StatelessWidget {
  const ProfileCard({super.key, required this.child, required this.padding});

  final Widget child;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    final c = ProfileColors.of(context);
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        color: c.surface,
        borderRadius: BorderRadius.circular(ParentUi.cardRadius),
        border: Border.all(color: c.border),
        boxShadow: c.isDark ? null : ProfileShadows.card,
      ),
      child: child,
    );
  }
}

class _ProfileStateCard extends StatelessWidget {
  const _ProfileStateCard({
    required this.title,
    required this.message,
    this.onPressed,
  }) : loading = false;

  const _ProfileStateCard.loading()
    : title = '',
      message = '',
      onPressed = null,
      loading = true;

  final String title;
  final String message;
  final VoidCallback? onPressed;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    return ProfileCard(
      padding: const EdgeInsets.fromLTRB(18, 28, 18, 28),
      child: loading
          ? SizedBox(
              height: 200,
              child: Center(
                child: CircularProgressIndicator(
                  color: ProfileColors.of(context).primaryBlue,
                ),
              ),
            )
          : Column(
              children: <Widget>[
                Icon(
                  Icons.info_outline_rounded,
                  color: ProfileColors.of(context).primaryBlue,
                  size: 40,
                ),
                const SizedBox(height: 12),
                Text(
                  title,
                  textAlign: TextAlign.center,
                  style: ProfileTextStyles.title.copyWith(fontSize: 18),
                ),
                const SizedBox(height: 8),
                Text(
                  message,
                  textAlign: TextAlign.center,
                  style: ProfileTextStyles.body.copyWith(
                    color: ProfileColors.of(context).secondaryText,
                    fontSize: 14,
                  ),
                ),
                if (onPressed != null) ...<Widget>[
                  const SizedBox(height: 16),
                  TextButton(
                    onPressed: onPressed,
                    style: TextButton.styleFrom(
                      backgroundColor: const Color(0xFFEAF4FF),
                      foregroundColor: ProfileColors.of(context).primaryBlue,
                    ),
                    child: const Text('Qayta urinish'),
                  ),
                ],
              ],
            ),
    );
  }
}

enum ProfileAction {
  editProfile,
  security,
  notifications,
  language,
  theme,
  help,
  about,
  logout,
}

class SettingsRowData {
  const SettingsRowData({
    required this.action,
    required this.icon,
    required this.iconColor,
    required this.iconBackground,
    required this.title,
    this.subtitle,
    this.value,
    this.destructive = false,
  });

  final ProfileAction action;
  final IconData icon;
  final Color iconColor;
  final Color iconBackground;
  final String title;
  final String? subtitle;
  final String? value;
  final bool destructive;
}

class ProfileColors {
  const ProfileColors._({
    required this.background,
    required this.surface,
    required this.primaryBlue,
    required this.red,
    required this.green,
    required this.purple,
    required this.orange,
    required this.pink,
    required this.text,
    required this.secondaryText,
    required this.border,
    required this.muted,
  });

  final Color background;
  final Color surface;
  final Color primaryBlue;
  final Color red;
  final Color green;
  final Color purple;
  final Color orange;
  final Color pink;
  final Color text;
  final Color secondaryText;
  final Color border;
  final Color muted;

  bool get isDark => background == _dark.background;

  static const ProfileColors _light = ProfileColors._(
    background: Color(0xFFF7FBFF),
    surface: Color(0xFFFFFFFF),
    primaryBlue: Color(0xFF1E73F8),
    red: Color(0xFFEF4444),
    green: Color(0xFF10B981),
    purple: Color(0xFF7C3AED),
    orange: Color(0xFFF59E0B),
    pink: Color(0xFFEC4899),
    text: Color(0xFF111827),
    secondaryText: Color(0xFF6B7280),
    border: Color(0xFFE5EAF2),
    muted: Color(0xFFF1F4F9),
  );

  static const ProfileColors _dark = ProfileColors._(
    background: Color(0xFF0B0F17),
    surface: Color(0xFF141926),
    primaryBlue: Color(0xFF4D8DFF),
    red: Color(0xFFFF6F6F),
    green: Color(0xFF34D399),
    purple: Color(0xFFA78BFA),
    orange: Color(0xFFFBBF24),
    pink: Color(0xFFF472B6),
    text: Color(0xFFEAF1FB),
    secondaryText: Color(0xFF94A3B8),
    border: Color(0xFF24304A),
    muted: Color(0xFF1A2030),
  );

  static ProfileColors of(BuildContext context) {
    return Theme.of(context).brightness == Brightness.dark ? _dark : _light;
  }
}

class ProfileTextStyles {
  const ProfileTextStyles._();

  static TextStyle get title {
    return GoogleFonts.inter(
      fontSize: 17,
      height: 1.16,
      fontWeight: FontWeight.w800,
      letterSpacing: 0,
    );
  }

  static TextStyle get body {
    return GoogleFonts.inter(
      fontSize: 14,
      height: 1.28,
      fontWeight: FontWeight.w500,
      letterSpacing: 0,
    );
  }

  static TextStyle get label {
    return GoogleFonts.inter(
      fontSize: 12.5,
      height: 1.16,
      fontWeight: FontWeight.w800,
      letterSpacing: 0,
    );
  }

  static TextStyle get link {
    return GoogleFonts.inter(
      fontSize: 14,
      height: 1.16,
      fontWeight: FontWeight.w800,
      letterSpacing: 0,
    );
  }
}

class ProfileShadows {
  const ProfileShadows._();

  static const List<BoxShadow> soft = <BoxShadow>[
    BoxShadow(color: Color(0x0F0B1220), blurRadius: 18, offset: Offset(0, 8)),
  ];

  static const List<BoxShadow> card = <BoxShadow>[
    BoxShadow(color: Color(0x0D0B1220), blurRadius: 18, offset: Offset(0, 8)),
  ];

  static const List<BoxShadow> topNav = <BoxShadow>[
    BoxShadow(color: Color(0x140B1220), blurRadius: 24, offset: Offset(0, -8)),
  ];
}
