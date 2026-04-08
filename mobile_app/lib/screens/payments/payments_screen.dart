import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/payments_provider.dart';
import 'package:chaqmoq_mobile/providers/students_provider.dart';
import 'package:chaqmoq_mobile/widgets/app_button.dart';
import 'package:chaqmoq_mobile/widgets/app_input_field.dart';
import 'package:chaqmoq_mobile/widgets/app_list_item_card.dart';
import 'package:chaqmoq_mobile/widgets/app_page_header.dart';
import 'package:chaqmoq_mobile/widgets/chaqmoq_card.dart';
import 'package:chaqmoq_mobile/widgets/empty_state.dart';
import 'package:chaqmoq_mobile/widgets/loading_state.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class PaymentsScreen extends StatefulWidget {
  const PaymentsScreen({super.key});

  @override
  State<PaymentsScreen> createState() => _PaymentsScreenState();
}

class _PaymentsScreenState extends State<PaymentsScreen> {
  final _searchController = TextEditingController();
  bool _queuedLoad = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_queuedLoad) {
      return;
    }
    _queuedLoad = true;
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (!mounted) {
        return;
      }
      await context.read<PaymentsProvider>().load();
      if (!mounted) {
        return;
      }
      final user = context.read<AuthProvider>().user;
      final canCreate =
          user?.isSuperuser == true ||
          user?.effectiveRole == 'director' ||
          user?.effectiveRole == 'manager';
      if (canCreate) {
        context.read<StudentsProvider>().ensureLoaded();
      }
    });
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _reload() async {
    await context.read<PaymentsProvider>().load(
      query: _searchController.text.trim(),
    );
  }

  Future<void> _openCreateSheet() async {
    await context.read<StudentsProvider>().ensureLoaded();
    if (!mounted) {
      return;
    }

    final created = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => const _CreatePaymentSheet(),
    );

    if (!mounted || created != true) {
      return;
    }

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('To\'lov muvaffaqiyatli yaratildi')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final provider = context.watch<PaymentsProvider>();
    final role = auth.user?.effectiveRole;
    final canCreate =
        auth.user?.isSuperuser == true ||
        role == 'director' ||
        role == 'manager';

    if (provider.isLoading && provider.items.isEmpty) {
      return const LoadingState(title: 'To\'lovlar yuklanmoqda...');
    }

    if (provider.errorMessage != null && provider.items.isEmpty) {
      return EmptyState(
        icon: Icons.payments_rounded,
        title: 'To\'lovlar bo\'limi ochilmadi',
        message: provider.errorMessage!,
        actionLabel: 'Qayta urinish',
        onAction: () => context.read<PaymentsProvider>().load(),
      );
    }

    return RefreshIndicator(
      onRefresh: _reload,
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          ChaqmoqCard(
            gradient: const LinearGradient(
              colors: [Color(0xFF0F172A), Color(0xFF0EA5E9)],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        AppFormatters.formatMoney(provider.totalAmount),
                        style: Theme.of(context).textTheme.headlineSmall
                            ?.copyWith(
                              color: Colors.white,
                              fontWeight: FontWeight.w800,
                            ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        '${provider.items.length} ta to\'lov asosida',
                        style: Theme.of(
                          context,
                        ).textTheme.bodyMedium?.copyWith(color: Colors.white70),
                      ),
                    ],
                  ),
                ),
                if (canCreate)
                  AppButton(
                    label: 'To\'lov qo\'shish',
                    icon: Icons.add_card_rounded,
                    expanded: false,
                    variant: AppButtonVariant.tonal,
                    onPressed: _openCreateSheet,
                  ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          const AppPageHeader(
            title: 'To\'lovlar',
            subtitle:
                'Qabul qilingan tushum, to\'lov turi va izohlarni kuzatib boring.',
          ),
          const SizedBox(height: 14),
          AppInputField(
            controller: _searchController,
            label: 'Qidiruv',
            hint: 'O\'quvchi yoki guruh bo\'yicha qidiring',
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
              icon: Icons.receipt_long_rounded,
              title: 'Hali to\'lovlar yo\'q',
              message: 'Markazingiz bo\'yicha to\'lovlar shu yerda ko\'rinadi.',
            )
          else
            for (final payment in provider.items) ...[
              AppListItemCard(
                title: payment.studentName,
                subtitle: payment.groupName,
                trailing: Text(
                  AppFormatters.formatMoney(payment.amount),
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                tags: [
                  Chip(
                    label: Text(
                      AppFormatters.paymentTypeLabel(payment.paymentType),
                    ),
                  ),
                  Chip(
                    label: Text(
                      'Naqd ${AppFormatters.formatMoney(payment.cashAmount)}',
                    ),
                  ),
                  Chip(
                    label: Text(
                      'Karta ${AppFormatters.formatMoney(payment.cardAmount)}',
                    ),
                  ),
                ],
                footer: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${AppFormatters.formatDate(payment.paidDate)} • ${payment.createdBy.isEmpty ? 'Tizim' : payment.createdBy}',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    if (payment.note.isNotEmpty) ...[
                      const SizedBox(height: 8),
                      Text(
                        payment.note,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ],
                ),
              ),
              if (payment != provider.items.last) const SizedBox(height: 14),
            ],
        ],
      ),
    );
  }
}

