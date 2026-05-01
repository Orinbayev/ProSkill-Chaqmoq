import 'package:chaqmoq_mobile/core/theme/parent_colors.dart';
import 'package:chaqmoq_mobile/core/theme/parent_text_styles.dart';
import 'package:flutter/material.dart';

/// Parent app bar mirroring primitives.jsx `ParentAppBar`.
/// 40dp icon-button back arrow + 19px bold title + optional right slot.
class AppParentAppBar extends StatelessWidget {
  const AppParentAppBar({
    super.key,
    required this.title,
    this.onBack,
    this.right,
    this.left,
    this.padding = const EdgeInsets.fromLTRB(18, 10, 18, 14),
  });

  final String title;
  final VoidCallback? onBack;
  final Widget? right;
  final Widget? left;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: padding,
      child: Row(
        children: [
          if (onBack != null)
            AppParentIconButton(
              icon: Icons.arrow_back_rounded,
              onTap: onBack!,
            )
          else
            ?left,
          if (onBack != null || left != null) const SizedBox(width: 10),
          Expanded(
            child: Text(
              title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: ParentTextStyles.title,
            ),
          ),
          if (right != null) ...[
            const SizedBox(width: 8),
            right!,
          ],
        ],
      ),
    );
  }
}

class AppParentIconButton extends StatelessWidget {
  const AppParentIconButton({
    super.key,
    required this.icon,
    required this.onTap,
    this.badgeCount,
    this.size = 40,
    this.iconSize = 22,
  });

  final IconData icon;
  final VoidCallback onTap;
  final int? badgeCount;
  final double size;
  final double iconSize;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            Container(
              width: size,
              height: size,
              decoration: BoxDecoration(
                color: ParentColors.card,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: ParentColors.line),
              ),
              child: Icon(icon, color: ParentColors.text, size: iconSize),
            ),
            if (badgeCount != null && badgeCount! > 0)
              Positioned(
                top: 5,
                right: 5,
                child: Container(
                  constraints: const BoxConstraints(minWidth: 16),
                  height: 16,
                  alignment: Alignment.center,
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  decoration: BoxDecoration(
                    color: ParentColors.danger,
                    borderRadius: BorderRadius.circular(100),
                    border: Border.all(color: ParentColors.bg, width: 2),
                  ),
                  child: Text(
                    badgeCount! > 99 ? '99+' : '$badgeCount',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 9,
                      fontWeight: FontWeight.w800,
                      height: 1,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class AppStudentIconButton extends StatelessWidget {
  const AppStudentIconButton({
    super.key,
    required this.icon,
    required this.onTap,
    this.badgeCount,
    this.size = 40,
    this.iconSize = 22,
  });

  final IconData icon;
  final VoidCallback onTap;
  final int? badgeCount;
  final double size;
  final double iconSize;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            Container(
              width: size,
              height: size,
              decoration: BoxDecoration(
                color: const Color(0x0AFFFFFF),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0x14FFFFFF)),
              ),
              child: Icon(icon, color: const Color(0xFFF1F2F6), size: iconSize),
            ),
            if (badgeCount != null && badgeCount! > 0)
              Positioned(
                top: 5,
                right: 5,
                child: Container(
                  constraints: const BoxConstraints(minWidth: 14),
                  height: 14,
                  alignment: Alignment.center,
                  padding: const EdgeInsets.symmetric(horizontal: 3),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFF4757),
                    borderRadius: BorderRadius.circular(100),
                    border: Border.all(color: const Color(0xFF0A0A0F), width: 2),
                  ),
                  child: Text(
                    badgeCount! > 9 ? '9+' : '$badgeCount',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 9,
                      fontWeight: FontWeight.w800,
                      height: 1,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
