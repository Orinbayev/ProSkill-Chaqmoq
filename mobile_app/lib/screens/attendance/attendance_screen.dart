import 'package:chaqmoq_mobile/core/theme/app_colors.dart';
import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/app_text_styles.dart';
import 'package:chaqmoq_mobile/core/utils/role_utils.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/attendance_provider.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/groups_provider.dart';
import 'package:chaqmoq_mobile/widgets/app_button.dart';
import 'package:chaqmoq_mobile/widgets/empty_state.dart';
import 'package:chaqmoq_mobile/widgets/glass_card.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class AttendanceScreen extends StatefulWidget {
  const AttendanceScreen({super.key});

  @override
  State<AttendanceScreen> createState() => _AttendanceScreenState();
}

class _AttendanceScreenState extends State<AttendanceScreen> {
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final role = context.read<AuthProvider>().user?.role;
    if (role != null) {
      context.read<GroupsProvider>().load(role);
    }
  }

  Future<void> _pickDate() async {
    final provider = context.read<AttendanceProvider>();
    final picked = await showDatePicker(
      context: context,
      initialDate: provider.selectedDate,
      firstDate: DateTime.now().subtract(const Duration(days: 365)),
      lastDate: DateTime.now().add(const Duration(days: 365)),
    );
    if (picked != null) {
      await provider.changeDate(picked);
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final groups = context.watch<GroupsProvider>();
    final attendance = context.watch<AttendanceProvider>();
    final role = auth.user?.role ?? '';

    if (!RoleUtils.isDirectorScope(role) && role != 'teacher') {
      return const EmptyState(
        title: 'Ruxsat yo\'q',
        message: 'Davomat bo\'limi sizning rol uchun yopiq',
        icon: Icons.lock_outline_rounded,
      );
    }

    return ListView(
      padding: const EdgeInsets.all(AppSpacing.xl),
      children: [
        Row(
          children: [
            Expanded(
              child: GlassCard(
                child: InkWell(
                  onTap: _pickDate,
                  child: Row(
                    children: [
                      const Icon(Icons.calendar_today_rounded, color: AppColors.primary),
                      const SizedBox(width: AppSpacing.md),
                      Expanded(
                        child: Text(
                          '${attendance.selectedDate.day}.${attendance.selectedDate.month}.${attendance.selectedDate.year}',
                          style: AppTextStyles.body,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.lg),
        GlassCard(
          child: DropdownButtonHideUnderline(
            child: DropdownButton<int>(
              value: attendance.selectedGroup?.id,
              hint: const Text('Guruhni tanlang'),
              isExpanded: true,
              items: groups.groups
                  .map(
                    (group) => DropdownMenuItem<int>(
                      value: group.id,
                      child: Text(group.name),
                    ),
                  )
                  .toList(),
              onChanged: (value) {
                if (value == null) {
                  return;
                }
                final group = groups.groups.firstWhere((item) => item.id == value);
                attendance.loadSheet(group, date: attendance.selectedDate);
              },
            ),
          ),
        ),
        const SizedBox(height: AppSpacing.xl),
        if (attendance.selectedGroup == null)
          const EmptyState(
            title: 'Guruh tanlanmagan',
            message: 'Davomatni ko\'rish yoki belgilash uchun guruh tanlang',
            icon: Icons.view_module_rounded,
          )
        else if (attendance.state == ViewState.loading)
          const Center(child: CircularProgressIndicator())
        else if (attendance.state == ViewState.error)
          EmptyState(
            title: 'Davomat yuklanmadi',
            message: attendance.errorMessage ?? 'Qayta urinib ko\'ring',
            icon: Icons.fact_check_rounded,
            actionLabel: 'Qayta yuklash',
            onAction: () => attendance.loadSheet(attendance.selectedGroup!, date: attendance.selectedDate),
          )
        else if (attendance.sheet == null || attendance.sheet!.items.isEmpty)
          const EmptyState(
            title: 'Ro\'yxat bo\'sh',
            message: 'Tanlangan guruh uchun o\'quvchi topilmadi',
            icon: Icons.person_search_rounded,
          )
        else ...[
          if (attendance.sheet!.readOnly)
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.lg),
              child: Text(
                'Tanlangan sana o\'tgan davrga tegishli. Rejim faqat ko\'rish uchun.',
                style: AppTextStyles.subtitle,
              ),
            ),
          ...attendance.sheet!.items.map(
            (item) => Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.lg),
              child: GlassCard(
                child: Row(
                  children: [
                    Expanded(child: Text(item.fullName, style: AppTextStyles.body)),
                    if (attendance.sheet!.readOnly)
                      Text(item.status, style: AppTextStyles.bodySmall)
                    else
                      Row(
                        children: [
                          ChoiceChip(
                            label: const Text('Present ✓'),
                            selected: item.status == 'present',
                            onSelected: (_) => attendance.updateStatus(item.studentId, 'present'),
                          ),
                          const SizedBox(width: AppSpacing.sm),
                          ChoiceChip(
                            label: const Text('Absent ✗'),
                            selected: item.status == 'absent_unexcused',
                            onSelected: (_) => attendance.updateStatus(item.studentId, 'absent_unexcused'),
                          ),
                        ],
                      ),
                  ],
                ),
              ),
            ),
          ),
          if (!attendance.sheet!.readOnly)
            AppButton(
              label: 'Davomatni saqlash',
              onPressed: () async {
                await attendance.submit();
                if (!context.mounted) {
                  return;
                }
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      attendance.submitState == ViewState.success
                          ? 'Davomat saqlandi'
                          : (attendance.errorMessage ?? 'Davomat saqlanmadi'),
                    ),
                  ),
                );
              },
              isLoading: attendance.submitState == ViewState.loading,
            ),
        ],
      ],
    );
  }
}
