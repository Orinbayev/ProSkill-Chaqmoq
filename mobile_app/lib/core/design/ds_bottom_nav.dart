import 'package:flutter/material.dart';

import 'ds_colors.dart';
import 'ds_typography.dart';

/// Barcha rollar uchun umumiy pastki navigatsiya.
class DsNavItem {
  const DsNavItem({required this.icon, required this.label});
  final IconData icon;
  final String label;
}

class DsBottomNav extends StatelessWidget {
  const DsBottomNav({
    super.key,
    required this.items,
    required this.currentIndex,
    required this.onTap,
  });

  final List<DsNavItem> items;
  final int currentIndex;
  final ValueChanged<int> onTap;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Container(
      decoration: BoxDecoration(
        color: ds.surface,
        border: Border(top: BorderSide(color: ds.border)),
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 60,
          child: Row(
            children: [
              for (final (i, item) in items.indexed)
                Expanded(
                  child: _NavCell(
                    item: item,
                    selected: i == currentIndex,
                    onTap: () => onTap(i),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NavCell extends StatelessWidget {
  const _NavCell({required this.item, required this.selected, required this.onTap});
  final DsNavItem item;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    final color = selected ? ds.primary : ds.textFaint;
    return InkWell(
      onTap: onTap,
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(item.icon, size: 22, color: color),
          const SizedBox(height: 3),
          Text(item.label, style: DsType.micro(color)),
        ],
      ),
    );
  }
}
