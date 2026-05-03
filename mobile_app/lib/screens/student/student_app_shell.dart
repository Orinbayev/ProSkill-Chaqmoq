import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/notifications_provider.dart';
import 'package:chaqmoq_mobile/screens/student/student_account_screen.dart';
import 'package:chaqmoq_mobile/screens/student/student_attendance_screen.dart';
import 'package:chaqmoq_mobile/screens/student/student_dashboard_screen.dart';
import 'package:chaqmoq_mobile/screens/student/student_leaderboard_screen.dart';
import 'package:chaqmoq_mobile/screens/student/student_notifications_screen.dart';
import 'package:chaqmoq_mobile/screens/student/student_payments_screen.dart';
import 'package:chaqmoq_mobile/widgets/app_state_widgets.dart';
import 'package:chaqmoq_mobile/widgets/app_student_bottom_nav.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class StudentAppShell extends StatefulWidget {
  const StudentAppShell({super.key});

  @override
  State<StudentAppShell> createState() => _StudentAppShellState();
}

class _StudentAppShellState extends State<StudentAppShell> {
  int _currentIndex = 0;

  // Tab order: Panel (0) | Davomat (1) | Reyting (2) | To'lovlar (3) | Profil (4)
  late final List<Widget> _screens = [
    StudentDashboardScreen(
      onOpenPayments: () => _setTab(3),
      onOpenAttendance: () => _setTab(1),
      onOpenLeaderboard: () => _setTab(2),
      onOpenNotifications: _openNotifications,
      onOpenProfile: () => _setTab(4),
    ),
    const StudentAttendanceScreen(),
    const StudentLeaderboardScreen(),
    const StudentPaymentsScreen(),
    const StudentAccountScreen(),
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      context.read<NotificationsProvider>().load();
    });
  }

  void _setTab(int index) {
    if (_currentIndex == index) return;
    setState(() => _currentIndex = index);
  }

  void _openNotifications() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => const StudentNotificationsScreen()),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isOffline = context.watch<AuthProvider>().isOfflineMode;

    final tokens = StudentTokens.of(context);
    return Scaffold(
      backgroundColor: tokens.bg,
      body: Column(
        children: [
          if (isOffline)
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 8, 14, 0),
              child: SafeArea(
                bottom: false,
                child: AppOfflineBanner(
                  dark: tokens.isDark,
                  lastSync: 'Saqlangan ma’lumot ko‘rsatilmoqda',
                ),
              ),
            ),
          Expanded(
            child: IndexedStack(index: _currentIndex, children: _screens),
          ),
        ],
      ),
      bottomNavigationBar: AppStudentBottomNav(
        activeIndex: _currentIndex,
        onChanged: _setTab,
        items: [
          AppStudentBottomNavItem(
            label: 'Panel',
            icon: Icons.dashboard_outlined,
            activeIcon: Icons.dashboard_rounded,
          ),
          AppStudentBottomNavItem(
            label: 'Davomat',
            icon: Icons.fact_check_outlined,
            activeIcon: Icons.fact_check_rounded,
          ),
          AppStudentBottomNavItem(
            label: 'Reyting',
            icon: Icons.bolt_outlined,
            activeIcon: Icons.bolt_rounded,
          ),
          AppStudentBottomNavItem(
            label: "To‘lovlar",
            icon: Icons.payments_outlined,
            activeIcon: Icons.payments_rounded,
          ),
          AppStudentBottomNavItem(
            label: 'Profil',
            icon: Icons.person_outline_rounded,
            activeIcon: Icons.person_rounded,
          ),
        ],
      ),
    );
  }
}
