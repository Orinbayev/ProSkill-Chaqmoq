import 'package:chaqmoq_mobile/core/theme/app_colors.dart';
import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/app_text_styles.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/teachers_provider.dart';
import 'package:chaqmoq_mobile/widgets/empty_state.dart';
import 'package:chaqmoq_mobile/widgets/glass_card.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class TeacherDetailScreen extends StatefulWidget {
  const TeacherDetailScreen({super.key, required this.teacher});

  final TeacherModel teacher;

  @override
  State<TeacherDetailScreen> createState() => _TeacherDetailScreenState();
}

class _TeacherDetailScreenState extends State<TeacherDetailScreen> {
  bool _requested = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_requested) {
      return;
    }
    _requested = true;
    context.read<TeachersProvider>().loadDetail(widget.teacher);
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<TeachersProvider>();
    final teacher = provider.selectedTeacher ?? widget.teacher;
    return Scaffold(
      appBar: AppBar(title: const Text('Ustoz profili')),
      body: DecoratedBox(
        decoration: const BoxDecoration(gradient: AppColors.appBackground),
        child: ListView(
          padding: const EdgeInsets.all(AppSpacing.xl),
          children: [
            GlassCard(
              child: Column(
                children: [
                  CircleAvatar(
                    radius: 40,
                    backgroundColor: AppColors.secondary.withValues(alpha: 0.2),
                    child: Text(Formatters.initials(teacher.fullName), style: AppTextStyles.title),
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  Text(teacher.fullName, style: AppTextStyles.headline, textAlign: TextAlign.center),
                  const SizedBox(height: AppSpacing.sm),
                  Text(teacher.email.isEmpty ? 'Email ko\'rsatilmagan' : teacher.email, style: AppTextStyles.subtitle),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.xl),
            Row(
              children: [
                Expanded(
                  child: GlassCard(
                    child: Column(
                      children: [
                        Text('Guruhlar', style: AppTextStyles.subtitle),
                        const SizedBox(height: AppSpacing.sm),
                        Text('${teacher.groupsCount}', style: AppTextStyles.headline),
                      ],
                    ),
                  ),
                ),
                const SizedBox(width: AppSpacing.lg),
                Expanded(
                  child: GlassCard(
                    child: Column(
                      children: [
                        Text('Daromad', style: AppTextStyles.subtitle),
                        const SizedBox(height: AppSpacing.sm),
                        Text(
                          Formatters.currency(teacher.expectedIncome, compact: true),
                          style: AppTextStyles.headline.copyWith(fontSize: 22),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.xl),
            if (provider.detailState == ViewState.error)
              EmptyState(
                title: 'Profil yuklanmadi',
                message: provider.errorMessage ?? 'Qayta urinib ko\'ring',
                icon: Icons.school_rounded,
                actionLabel: 'Qayta yuklash',
                onAction: () => provider.loadDetail(widget.teacher),
              )
            else
              ...teacher.groupNames.map(
                (name) => Padding(
                  padding: const EdgeInsets.only(bottom: AppSpacing.lg),
                  child: GlassCard(
                    child: Text(name, style: AppTextStyles.body),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
