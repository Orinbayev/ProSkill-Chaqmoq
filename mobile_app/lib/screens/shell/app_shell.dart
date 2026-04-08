import 'package:chaqmoq_mobile/core/theme/app_foundation.dart';
import 'package:chaqmoq_mobile/core/utils/role_utils.dart';
import 'package:chaqmoq_mobile/providers/attendance_provider.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/dashboard_provider.dart';
import 'package:chaqmoq_mobile/providers/groups_provider.dart';
import 'package:chaqmoq_mobile/providers/notifications_provider.dart';
import 'package:chaqmoq_mobile/providers/payments_provider.dart';
import 'package:chaqmoq_mobile/providers/profile_provider.dart';
import 'package:chaqmoq_mobile/providers/students_provider.dart';
import 'package:chaqmoq_mobile/providers/teachers_provider.dart';
import 'package:chaqmoq_mobile/screens/attendance/attendance_screen.dart';
import 'package:chaqmoq_mobile/screens/dashboard/dashboard_screen.dart';
import 'package:chaqmoq_mobile/screens/groups/groups_screen.dart';
import 'package:chaqmoq_mobile/screens/notifications/notifications_screen.dart';
import 'package:chaqmoq_mobile/screens/payments/payments_screen.dart';
import 'package:chaqmoq_mobile/screens/profile/profile_screen.dart';
import 'package:chaqmoq_mobile/screens/students/students_screen.dart';
import 'package:chaqmoq_mobile/screens/teachers/teachers_screen.dart';
import 'package:chaqmoq_mobile/widgets/app_button.dart';
import 'package:chaqmoq_mobile/widgets/app_drawer.dart';
import 'package:chaqmoq_mobile/widgets/app_input_field.dart';
import 'package:chaqmoq_mobile/widgets/app_shell_title.dart';
import 'package:chaqmoq_mobile/widgets/app_view.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  AppSection? _selectedSection;
  int? _bootstrappedUserId;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final user = context.read<AuthProvider>().user;
    if (user == null || _bootstrappedUserId == user.id) {
      return;
    }

    _bootstrappedUserId = user.id;
    final primary = RoleUtils.primarySections(user.effectiveRole);
    _selectedSection = primary.first.section;

    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (!mounted) {
        return;
      }
      context.read<DashboardProvider>().reset();
      context.read<StudentsProvider>().reset();
      context.read<TeachersProvider>().reset();
      context.read<GroupsProvider>().reset();
      context.read<AttendanceProvider>().reset();
      context.read<PaymentsProvider>().reset();
      context.read<NotificationsProvider>().reset();
      context.read<ProfileProvider>().reset();
      await context.read<DashboardProvider>().loadForUser(user, force: true);
      if (!mounted) {
        return;
      }
      await context.read<NotificationsProvider>().load();
    });
  }

  Widget _buildBody(AppSection section) {
    return switch (section) {
      AppSection.home => const DashboardScreen(),
      AppSection.students => const StudentsScreen(),
      AppSection.teachers => const TeachersScreen(),
      AppSection.groups => const GroupsScreen(),
      AppSection.attendance => const AttendanceScreen(),
      AppSection.payments => const PaymentsScreen(),
      AppSection.notifications => const NotificationsScreen(),
      AppSection.profile => const ProfileScreen(),
    };
  }

  Future<void> _logout() async {
    await context.read<AuthProvider>().logout();
  }

  Future<void> _switchWorkspace() async {
    final auth = context.read<AuthProvider>();
    final controller = TextEditingController(text: auth.lastUsedSlug);
    final newSlug = await showDialog<String>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('Markazni almashtirish'),
          content: AppInputField(
            controller: controller,
            label: 'Markaz slugi',
            hint: 'masalan: proskill',
            prefixIcon: Icons.apartment_rounded,
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: const Text('Bekor qilish'),
            ),
            AppButton(
              label: 'Saqlash',
              expanded: false,
              onPressed: () {
                Navigator.of(dialogContext).pop(controller.text.trim());
              },
            ),
          ],
        );
      },
    );

    if (!mounted || newSlug == null || newSlug.isEmpty) {
      return;
    }

    await auth.switchTenant(newSlug);
    if (!mounted) {
      return;
    }
    final user = auth.user;
    if (user != null) {
      await context.read<DashboardProvider>().loadForUser(user, force: true);
      if (!mounted) {
        return;
      }
      context.read<NotificationsProvider>().load();
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Ish maydoni $newSlug ga almashtirildi')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final notifications = context.watch<NotificationsProvider>();
    final user = auth.user;

    if (user == null) {
      return const SizedBox.shrink();
    }

    final primary = RoleUtils.primarySections(user.effectiveRole);
    final secondary = RoleUtils.secondarySections(user.effectiveRole);
    final allowedSections = {
      ...primary.map((item) => item.section),
      ...secondary.map((item) => item.section),
    };
    final activeSection = allowedSections.contains(_selectedSection)
        ? _selectedSection!
        : primary.first.section;
    _selectedSection = activeSection;

    final primaryIndex = primary.indexWhere(
      (item) => item.section == activeSection,
    );

    return Scaffold(
      extendBody: true,
      appBar: AppBar(
        toolbarHeight: 74,
        title: AppShellTitle(
          title: RoleUtils.sectionTitle(activeSection),
          subtitle: user.center?.name ?? 'ChaqmoqApp',
        ),
        actions: [
          IconButton(
            tooltip: 'Bildirishnomalar',
            onPressed: () {
              setState(() => _selectedSection = AppSection.notifications);
            },
            icon: Stack(
              clipBehavior: Clip.none,
              children: [
                const Icon(Icons.notifications_none_rounded),
                if (notifications.unreadCount > 0)
                  Positioned(
                    right: -4,
                    top: -4,
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
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Colors.white,
                          fontSize: 9,
                          fontWeight: FontWeight.w800,
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
      drawer: AppDrawer(
        user: user,
        selectedSection: activeSection,
        primarySections: primary,
        secondarySections: secondary,
        unreadNotifications: notifications.unreadCount,
        onSelectSection: (section) {
          Navigator.of(context).pop();
          setState(() => _selectedSection = section);
        },
        onLogout: () {
          Navigator.of(context).pop();
          _logout();
        },
        onSwitchWorkspace: user.isSuperuser ? _switchWorkspace : null,
      ),
      body: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [Color(0xFFEFF6FF), AppColors.canvas, AppColors.canvas],
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            stops: [0, 0.22, 1],
          ),
        ),
        child: AppView(
          child: AnimatedSwitcher(
            duration: const Duration(milliseconds: 280),
            switchInCurve: Curves.easeOutCubic,
            switchOutCurve: Curves.easeInCubic,
            child: KeyedSubtree(
              key: ValueKey(activeSection),
              child: _buildBody(activeSection),
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
              selectedIndex: primaryIndex < 0 ? 0 : primaryIndex,
              onDestinationSelected: (index) {
                setState(() => _selectedSection = primary[index].section);
              },
              destinations: [
                for (final item in primary)
                  NavigationDestination(icon: Icon(item.icon), label: item.label),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
