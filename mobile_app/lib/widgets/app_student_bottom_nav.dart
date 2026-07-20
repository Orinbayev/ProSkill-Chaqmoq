import 'package:chaqmoq_mobile/core/design/ds_bottom_nav.dart';
import 'package:flutter/material.dart';

class AppStudentBottomNavItem {
  const AppStudentBottomNavItem({
    required this.label,
    required this.icon,
    required this.activeIcon,
    this.badgeCount = 0,
  });

  final String label;
  final IconData icon;
  final IconData activeIcon;
  final int badgeCount;
}

/// O'quvchi pastki nav — boshqa rollar bilan bir xil DsBottomNav (Sky/Slate).
class AppStudentBottomNav extends StatelessWidget {
  const AppStudentBottomNav({
    super.key,
    required this.activeIndex,
    required this.onChanged,
    required this.items,
  });

  final int activeIndex;
  final ValueChanged<int> onChanged;
  final List<AppStudentBottomNavItem> items;

  @override
  Widget build(BuildContext context) {
    return DsBottomNav(
      currentIndex: activeIndex,
      onTap: onChanged,
      items: [
        for (final item in items)
          DsNavItem(icon: item.activeIcon, label: item.label),
      ],
    );
  }
}
