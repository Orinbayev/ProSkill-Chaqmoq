import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/game_provider.dart';
import 'package:chaqmoq_mobile/providers/notifications_provider.dart';
import 'package:chaqmoq_mobile/screens/student/student_account_screen.dart';
import 'package:chaqmoq_mobile/screens/student/student_attendance_screen.dart';
import 'package:chaqmoq_mobile/screens/student/game/game_hub_screen.dart';
import 'package:chaqmoq_mobile/screens/student/student_dashboard_screen.dart';
import 'package:chaqmoq_mobile/screens/student/student_leaderboard_screen.dart';
import 'package:chaqmoq_mobile/screens/student/student_notifications_screen.dart';
import 'package:chaqmoq_mobile/screens/student/student_payments_screen.dart';
import 'package:chaqmoq_mobile/screens/student/student_store_screen.dart';
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

  static const _gameTabIndex = 2;

  // Tab order: Panel (0) | Davomat (1) | O'yin (2) | Reyting (3) | Do'kon (4) |
  //            To'lovlar (5) | Profil (6)
  late final List<Widget> _screens = [
    StudentDashboardScreen(
      onOpenPayments: () => _setTab(5),
      onOpenAttendance: () => _setTab(1),
      onOpenLeaderboard: () => _setTab(3),
      onOpenNotifications: _openNotifications,
      onOpenProfile: () => _setTab(6),
    ),
    const StudentAttendanceScreen(),
    const GameHubScreen(),
    const StudentLeaderboardScreen(),
    const StudentStoreScreen(),
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

    // Ekranlar IndexedStack ichida yashaydi, ya'ni `initState` faqat bir marta
    // ishlaydi. O'yin bo'limiga qaytilganda jon/chaqmoq va katalog eskirgan
    // bo'lishi mumkin (admin yangi o'yin qo'shgan bo'lsa ham) — shuning uchun
    // tab ochilganda qayta so'raymiz.
    if (index == _gameTabIndex) {
      // `refresh()` darhol `notifyListeners()` chaqiradi — uni setState bilan
      // bir kadrga tiqmaymiz, aks holda qayta qurish o'rtasida xabar ketadi.
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        context.read<GameProvider>().refresh();
      });
    }
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
            label: 'O‘yin',
            icon: Icons.sports_esports_outlined,
            activeIcon: Icons.sports_esports_rounded,
          ),
          AppStudentBottomNavItem(
            label: 'Reyting',
            icon: Icons.bolt_outlined,
            activeIcon: Icons.bolt_rounded,
          ),
          AppStudentBottomNavItem(
            label: "Do‘kon",
            icon: Icons.storefront_outlined,
            activeIcon: Icons.storefront_rounded,
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
