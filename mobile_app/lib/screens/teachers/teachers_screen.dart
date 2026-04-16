import 'package:chaqmoq_mobile/core/theme/app_colors.dart';
import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/app_text_styles.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/teachers_provider.dart';
import 'package:chaqmoq_mobile/screens/teachers/teacher_detail_screen.dart';
import 'package:chaqmoq_mobile/widgets/empty_state.dart';
import 'package:chaqmoq_mobile/widgets/glass_card.dart';
import 'package:chaqmoq_mobile/widgets/shimmer_loader.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class TeachersScreen extends StatefulWidget {
  const TeachersScreen({super.key});

  @override
  State<TeachersScreen> createState() => _TeachersScreenState();
}

class _TeachersScreenState extends State<TeachersScreen> {
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    context.read<TeachersProvider>().load();
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<TeachersProvider>();
    return RefreshIndicator(
      onRefresh: provider.refresh,
      child: ListView(
        padding: const EdgeInsets.all(AppSpacing.xl),
        children: [
          if (provider.state == ViewState.loading)
            const ShimmerLoader.list()
          else if (provider.state == ViewState.error)
            EmptyState(
              title: 'Ustozlar yuklanmadi',
              message: provider.errorMessage ?? 'Qayta urinib ko\'ring',
              icon: Icons.school_rounded,
              actionLabel: 'Qayta yuklash',
              onAction: provider.refresh,
            )
          else if (provider.teachers.isEmpty)
            const EmptyState(
              title: 'Ustoz yo\'q',
              message: 'Hozircha ro\'yxatda ustozlar topilmadi',
              icon: Icons.school_outlined,
            )
          else
            ...provider.teachers.map(
              (teacher) => Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.lg),
                child: _TeacherCard(teacher: teacher),
              ),
            ),
        ],
      ),
    );
  }
}

class _TeacherCard extends StatelessWidget {
  const _TeacherCard({required this.teacher});

  final TeacherModel teacher;

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      onTap: () {
        Navigator.of(context).push(
          MaterialPageRoute<void>(
            builder: (_) => TeacherDetailScreen(teacher: teacher),
          ),
        );
      },
      child: Row(
        children: [
          CircleAvatar(
            radius: 24,
            backgroundColor: AppColors.secondary.withValues(alpha: 0.2),
            child: Text(Formatters.initials(teacher.fullName), style: AppTextStyles.label),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(teacher.fullName, style: AppTextStyles.title.copyWith(fontSize: 16)),
                const SizedBox(height: AppSpacing.xs),
                Text(
                  '${teacher.groupsCount} guruh • ${teacher.studentsCount} o\'quvchi',
                  style: AppTextStyles.bodySmall,
                ),
              ],
            ),
          ),
          Text(
            Formatters.currency(teacher.expectedIncome, compact: true),
            style: AppTextStyles.label.copyWith(color: AppColors.secondary),
          ),
        ],
      ),
    );
  }
}
