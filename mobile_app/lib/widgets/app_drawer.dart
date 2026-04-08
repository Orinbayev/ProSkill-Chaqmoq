import 'package:chaqmoq_mobile/core/theme/app_foundation.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/core/utils/role_utils.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:flutter/material.dart';

class AppDrawer extends StatelessWidget {
  const AppDrawer({
    super.key,
    required this.user,
    required this.selectedSection,
    required this.primarySections,
    required this.secondarySections,
    required this.unreadNotifications,
    required this.onSelectSection,
    required this.onLogout,
    this.onSwitchWorkspace,
  });

  final AppUser user;
  final AppSection selectedSection;
  final List<SectionItem> primarySections;
  final List<SectionItem> secondarySections;
  final int unreadNotifications;
  final ValueChanged<AppSection> onSelectSection;
  final VoidCallback onLogout;
  final VoidCallback? onSwitchWorkspace;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    Widget buildTile(SectionItem item) {
      final isSelected = item.section == selectedSection;
      final isNotification = item.section == AppSection.notifications;

      return ListTile(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppRadius.md),
        ),
        selected: isSelected,
        selectedTileColor: colorScheme.primary.withValues(alpha: 0.08),
        leading: Stack(
          clipBehavior: Clip.none,
          children: [
            Icon(item.icon),
            if (isNotification && unreadNotifications > 0)
              Positioned(
                right: -8,
                top: -6,
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 5,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    color: colorScheme.error,
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    unreadNotifications > 99 ? '99+' : '$unreadNotifications',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ),
          ],
        ),
        title: Text(item.label),
        onTap: () => onSelectSection(item.section),
      );
    }

    return Drawer(
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 16),
          child: Column(
            children: [
              Container(
                padding: const EdgeInsets.all(18),
                decoration: BoxDecoration(
                  gradient: AppGradients.brand,
                  borderRadius: BorderRadius.circular(AppRadius.xl),
                  boxShadow: AppShadows.soft,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      width: 52,
                      height: 52,
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.14),
                        borderRadius: BorderRadius.circular(18),
                      ),
                      alignment: Alignment.center,
                      child: const Icon(
                        Icons.bolt_rounded,
                        color: Colors.white,
                        size: 30,
                      ),
                    ),
                    const SizedBox(height: 14),
                    Text(
                      user.fullName.isEmpty
                          ? 'Chaqmoq foydalanuvchisi'
                          : user.fullName,
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      AppFormatters.roleLabel(user.effectiveRole),
                      style: Theme.of(
                        context,
                      ).textTheme.bodyMedium?.copyWith(color: Colors.white70),
                    ),
                    const SizedBox(height: 14),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        _InfoPill(
                          icon: Icons.apartment_rounded,
                          label: user.center?.name ?? 'Barcha markazlar',
                        ),
                        _InfoPill(
                          icon: Icons.link_rounded,
                          label: user.center?.slug.isNotEmpty == true
                              ? user.center!.slug
                              : 'ish maydoni',
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 18),
              Expanded(
                child: ListView(
                  padding: EdgeInsets.zero,
                  children: [
                    Text(
                      'Asosiy',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 8),
                    for (final item in primarySections) buildTile(item),
                    if (secondarySections.isNotEmpty) ...[
                      const SizedBox(height: 12),
                      Text(
                        'Qo\'shimcha',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 8),
                      for (final item in secondarySections) buildTile(item),
                    ],
                    if (onSwitchWorkspace != null) ...[
                      const SizedBox(height: 12),
                      ListTile(
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(AppRadius.md),
                        ),
                        leading: const Icon(Icons.swap_horiz_rounded),
                        title: const Text('Markazni almashtirish'),
                        subtitle: const Text(
                          'Chiqmasdan turib slugni o\'zgartiring',
                        ),
                        onTap: onSwitchWorkspace,
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: onLogout,
                icon: const Icon(Icons.logout_rounded),
                label: const Text('Chiqish'),
                style: OutlinedButton.styleFrom(
                  minimumSize: const Size.fromHeight(52),
                  side: const BorderSide(color: AppColors.border),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _InfoPill extends StatelessWidget {
  const _InfoPill({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: Colors.white),
          const SizedBox(width: 6),
          Flexible(
            child: Text(
              label,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Colors.white,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
