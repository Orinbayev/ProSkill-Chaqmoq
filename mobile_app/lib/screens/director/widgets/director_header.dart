import 'package:flutter/material.dart';

import '../../../core/design/ds_colors.dart';
import '../../../core/design/ds_components.dart';
import '../../../core/design/ds_tokens.dart';
import '../../../core/design/ds_typography.dart';

/// Rol paneli yuqori sarlavhasi: markaz · rol, ism, bildirishnoma, avatar.
class DirectorHeader extends StatelessWidget {
  const DirectorHeader({super.key, required this.subtitle, required this.name, this.onProfileTap, this.onBellTap});
  final String subtitle;
  final String name;
  final VoidCallback? onProfileTap;
  final VoidCallback? onBellTap;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(subtitle, style: DsType.small(ds.textMuted)),
              const SizedBox(height: 2),
              Text(name, style: DsType.h1(ds.textPrimary)),
            ],
          ),
        ),
        _IconButton(
          icon: Icons.notifications_none_rounded,
          onTap: onBellTap ?? onProfileTap ?? () {},
          badge: true,
        ),
        const SizedBox(width: 10),
        GestureDetector(
          onTap: onProfileTap,
          behavior: HitTestBehavior.opaque,
          child: DsAvatar(name, size: 44),
        ),
      ],
    );
  }
}

class _IconButton extends StatelessWidget {
  const _IconButton({required this.icon, required this.onTap, this.badge = false});
  final IconData icon;
  final VoidCallback onTap;
  final bool badge;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(color: ds.card, shape: BoxShape.circle, border: Border.all(color: ds.border)),
        child: Stack(
          alignment: Alignment.center,
          children: [
            Icon(icon, size: 22, color: ds.textSecondary),
            if (badge)
              Positioned(
                top: 12,
                right: 13,
                child: Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(color: ds.danger, shape: BoxShape.circle, border: Border.all(color: ds.card, width: 1.5)),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// Urg'u gradientli "hero" karta (bugungi tushum kabi asosiy raqam uchun).
class DirectorHeroCard extends StatelessWidget {
  const DirectorHeroCard({
    super.key,
    required this.label,
    required this.value,
    this.caption,
    this.action,
  });
  final String label;
  final String value;
  final String? caption;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(DsSpace.x5),
      decoration: BoxDecoration(
        gradient: LinearGradient(colors: ds.primaryGradient, begin: Alignment.topLeft, end: Alignment.bottomRight),
        borderRadius: DsRadius.all(DsRadius.lg),
        boxShadow: DsShadow.primaryGlow(ds.primary),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(label, style: DsType.caption(Colors.white.withValues(alpha: 0.9))),
              const Spacer(),
              const Icon(Icons.bolt, color: Colors.white, size: 20),
            ],
          ),
          const SizedBox(height: 6),
          Text(value, style: DsType.display(Colors.white)),
          if (caption != null) ...[
            const SizedBox(height: 2),
            Text(caption!, style: DsType.small(Colors.white.withValues(alpha: 0.85))),
          ],
          if (action != null) ...[const SizedBox(height: 14), action!],
        ],
      ),
    );
  }
}