class _CreatePaymentSheet extends StatefulWidget {
  const _CreatePaymentSheet();

  @override
  State<_CreatePaymentSheet> createState() => _CreatePaymentSheetState();
}

class _CreatePaymentSheetState extends State<_CreatePaymentSheet> {
  final _formKey = GlobalKey<FormState>();
  final _cashController = TextEditingController();
  final _cardController = TextEditingController();
  final _noteController = TextEditingController();
  int? _selectedStudentId;
  int? _selectedEnrollmentId;
  DateTime _selectedMonth = DateTime(
    DateTime.now().year,
    DateTime.now().month,
    1,
  );

  @override
  void dispose() {
    _cashController.dispose();
    _cardController.dispose();
    _noteController.dispose();
    super.dispose();
  }

  StudentModel? _findStudent(List<StudentModel> students, int? id) {
    if (id == null) {
      return null;
    }
    for (final student in students) {
      if (student.id == id) {
        return student;
      }
    }
    return null;
  }

  Future<void> _pickMonth() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedMonth,
      firstDate: DateTime.now().subtract(const Duration(days: 365 * 2)),
      lastDate: DateTime.now().add(const Duration(days: 365 * 2)),
      initialDatePickerMode: DatePickerMode.year,
    );

    if (picked == null || !mounted) {
      return;
    }
    setState(() => _selectedMonth = DateTime(picked.year, picked.month, 1));
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }
    if (_selectedEnrollmentId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Avval guruh birikmasini tanlang')),
      );
      return;
    }

    final cashAmount = int.tryParse(_cashController.text.trim()) ?? 0;
    final cardAmount = int.tryParse(_cardController.text.trim()) ?? 0;
    if (cashAmount <= 0 && cardAmount <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Naqd yoki karta summasini kiriting')),
      );
      return;
    }

    final provider = context.read<PaymentsProvider>();
    final payment = await provider.create(
      enrollmentId: _selectedEnrollmentId!,
      cashAmount: cashAmount,
      cardAmount: cardAmount,
      month: _selectedMonth,
      note: _noteController.text.trim(),
    );

    if (!mounted || payment == null) {
      return;
    }
    Navigator.of(context).pop(true);
  }

  @override
  Widget build(BuildContext context) {
    final payments = context.watch<PaymentsProvider>();
    final studentsProvider = context.watch<StudentsProvider>();
    final students = studentsProvider.items
        .where((student) => student.groups.isNotEmpty)
        .toList();
    final selectedStudent = _findStudent(students, _selectedStudentId);
    final enrollments = selectedStudent?.groups ?? <GroupEnrollment>[];

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
                'To\'lov yaratish',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<int>(
                initialValue: _selectedStudentId,
                decoration: const InputDecoration(labelText: 'O\'quvchi'),
                items: [
                  for (final student in students)
                    DropdownMenuItem<int>(
                      value: student.id,
                      child: Text(student.fullName),
                    ),
                ],
                onChanged: (value) {
                  setState(() {
                    _selectedStudentId = value;
                    _selectedEnrollmentId = null;
                  });
                },
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<int>(
                initialValue: _selectedEnrollmentId,
                decoration: const InputDecoration(
                  labelText: 'Guruh birikmasi',
                ),
                items: [
                  for (final enrollment in enrollments)
                    DropdownMenuItem<int>(
                      value: enrollment.enrollmentId,
                      child: Text(enrollment.group.name),
                    ),
                ],
                onChanged: enrollments.isEmpty
                    ? null
                    : (value) => setState(() => _selectedEnrollmentId = value),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: AppInputField(
                      controller: _cashController,
                      keyboardType: TextInputType.number,
                      label: 'Naqd summa',
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: AppInputField(
                      controller: _cardController,
                      keyboardType: TextInputType.number,
                      label: 'Karta summasi',
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: _pickMonth,
                icon: const Icon(Icons.calendar_month_rounded),
                label: Text(
                  AppFormatters.formatMonthYear(_selectedMonth),
                ),
              ),
              const SizedBox(height: 12),
              AppInputField(
                controller: _noteController,
                minLines: 2,
                maxLines: 4,
                label: 'Izoh',
              ),
              if (payments.errorMessage != null) ...[
                const SizedBox(height: 12),
                Text(
                  payments.errorMessage!,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.error,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
              const SizedBox(height: 20),
              AppButton(
                label: payments.isSaving
                    ? 'Yaratilmoqda...'
                    : 'To\'lovni yaratish',
                icon: Icons.check_rounded,
                loading: payments.isSaving,
                onPressed: _submit,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
