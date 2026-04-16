import 'package:chaqmoq_mobile/core/theme/app_colors.dart';
import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/app_text_styles.dart';
import 'package:chaqmoq_mobile/core/utils/role_utils.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/notifications_provider.dart';
import 'package:chaqmoq_mobile/screens/attendance/attendance_screen.dart';
import 'package:chaqmoq_mobile/screens/dashboard/dashboard_screen.dart';
import 'package:chaqmoq_mobile/screens/groups/groups_screen.dart';
import 'package:chaqmoq_mobile/screens/notifications/notifications_screen.dart';
import 'package:chaqmoq_mobile/screens/payments/payments_screen.dart';
import 'package:chaqmoq_mobile/screens/profile/profile_screen.dart';
import 'package:chaqmoq_mobile/screens/students/students_screen.dart';
import 'package:chaqmoq_mobile/screens/teachers/teachers_screen.dart';
import 'package:chaqmoq_mobile/widgets/role_badge.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:provider/provider.dart';

enum ShellTab { dashboard, students, teachers, groups, attendance, payments, notifications, profile }

class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  ShellTab _currentTab = ShellTab.dashboard;

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

  List<_ShellItem> _itemsForRole(String role) {
    final normalized = RoleUtils.normalize(role);
    if (normalized == 'superuser') {
      return const [
        _ShellItem(ShellTab.dashboard, 'Dashboard', Icons.home_rounded),
        _ShellItem(ShellTab.students, 'O\'quvchi', Icons.groups_rounded),
        _ShellItem(ShellTab.teachers, 'Ustoz', Icons.school_rounded),
        _ShellItem(ShellTab.groups, 'Guruh', Icons.view_module_rounded),
        _ShellItem(ShellTab.notifications, 'Xabar', Icons.notifications_rounded),
        _ShellItem(ShellTab.profile, 'Profil', Icons.person_rounded),
      ];
    }
    if (normalized == 'director' || normalized == 'manager') {
      return const [
        _ShellItem(ShellTab.dashboard, 'Dashboard', Icons.home_rounded),
        _ShellItem(ShellTab.students, 'O\'quvchi', Icons.groups_rounded),
        _ShellItem(ShellTab.groups, 'Guruh', Icons.view_module_rounded),
        _ShellItem(ShellTab.notifications, 'Xabar', Icons.notifications_rounded),
        _ShellItem(ShellTab.profile, 'Profil', Icons.person_rounded),
      ];
    }
    if (normalized == 'teacher') {
      return const [
        _ShellItem(ShellTab.dashboard, 'Dashboard', Icons.home_rounded),
        _ShellItem(ShellTab.groups, 'Guruh', Icons.view_module_rounded),
        _ShellItem(ShellTab.attendance, 'Davomat', Icons.fact_check_rounded),
        _ShellItem(ShellTab.notifications, 'Xabar', Icons.notifications_rounded),
        _ShellItem(ShellTab.profile, 'Profil', Icons.person_rounded),
      ];
    }
    return const [
      _ShellItem(ShellTab.dashboard, 'Dashboard', Icons.home_rounded),
      _ShellItem(ShellTab.payments, 'To\'lov', Icons.credit_card_rounded),
      _ShellItem(ShellTab.notifications, 'Xabar', Icons.notifications_rounded),
      _ShellItem(ShellTab.profile, 'Profil', Icons.person_rounded),
    ];
  }

  Widget _screenForTab(ShellTab tab) {
    return switch (tab) {
      ShellTab.dashboard => const DashboardScreen(),
      ShellTab.students => const StudentsScreen(),
      ShellTab.teachers => const TeachersScreen(),
      ShellTab.groups => const GroupsScreen(),
      ShellTab.attendance => const AttendanceScreen(),
      ShellTab.payments => const PaymentsScreen(),
      ShellTab.notifications => const NotificationsScreen(),
      ShellTab.profile => const ProfileScreen(),
    };
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final notifications = context.watch<NotificationsProvider>();
    final user = auth.user;
    if (user == null) {
      return const SizedBox.shrink();
    }

    final items = _itemsForRole(user.role);
    if (!items.any((item) => item.tab == _currentTab)) {
      _currentTab = items.first.tab;
    }
    final selectedIndex = items.indexWhere((item) => item.tab == _currentTab);

    return Scaffold(
      extendBody: true,
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('ChaqmoqApp ⚡', style: AppTextStyles.title),
            Text(user.center?.name ?? 'CRM Platform', style: AppTextStyles.bodySmall),
          ],
        ),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: AppSpacing.sm),
            child: RoleBadge(role: user.role),
          ),
          IconButton(
            onPressed: () => setState(() => _currentTab = ShellTab.notifications),
            icon: Stack(
              clipBehavior: Clip.none,
              children: [
                const Icon(Icons.notifications_none_rounded),
                if (notifications.unreadCount > 0)
                  Positioned(
                    top: -2,
                    right: -2,
                    child: Container(
                      width: 18,
                      height: 18,
                      decoration: const BoxDecoration(
                        color: AppColors.danger,
                        shape: BoxShape.circle,
                      ),
                      alignment: Alignment.center,
                      child: Text(
                        notifications.unreadCount > 9
                            ? '9+'
                            : '${notifications.unreadCount}',
                        style: AppTextStyles.bodySmall.copyWith(
                          color: AppColors.white,
                          fontSize: 9,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
        ],
      ),
      body: DecoratedBox(
        decoration: const BoxDecoration(gradient: AppColors.appBackground),
        child: SafeArea(
          top: false,
          child: AnimatedSwitcher(
            duration: 280.ms,
            child: KeyedSubtree(
              key: ValueKey(_currentTab),
              child: _screenForTab(_currentTab)
                  .animate()
                  .fadeIn(duration: 260.ms)
                  .slideY(begin: 0.02, end: 0),
            ),
          ),
        ),
      ),
      bottomNavigationBar: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(AppRadius.xl),
            child: NavigationBar(
              selectedIndex: selectedIndex < 0 ? 0 : selectedIndex,
              onDestinationSelected: (index) {
                setState(() => _currentTab = items[index].tab);
              },
              destinations: items
                  .map(
                    (item) => NavigationDestination(
                      icon: Icon(item.icon),
                      label: item.label,
                    ),
                  )
                  .toList(),
            ),
          ),
        ),
      ),
    );
  }
}

class _ShellItem {
  const _ShellItem(this.tab, this.label, this.icon);

  final ShellTab tab;
  final String label;
  final IconData icon;
}
