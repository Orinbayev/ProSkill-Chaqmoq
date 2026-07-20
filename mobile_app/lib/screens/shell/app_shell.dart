import 'package:chaqmoq_mobile/core/design/ds_bottom_nav.dart';
import 'package:chaqmoq_mobile/core/design/ds_colors.dart';
import 'package:chaqmoq_mobile/core/design/ds_typography.dart';
import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/utils/role_panel_style.dart';
import 'package:chaqmoq_mobile/core/utils/role_utils.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/notifications_provider.dart';
import 'package:chaqmoq_mobile/screens/account/account_screen.dart';
import 'package:chaqmoq_mobile/screens/dashboard/dashboard_screen.dart';
import 'package:chaqmoq_mobile/screens/groups/groups_screen.dart';
import 'package:chaqmoq_mobile/screens/notifications/notifications_screen.dart';
import 'package:chaqmoq_mobile/screens/leads/leads_screen.dart';
import 'package:chaqmoq_mobile/screens/students/students_screen.dart';
import 'package:chaqmoq_mobile/screens/teachers/teachers_screen.dart';
import 'package:chaqmoq_mobile/widgets/brand_logo.dart';
import 'package:chaqmoq_mobile/widgets/role_badge.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:provider/provider.dart';

enum ShellTab { dashboard, students, teachers, groups, leads, notifications, profile }

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
      if (!mounted) return;
      context.read<NotificationsProvider>().load();
    });
  }

  List<_ShellItem> _itemsForRole(String role) {
    final normalized = RoleUtils.normalize(role);
    if (normalized == 'superuser') {
      return const [
        _ShellItem(ShellTab.dashboard, 'Dashboard', Icons.home_rounded),
        _ShellItem(ShellTab.students, "O'quvchi", Icons.groups_rounded),
        _ShellItem(ShellTab.teachers, 'Ustoz', Icons.school_rounded),
        _ShellItem(ShellTab.groups, 'Guruh', Icons.view_module_rounded),
        _ShellItem(ShellTab.notifications, 'Xabar', Icons.notifications_rounded),
        _ShellItem(ShellTab.profile, 'Profil', Icons.person_rounded),
      ];
    }
    if (normalized == 'director' || normalized == 'manager') {
      return const [
        _ShellItem(ShellTab.dashboard, 'Dashboard', Icons.home_rounded),
        _ShellItem(ShellTab.students, "O'quvchi", Icons.groups_rounded),
        _ShellItem(ShellTab.groups, 'Guruh', Icons.view_module_rounded),
        _ShellItem(ShellTab.leads, 'Leadlar', Icons.person_add_rounded),
        _ShellItem(ShellTab.profile, 'Profil', Icons.person_rounded),
      ];
    }
    if (normalized == 'teacher') {
      return const [
        _ShellItem(ShellTab.dashboard, 'Dashboard', Icons.home_rounded),
        _ShellItem(ShellTab.groups, 'Guruh', Icons.view_module_rounded),
        _ShellItem(ShellTab.notifications, 'Xabar', Icons.notifications_rounded),
        _ShellItem(ShellTab.profile, 'Profil', Icons.person_rounded),
      ];
    }
    return const [
      _ShellItem(ShellTab.dashboard, 'Dashboard', Icons.home_rounded),
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
      ShellTab.leads => const LeadsScreen(),
      ShellTab.notifications => const NotificationsScreen(),
      ShellTab.profile => const AccountScreen(),
    };
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final notifications = context.watch<NotificationsProvider>();
    final user = auth.user;
    if (user == null) return const SizedBox.shrink();

    final ds = context.ds;
    final items = _itemsForRole(user.role);
    final panel = RolePanelStyles.of(
      user.role,
      isDark: Theme.of(context).brightness == Brightness.dark,
    );
    if (!items.any((item) => item.tab == _currentTab)) {
      _currentTab = items.first.tab;
    }
    final selectedIndex = items.indexWhere((item) => item.tab == _currentTab);

    return Scaffold(
      backgroundColor: ds.bg,
      appBar: AppBar(
        backgroundColor: ds.surface,
        surfaceTintColor: Colors.transparent,
        title: Row(
          children: [
            const BrandLogo(size: 34, radius: 10, showShadow: false),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(panel.panelLabel, style: DsType.bodyStrong(ds.textPrimary)),
                  Text(
                    user.center?.name ?? 'CRM Platform',
                    style: DsType.small(ds.textMuted),
                  ),
                ],
              ),
            ),
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
                Icon(Icons.notifications_none_rounded, color: ds.textSecondary),
                if (notifications.unreadCount > 0)
                  Positioned(
                    top: -2,
                    right: -2,
                    child: Container(
                      width: 18,
                      height: 18,
                      decoration: BoxDecoration(
                        color: ds.danger,
                        shape: BoxShape.circle,
                      ),
                      alignment: Alignment.center,
                      child: Text(
                        notifications.unreadCount > 9
                            ? '9+'
                            : '${notifications.unreadCount}',
                        style: DsType.micro(Colors.white),
                      ),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
        ],
      ),
      body: AnimatedSwitcher(
        duration: 280.ms,
        child: KeyedSubtree(
          key: ValueKey(_currentTab),
          child: _screenForTab(_currentTab)
              .animate()
              .fadeIn(duration: 260.ms)
              .slideY(begin: 0.02, end: 0),
        ),
      ),
      bottomNavigationBar: DsBottomNav(
        currentIndex: selectedIndex < 0 ? 0 : selectedIndex,
        onTap: (index) => setState(() => _currentTab = items[index].tab),
        items: [
          for (final item in items) DsNavItem(icon: item.icon, label: item.label),
        ],
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
