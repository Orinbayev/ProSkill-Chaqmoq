import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

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
    final tokens = StudentTokens.of(context);
    final navBg = tokens.isDark
        ? const Color(0xD913131A)
        : Colors.white.withValues(alpha: 0.96);
    return SafeArea(
      top: false,
      minimum: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 0, 14, 10),
        child: Container(
          height: 70,
          decoration: BoxDecoration(
            color: navBg,
            borderRadius: BorderRadius.circular(22),
            border: Border.all(color: tokens.border),
            boxShadow: [
              BoxShadow(
                color: tokens.isDark
                    ? const Color(0x66000000)
                    : tokens.shadow,
                blurRadius: 24,
                offset: const Offset(0, 8),
              ),
            ],
          ),
          padding: const EdgeInsets.symmetric(horizontal: 6),
          child: Row(
            children: [
              for (var i = 0; i < items.length; i++)
                Expanded(
                  child: _StudentNavItem(
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

class _StudentNavItem extends StatelessWidget {
  const _StudentNavItem({
    required this.item,
    required this.active,
    required this.onTap,
  });

  final AppStudentBottomNavItem item;
  final bool active;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final color = active ? tokens.primary : tokens.textMuted;
    final pillBg = active ? tokens.primary.withValues(alpha: 0.16) : Colors.transparent;
    final badgeBorder = tokens.isDark ? const Color(0xFF13131A) : Colors.white;
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 6),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Stack(
                clipBehavior: Clip.none,
                children: [
                  AnimatedContainer(
                    duration: const Duration(milliseconds: 200),
                    padding: EdgeInsets.symmetric(
                      horizontal: active ? 16 : 0,
                      vertical: 5,
                    ),
                    decoration: BoxDecoration(
                      color: pillBg,
                      borderRadius: BorderRadius.circular(100),
                    ),
                    child: Icon(
                      active ? item.activeIcon : item.icon,
                      color: color,
                      size: 22,
                    ),
                  ),
                  if (item.badgeCount > 0)
                    Positioned(
                      right: -2,
                      top: -2,
                      child: Container(
                        constraints: const BoxConstraints(minWidth: 14),
                        height: 14,
                        alignment: Alignment.center,
                        padding: const EdgeInsets.symmetric(horizontal: 3),
                        decoration: BoxDecoration(
                          color: tokens.danger,
                          borderRadius: BorderRadius.circular(100),
                          border: Border.all(color: badgeBorder, width: 2),
                        ),
                        child: Text(
                          item.badgeCount > 9 ? '9+' : '${item.badgeCount}',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 8,
                            fontWeight: FontWeight.w800,
                            height: 1,
                          ),
                        ),
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 3),
              Text(
                item.label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: GoogleFonts.inter(
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                  color: color,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
