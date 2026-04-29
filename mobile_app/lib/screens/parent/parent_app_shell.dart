import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/parent_dashboard_provider.dart';
import 'package:chaqmoq_mobile/screens/attendance/attendance_screen.dart'
    as attendance;
import 'package:chaqmoq_mobile/screens/auth/login_screen.dart';
import 'package:chaqmoq_mobile/screens/notifications/notifications_screen.dart';
import 'package:chaqmoq_mobile/screens/parent/parent_dashboard_screen.dart'
    as dashboard;
import 'package:chaqmoq_mobile/screens/payments/payments_screen.dart'
    as payments;
import 'package:chaqmoq_mobile/screens/profile/profile_screen.dart' as profile;
import 'package:chaqmoq_mobile/screens/progress/progress_screen.dart'
    as progress;
import 'package:chaqmoq_mobile/screens/settings/settings_screen.dart';
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

  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();

  void _setTab(int index) {
    Navigator.of(context).maybePop();
    setState(() => _currentIndex = index);
  }

  void _openNotifications() {
    Navigator.of(context).maybePop();
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => const Scaffold(
          backgroundColor: Color(0xFFF7FBFF),
          body: SafeArea(child: NotificationsScreen()),
        ),
      ),
    );
  }

  void _openSettings() {
    Navigator.of(context).pop();
    Navigator.of(
      context,
    ).push(MaterialPageRoute<void>(builder: (_) => const SettingsScreen()));
  }

  Future<void> _logout() async {
    Navigator.of(context).maybePop();
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: _scaffoldKey,
      backgroundColor: const Color(0xFFF7FBFF),
      drawer: ParentDrawer(
        onDashboard: () => _setTab(0),
        onAttendance: () => _setTab(1),
        onPayments: () => _setTab(2),
        onProgress: () => _setTab(3),
        onNotifications: _openNotifications,
        onSettings: _openSettings,
        onLogout: _logout,
      ),
      body: IndexedStack(index: _currentIndex, children: _screens),
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
          boxShadow: [
            BoxShadow(
              color: Color(0x140B1220),
              blurRadius: 24,
              offset: Offset(0, -8),
            ),
          ],
        ),
        child: SafeArea(
          top: false,
          child: ClipRRect(
            borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
            child: BottomNavigationBar(
              currentIndex: _currentIndex,
              onTap: _setTab,
              type: BottomNavigationBarType.fixed,
              backgroundColor: Colors.white,
              elevation: 0,
              selectedItemColor: const Color(0xFF1E73F8),
              unselectedItemColor: const Color(0xFF6B7280),
              iconSize: 24,
              selectedFontSize: 11.5,
              unselectedFontSize: 11.5,
              selectedLabelStyle: _labelStyle.copyWith(
                color: const Color(0xFF1E73F8),
              ),
              unselectedLabelStyle: _labelStyle.copyWith(
                color: const Color(0xFF6B7280),
                fontWeight: FontWeight.w600,
              ),
              items: const [
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
      ),
    );
  }

  static TextStyle get _labelStyle {
    return GoogleFonts.inter(
      fontSize: 11.5,
      height: 1.16,
      fontWeight: FontWeight.w800,
      letterSpacing: 0,
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
      backgroundColor: const Color(0xFFF7FBFF),
      child: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(18, 18, 18, 24),
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: const Color(0xFFE5EAF2)),
              ),
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 26,
                    backgroundColor: const Color(0xFFEAF4FF),
                    child: Text(
                      _initials(name),
                      style: _ParentAppShellState._labelStyle.copyWith(
                        color: const Color(0xFF1E73F8),
                        fontSize: 16,
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: _ParentAppShellState._labelStyle.copyWith(
                            fontSize: 16,
                            color: const Color(0xFF111827),
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          subtitle,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: _ParentAppShellState._labelStyle.copyWith(
                            color: const Color(0xFF6B7280),
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
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
            _DrawerItem(
              Icons.event_available_outlined,
              'Davomat',
              onAttendance,
            ),
            _DrawerItem(
              Icons.account_balance_wallet_outlined,
              'To‘lovlar',
              onPayments,
            ),
            _DrawerItem(
              Icons.bar_chart_rounded,
              'Progress',
              onProgress,
            ),
            _DrawerItem(
              Icons.notifications_none_rounded,
              'Bildirishnomalar',
              onNotifications,
            ),
            _DrawerItem(Icons.settings_rounded, 'Sozlamalar', onSettings),
            const Divider(height: 28),
            _DrawerItem(
              Icons.logout_rounded,
              'Chiqish',
              onLogout,
              color: const Color(0xFFEF4444),
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
    if (parts.isEmpty) {
      return 'O';
    }
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
    final itemColor = color ?? const Color(0xFF111827);
    return ListTile(
      onTap: onTap,
      leading: Icon(icon, color: itemColor),
      title: Text(
        title,
        style: _ParentAppShellState._labelStyle.copyWith(
          color: itemColor,
          fontSize: 14,
        ),
      ),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
    );
  }
}
