import 'package:chaqmoq_mobile/core/theme/student_colors.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/notifications_provider.dart';
import 'package:chaqmoq_mobile/screens/student/student_account_screen.dart';
import 'package:chaqmoq_mobile/screens/student/student_dashboard_screen.dart';
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

  late final List<Widget> _screens = [
    StudentDashboardScreen(
      onOpenPayments: () => _setTab(1),
      onOpenNotifications: () => _setTab(2),
      onOpenProfile: () => _setTab(3),
    ),
    const StudentPaymentsScreen(),
    const StudentNotificationsScreen(),
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

  @override
  Widget build(BuildContext context) {
    final unreadCount = context.watch<NotificationsProvider>().unreadCount;
    final isOffline = context.watch<AuthProvider>().isOfflineMode;

    return Scaffold(
      backgroundColor: StudentColors.bg,
      body: Column(
        children: [
          if (isOffline)
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 8, 14, 0),
              child: SafeArea(
                bottom: false,
                child: AppOfflineBanner(
                  dark: true,
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
            label: "To‘lovlar",
            icon: Icons.payments_outlined,
            activeIcon: Icons.payments_rounded,
          ),
          AppStudentBottomNavItem(
            label: 'Xabarlar',
            icon: Icons.forum_outlined,
            activeIcon: Icons.forum_rounded,
            badgeCount: unreadCount,
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

