import 'package:chaqmoq_mobile/core/theme/app_colors.dart';
import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/app_text_styles.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/groups_provider.dart';
import 'package:chaqmoq_mobile/screens/groups/group_detail_screen.dart';
import 'package:chaqmoq_mobile/widgets/empty_state.dart';
import 'package:chaqmoq_mobile/widgets/glass_card.dart';
import 'package:chaqmoq_mobile/widgets/shimmer_loader.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class GroupsScreen extends StatefulWidget {
  const GroupsScreen({super.key});

  @override
  State<GroupsScreen> createState() => _GroupsScreenState();
}

class _GroupsScreenState extends State<GroupsScreen> {
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final role = context.read<AuthProvider>().user?.role;
    if (role != null) {
      context.read<GroupsProvider>().load(role);
    }
  }

  @override
  Widget build(BuildContext context) {
    final role = context.watch<AuthProvider>().user?.role ?? '';
    final provider = context.watch<GroupsProvider>();
    return RefreshIndicator(
      onRefresh: () => provider.refresh(role),
      child: ListView(
        padding: const EdgeInsets.all(AppSpacing.xl),
        children: [
          if (provider.state == ViewState.loading)
            const ShimmerLoader.list()
          else if (provider.state == ViewState.error)
            EmptyState(
              title: 'Guruhlar yuklanmadi',
              message: provider.errorMessage ?? 'Qayta urinib ko\'ring',
              icon: Icons.view_module_rounded,
              actionLabel: 'Qayta yuklash',
              onAction: () => provider.refresh(role),
            )
          else if (provider.groups.isEmpty)
            const EmptyState(
              title: 'Guruh mavjud emas',
              message: 'Hozircha ro\'yxatda guruh topilmadi',
              icon: Icons.grid_view_rounded,
            )
          else
            ...provider.groups.map(
              (group) => Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.lg),
                child: _GroupCard(group: group),
              ),
            ),
        ],
      ),
    );
  }
}

class _GroupCard extends StatelessWidget {
  const _GroupCard({required this.group});

  final GroupModel group;

  @override
  Widget build(BuildContext context) {
    final fill = (group.fillRate * 100).clamp(0, 100);
    final color = fill < 70
        ? AppColors.success
        : fill < 90
            ? AppColors.warning
            : AppColors.danger;
    return GlassCard(
      onTap: () {
        Navigator.of(context).push(
          MaterialPageRoute<void>(
            builder: (_) => GroupDetailScreen(group: group),
          ),
        );
      },
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: Text(group.name, style: AppTextStyles.title)),
              Text('${fill.toStringAsFixed(0)}%', style: AppTextStyles.label.copyWith(color: color)),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Text('Ustoz: ${group.teacherName.isEmpty ? 'Biriktirilmagan' : group.teacherName}', style: AppTextStyles.bodySmall),
          const SizedBox(height: AppSpacing.xs),
          Text(
            '${group.studentCount}/${group.capacity == 0 ? 24 : group.capacity} o\'quvchi • ${group.schedule.isEmpty ? 'Jadval kiritilmagan' : group.schedule}',
            style: AppTextStyles.bodySmall,
          ),
          const SizedBox(height: AppSpacing.lg),
          ClipRRect(
            borderRadius: BorderRadius.circular(AppRadius.pill),
            child: LinearProgressIndicator(
              value: group.capacity == 0 ? 0 : group.fillRate.clamp(0, 1),
              minHeight: 8,
              color: color,
              backgroundColor: AppColors.surfaceAlt,
            ),
          ),
        ],
      ),
    );
  }
}
