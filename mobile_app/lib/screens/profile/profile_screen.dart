import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/parent_models.dart';
import 'package:chaqmoq_mobile/providers/app_preferences_provider.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/parent_dashboard_provider.dart';
import 'package:chaqmoq_mobile/screens/auth/login_screen.dart';
import 'package:chaqmoq_mobile/screens/notifications/notifications_screen.dart';
import 'package:chaqmoq_mobile/screens/parent/add_child_screen.dart';
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
        return AlertDialog(
          backgroundColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
          ),
          title: Text(
            'Hisobdan chiqish',
            style: ProfileTextStyles.title.copyWith(fontSize: 20),
          ),
          content: Text(
            'Rostdan ham hisobdan chiqmoqchimisiz?',
            style: ProfileTextStyles.body.copyWith(
              color: ProfileColors.secondaryText,
            ),
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              child: Text(
                'Bekor qilish',
                style: ProfileTextStyles.link.copyWith(fontSize: 14),
              ),
            ),
            FilledButton(
              onPressed: () => Navigator.of(dialogContext).pop(true),
              style: FilledButton.styleFrom(
                backgroundColor: ProfileColors.red,
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
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute<void>(builder: (_) => const LoginScreen()),
      (_) => false,
    );
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

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.dark,
        statusBarBrightness: Brightness.light,
        systemNavigationBarColor: Colors.white,
        systemNavigationBarIconBrightness: Brightness.dark,
      ),
      child: Scaffold(
        backgroundColor: ProfileColors.background,
        bottomNavigationBar: widget.showBottomNav
            ? const ParentBottomNav()
            : null,
        body: SafeArea(
          child: RefreshIndicator(
            color: ProfileColors.primaryBlue,
            onRefresh: () => _load(force: true),
            child: SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(
                parent: BouncingScrollPhysics(),
              ),
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 32),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  ProfileHeader(
                    onNotifications: _openNotifications,
                    onSettings: _openSettingsScreen,
                  ),
                  const SizedBox(height: 16),
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
                      const LinearProgressIndicator(
                        minHeight: 3,
                        color: ProfileColors.primaryBlue,
                        backgroundColor: Color(0xFFEAF4FF),
                      ),
                      const SizedBox(height: 10),
                    ],
                    ParentInfoCard(parent: parent, onTap: _openEditProfile),
                    const SizedBox(height: 18),
                    ChildrenSection(
                      children: children,
                      onAddChild: _openAddChild,
                    ),
                    const SizedBox(height: 18),
                    SettingsListCard(
                      languageLabel: preferences.languageLabel,
                      themeLabel: preferences.themeLabel,
                      onActionTap: _handleSettingAction,
                    ),
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

class ProfileHeader extends StatelessWidget {
  const ProfileHeader({
    super.key,
    required this.onNotifications,
    required this.onSettings,
  });

  final VoidCallback onNotifications;
  final VoidCallback onSettings;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 6,
                ),
                decoration: BoxDecoration(
                  color: const Color(0xFFEAF4FF),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  'Ota-ona paneli',
                  style: ProfileTextStyles.label.copyWith(
                    color: ProfileColors.primaryBlue,
                    fontSize: 11.5,
                  ),
                ),
              ),
              const SizedBox(height: 10),
              Text(
                'Profil',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: ProfileTextStyles.title.copyWith(fontSize: 28),
              ),
            ],
          ),
        ),
        const SizedBox(width: 8),
        _CircleActionButton(
          icon: Icons.notifications_none_rounded,
          showBadge: true,
          onTap: onNotifications,
        ),
        const SizedBox(width: 8),
        _CircleActionButton(icon: Icons.settings_outlined, onTap: onSettings),
      ],
    );
  }
}

class ParentInfoCard extends StatelessWidget {
  const ParentInfoCard({super.key, required this.parent, required this.onTap});

