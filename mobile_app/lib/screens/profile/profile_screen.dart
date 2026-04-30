import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/parent_models.dart';
import 'package:chaqmoq_mobile/providers/app_preferences_provider.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/notifications_provider.dart';
import 'package:chaqmoq_mobile/providers/parent_dashboard_provider.dart';
import 'package:chaqmoq_mobile/screens/auth/login_screen.dart';
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
              padding: ParentUi.screenPadding,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  ProfileHeader(
                    onNotifications: _openNotifications,
                    onSettings: _openSettingsScreen,
                  ),
                  const SizedBox(height: ParentUi.sectionGap),
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
                      const SizedBox(height: 8),
                    ],
                    ParentInfoCard(parent: parent, onTap: _openEditProfile),
                    const SizedBox(height: ParentUi.sectionGap),
                    ChildrenSection(
                      children: children,
                      onAddChild: _openAddChild,
                    ),
                    const SizedBox(height: ParentUi.sectionGap),
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
                style: ProfileTextStyles.title.copyWith(fontSize: 22),
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
      borderRadius: BorderRadius.circular(ParentUi.cardRadius),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(ParentUi.cardRadius),
        child: ProfileCard(
          padding: ParentUi.cardPadding,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Stack(
                clipBehavior: Clip.none,
                children: <Widget>[
                  Container(
                    width: 72,
                    height: 72,
                    decoration: const BoxDecoration(
                      shape: BoxShape.circle,
                      color: Color(0xFFE7F0FF),
                    ),
                    clipBehavior: Clip.antiAlias,
                    child: AdaptiveAvatar(
                      name: name,
                      imageUrl: parent?.avatarUrl ?? '',
                      size: 72,
                      icon: Icons.person_outline_rounded,
                    ),
                  ),
                  Positioned(
                    right: -2,
                    bottom: -2,
                    child: Container(
                      width: 28,
                      height: 28,
                      decoration: BoxDecoration(
                        color: Colors.white,
                        shape: BoxShape.circle,
                        boxShadow: ProfileShadows.soft,
                        border: Border.all(color: ProfileColors.border),
                      ),
                      child: const Icon(
                        Icons.photo_camera_outlined,
                        color: ProfileColors.primaryBlue,
                        size: 16,
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
                      style: ProfileTextStyles.title.copyWith(fontSize: 17),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      'Ota-ona paneli',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: ProfileTextStyles.body.copyWith(
                        color: ProfileColors.secondaryText,
                        fontSize: 12.6,
                      ),
                    ),
                    const SizedBox(height: 8),
                    _ContactLine(icon: Icons.phone_outlined, text: phone),
                    const SizedBox(height: 5),
                    _ContactLine(icon: Icons.mail_outline_rounded, text: email),
                  ],
                ),
              ),
              const SizedBox(width: 6),
              const Padding(
                padding: EdgeInsets.only(top: 4),
                child: Icon(
                  Icons.chevron_right_rounded,
                  color: Color(0xFF8B95A1),
                  size: 22,
                ),
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
                style: ProfileTextStyles.title.copyWith(fontSize: 17),
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
                    style: ProfileTextStyles.link.copyWith(fontSize: 13.2),
                  ),
                  const SizedBox(width: 4),
                  const Icon(Icons.add_rounded, size: 18),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        if (children.isEmpty)
          ProfileCard(
            padding: const EdgeInsets.all(18),
            child: Text(
              'Farzandlar ro‘yxati topilmadi',
              style: ProfileTextStyles.body.copyWith(
                color: ProfileColors.secondaryText,
                fontSize: 12.8,
              ),
            ),
          )
        else
          LayoutBuilder(
            builder: (context, constraints) {
              final cardWidth = constraints.maxWidth < 360
                  ? constraints.maxWidth * 0.76
                  : constraints.maxWidth * 0.66;
              final resolvedWidth = cardWidth.clamp(188.0, 236.0).toDouble();
              return SizedBox(
                height: 184,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  physics: const BouncingScrollPhysics(),
                  itemCount: children.length,
                  separatorBuilder: (_, _) => const SizedBox(width: 12),
                  itemBuilder: (BuildContext context, int index) {
                    final child = children[index];
                    return ChildCard(
                      child: child,
                      selected:
                          child.id == selectedId ||
                          (selectedId == null && index == 0),
                      width: resolvedWidth,
                    );
                  },
                ),
              );
            },
          ),
      ],
    );
  }
}

class ChildCard extends StatelessWidget {
  const ChildCard({
    super.key,
    required this.child,
    required this.selected,
    required this.width,
  });

  final ParentChildModel child;
  final bool selected;
  final double width;

