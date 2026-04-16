import 'package:chaqmoq_mobile/core/theme/app_colors.dart';
import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/app_text_styles.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/core/utils/role_utils.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/students_provider.dart';
import 'package:chaqmoq_mobile/screens/students/student_detail_screen.dart';
import 'package:chaqmoq_mobile/widgets/app_input.dart';
import 'package:chaqmoq_mobile/widgets/empty_state.dart';
import 'package:chaqmoq_mobile/widgets/glass_card.dart';
import 'package:chaqmoq_mobile/widgets/shimmer_loader.dart';
import 'package:chaqmoq_mobile/widgets/stat_chip.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:provider/provider.dart';

class StudentsScreen extends StatefulWidget {
  const StudentsScreen({super.key});

  @override
  State<StudentsScreen> createState() => _StudentsScreenState();
}

class _StudentsScreenState extends State<StudentsScreen> {
  final TextEditingController _searchController = TextEditingController();

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    context.read<StudentsProvider>().load();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final students = context.watch<StudentsProvider>();
    final user = auth.user;
    final canAdd = user != null && RoleUtils.isDirectorScope(user.role) && user.role != 'teacher';

    return Scaffold(
      backgroundColor: Colors.transparent,
      floatingActionButton: canAdd
          ? FloatingActionButton(
              backgroundColor: AppColors.primary,
              onPressed: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Yangi o\'quvchi qo\'shish formasi backend bilan ulanishi kerak.')),
                );
              },
              child: const Icon(Icons.add_rounded, color: AppColors.white),
            )
          : null,
      body: RefreshIndicator(
        onRefresh: students.refresh,
        child: ListView(
          padding: const EdgeInsets.all(AppSpacing.xl),
          children: [
            AppInput(
              controller: _searchController,
              label: 'Qidiruv',
              hint: 'Ism, guruh yoki telefon',
              prefixIcon: Icons.search_rounded,
              onChanged: students.setQuery,
            ),
            const SizedBox(height: AppSpacing.lg),
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  _FilterChipItem(
                    label: 'All',
                    selected: students.filter == 'all',
                    onTap: () => students.setFilter('all'),
                  ),
                  _FilterChipItem(
                    label: 'Active',
                    selected: students.filter == 'active',
                    onTap: () => students.setFilter('active'),
                  ),
                  _FilterChipItem(
                    label: 'Inactive',
                    selected: students.filter == 'inactive',
                    onTap: () => students.setFilter('inactive'),
                  ),
                  _FilterChipItem(
                    label: 'Debt',
                    selected: students.filter == 'debt',
                    onTap: () => students.setFilter('debt'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.xl),
            if (students.state == ViewState.loading)
              const ShimmerLoader.list()
            else if (students.state == ViewState.error)
              EmptyState(
                title: 'O\'quvchilar yuklanmadi',
                message: students.errorMessage ?? 'Qayta urinib ko\'ring',
                icon: Icons.groups_rounded,
                actionLabel: 'Qayta yuklash',
                onAction: students.refresh,
              )
            else if (students.filteredStudents.isEmpty)
              EmptyState(
                title: 'O\'quvchi topilmadi',
                message: 'Qidiruv yoki filtr bo\'yicha mos natija yo\'q',
                icon: Icons.search_off_rounded,
                actionLabel: 'Yangilash',
                onAction: students.refresh,
              )
            else
              ...students.filteredStudents.map(
                (student) => Padding(
                  padding: const EdgeInsets.only(bottom: AppSpacing.lg),
                  child: _StudentCard(student: student),
                ),
              ),
          ],
        ),
      ).animate().fadeIn(duration: 250.ms),
    );
  }
}

class _FilterChipItem extends StatelessWidget {
  const _FilterChipItem({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: AppSpacing.sm),
      child: FilterChip(
        selected: selected,
        onSelected: (_) => onTap(),
        label: Text(label),
        backgroundColor: AppColors.glass,
        selectedColor: AppColors.primary.withValues(alpha: 0.2),
        side: const BorderSide(color: AppColors.border),
      ),
    );
  }
}

class _StudentCard extends StatelessWidget {
  const _StudentCard({required this.student});

  final StudentModel student;

  @override
  Widget build(BuildContext context) {
    final avatarColor = Color(Formatters.avatarColor(student.fullName));
    return GlassCard(
      onTap: () {
        Navigator.of(context).push(
          MaterialPageRoute<void>(
            builder: (_) => StudentDetailScreen(student: student),
          ),
        );
      },
      child: Row(
        children: [
          Hero(
            tag: 'student-avatar-${student.id}',
            child: CircleAvatar(
              radius: 26,
              backgroundColor: avatarColor.withValues(alpha: 0.18),
              child: Text(
                Formatters.initials(student.fullName),
                style: AppTextStyles.label.copyWith(color: avatarColor),
              ),
            ),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(student.fullName, style: AppTextStyles.title.copyWith(fontSize: 16)),
                const SizedBox(height: AppSpacing.xs),
                Text(
                  '${student.groupName.isEmpty ? 'Guruh biriktirilmagan' : student.groupName} • ${student.phone.isEmpty ? 'Telefon yo\'q' : student.phone}',
                  style: AppTextStyles.bodySmall,
                ),
              ],
            ),
          ),
          StatChip(
            label: student.balance < 0
                ? '-${Formatters.currency(student.balance.abs(), compact: true)}'
                : Formatters.currency(student.balance, compact: true),
            color: student.balance < 0 ? AppColors.danger : AppColors.success,
          ),
        ],
      ),
    );
  }
}
