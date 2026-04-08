import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/teachers_provider.dart';
import 'package:chaqmoq_mobile/widgets/app_button.dart';
import 'package:chaqmoq_mobile/widgets/app_input_field.dart';
import 'package:chaqmoq_mobile/widgets/app_list_item_card.dart';
import 'package:chaqmoq_mobile/widgets/app_page_header.dart';
import 'package:chaqmoq_mobile/widgets/empty_state.dart';
import 'package:chaqmoq_mobile/widgets/loading_state.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class TeachersScreen extends StatefulWidget {
  const TeachersScreen({super.key});

  @override
  State<TeachersScreen> createState() => _TeachersScreenState();
}

class _TeachersScreenState extends State<TeachersScreen> {
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
      context.read<TeachersProvider>().load();
    });
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _reload() async {
    await context.read<TeachersProvider>().load(
      query: _searchController.text.trim(),
    );
  }

  Future<void> _openCreateSheet() async {
    final created = await showModalBottomSheet<TeacherModel>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => const _CreateTeacherSheet(),
    );

    if (!mounted || created == null) {
      return;
    }

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('${created.fullName} muvaffaqiyatli qo\'shildi')),
    );
  }

  void _showDetails(TeacherModel teacher) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => _TeacherDetailSheet(teacher: teacher),
    );
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final provider = context.watch<TeachersProvider>();
    final role = auth.user?.effectiveRole;
    final canCreate =
        auth.user?.isSuperuser == true ||
        role == 'director' ||
        role == 'manager';

    if (provider.isLoading && provider.items.isEmpty) {
      return const LoadingState(title: 'O\'qituvchilar yuklanmoqda...');
    }

    if (provider.errorMessage != null && provider.items.isEmpty) {
      return EmptyState(
        icon: Icons.badge_rounded,
        title: 'O\'qituvchilar bo\'limi ochilmadi',
        message: provider.errorMessage!,
        actionLabel: 'Qayta urinish',
        onAction: () => context.read<TeachersProvider>().load(),
      );
    }

    return RefreshIndicator(
      onRefresh: _reload,
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          AppPageHeader(
            title: 'O\'qituvchilar',
            subtitle:
                'Dars yuklamasi, qamrov va kutilayotgan daromadni kuzating.',
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
            hint: 'O\'qituvchi qidirish',
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
              icon: Icons.school_rounded,
              title: 'O\'qituvchilar topilmadi',
              message: 'Yangi o\'qituvchi qo\'shing yoki ro\'yxatni yangilang.',
            )
          else
            for (final teacher in provider.items) ...[
              AppListItemCard(
                onTap: () => _showDetails(teacher),
                title: teacher.fullName,
                subtitle:
                    teacher.phone.isEmpty ? teacher.email : teacher.phone,
                trailing: Chip(label: Text('${teacher.groupsCount} guruh')),
                tags: [
                  Chip(label: Text('${teacher.studentsCount} o\'quvchi')),
                  Chip(
                    label: Text(
                      '${teacher.todayAttendanceCount} ta davomat belgisi',
                    ),
                  ),
                  for (final group in teacher.groups.take(3))
                    Chip(label: Text(group.name)),
                ],
              ),
              if (teacher != provider.items.last) const SizedBox(height: 14),
            ],
        ],
      ),
    );
  }
}

class _CreateTeacherSheet extends StatefulWidget {
  const _CreateTeacherSheet();

  @override
  State<_CreateTeacherSheet> createState() => _CreateTeacherSheetState();
}

class _CreateTeacherSheetState extends State<_CreateTeacherSheet> {
  final _formKey = GlobalKey<FormState>();
  final _ismController = TextEditingController();
  final _familyaController = TextEditingController();
  final _emailController = TextEditingController();
  final _phoneController = TextEditingController();
  final _passwordController = TextEditingController();
  final _shareController = TextEditingController(text: '40');

  @override
  void dispose() {
    _ismController.dispose();
    _familyaController.dispose();
    _emailController.dispose();
    _phoneController.dispose();
    _passwordController.dispose();
    _shareController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    final provider = context.read<TeachersProvider>();
    final teacher = await provider.create({
      'ism': _ismController.text.trim(),
      'familya': _familyaController.text.trim(),
      'email': _emailController.text.trim(),
      'phone_number': _phoneController.text.trim(),
      'telefon1': _phoneController.text.trim(),
      'password': _passwordController.text.trim(),
      'oqituvchi_foizi': int.tryParse(_shareController.text.trim()) ?? 40,
    });

    if (!mounted || teacher == null) {
      return;
    }
    Navigator.of(context).pop(teacher);
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<TeachersProvider>();

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
                'O\'qituvchi qo\'shish',
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
              const SizedBox(height: 12),
              AppInputField(
                controller: _shareController,
                keyboardType: TextInputType.number,
                label: 'Ustoz ulushi %',
              ),
              if (provider.errorMessage != null) ...[
                const SizedBox(height: 12),
                Text(
                  provider.errorMessage!,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.error,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
              const SizedBox(height: 20),
              AppButton(
                label: provider.isSaving
                    ? 'Qo\'shilmoqda...'
                    : 'O\'qituvchini qo\'shish',
                icon: Icons.check_rounded,
                loading: provider.isSaving,
                onPressed: _submit,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _TeacherDetailSheet extends StatelessWidget {
  const _TeacherDetailSheet({required this.teacher});

  final TeacherModel teacher;

  List<String> _expectedIncomeRows() {
    return teacher.expectedIncome.entries
        .where((entry) => entry.value is num || entry.value is String)
        .map((entry) => '${entry.key.replaceAll('_', ' ')}: ${entry.value}')
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    final rows = _expectedIncomeRows();

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              teacher.fullName,
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            Text(
              teacher.phone.isEmpty ? teacher.email : teacher.phone,
              style: Theme.of(context).textTheme.bodyLarge,
            ),
            const SizedBox(height: 18),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                Chip(label: Text('${teacher.groupsCount} guruh')),
                Chip(label: Text('${teacher.studentsCount} o\'quvchi')),
                Chip(
                  label: Text(
                    '${teacher.todayAttendanceCount} ta davomat belgisi',
                  ),
                ),
              ],
            ),
            if (rows.isNotEmpty) ...[
              const SizedBox(height: 20),
              Text(
                'Kutilayotgan daromad',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 10),
              for (final row in rows) ...[
                Text(row, style: Theme.of(context).textTheme.bodyMedium),
                if (row != rows.last) const SizedBox(height: 6),
              ],
            ],
            if (teacher.groups.isNotEmpty) ...[
              const SizedBox(height: 20),
              Text(
                'Biriktirilgan guruhlar',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 10),
              for (final group in teacher.groups) ...[
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(group.name),
                  subtitle: Text(group.category),
                  trailing: Text(AppFormatters.formatMoney(group.monthlyPrice)),
                ),
              ],
            ],
          ],
        ),
      ),
    );
  }
}
