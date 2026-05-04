import 'package:chaqmoq_mobile/core/theme/parent_colors.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

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
      label: 'To‘lovlar',
      icon: Icons.payments_outlined,
      activeIcon: Icons.payments_rounded,
    ),
    AppParentBottomNavItem(
      label: "O‘zlashtirish",
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
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      decoration: BoxDecoration(
        color: isDark
            ? const Color(0xE6141926)
            : Colors.white.withAlpha(((0.92) * 255).round()),
        border: Border(
          top: BorderSide(color: ParentColors.line),
        ),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0A0F1E33),
            blurRadius: 24,
            offset: Offset(0, -8),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        minimum: const EdgeInsets.only(bottom: 4),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
          child: Row(
            children: [
              for (var i = 0; i < items.length; i++)
                Expanded(
                  child: _NavItemView(
                    item: items[i],
                    active: i == activeIndex,
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

class _NavItemView extends StatelessWidget {
  const _NavItemView({
    required this.item,
    required this.active,
    required this.onTap,
  });

  final AppParentBottomNavItem item;
  final bool active;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = active ? ParentColors.primary : ParentColors.textMuted;
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 6),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(active ? item.activeIcon : item.icon, color: color, size: 24),
              const SizedBox(height: 3),
              Text(
                item.label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: GoogleFonts.inter(
                  fontSize: 10.5,
                  fontWeight: FontWeight.w700,
                  color: color,
                  letterSpacing: 0.1,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