  final UserModel? parent;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final String name = parent?.fullName.trim().isNotEmpty == true
        ? parent!.fullName
        : 'Ota-ona';
    final String phone = parent?.phone.trim().isNotEmpty == true
        ? parent!.phone
        : 'Telefon kiritilmagan';
    final String email = parent?.email.trim().isNotEmpty == true
        ? parent!.email
        : 'Email kiritilmagan';

    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: ProfileCard(
          padding: const EdgeInsets.fromLTRB(18, 18, 16, 18),
          child: Row(
            children: <Widget>[
              Stack(
                clipBehavior: Clip.none,
                children: <Widget>[
                  Container(
                    width: 88,
                    height: 88,
                    decoration: const BoxDecoration(
                      shape: BoxShape.circle,
                      color: Color(0xFFE7F0FF),
                    ),
                    clipBehavior: Clip.antiAlias,
                    child: Image.asset(
                      'assets/images/parent_avatar.png',
                      fit: BoxFit.cover,
                    ),
                  ),
                  Positioned(
                    right: -2,
                    bottom: -2,
                    child: Container(
                      width: 34,
                      height: 34,
                      decoration: BoxDecoration(
                        color: Colors.white,
                        shape: BoxShape.circle,
                        boxShadow: ProfileShadows.soft,
                        border: Border.all(color: ProfileColors.border),
                      ),
                      child: const Icon(
                        Icons.photo_camera_outlined,
                        color: ProfileColors.primaryBlue,
                        size: 19,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: ProfileTextStyles.title.copyWith(fontSize: 20),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      'Ota-ona paneli',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: ProfileTextStyles.body.copyWith(
                        color: ProfileColors.secondaryText,
                        fontSize: 14,
                      ),
                    ),
                    const SizedBox(height: 12),
                    _ContactLine(icon: Icons.phone_outlined, text: phone),
                    const SizedBox(height: 7),
                    _ContactLine(icon: Icons.mail_outline_rounded, text: email),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              const Icon(
                Icons.chevron_right_rounded,
                color: Color(0xFF8B95A1),
                size: 22,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class ChildrenSection extends StatelessWidget {
  const ChildrenSection({
    super.key,
    required this.children,
    required this.onAddChild,
  });

  final List<ParentChildModel> children;
  final VoidCallback onAddChild;

  @override
  Widget build(BuildContext context) {
    final ParentDashboardProvider dashboard = context
        .watch<ParentDashboardProvider>();
    final int? selectedId =
        dashboard.selectedChildId ?? dashboard.data?.selectedChild.id;

    final List<ChildProfileData> cards = <ChildProfileData>[
      for (int index = 0; index < children.length; index++)
        ChildProfileData(
          id: children[index].id,
          name: children[index].fullName,
          group: _childGroupLine(children[index]),
          displayId: children[index].childCode.isNotEmpty
              ? 'Kod: ${children[index].childCode}'
              : '',
          avatar: _avatarAsset(index),
          selected:
              children[index].id == selectedId ||
              (selectedId == null && index == 0),
        ),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          children: <Widget>[
            Expanded(
              child: Text(
                'Mening farzandlarim',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: ProfileTextStyles.title.copyWith(fontSize: 18),
              ),
            ),
            TextButton(
              onPressed: onAddChild,
              style: TextButton.styleFrom(
                foregroundColor: ProfileColors.primaryBlue,
                padding: EdgeInsets.zero,
                minimumSize: const Size(0, 30),
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  Text(
                    'Qo‘shish',
                    style: ProfileTextStyles.link.copyWith(fontSize: 14),
                  ),
                  const SizedBox(width: 6),
                  const Icon(Icons.add_rounded, size: 22),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        if (cards.isEmpty)
          ProfileCard(
            padding: const EdgeInsets.all(18),
            child: Text(
              'Farzandlar ro‘yxati topilmadi',
              style: ProfileTextStyles.body.copyWith(
                color: ProfileColors.secondaryText,
                fontSize: 13.5,
              ),
            ),
          )
        else
          SizedBox(
            height: 186,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              physics: const BouncingScrollPhysics(),
              itemCount: cards.length,
              separatorBuilder: (_, _) => const SizedBox(width: 12),
              itemBuilder: (BuildContext context, int index) {
                return ChildCard(data: cards[index]);
              },
            ),
          ),
      ],
    );
  }
}

class ChildCard extends StatelessWidget {
  const ChildCard({super.key, required this.data});

  final ChildProfileData data;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(18),
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: () =>
            context.read<ParentDashboardProvider>().selectChild(data.id),
        child: Ink(
          width: 206,
          padding: const EdgeInsets.fromLTRB(14, 18, 14, 14),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(18),
            border: Border.all(
              color: data.selected
                  ? ProfileColors.primaryBlue
                  : ProfileColors.border,
              width: data.selected ? 2 : 1,
            ),
            boxShadow: ProfileShadows.card,
          ),
          child: Stack(
            children: <Widget>[
              if (data.selected)
                Positioned(
                  right: 0,
                  top: 0,
                  child: Container(
                    width: 26,
                    height: 26,
                    decoration: const BoxDecoration(
                      color: ProfileColors.primaryBlue,
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(
                      Icons.check_rounded,
                      color: Colors.white,
                      size: 18,
                    ),
                  ),
                ),
              Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: <Widget>[
                    Container(
                      width: 62,
                      height: 62,
                      decoration: const BoxDecoration(shape: BoxShape.circle),
                      clipBehavior: Clip.antiAlias,
                      child: Image.asset(data.avatar, fit: BoxFit.cover),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      data.name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      textAlign: TextAlign.center,
                      style: ProfileTextStyles.title.copyWith(fontSize: 15.5),
                    ),
                    const SizedBox(height: 7),
                    Text(
                      data.group,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      textAlign: TextAlign.center,
                      style: ProfileTextStyles.body.copyWith(
                        color: ProfileColors.secondaryText,
                        fontSize: 13,
                      ),
                    ),
                    if (data.displayId.isNotEmpty) ...<Widget>[
                      const SizedBox(height: 5),
                      Text(
                        data.displayId,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        textAlign: TextAlign.center,
                        style: ProfileTextStyles.body.copyWith(
                          color: ProfileColors.secondaryText,
                          fontSize: 13,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class SettingsListCard extends StatelessWidget {
  const SettingsListCard({
    super.key,
    required this.languageLabel,
    required this.themeLabel,
    required this.onActionTap,
  });

  final String languageLabel;
  final String themeLabel;
  final Future<void> Function(ProfileAction action) onActionTap;

  List<SettingsRowData> get _rows => <SettingsRowData>[
    const SettingsRowData(
      action: ProfileAction.editProfile,
      icon: Icons.person_outline_rounded,
      iconColor: ProfileColors.primaryBlue,
      iconBackground: Color(0xFFE8F1FF),
      title: 'Shaxsiy ma’lumotlar',
      subtitle: 'Telefon, email va ismni tahrirlash',
    ),
    const SettingsRowData(
      action: ProfileAction.security,
      icon: Icons.lock_outline_rounded,
      iconColor: ProfileColors.purple,
      iconBackground: Color(0xFFEDE2FF),
      title: 'Hisob xavfsizligi',
      subtitle: 'Parolni yangilash',
    ),
    const SettingsRowData(
      action: ProfileAction.notifications,
      icon: Icons.notifications_none_rounded,
      iconColor: ProfileColors.green,
      iconBackground: Color(0xFFE4F8EC),
      title: 'Bildirishnoma sozlamalari',
      subtitle: 'Push bildirishnomalarni boshqarish',
    ),
    SettingsRowData(
      action: ProfileAction.language,
      icon: Icons.language_rounded,
      iconColor: ProfileColors.orange,
      iconBackground: const Color(0xFFFFF1D8),
      title: 'Til',
      value: languageLabel,
    ),
    SettingsRowData(
      action: ProfileAction.theme,
      icon: Icons.dark_mode_outlined,
      iconColor: ProfileColors.primaryBlue,
      iconBackground: const Color(0xFFE8F1FF),
      title: 'Mavzu',
      value: themeLabel,
    ),
    const SettingsRowData(
      action: ProfileAction.help,
      icon: Icons.help_outline_rounded,
      iconColor: ProfileColors.pink,
      iconBackground: Color(0xFFFFE1F0),
      title: 'Yordam va qo‘llab-quvvatlash',
      subtitle: 'Savollar va bog‘lanish',
    ),
    const SettingsRowData(
      action: ProfileAction.about,
      icon: Icons.info_outline_rounded,
      iconColor: Color(0xFF6B7280),
      iconBackground: Color(0xFFF0F2F6),
      title: 'Ilova haqida',
      value: 'Versiya 1.0.0',
    ),
    const SettingsRowData(
      action: ProfileAction.logout,
      icon: Icons.logout_rounded,
      iconColor: ProfileColors.red,
      iconBackground: Color(0xFFFFE7E7),
      title: 'Chiqish',
      subtitle: 'Hisobdan chiqish',
      destructive: true,
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final List<SettingsRowData> rows = _rows;
    return ProfileCard(
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
    return Column(
      children: <Widget>[
        InkWell(
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(14, 14, 14, 14),
            child: Row(
              children: <Widget>[
                Container(
                  width: 42,
                  height: 42,
                  decoration: BoxDecoration(
                    color: data.iconBackground,
                    shape: BoxShape.circle,
                  ),
                  child: Icon(data.icon, color: data.iconColor, size: 23),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        data.title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: ProfileTextStyles.title.copyWith(
                          color: data.destructive
                              ? ProfileColors.red
                              : ProfileColors.text,
                          fontSize: 15.5,
                        ),
                      ),
                      if (data.subtitle != null) ...<Widget>[
                        const SizedBox(height: 5),
                        Text(
                          data.subtitle!,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: ProfileTextStyles.body.copyWith(
                            color: data.destructive
                                ? ProfileColors.red
                                : ProfileColors.secondaryText,
                            fontSize: 13,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
                if (data.value != null) ...<Widget>[
                  const SizedBox(width: 8),
                  Flexible(
                    child: Text(
                      data.value!,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      textAlign: TextAlign.right,
                      style: ProfileTextStyles.body.copyWith(
                        color: ProfileColors.secondaryText,
                        fontSize: 13,
                      ),
                    ),
                  ),
                ],
                if (!data.destructive) ...<Widget>[
                  const SizedBox(width: 6),
                  const Icon(
                    Icons.chevron_right_rounded,
                    color: Color(0xFF8B95A1),
                    size: 20,
                  ),
                ],
              ],
            ),
          ),
        ),
        if (showDivider)
          const Padding(
            padding: EdgeInsets.only(left: 68),
            child: Divider(height: 1, color: ProfileColors.border),
          ),
      ],
    );
  }
}

class ParentBottomNav extends StatelessWidget {
  const ParentBottomNav({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
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
            backgroundColor: Colors.white,
            elevation: 0,
            iconSize: 24,
            selectedItemColor: ProfileColors.primaryBlue,
            unselectedItemColor: ProfileColors.secondaryText,
            selectedLabelStyle: ProfileTextStyles.label.copyWith(
              fontSize: 11.5,
            ),
            unselectedLabelStyle: ProfileTextStyles.label.copyWith(
              fontSize: 11.5,
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
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: ProfileColors.border),
        boxShadow: ProfileShadows.card,
      ),
      child: child,
    );
  }
}

class _ContactLine extends StatelessWidget {
  const _ContactLine({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        Icon(icon, color: ProfileColors.secondaryText, size: 18),
        const SizedBox(width: 9),
        Expanded(
          child: Text(
            text,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: ProfileTextStyles.body.copyWith(
              color: ProfileColors.secondaryText,
              fontSize: 13.5,
            ),
          ),
        ),
      ],
    );
  }
}

class _CircleActionButton extends StatelessWidget {
  const _CircleActionButton({
    required this.icon,
    required this.onTap,
    this.showBadge = false,
  });

  final IconData icon;
  final VoidCallback onTap;
  final bool showBadge;

  @override
  Widget build(BuildContext context) {
    final int unreadCount =
        context.watch<ParentDashboardProvider>().data?.unreadNotifications ?? 0;
    return Stack(
      clipBehavior: Clip.none,
      children: <Widget>[
        InkWell(
          onTap: onTap,
          customBorder: const CircleBorder(),
          child: Container(
            width: 46,
            height: 46,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: Colors.white,
              shape: BoxShape.circle,
              border: Border.all(color: ProfileColors.border),
              boxShadow: ProfileShadows.soft,
            ),
            child: Icon(icon, color: ProfileColors.text, size: 25),
          ),
        ),
        if (showBadge && unreadCount > 0)
          Positioned(
            right: 4,
            top: 2,
            child: Container(
              constraints: const BoxConstraints(minWidth: 18),
              height: 18,
              alignment: Alignment.center,
              padding: const EdgeInsets.symmetric(horizontal: 4),
              decoration: BoxDecoration(
                color: ProfileColors.red,
                borderRadius: BorderRadius.circular(999),
                border: Border.all(color: Colors.white, width: 2),
              ),
              child: Text(
                unreadCount > 99 ? '99+' : '$unreadCount',
                style: ProfileTextStyles.label.copyWith(
                  color: Colors.white,
                  fontSize: 9.5,
                  height: 1,
                ),
              ),
            ),
          ),
      ],
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
      padding: const EdgeInsets.fromLTRB(18, 36, 18, 36),
      child: loading
          ? const SizedBox(
              height: 220,
              child: Center(
                child: CircularProgressIndicator(
                  color: ProfileColors.primaryBlue,
                ),
              ),
            )
          : Column(
              children: <Widget>[
                const Icon(
                  Icons.info_outline_rounded,
                  color: ProfileColors.primaryBlue,
                  size: 40,
                ),
                const SizedBox(height: 12),
                Text(
                  title,
                  textAlign: TextAlign.center,
                  style: ProfileTextStyles.title.copyWith(fontSize: 19),
                ),
                const SizedBox(height: 8),
                Text(
                  message,
                  textAlign: TextAlign.center,
                  style: ProfileTextStyles.body.copyWith(
                    color: ProfileColors.secondaryText,
                    fontSize: 14,
                  ),
                ),
                if (onPressed != null) ...<Widget>[
                  const SizedBox(height: 16),
                  TextButton(
                    onPressed: onPressed,
                    style: TextButton.styleFrom(
                      backgroundColor: const Color(0xFFEAF4FF),
                      foregroundColor: ProfileColors.primaryBlue,
                    ),
                    child: const Text('Qayta urinish'),
                  ),
                ],
              ],
            ),
    );
  }
}

String _avatarAsset(int index) {
  const List<String> assets = <String>[
    'assets/images/profile_child_sardor.png',
    'assets/images/profile_child_madina.png',
    'assets/images/profile_child_ali.png',
  ];
  return assets[index % assets.length];
}

String _childGroupLine(ParentChildModel child) {
  final List<String> parts = <String>[
    if (child.className.trim().isNotEmpty) child.className.trim(),
    if (child.groupName.trim().isNotEmpty) child.groupName.trim(),
  ];
  return parts.isEmpty ? 'Guruh biriktirilmagan' : parts.join(' • ');
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

class ChildProfileData {
  const ChildProfileData({
    required this.name,
    required this.group,
    required this.id,
    required this.displayId,
    required this.avatar,
    this.selected = false,
  });

  final String name;
  final String group;
  final int id;
  final String displayId;
  final String avatar;
  final bool selected;
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
  const ProfileColors._();

  static const Color background = Color(0xFFF7FBFF);
  static const Color primaryBlue = Color(0xFF1E73F8);
  static const Color red = Color(0xFFEF4444);
  static const Color green = Color(0xFF10B981);
  static const Color purple = Color(0xFF7C3AED);
  static const Color orange = Color(0xFFF59E0B);
  static const Color pink = Color(0xFFEC4899);
  static const Color text = Color(0xFF111827);
  static const Color secondaryText = Color(0xFF6B7280);
  static const Color border = Color(0xFFE5EAF2);
}

class ProfileTextStyles {
  const ProfileTextStyles._();

  static TextStyle get title {
    return GoogleFonts.inter(
      fontSize: 18,
      height: 1.16,
      fontWeight: FontWeight.w800,
      color: ProfileColors.text,
      letterSpacing: 0,
    );
  }

  static TextStyle get body {
    return GoogleFonts.inter(
      fontSize: 15,
      height: 1.28,
      fontWeight: FontWeight.w500,
      color: ProfileColors.text,
      letterSpacing: 0,
    );
  }

  static TextStyle get label {
    return GoogleFonts.inter(
      fontSize: 13,
      height: 1.16,
      fontWeight: FontWeight.w800,
      color: ProfileColors.text,
      letterSpacing: 0,
    );
  }

  static TextStyle get link {
    return GoogleFonts.inter(
      fontSize: 15,
      height: 1.16,
      fontWeight: FontWeight.w800,
      color: ProfileColors.primaryBlue,
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
