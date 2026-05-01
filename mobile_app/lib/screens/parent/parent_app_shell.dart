import 'package:chaqmoq_mobile/core/theme/parent_colors.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/notifications_provider.dart';
import 'package:chaqmoq_mobile/providers/parent_dashboard_provider.dart';
import 'package:chaqmoq_mobile/screens/attendance/attendance_screen.dart'
    as attendance;
import 'package:chaqmoq_mobile/screens/auth/login_screen.dart';
import 'package:chaqmoq_mobile/screens/parent/parent_dashboard_screen.dart'
    as dashboard;
import 'package:chaqmoq_mobile/screens/parent/parent_notifications_screen.dart';
import 'package:chaqmoq_mobile/screens/parent/parent_ui.dart';
import 'package:chaqmoq_mobile/screens/payments/payments_screen.dart'
    as payments;
import 'package:chaqmoq_mobile/screens/profile/profile_screen.dart' as profile;
import 'package:chaqmoq_mobile/screens/progress/progress_screen.dart'
    as progress;
import 'package:chaqmoq_mobile/screens/settings/settings_screen.dart';
import 'package:chaqmoq_mobile/widgets/app_parent_bottom_nav.dart';
import 'package:chaqmoq_mobile/widgets/app_state_widgets.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

class ParentAppShell extends StatefulWidget {
  const ParentAppShell({super.key});

  @override
  State<ParentAppShell> createState() => _ParentAppShellState();
}

class _ParentAppShellState extends State<ParentAppShell> {
  int _currentIndex = 0;
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        context.read<NotificationsProvider>().load();
      }
    });
  }

  late final List<Widget> _screens = [
    dashboard.ParentDashboardScreen(
      showBottomNav: false,
      onOpenDrawer: () => _scaffoldKey.currentState?.openDrawer(),
      onOpenNotifications: _openNotifications,
      onOpenAttendance: () => _setTab(1),
      onOpenPayments: () => _setTab(2),
      onOpenProgress: () => _setTab(3),
      onOpenProfile: () => _setTab(4),
    ),
    const attendance.AttendanceScreen(showBottomNav: false),
    const payments.PaymentsScreen(showBottomNav: false),
    const progress.ProgressScreen(showBottomNav: false),
    const profile.ProfileScreen(showBottomNav: false),
  ];

  void _setTab(int index) {
    Navigator.of(context).maybePop();
    setState(() => _currentIndex = index);
  }

  void _openNotifications() {
    Navigator.of(context).maybePop();
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => const ParentNotificationsScreen(),
      ),
    );
  }

  void _openSettings() {
    Navigator.of(context).maybePop();
    Navigator.of(
      context,
    ).push(MaterialPageRoute<void>(builder: (_) => const SettingsScreen()));
  }

  Future<void> _logout() async {
    Navigator.of(context).maybePop();
    context.read<ParentDashboardProvider>().clear();
    await context.read<AuthProvider>().logout();
    if (!mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute<void>(builder: (_) => const LoginScreen()),
      (_) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    final isOffline = context.watch<AuthProvider>().isOfflineMode;
    return Scaffold(
      key: _scaffoldKey,
      backgroundColor: ParentColors.bg,
      drawer: ParentDrawer(
        onDashboard: () => _setTab(0),
        onAttendance: () => _setTab(1),
        onPayments: () => _setTab(2),
        onProgress: () => _setTab(3),
        onNotifications: _openNotifications,
        onSettings: _openSettings,
        onLogout: _logout,
      ),
      body: Column(
        children: [
          if (isOffline)
            Padding(
              padding: const EdgeInsets.fromLTRB(18, 8, 18, 0),
              child: SafeArea(
                bottom: false,
                child: AppOfflineBanner(
                  lastSync: 'Saqlangan ma’lumot ko‘rsatilmoqda',
                ),
              ),
            ),
          Expanded(
            child: IndexedStack(index: _currentIndex, children: _screens),
          ),
        ],
      ),
      bottomNavigationBar: AppParentBottomNav(
        activeIndex: _currentIndex,
        onChanged: _setTab,
      ),
    );
  }
}

class ParentDrawer extends StatelessWidget {
  const ParentDrawer({
    super.key,
    required this.onDashboard,
    required this.onAttendance,
    required this.onPayments,
    required this.onProgress,
    required this.onNotifications,
    required this.onSettings,
    required this.onLogout,
  });

  final VoidCallback onDashboard;
  final VoidCallback onAttendance;
  final VoidCallback onPayments;
  final VoidCallback onProgress;
  final VoidCallback onNotifications;
  final VoidCallback onSettings;
  final VoidCallback onLogout;

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().user;
    final name = user?.fullName.isNotEmpty == true ? user!.fullName : 'Ota-ona';
    final subtitle = (user?.center?.name ?? '').trim().isNotEmpty
        ? (user?.center?.name ?? '').trim()
        : 'Ota-ona';
    return Drawer(
      backgroundColor: ParentColors.bg,
      child: SafeArea(
        child: ListView(
          padding: ParentUi.screenPadding,
          children: [
            Container(
              padding: ParentUi.cardPadding,
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(ParentUi.cardRadius),
                border: Border.all(color: ParentColors.line),
              ),
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 24,
                    backgroundColor: ParentColors.primaryTint,
                    child: Text(
                      _initials(name),
                      style: GoogleFonts.inter(
                        fontSize: 15,
                        fontWeight: FontWeight.w800,
                        color: ParentColors.primary,
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: GoogleFonts.inter(
                            fontSize: 15,
                            fontWeight: FontWeight.w800,
                            color: ParentColors.text,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          subtitle,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: GoogleFonts.inter(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: ParentColors.textMuted,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 18),
            _DrawerItem(Icons.home_rounded, 'Bosh sahifa', onDashboard),
            _DrawerItem(Icons.fact_check_outlined, 'Davomat', onAttendance),
            _DrawerItem(
                Icons.payments_outlined, 'To‘lovlar', onPayments),
            _DrawerItem(Icons.insights_outlined, 'Progress', onProgress),
            _DrawerItem(Icons.notifications_none_rounded,
                'Bildirishnomalar', onNotifications),
            _DrawerItem(Icons.settings_rounded, 'Sozlamalar', onSettings),
            const Divider(height: 28),
            _DrawerItem(
              Icons.logout_rounded,
              'Chiqish',
              onLogout,
              color: ParentColors.danger,
            ),
          ],
        ),
      ),
    );
  }

  static String _initials(String value) {
    final parts = value
        .trim()
        .split(RegExp(r'\s+'))
        .where((e) => e.isNotEmpty)
        .toList();
    if (parts.isEmpty) return 'O';
    return parts.take(2).map((e) => e[0].toUpperCase()).join();
  }
}

class _DrawerItem extends StatelessWidget {
  const _DrawerItem(this.icon, this.title, this.onTap, {this.color});

  final IconData icon;
  final String title;
  final VoidCallback onTap;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final itemColor = color ?? ParentColors.text;
    return ListTile(
      onTap: onTap,
      leading: Icon(icon, color: itemColor),
      title: Text(
        title,
        style: GoogleFonts.inter(
          color: itemColor,
          fontSize: 14,
          fontWeight: FontWeight.w800,
        ),
      ),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
    );
  }
}