  @override
  Widget build(BuildContext context) {
    final chips = <String>[
      if (child.childCode.trim().isNotEmpty) 'Kod: ${child.childCode.trim()}',
    ];
    final summaryLine = <String>[
      if (child.className.trim().isNotEmpty) child.className.trim(),
      if (child.groupName.trim().isNotEmpty) child.groupName.trim(),
    ].join(' • ');
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(ParentUi.cardRadius),
      child: InkWell(
        borderRadius: BorderRadius.circular(ParentUi.cardRadius),
        onTap: () =>
            context.read<ParentDashboardProvider>().selectChild(child.id),
        child: Ink(
          width: width,
          padding: ParentUi.denseCardPadding,
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(ParentUi.cardRadius),
            border: Border.all(
              color: selected
                  ? ProfileColors.primaryBlue
                  : ProfileColors.border,
              width: selected ? 2 : 1,
            ),
            boxShadow: ProfileShadows.card,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: <Widget>[
              Align(
                alignment: Alignment.topRight,
                child: AnimatedOpacity(
                  opacity: selected ? 1 : 0,
                  duration: const Duration(milliseconds: 180),
                  child: Container(
                    width: 20,
                    height: 20,
                    decoration: const BoxDecoration(
                      color: ProfileColors.primaryBlue,
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(
                      Icons.check_rounded,
                      color: Colors.white,
                      size: 14,
                    ),
                  ),
                ),
              ),
              Container(
                width: 58,
                height: 58,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: selected
                        ? ProfileColors.primaryBlue.withValues(alpha: 0.18)
                        : ProfileColors.border,
                  ),
                ),
                child: AdaptiveAvatar(
                  name: child.fullName,
                  imageUrl: child.avatarUrl,
                  size: 50,
                  icon: Icons.school_rounded,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                child.fullName,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center,
                style: ProfileTextStyles.title.copyWith(
                  fontSize: 13.8,
                  height: 1.18,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                summaryLine.isNotEmpty
                    ? summaryLine
                    : 'Guruh biriktirilmagan',
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center,
                style: ProfileTextStyles.body.copyWith(
                  color: ProfileColors.secondaryText,
                  fontSize: 11.8,
                  height: 1.25,
                ),
              ),
              if (chips.isNotEmpty) ...<Widget>[
                const SizedBox(height: 8),
                Wrap(
                  alignment: WrapAlignment.center,
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    for (final chip in chips)
                      ConstrainedBox(
                        constraints: BoxConstraints(maxWidth: width - 42),
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 9,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: const Color(0xFFF4F7FB),
                            borderRadius: BorderRadius.circular(999),
                          ),
                          child: Text(
                            chip,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            textAlign: TextAlign.center,
                            style: ProfileTextStyles.body.copyWith(
                              color: ProfileColors.secondaryText,
                              fontSize: 11.2,
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              ],
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
            padding: ParentUi.denseCardPadding,
            child: Row(
              children: <Widget>[
                Container(
                  width: 38,
                  height: 38,
                  decoration: BoxDecoration(
                    color: data.iconBackground,
                    shape: BoxShape.circle,
                  ),
                  child: Icon(data.icon, color: data.iconColor, size: 20),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        data.title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: ProfileTextStyles.title.copyWith(
                          color: data.destructive
                              ? ProfileColors.red
                              : ProfileColors.text,
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
                            color: data.destructive
                                ? ProfileColors.red
                                : ProfileColors.secondaryText,
                            fontSize: 12.4,
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
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      textAlign: TextAlign.right,
                      style: ProfileTextStyles.body.copyWith(
                        color: ProfileColors.secondaryText,
                        fontSize: 12.4,
                      ),
                    ),
                  ),
                ],
                if (!data.destructive) ...<Widget>[
                  const SizedBox(width: 4),
                  const Icon(
                    Icons.chevron_right_rounded,
                    color: Color(0xFF8B95A1),
                    size: 18,
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
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(ParentUi.cardRadius),
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
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            text,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: ProfileTextStyles.body.copyWith(
              color: ProfileColors.secondaryText,
              fontSize: 12.6,
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
    final notifications = context.watch<NotificationsProvider>();
    final fallbackUnreadCount =
        context.watch<ParentDashboardProvider>().data?.unreadNotifications ?? 0;
    final unreadCount = ParentUi.resolveUnreadCount(
      notifications: notifications,
      fallback: fallbackUnreadCount,
    );
    return Stack(
      clipBehavior: Clip.none,
      children: <Widget>[
        InkWell(
          onTap: onTap,
          customBorder: const CircleBorder(),
          child: Container(
            width: ParentUi.iconButtonSize,
            height: ParentUi.iconButtonSize,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: Colors.white,
              shape: BoxShape.circle,
              border: Border.all(color: ProfileColors.border),
              boxShadow: ProfileShadows.soft,
            ),
            child: Icon(icon, color: ProfileColors.text, size: 22),
          ),
        ),
        if (showBadge && unreadCount > 0)
          Positioned(
            right: 4,
            top: 2,
            child: Container(
              constraints: const BoxConstraints(minWidth: 18),
              height: ParentUi.miniBadgeHeight,
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
                  fontSize: 9,
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
      padding: const EdgeInsets.fromLTRB(18, 28, 18, 28),
      child: loading
          ? const SizedBox(
              height: 200,
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
                  style: ProfileTextStyles.title.copyWith(fontSize: 18),
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
      fontSize: 17,
      height: 1.16,
      fontWeight: FontWeight.w800,
      color: ProfileColors.text,
      letterSpacing: 0,
    );
  }

  static TextStyle get body {
    return GoogleFonts.inter(
      fontSize: 14,
      height: 1.28,
      fontWeight: FontWeight.w500,
      color: ProfileColors.text,
      letterSpacing: 0,
    );
  }

  static TextStyle get label {
    return GoogleFonts.inter(
      fontSize: 12.5,
      height: 1.16,
      fontWeight: FontWeight.w800,
      color: ProfileColors.text,
      letterSpacing: 0,
    );
  }

  static TextStyle get link {
    return GoogleFonts.inter(
      fontSize: 14,
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
