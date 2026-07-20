import 'package:chaqmoq_mobile/core/design/ds_bottom_nav.dart';
import 'package:flutter/material.dart';

class AppParentBottomNavItem {
  const AppParentBottomNavItem({
    required this.label,
    required this.icon,
    required this.activeIcon,
  });

  final String label;
  final IconData icon;
  final IconData activeIcon;
}

/// Fixed 5-tab bar — Bosh / Davomat / To'lovlar / Progress / Profil.
/// DsBottomNav bilan bir xil Sky/Slate ko'rinish.
class AppParentBottomNav extends StatelessWidget {
  const AppParentBottomNav({
    super.key,
    required this.activeIndex,
    required this.onChanged,
    this.items = defaultItems,
  });

  static const List<AppParentBottomNavItem> defaultItems = [
    AppParentBottomNavItem(
      label: 'Bosh',
      icon: Icons.home_outlined,
      activeIcon: Icons.home_rounded,
    ),
    AppParentBottomNavItem(
      label: 'Davomat',
      icon: Icons.fact_check_outlined,
      activeIcon: Icons.fact_check_rounded,
    ),
    AppParentBottomNavItem(
      label: "To'lovlar",
      icon: Icons.payments_outlined,
      activeIcon: Icons.payments_rounded,
    ),
    AppParentBottomNavItem(
      label: "O'zlashtirish",
      icon: Icons.insights_outlined,
      activeIcon: Icons.insights_rounded,
    ),
    AppParentBottomNavItem(
      label: 'Profil',
      icon: Icons.person_outline_rounded,
      activeIcon: Icons.person_rounded,
    ),
  ];

  final int activeIndex;
  final ValueChanged<int> onChanged;
  final List<AppParentBottomNavItem> items;

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
