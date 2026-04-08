import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/attendance_provider.dart';
import 'package:chaqmoq_mobile/providers/groups_provider.dart';
import 'package:chaqmoq_mobile/widgets/app_button.dart';
import 'package:chaqmoq_mobile/widgets/app_page_header.dart';
import 'package:chaqmoq_mobile/widgets/chaqmoq_card.dart';
import 'package:chaqmoq_mobile/widgets/empty_state.dart';
import 'package:chaqmoq_mobile/widgets/loading_state.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class AttendanceScreen extends StatefulWidget {
  const AttendanceScreen({super.key});

  @override
  State<AttendanceScreen> createState() => _AttendanceScreenState();
}

class _AttendanceScreenState extends State<AttendanceScreen> {
  int? _selectedGroupId;
  DateTime _selectedDate = DateTime.now();
  final Map<int, String> _statuses = <int, String>{};
  final Map<int, bool> _forced = <int, bool>{};
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
      final groupsProvider = context.read<GroupsProvider>();
      await groupsProvider.ensureLoaded();
      if (!mounted || groupsProvider.items.isEmpty) {
        return;
      }
      _selectedGroupId = groupsProvider.items.first.id;
      await _loadSheet();
    });
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDate,
      firstDate: DateTime.now().subtract(const Duration(days: 365)),
      lastDate: DateTime.now().add(const Duration(days: 365)),
    );

    if (picked == null || !mounted) {
      return;
    }
    setState(() => _selectedDate = picked);
    await _loadSheet();
  }

  Future<void> _loadSheet() async {
    if (_selectedGroupId == null) {
      return;
    }

    await context.read<AttendanceProvider>().load(
      groupId: _selectedGroupId!,
      date: _selectedDate,
    );

    if (!mounted) {
      return;
    }

    final sheet = context.read<AttendanceProvider>().sheet;
    if (sheet == null) {
      return;
    }

    setState(() {
      _statuses
        ..clear()
        ..addEntries(
          sheet.items.map((item) => MapEntry(item.id, item.attendanceStatus)),
        );
      _forced
        ..clear()
        ..addEntries(sheet.items.map((item) => MapEntry(item.id, item.forced)));
    });
  }

  Future<void> _saveAttendance() async {
    if (_selectedGroupId == null) {
      return;
    }

    final items = _statuses.entries
        .map(
          (entry) => {
            'student_id': entry.key,
            'status': entry.value,
            'forced': _forced[entry.key] ?? false,
          },
        )
        .toList();

    final success = await context.read<AttendanceProvider>().submit(
      groupId: _selectedGroupId!,
      date: _selectedDate,
      items: items,
    );

    if (!mounted || !success) {
      return;
    }

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Davomat muvaffaqiyatli saqlandi')),
    );
  }

  void _setStatus(AttendanceMember member, String status) {
    setState(() => _statuses[member.id] = status);
  }

  @override
  Widget build(BuildContext context) {
    final groupsProvider = context.watch<GroupsProvider>();
    final attendanceProvider = context.watch<AttendanceProvider>();
    final groups = groupsProvider.items;
    final sheet = attendanceProvider.sheet;

    if (groupsProvider.isLoading && groups.isEmpty) {
      return const LoadingState(title: 'Davomat guruhlari yuklanmoqda...');
    }

    if (groups.isEmpty) {
      return EmptyState(
        icon: Icons.fact_check_rounded,
        title: 'Guruhlar mavjud emas',
        message:
            groupsProvider.errorMessage ??
            'Bugungi davomat uchun sizga biriktirilgan guruh topilmadi.',
        actionLabel: 'Qayta urinish',
        onAction: () => context.read<GroupsProvider>().load(),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadSheet,
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const AppPageHeader(
            title: 'Davomat nazorati',
            subtitle:
                'Guruhni tanlang, ro\'yxatni tekshiring va davomatni bir oqimda yuboring.',
          ),
          const SizedBox(height: 14),
          ChaqmoqCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                DropdownButtonFormField<int>(
                  initialValue: _selectedGroupId,
                  items: [
                    for (final group in groups)
                      DropdownMenuItem<int>(
                        value: group.id,
                        child: Text(group.name),
                      ),
                  ],
                  onChanged: (value) async {
                    setState(() => _selectedGroupId = value);
                    await _loadSheet();
                  },
                  decoration: const InputDecoration(labelText: 'Guruh'),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: AppButton(
                        label: AppFormatters.formatDate(_selectedDate),
                        icon: Icons.calendar_month_rounded,
                        variant: AppButtonVariant.outlined,
                        onPressed: _pickDate,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: AppButton(
                        label: 'Yangilash',
                        icon: Icons.sync_rounded,
                        variant: AppButtonVariant.tonal,
                        onPressed: _loadSheet,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          if (attendanceProvider.errorMessage != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(
                attendanceProvider.errorMessage!,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.error,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          if (attendanceProvider.isLoading && sheet == null)
            const LoadingState(title: 'Davomat varaqasi yuklanmoqda...')
          else if (sheet == null)
            const EmptyState(
              icon: Icons.calendar_today_rounded,
              title: 'Davomat varaqasi yuklanmadi',
              message: 'Bugungi davomatni ko\'rish uchun guruh tanlang.',
            )
          else ...[
            ChaqmoqCard(
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          sheet.group.name,
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        const SizedBox(height: 6),
                        Text(
                          '${sheet.items.length} o\'quvchi • ${AppFormatters.formatDate(sheet.date)}',
                          style: Theme.of(context).textTheme.bodyMedium,
                        ),
                      ],
                    ),
                  ),
                  AppButton(
                    label: 'Saqlash',
                    icon: Icons.save_rounded,
                    expanded: false,
                    loading: attendanceProvider.isSaving,
                    onPressed: _saveAttendance,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 14),
            for (final member in sheet.items) ...[
              ChaqmoqCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                member.fullName,
                                style: Theme.of(context).textTheme.titleMedium,
                              ),
                              const SizedBox(height: 4),
                              Text(
                                member.phone,
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 12),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            Text(
                              'Qarz ${AppFormatters.formatMoney(member.debt)}',
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                            Text(
                              'Balans ${AppFormatters.formatMoney(member.balance)}',
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ],
                        ),
                      ],
                    ),
                    const SizedBox(height: 14),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        _StatusChip(
                          label: 'Qatnashdi',
                          selected:
                              (_statuses[member.id] ??
                                  member.attendanceStatus) ==
                              'present',
                          onTap: () => _setStatus(member, 'present'),
                        ),
                        _StatusChip(
                          label: 'Sababli',
                          selected:
                              (_statuses[member.id] ??
                                  member.attendanceStatus) ==
                              'absent_excused',
                          onTap: () => _setStatus(member, 'absent_excused'),
                        ),
                        _StatusChip(
                          label: 'Sababsiz',
                          selected:
                              (_statuses[member.id] ??
                                  member.attendanceStatus) ==
                              'absent_unexcused',
                          onTap: () => _setStatus(member, 'absent_unexcused'),
                        ),
                        FilterChip(
                          label: const Text('Majburiy'),
                          selected: _forced[member.id] ?? member.forced,
                          onSelected: (value) {
                            setState(() => _forced[member.id] = value);
                          },
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              if (member != sheet.items.last) const SizedBox(height: 14),
            ],
          ],
        ],
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return ChoiceChip(
      label: Text(label),
      selected: selected,
      onSelected: (_) => onTap(),
    );
  }
}
