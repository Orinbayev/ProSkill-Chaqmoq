import 'package:chaqmoq_mobile/core/theme/app_colors.dart';
import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/app_text_styles.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/groups_provider.dart';
import 'package:chaqmoq_mobile/widgets/empty_state.dart';
import 'package:chaqmoq_mobile/widgets/glass_card.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class GroupDetailScreen extends StatefulWidget {
  const GroupDetailScreen({super.key, required this.group});

  final GroupModel group;

  @override
  State<GroupDetailScreen> createState() => _GroupDetailScreenState();
}

class _GroupDetailScreenState extends State<GroupDetailScreen> {
  bool _requested = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_requested) {
      return;
    }
    _requested = true;
    context.read<GroupsProvider>().loadGroupStudents(widget.group.id);
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<GroupsProvider>();
    return Scaffold(
      appBar: AppBar(title: const Text('Guruh tafsiloti')),
      body: DecoratedBox(
        decoration: const BoxDecoration(gradient: AppColors.appBackground),
        child: ListView(
          padding: const EdgeInsets.all(AppSpacing.xl),
          children: [
            GlassCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(widget.group.name, style: AppTextStyles.headline),
                  const SizedBox(height: AppSpacing.sm),
                  Text('Ustoz: ${widget.group.teacherName}', style: AppTextStyles.subtitle),
                  const SizedBox(height: AppSpacing.sm),
                  Text('Davomat: ${widget.group.attendanceRate.toStringAsFixed(0)}%', style: AppTextStyles.subtitle),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.xl),
            if (provider.detailState == ViewState.loading)
              const Center(child: CircularProgressIndicator())
            else if (provider.detailState == ViewState.error)
              EmptyState(
                title: 'Talabalar ro\'yxati yuklanmadi',
                message: provider.errorMessage ?? 'Qayta urinib ko\'ring',
                icon: Icons.group_off_rounded,
                actionLabel: 'Qayta yuklash',
                onAction: () => provider.loadGroupStudents(widget.group.id),
              )
            else if (provider.groupStudents.isEmpty)
              const EmptyState(
                title: 'Talaba mavjud emas',
                message: 'Ushbu guruhda hozircha o\'quvchi topilmadi',
                icon: Icons.person_off_rounded,
              )
            else
              ...provider.groupStudents.map(
                (student) => Padding(
                  padding: const EdgeInsets.only(bottom: AppSpacing.lg),
                  child: GlassCard(
                    child: Row(
                      children: [
                        CircleAvatar(
                          backgroundColor: AppColors.primary.withValues(alpha: 0.18),
                          child: Text(Formatters.initials(student.fullName), style: AppTextStyles.bodySmall),
                        ),
                        const SizedBox(width: AppSpacing.md),
                        Expanded(
                          child: Text(student.fullName, style: AppTextStyles.body),
                        ),
                      ],
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
