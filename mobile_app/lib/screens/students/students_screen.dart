import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/groups_provider.dart';
import 'package:chaqmoq_mobile/providers/students_provider.dart';
import 'package:chaqmoq_mobile/widgets/app_button.dart';
import 'package:chaqmoq_mobile/widgets/app_input_field.dart';
import 'package:chaqmoq_mobile/widgets/app_list_item_card.dart';
import 'package:chaqmoq_mobile/widgets/app_page_header.dart';
import 'package:chaqmoq_mobile/widgets/empty_state.dart';
import 'package:chaqmoq_mobile/widgets/loading_state.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class StudentsScreen extends StatefulWidget {
  const StudentsScreen({super.key});

  @override
  State<StudentsScreen> createState() => _StudentsScreenState();
}

class _StudentsScreenState extends State<StudentsScreen> {
  final _searchController = TextEditingController();
  bool _queuedLoad = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_queuedLoad) {
      return;
    }
    _queuedLoad = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      context.read<StudentsProvider>().load();
      context.read<GroupsProvider>().ensureLoaded();
    });
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _reload() async {
    await context.read<StudentsProvider>().load(
      query: _searchController.text.trim(),
    );
  }

  Future<void> _openCreateSheet() async {
    await context.read<GroupsProvider>().ensureLoaded();
    if (!mounted) {
      return;
    }

    final created = await showModalBottomSheet<StudentModel>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => const _CreateStudentSheet(),
    );

    if (!mounted || created == null) {
      return;
    }

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('${created.fullName} muvaffaqiyatli qo\'shildi')),
    );
  }

  void _showDetails(StudentModel student) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => _StudentDetailSheet(student: student),
    );
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final provider = context.watch<StudentsProvider>();
    final canCreate =
        auth.user?.isSuperuser == true ||
        auth.user?.permissions.canAddStudent == true;

    if (provider.isLoading && provider.items.isEmpty) {
      return const LoadingState(title: 'O\'quvchilar yuklanmoqda...');
    }

    if (provider.errorMessage != null && provider.items.isEmpty) {
      return EmptyState(
        icon: Icons.school_rounded,
        title: 'O\'quvchilar bo\'limi ochilmadi',
        message: provider.errorMessage!,
        actionLabel: 'Qayta urinish',
        onAction: () => context.read<StudentsProvider>().load(),
      );
    }

    return RefreshIndicator(
      onRefresh: _reload,
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          AppPageHeader(
            title: 'O\'quvchilar',
            subtitle:
                'O\'quvchilar profili, balans, davomat va guruh birikmalarini boshqaring.',
            action: canCreate
                ? AppButton(
                    label: 'Qo\'shish',
                    icon: Icons.person_add_alt_1_rounded,
                    expanded: false,
                    onPressed: _openCreateSheet,
                  )
                : null,
          ),
          const SizedBox(height: 14),
          AppInputField(
            controller: _searchController,
            label: 'Qidiruv',
            hint: 'O\'quvchi qidirish',
            prefixIcon: Icons.search_rounded,
            textInputAction: TextInputAction.search,
            onFieldSubmitted: (_) => _reload(),
            suffixIcon: IconButton(
              onPressed: _reload,
              icon: const Icon(Icons.arrow_forward_rounded),
            ),
          ),
          const SizedBox(height: 14),
          if (provider.items.isEmpty)
            const EmptyState(
              icon: Icons.person_search_rounded,
              title: 'Hali o\'quvchilar yo\'q',
              message: 'Yangi o\'quvchi qo\'shing yoki ro\'yxatni yangilang.',
            )
          else
            for (final student in provider.items) ...[
              AppListItemCard(
                onTap: () => _showDetails(student),
                title: student.fullName,
                subtitle:
                    student.phone.isEmpty ? student.email : student.phone,
                trailing: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      AppFormatters.formatMoney(student.balance),
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    Text(
                      'Qarz ${AppFormatters.formatMoney(student.debt)}',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
                tags: [
                  Chip(
                    label: Text(
                      '${student.attendance.attendanceRate.toStringAsFixed(0)}% davomat',
                    ),
                  ),
                  for (final group in student.groups.take(3))
                    Chip(label: Text(group.group.name)),
                ],
                footer: student.lastPayment == null
                    ? null
                    : Text(
                        'Oxirgi to\'lov: ${AppFormatters.formatMoney(student.lastPayment!.amount)} • ${AppFormatters.formatDate(student.lastPayment!.paidDate)}',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
              ),
              if (student != provider.items.last) const SizedBox(height: 14),
            ],
        ],
      ),
    );
  }
}

class _CreateStudentSheet extends StatefulWidget {
  const _CreateStudentSheet();

  @override
  State<_CreateStudentSheet> createState() => _CreateStudentSheetState();
}

class _CreateStudentSheetState extends State<_CreateStudentSheet> {
  final _formKey = GlobalKey<FormState>();
  final _ismController = TextEditingController();
  final _familyaController = TextEditingController();
  final _otchestvoController = TextEditingController();
  final _emailController = TextEditingController();
  final _phoneController = TextEditingController();
  final _passwordController = TextEditingController();
  final Set<int> _groupIds = <int>{};

