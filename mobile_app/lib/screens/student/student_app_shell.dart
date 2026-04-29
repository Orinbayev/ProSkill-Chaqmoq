import 'package:chaqmoq_mobile/core/theme/app_colors.dart';
import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/notifications_provider.dart';
import 'package:chaqmoq_mobile/screens/account/account_screen.dart';
import 'package:chaqmoq_mobile/screens/notifications/notifications_screen.dart';
import 'package:chaqmoq_mobile/screens/student/student_dashboard_screen.dart';
import 'package:chaqmoq_mobile/screens/student/student_payments_screen.dart';
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
    const NotificationsScreen(),
    const AccountScreen(),
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      context.read<NotificationsProvider>().load();
    });
  }

  void _setTab(int index) {
    if (_currentIndex == index) {
      return;
    }
    setState(() => _currentIndex = index);
  }

  @override
  Widget build(BuildContext context) {
    final unreadCount = context.watch<NotificationsProvider>().unreadCount;
    final isOffline = context.watch<AuthProvider>().isOfflineMode;

    return Scaffold(
      backgroundColor: AppColors.background,
      body: Column(
        children: [
          if (isOffline)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 10),
              color: const Color(0xFF102235),
              child: SafeArea(
                bottom: false,
                child: Text(
                  'Offline rejim: saqlangan ma’lumotlar ko‘rsatilmoqda.',
                  style: Theme.of(
                    context,
                  ).textTheme.bodySmall?.copyWith(color: AppColors.textPrimary),
                ),
              ),
            ),
          Expanded(
            child: IndexedStack(index: _currentIndex, children: _screens),
          ),
        ],
      ),
      bottomNavigationBar: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(AppRadius.xl),
            child: NavigationBar(
              selectedIndex: _currentIndex,
              onDestinationSelected: _setTab,
              destinations: [
                const NavigationDestination(
                  icon: Icon(Icons.home_rounded),
                  label: 'Panel',
                ),
                const NavigationDestination(
                  icon: Icon(Icons.credit_card_rounded),
                  label: 'To‘lovlar',
                ),
                NavigationDestination(
                  icon: Stack(
                    clipBehavior: Clip.none,
                    children: [
                      const Icon(Icons.notifications_none_rounded),
                      if (unreadCount > 0)
                        Positioned(
                          top: -2,
                          right: -4,
                          child: Container(
                            width: 16,
                            height: 16,
                            alignment: Alignment.center,
                            decoration: const BoxDecoration(
                              color: AppColors.danger,
                              shape: BoxShape.circle,
                            ),
                            child: Text(
                              unreadCount > 9 ? '9+' : '$unreadCount',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 8,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                        ),
                    ],
                  ),
                  label: 'Xabarlar',
                ),
                const NavigationDestination(
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
}
