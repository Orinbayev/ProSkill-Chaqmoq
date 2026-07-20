import 'package:chaqmoq_mobile/core/design/ds_bottom_nav.dart';
import 'package:chaqmoq_mobile/core/design/ds_colors.dart';
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
    final ds = context.ds;

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: isDark ? SystemUiOverlayStyle.light : SystemUiOverlayStyle.dark,
      child: Scaffold(
        backgroundColor: ds.bg,
        body: IndexedStack(index: _tab, children: _screens),
        bottomNavigationBar: DsBottomNav(
          currentIndex: _tab,
          onTap: _setTab,
          items: const [
            DsNavItem(icon: Icons.home_rounded, label: 'Asosiy'),
            DsNavItem(icon: Icons.groups_rounded, label: 'Guruhlar'),
            DsNavItem(icon: Icons.account_balance_wallet_rounded, label: 'Daromad'),
            DsNavItem(icon: Icons.person_rounded, label: 'Profil'),
          ],
        ),
      ),
    );
  }
}
