import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/teacher_provider.dart';
import 'package:chaqmoq_mobile/screens/auth/login_screen.dart';
import 'package:chaqmoq_mobile/screens/teacher/teacher_dashboard_screen.dart';
import 'package:chaqmoq_mobile/screens/teacher/teacher_groups_screen.dart';
import 'package:chaqmoq_mobile/screens/teacher/teacher_income_screen.dart';
import 'package:chaqmoq_mobile/screens/teacher/teacher_profile_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

class TeacherAppShell extends StatefulWidget {
  const TeacherAppShell({super.key});

  @override
  State<TeacherAppShell> createState() => _TeacherAppShellState();
}

class _TeacherAppShellState extends State<TeacherAppShell> {
  int _tab = 0;

  void _setTab(int i) => setState(() => _tab = i);

  late final _screens = <Widget>[
    TeacherDashboardScreen(onGoGroups: () => _setTab(1), onGoIncome: () => _setTab(2)),
    TeacherGroupsScreen(),
    TeacherIncomeScreen(),
    TeacherProfileScreen(onLogout: _logout),
  ];

  Future<void> _logout() async {
    await context.read<AuthProvider>().logout();
    if (!mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute<void>(builder: (_) => const LoginScreen()),
      (_) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light,
      child: Scaffold(
        backgroundColor: const Color(0xFF0B1220),
        body: IndexedStack(index: _tab, children: _screens),
        bottomNavigationBar: _TeacherBottomNav(active: _tab, onChanged: _setTab),
      ),
    );
  }
}

class _TeacherBottomNav extends StatelessWidget {
  const _TeacherBottomNav({required this.active, required this.onChanged});

  final int active;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    const accent = Color(0xFF6366F1); // indigo
    const items = [
      (Icons.home_rounded, Icons.home_outlined, 'Asosiy'),
      (Icons.groups_rounded, Icons.groups_outlined, 'Guruhlar'),
      (Icons.account_balance_wallet_rounded, Icons.account_balance_wallet_outlined, 'Daromad'),
      (Icons.person_rounded, Icons.person_outlined, 'Profil'),
    ];

    return Container(
      decoration: const BoxDecoration(
        color: Color(0xFF0F1B2A),
        border: Border(top: BorderSide(color: Color(0x14FFFFFF), width: 1)),
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 60,
          child: Row(
            children: [
              for (int i = 0; i < items.length; i++)
                Expanded(
                  child: _NavItem(
                    icon: active == i ? items[i].$1 : items[i].$2,
                    label: items[i].$3,
                    active: active == i,
                    accent: accent,
                    onTap: () => onChanged(i),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  const _NavItem({
    required this.icon,
    required this.label,
    required this.active,
    required this.accent,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final bool active;
  final Color accent;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 24, color: active ? accent : const Color(0xFF5A6B80)),
          const SizedBox(height: 3),
          Text(
            label,
            style: TextStyle(
              fontSize: 10,
              fontWeight: active ? FontWeight.w700 : FontWeight.w500,
              color: active ? accent : const Color(0xFF5A6B80),
            ),
          ),
        ],
      ),
    );
  }
}
