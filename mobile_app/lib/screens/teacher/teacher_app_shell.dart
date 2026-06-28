import 'package:chaqmoq_mobile/screens/teacher/teacher_dashboard_screen.dart';
import 'package:chaqmoq_mobile/screens/teacher/teacher_groups_screen.dart';
import 'package:chaqmoq_mobile/screens/teacher/teacher_income_screen.dart';
import 'package:chaqmoq_mobile/screens/teacher/teacher_profile_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

class TeacherAppShell extends StatefulWidget {
  const TeacherAppShell({super.key});

  @override
  State<TeacherAppShell> createState() => _TeacherAppShellState();
}

class _TeacherAppShellState extends State<TeacherAppShell> {
  int _tab = 0;

  void _setTab(int i) {
    HapticFeedback.selectionClick();
    setState(() => _tab = i);
  }

  late final _screens = <Widget>[
    TeacherDashboardScreen(
      onGoGroups: () => _setTab(1),
      onGoIncome: () => _setTab(2),
    ),
    const TeacherGroupsScreen(),
    const TeacherIncomeScreen(),
    TeacherProfileScreen(onGoTab: _setTab),
  ];

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bg = isDark ? const Color(0xFF0B1220) : const Color(0xFFF5F7FB);
    final navBg = isDark ? const Color(0xFF0F1B2A) : Colors.white;
    final navBorder = isDark ? const Color(0x14FFFFFF) : const Color(0x12000000);

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: isDark ? SystemUiOverlayStyle.light : SystemUiOverlayStyle.dark,
      child: Scaffold(
        backgroundColor: bg,
        body: IndexedStack(index: _tab, children: _screens),
        bottomNavigationBar: Container(
          decoration: BoxDecoration(
            color: navBg,
            border: Border(top: BorderSide(color: navBorder, width: 1)),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: isDark ? 0.3 : 0.05),
                blurRadius: 12,
                offset: const Offset(0, -2),
              ),
            ],
          ),
          child: SafeArea(
            top: false,
            child: SizedBox(
              height: 58,
              child: Row(
                children: [
                  _NavItem(0, Icons.home_rounded, Icons.home_outlined, 'Asosiy', _tab, _setTab),
                  _NavItem(1, Icons.groups_rounded, Icons.groups_outlined, 'Guruhlar', _tab, _setTab),
                  _NavItem(2, Icons.account_balance_wallet_rounded, Icons.account_balance_wallet_outlined, 'Daromad', _tab, _setTab),
                  _NavItem(3, Icons.person_rounded, Icons.person_outlined, 'Profil', _tab, _setTab),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  const _NavItem(this.index, this.activeIcon, this.inactiveIcon, this.label, this.current, this.onTap);

  final int index;
  final IconData activeIcon;
  final IconData inactiveIcon;
  final String label;
  final int current;
  final ValueChanged<int> onTap;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final active = index == current;
    const accent = Color(0xFF6366F1);
    final inactiveColor = isDark ? const Color(0xFF4A5568) : const Color(0xFF9CA3AF);

    return Expanded(
      child: GestureDetector(
        onTap: () => onTap(index),
        behavior: HitTestBehavior.opaque,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
              decoration: BoxDecoration(
                color: active ? accent.withValues(alpha: 0.12) : Colors.transparent,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(
                active ? activeIcon : inactiveIcon,
                size: 22,
                color: active ? accent : inactiveColor,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              label,
              style: TextStyle(
                fontSize: 10,
                fontWeight: active ? FontWeight.w700 : FontWeight.w500,
                color: active ? accent : inactiveColor,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