  @override
  void dispose() {
    _ismController.dispose();
    _familyaController.dispose();
    _otchestvoController.dispose();
    _emailController.dispose();
    _phoneController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    final provider = context.read<StudentsProvider>();
    final student = await provider.create({
      'ism': _ismController.text.trim(),
      'familya': _familyaController.text.trim(),
      'otchestvo': _otchestvoController.text.trim(),
      'email': _emailController.text.trim(),
      'phone_number': _phoneController.text.trim(),
      'telefon1': _phoneController.text.trim(),
      'password': _passwordController.text.trim(),
      'group_ids': _groupIds.toList(),
    });

    if (!mounted || student == null) {
      return;
    }
    Navigator.of(context).pop(student);
  }

  @override
  Widget build(BuildContext context) {
    final students = context.watch<StudentsProvider>();
    final groups = context.watch<GroupsProvider>().items;

    return Padding(
      padding: EdgeInsets.fromLTRB(
        20,
        0,
        20,
        MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      child: SingleChildScrollView(
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'O\'quvchi qo\'shish',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 16),
              AppInputField(
                controller: _ismController,
                label: 'Ism',
                validator: (value) =>
                    value == null || value.trim().isEmpty ? 'Majburiy maydon' : null,
              ),
              const SizedBox(height: 12),
              AppInputField(
                controller: _familyaController,
                label: 'Familiya',
                validator: (value) =>
                    value == null || value.trim().isEmpty ? 'Majburiy maydon' : null,
              ),
              const SizedBox(height: 12),
              AppInputField(
                controller: _otchestvoController,
                label: 'Sharif',
              ),
              const SizedBox(height: 12),
              AppInputField(
                controller: _phoneController,
                keyboardType: TextInputType.phone,
                label: 'Telefon',
              ),
              const SizedBox(height: 12),
              AppInputField(
                controller: _emailController,
                keyboardType: TextInputType.emailAddress,
                label: 'Elektron pochta',
              ),
              const SizedBox(height: 12),
              AppInputField(
                controller: _passwordController,
                label: 'Vaqtinchalik parol',
                validator: (value) {
                  if (value == null || value.trim().length < 6) {
                    return 'Kamida 6 ta belgi kiriting';
                  }
                  return null;
                },
              ),
              if (groups.isNotEmpty) ...[
                const SizedBox(height: 16),
                Text(
                  'Biriktiriladigan guruhlar',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final group in groups)
                      FilterChip(
                        label: Text(group.name),
                        selected: _groupIds.contains(group.id),
                        onSelected: (selected) {
                          setState(() {
                            if (selected) {
                              _groupIds.add(group.id);
                            } else {
                              _groupIds.remove(group.id);
                            }
                          });
                        },
                      ),
                  ],
                ),
              ],
              if (students.errorMessage != null) ...[
                const SizedBox(height: 12),
                Text(
                  students.errorMessage!,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.error,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
              const SizedBox(height: 20),
              AppButton(
                label: students.isSaving
                    ? 'Qo\'shilmoqda...'
                    : 'O\'quvchini qo\'shish',
                icon: Icons.check_rounded,
                loading: students.isSaving,
                onPressed: _submit,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StudentDetailSheet extends StatelessWidget {
  const _StudentDetailSheet({required this.student});

  final StudentModel student;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              student.fullName,
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            Text(
              student.phone.isEmpty ? student.email : student.phone,
              style: Theme.of(context).textTheme.bodyLarge,
            ),
            const SizedBox(height: 18),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                Chip(
                  label: Text(
                    'Balans ${AppFormatters.formatMoney(student.balance)}',
                  ),
                ),
                Chip(
                  label: Text(
                    'Qarz ${AppFormatters.formatMoney(student.debt)}',
                  ),
                ),
                Chip(
                  label: Text(
                    '${student.attendance.attendanceRate.toStringAsFixed(0)}% davomat',
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            if (student.groups.isNotEmpty) ...[
              Text('Guruhlar', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 10),
              for (final group in student.groups) ...[
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(group.group.name),
                  subtitle: Text(
                    '${AppFormatters.formatMoney(group.coursePrice)} • To\'langan ${AppFormatters.formatMoney(group.paidTotal)}',
                  ),
                  trailing: Chip(
                    label: Text(group.isActive ? 'Faol' : 'Nofaol'),
                  ),
                ),
              ],
            ],
            if (student.payments.isNotEmpty) ...[
              const SizedBox(height: 12),
              Text(
                'So\'nggi to\'lovlar',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 10),
              for (final payment in student.payments) ...[
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(payment.groupName),
                  subtitle: Text(AppFormatters.formatDate(payment.paidDate)),
                  trailing: Text(AppFormatters.formatMoney(payment.amount)),
                ),
              ],
            ],
          ],
        ),
      ),
    );
  }
}
