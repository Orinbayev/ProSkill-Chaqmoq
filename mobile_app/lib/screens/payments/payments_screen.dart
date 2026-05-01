import 'dart:convert';

import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/parent_models.dart';
import 'package:chaqmoq_mobile/providers/notifications_provider.dart';
import 'package:chaqmoq_mobile/providers/parent_dashboard_provider.dart';
import 'package:chaqmoq_mobile/screens/notifications/notifications_screen.dart';
import 'package:chaqmoq_mobile/screens/parent/parent_ui.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/local_notification_service.dart';
import 'package:chaqmoq_mobile/services/parent_dashboard_service.dart';
import 'package:chaqmoq_mobile/services/storage_service.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

class PaymentsScreen extends StatefulWidget {
  const PaymentsScreen({super.key, this.showBottomNav = true});

  final bool showBottomNav;

  @override
  State<PaymentsScreen> createState() => _PaymentsScreenState();
}

class _PaymentsScreenState extends State<PaymentsScreen> {
  ParentPaymentsModel? _data;
  ViewState _state = ViewState.idle;
  String? _errorMessage;
  int? _loadedChildId;
  PaymentHistoryFilter _historyFilter = PaymentHistoryFilter.all;
  ParentReminderSettingsModel? _reminderSettings;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final dashboard = context.watch<ParentDashboardProvider>();
    final childId =
        dashboard.selectedChildId ?? dashboard.data?.selectedChild.id;
    if (childId != null && childId > 0 && childId != _loadedChildId) {
      _loadedChildId = childId;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          _load(force: true);
        }
      });
    }
  }

  Future<void> _load({bool force = false}) async {
    if (_state == ViewState.loading && !force) {
      return;
    }
    setState(() {
      _state = ViewState.loading;
      _errorMessage = null;
    });
    try {
      final data = await context.read<ParentDashboardService>().fetchPayments(
        childId: _loadedChildId,
      );
      final reminder = await _readReminderSettingsFor(data);
      if (!mounted) {
        return;
      }
      setState(() {
        _data = data;
        _reminderSettings = reminder;
        _state = ViewState.success;
      });
    } on ApiException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _state = ViewState.error;
        _errorMessage = error.message;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _state = ViewState.error;
        _errorMessage = 'To‘lovlar yuklanmadi';
      });
    }
  }

  List<PaymentHistoryItem> _historyRows() {
    if (_data == null) {
      return const <PaymentHistoryItem>[];
    }
    return _buildPaymentHistoryItems(
      _data!,
      filter: _historyFilter,
    );
  }

  Future<ParentReminderSettingsModel?> _readReminderSettingsFor(
    ParentPaymentsModel data,
  ) async {
    final raw = await context.read<StorageService>().readParentReminderSettings();
    if (raw == null || raw.trim().isEmpty) {
      return null;
    }
    try {
      final model = ParentReminderSettingsModel.fromJson(
        jsonDecode(raw) as Map<String, dynamic>,
      );
      final currentSlug = await _currentCenterSlug(data);
      if (
          !model.matchesChild(
            currentChildId: data.child.id,
            currentCenterSlug: currentSlug,
          )) {
        return null;
      }
      return model;
    } catch (_) {
      return null;
    }
  }

  Future<String> _currentCenterSlug(ParentPaymentsModel data) async {
    final slug = data.child.center?.slug.trim() ?? '';
    if (slug.isNotEmpty) {
      return slug;
    }
    return (await context.read<StorageService>().readSlug())?.trim() ?? '';
  }

  Future<void> _saveReminderSettings(
    ParentReminderSettingsModel? settings,
  ) async {
    final storage = context.read<StorageService>();
    if (settings == null) {
      await storage.saveParentReminderSettings('');
      return;
    }
    await storage.saveParentReminderSettings(jsonEncode(settings.toJson()));
  }

  Future<void> _showReminderSheet() async {
    final summary = _data?.summary;
    final childName = _data?.child.fullName.trim().isNotEmpty == true
        ? _data!.child.fullName
        : 'farzandingiz';
    final dueDate = summary?.nextPaymentDate;
    if (dueDate == null) {
      _showMessage('Keyingi to‘lov sanasi hali belgilanmagan');
      return;
    }

    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (sheetContext) {
        return _PaymentBottomSheet(
          title: 'To‘lov eslatmasi',
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (_reminderSettings != null) ...[
                _CurrentReminderCard(
                  settings: _reminderSettings!,
                  onClear: () async {
                    Navigator.of(sheetContext).pop();
                    await _clearScheduledReminder(showMessage: true);
                  },
                ),
                const SizedBox(height: 12),
              ],
              _ReminderOptionTile(
                icon: Icons.event_outlined,
                iconBackground: const Color(0xFFEAF4FF),
                title: '1 kun oldin',
                subtitle: 'To‘lov sanasidan bir kun avval bildirishnoma oling',
                onTap: () async {
                  Navigator.of(sheetContext).pop();
                  await _scheduleReminderAt(
                    _normalizedReminderTime(dueDate.subtract(const Duration(days: 1))),
                    title: '1 kun oldin',
                    childName: childName,
                  );
                },
              ),
              _ReminderOptionTile(
                icon: Icons.calendar_view_week_outlined,
                iconBackground: const Color(0xFFF2EEFF),
                title: '3 kun oldin',
                subtitle: 'To‘lov sanasidan uch kun avval eslatma yuboriladi',
                onTap: () async {
                  Navigator.of(sheetContext).pop();
                  await _scheduleReminderAt(
                    _normalizedReminderTime(dueDate.subtract(const Duration(days: 3))),
                    title: '3 kun oldin',
                    childName: childName,
                  );
                },
              ),
              _ReminderOptionTile(
                icon: Icons.upcoming_outlined,
                iconBackground: const Color(0xFFFFF4DA),
                title: '7 kun oldin',
                subtitle: 'Bir hafta oldin tayyor turishingiz uchun eslatadi',
                onTap: () async {
                  Navigator.of(sheetContext).pop();
                  await _scheduleReminderAt(
                    _normalizedReminderTime(dueDate.subtract(const Duration(days: 7))),
                    title: '7 kun oldin',
                    childName: childName,
                  );
                },
              ),
              _ReminderOptionTile(
                icon: Icons.notifications_active_outlined,
                iconBackground: const Color(0xFFEAFBF2),
                title: 'To‘lov kuni',
                subtitle: 'To‘lov kuni ertalab eslatma yuboriladi',
                onTap: () async {
                  Navigator.of(sheetContext).pop();
                  await _scheduleReminderAt(
                    _normalizedReminderTime(dueDate),
                    title: 'To‘lov kuni',
                    childName: childName,
                  );
                },
              ),
              _ReminderOptionTile(
                icon: Icons.schedule_outlined,
                iconBackground: const Color(0xFFF8ECFF),
                title: 'Maxsus sana va vaqt',
                subtitle: 'O‘zingiz istagan kun va soatni tanlang',
                onTap: () async {
                  Navigator.of(sheetContext).pop();
                  await _pickCustomReminder(childName);
                },
              ),
            ],
          ),
        );
      },
    );
  }

  DateTime _normalizedReminderTime(DateTime source) {
    return DateTime(source.year, source.month, source.day, 9);
  }

  Future<void> _pickCustomReminder(String childName) async {
    final now = DateTime.now();
    final pickedDate = await showDatePicker(
      context: context,
      initialDate: now,
      firstDate: DateTime(now.year - 1),
      lastDate: DateTime(now.year + 3),
      helpText: 'Eslatma sanasi',
      cancelText: 'Bekor qilish',
      confirmText: 'Tanlash',
    );
    if (!mounted || pickedDate == null) {
      return;
    }
    final pickedTime = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(now.add(const Duration(hours: 1))),
      helpText: 'Eslatma vaqti',
      cancelText: 'Bekor qilish',
      confirmText: 'Tanlash',
    );
    if (!mounted || pickedTime == null) {
      return;
    }
    final scheduled = DateTime(
      pickedDate.year,
      pickedDate.month,
      pickedDate.day,
      pickedTime.hour,
      pickedTime.minute,
    );
    await _scheduleReminderAt(
      scheduled,
      title: 'Maxsus eslatma',
      childName: childName,
    );
  }

  Future<void> _scheduleReminderAt(
    DateTime scheduledAt, {
    required String title,
    required String childName,
  }) async {
    try {
      final outstanding = _data?.summary.outstandingTotal ?? 0;
      final notificationId = await context
          .read<LocalNotificationService>()
          .schedulePaymentReminder(
        scheduledAt: scheduledAt,
        title: 'To‘lov eslatmasi',
        body:
            '$childName uchun ${outstanding > 0 ? _uzs(outstanding) : 'to‘lov'} bo‘yicha $title eslatmasi',
      );
      final data = _data;
      if (data != null) {
        final previous = _reminderSettings;
        final settings = ParentReminderSettingsModel(
          childId: data.child.id,
          centerSlug: await _currentCenterSlug(data),
          label: title,
          scheduledAt: scheduledAt,
          notificationId: notificationId,
          note: childName,
        );
        await _saveReminderSettings(settings);
        if (previous?.notificationId != null &&
            previous!.notificationId != notificationId) {
          await context.read<LocalNotificationService>().cancel(
            previous.notificationId!,
          );
        }
        if (mounted) {
          setState(() => _reminderSettings = settings);
        }
      }
      if (!mounted) {
        return;
      }
      _showMessage('Eslatma muvaffaqiyatli o‘rnatildi');
    } on LocalNotificationException catch (error) {
      if (!mounted) {
        return;
      }
      _showMessage(error.message);
    }
  }

  Future<void> _clearScheduledReminder({required bool showMessage}) async {
    final reminder = _reminderSettings;
    if (reminder?.notificationId != null) {
      await context.read<LocalNotificationService>().cancel(
        reminder!.notificationId!,
      );
    }
    await _saveReminderSettings(null);
    if (!mounted) {
      return;
    }
    setState(() => _reminderSettings = null);
    if (showMessage) {
      _showMessage('Eslatma bekor qilindi');
    }
  }

  Future<void> _showFilterMenu() async {
    final selected = await showModalBottomSheet<PaymentHistoryFilter>(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) {
        return _PaymentBottomSheet(
          title: 'Filtr',
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (final filter in PaymentHistoryFilter.values)
                _FilterOptionTile(
                  label: filter.label,
                  selected: filter == _historyFilter,
                  onTap: () => Navigator.of(sheetContext).pop(filter),
                ),
            ],
          ),
        );
      },
    );
    if (!mounted || selected == null) {
      return;
    }
    setState(() => _historyFilter = selected);
  }

  void _openNotifications() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => const Scaffold(
          backgroundColor: Color(0xFFF7FBFF),
          body: SafeArea(child: NotificationsScreen()),
        ),
      ),
    );
  }

  Future<void> _openPaymentFlow() async {
    final data = _data;
    if (data == null) {
      return;
    }
    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (sheetContext) => _PaymentContactSheet(
        data: data,
        onCallTap: () => _callCenter(data.centerContactPhone),
        onCopyTap: () => _copyCenterContact(data.centerContactPhone),
      ),
    );
  }

  Future<void> _openHistoryModal(ParentPaymentSummaryModel summary) async {
    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (sheetContext) => _PaymentBottomSheet(
        title: 'To‘lov tarixi',
        child: PaymentHistoryCard(
          items: _historyRows(),
          selectedFilter: _historyFilter,
          onFilterTap: () async {
            Navigator.of(sheetContext).pop();
            await _showFilterMenu();
            if (mounted) {
              await _openHistoryModal(summary);
            }
          },
          onItemTap: (item) {
            Navigator.of(sheetContext).pop();
            if (item.historySource != null) {
              _openHistoryItemDetails(item.historySource!);
              return;
            }
            if (item.planSource != null) {
              _openPlanItemDetails(item.planSource!);
            }
          },
        ),
      ),
    );
  }

  void _openHistoryItemDetails(ParentPaymentHistoryModel item) {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (_) => _PaymentEntryDetailsSheet(
        title: item.title.isNotEmpty ? item.title : 'To‘lov tafsiloti',
        status: _paymentStatusFor(item.status),
        primaryAmount: _uzs(item.amount),
        date: Formatters.date(item.date),
        course: item.groupName.trim().isNotEmpty
            ? item.groupName.trim()
            : 'Kurs ko‘rsatilmagan',
        paymentType: item.paymentType.trim().isNotEmpty
            ? item.paymentType.trim()
            : 'To‘lov turi ko‘rsatilmagan',
        note: item.note.trim().isNotEmpty
            ? item.note.trim()
            : 'Qo‘shimcha izoh mavjud emas',
      ),
    );
  }

  void _openPlanItemDetails(ParentPaymentPlanItemModel item) {
    final status = _paymentStatusFor(item.status);
    final amount = switch (status) {
      PaymentStatus.paid => item.paidAmount,
      PaymentStatus.pending => item.plannedAmount,
      PaymentStatus.unpaid => item.remainingAmount,
    };
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (_) => _PaymentEntryDetailsSheet(
        title: item.title.isNotEmpty ? item.title : 'To‘lov rejasi',
        status: status,
        primaryAmount: _uzs(amount),
        date: Formatters.date(item.dueDate ?? item.month),
        course: item.groupName.trim().isNotEmpty
            ? item.groupName.trim()
            : 'Kurs ko‘rsatilmagan',
        paymentType: item.monthLabel.trim().isNotEmpty
            ? item.monthLabel.trim()
            : 'Davr ko‘rsatilmagan',
        note: item.statusLabel.trim().isNotEmpty
            ? item.statusLabel.trim()
            : 'Qo‘shimcha izoh mavjud emas',
        plannedAmount: _uzs(item.plannedAmount),
        paidAmount: _uzs(item.paidAmount),
        remainingAmount: _uzs(item.remainingAmount),
      ),
    );
  }

  Future<void> _callCenter(String phone) async {
    final trimmed = phone.trim();
    if (trimmed.isEmpty) {
      _showMessage('Markaz telefoni kiritilmagan');
      return;
    }
    final uri = Uri(scheme: 'tel', path: trimmed);
    final launched = await launchUrl(uri);
    if (launched) {
      return;
    }
    await _copyCenterContact(trimmed, showMessage: false);
    if (!mounted) {
      return;
    }
    _showMessage('Qo‘ng‘iroq ochilmadi, telefon raqami nusxalandi');
  }

  Future<void> _copyCenterContact(
    String phone, {
    bool showMessage = true,
  }) async {
    final trimmed = phone.trim();
    if (trimmed.isEmpty) {
      _showMessage('Markaz telefoni kiritilmagan');
      return;
    }
    await Clipboard.setData(ClipboardData(text: trimmed));
    if (showMessage && mounted) {
      _showMessage('Markaz telefoni nusxalandi');
    }
  }

  void _showMessage(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        behavior: SnackBarBehavior.floating,
        margin: const EdgeInsets.fromLTRB(16, 12, 16, 16),
        content: Text(message),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final fallbackChild = context
        .watch<ParentDashboardProvider>()
        .data
        ?.selectedChild;
    final child = _data?.child ?? fallbackChild;
    final summary =
        _data?.summary ??
        const ParentPaymentSummaryModel(
          totalPlan: 0,
          totalBalance: 0,
          paidTotal: 0,
          debtAmount: 0,
        );

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.dark,
        statusBarBrightness: Brightness.light,
        systemNavigationBarColor: Colors.white,
        systemNavigationBarIconBrightness: Brightness.dark,
      ),
      child: Scaffold(
        backgroundColor: PaymentColors.background,
        bottomNavigationBar: widget.showBottomNav
            ? const ParentBottomNav()
            : null,
        body: SafeArea(
          child: RefreshIndicator(
            color: PaymentColors.primaryBlue,
            onRefresh: () => _load(force: true),
            child: SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(
                parent: BouncingScrollPhysics(),
              ),
              padding: ParentUi.screenPadding,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  PaymentsHeader(
                    child: child,
                    onNotificationsTap: _openNotifications,
                  ),
                  const SizedBox(height: 12),
                  if (_state == ViewState.loading && _data == null)
                    const _PaymentStateCard.loading()
                  else if (_state == ViewState.error && _data == null)
                    _PaymentStateCard(
                      title: 'To‘lovlar yuklanmadi',
                      message: _errorMessage ?? 'Qayta urinib ko‘ring',
                      onPressed: () => _load(force: true),
                    )
                  else ...[
                    if (_state == ViewState.loading) ...[
                      const LinearProgressIndicator(
                        minHeight: 3,
                        color: PaymentColors.primaryBlue,
                        backgroundColor: Color(0xFFEAF4FF),
                      ),
                      const SizedBox(height: 8),
                    ],
                    _PayDueHero(
                      summary: summary,
                      onPay: _openPaymentFlow,
                    ),
                    const SizedBox(height: 10),
                    _ReminderInline(
                      reminderSettings: _reminderSettings,
                      hasDueDate: summary.nextPaymentDate != null,
                      onTap: _showReminderSheet,
                    ),
                    const SizedBox(height: 10),
                    _BalanceCard(summary: summary),
                    const SizedBox(height: 10),
                    _MonthsListCard(
                      planItems: _data?.planItems ?? const [],
                      onItemTap: _openPlanItemDetails,
                    ),
                    const SizedBox(height: 10),
                    _HistoryButton(
                      onTap: () => _openHistoryModal(summary),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class PaymentsHeader extends StatelessWidget {
  const PaymentsHeader({
    super.key,
    this.child,
    required this.onNotificationsTap,
  });

  final ParentChildModel? child;
  final VoidCallback onNotificationsTap;

  @override
  Widget build(BuildContext context) {
    final childLine = child == null
        ? 'Farzand tanlanmoqda'
        : _childGroupLine(child!);
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 6,
                ),
                decoration: BoxDecoration(
                  color: PaymentColors.primaryBlueSoft,
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  'Ota-ona paneli',
                  style: PaymentTextStyles.label.copyWith(
                    fontSize: 11.2,
                    color: PaymentColors.primaryBlue,
                  ),
                ),
              ),
              const SizedBox(height: 8),
              FittedBox(
                fit: BoxFit.scaleDown,
                alignment: Alignment.centerLeft,
                child: Text(
                  'To‘lovlar',
                  maxLines: 1,
                  style: PaymentTextStyles.title.copyWith(fontSize: 21),
                ),
              ),
              const SizedBox(height: 4),
              Text(
                childLine,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: PaymentTextStyles.body.copyWith(
                  color: PaymentColors.secondaryText,
                  fontSize: 12.8,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(width: 8),
        _NotificationButton(onTap: onNotificationsTap),
      ],
    );
  }
}

class _PayDueHero extends StatelessWidget {
  const _PayDueHero({required this.summary, required this.onPay});

  final ParentPaymentSummaryModel summary;
  final VoidCallback onPay;

  String _monthLabel(DateTime? value) {
    if (value == null) return '';
    return Formatters.month(value).split(' ').first;
  }

  @override
  Widget build(BuildContext context) {
    final hasDebt = summary.debtAmount > 0;
    final dueDate = summary.nextPaymentDate;
    final dueLabel = _monthLabel(dueDate);
    final monthLabel = dueLabel.isNotEmpty
        ? dueLabel
        : _monthLabel(DateTime.now());
    final subtitle = monthLabel.isEmpty
        ? 'Joriy oy uchun'
        : '$monthLabel oyi uchun';
    final deadlineLine = dueDate == null
        ? null
        : 'Muddat: ${Formatters.shortDayMonth(dueDate)} • ${_daysUntil(dueDate)}';

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 18),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(ParentUi.sheetRadius),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: hasDebt
              ? const [Color(0xFF173B78), Color(0xFF2B4C88)]
              : const [Color(0xFF0F8A55), Color(0xFF12A66A)],
        ),
        boxShadow: const [
          BoxShadow(
            color: Color(0x22173B78),
            blurRadius: 24,
            offset: Offset(0, 12),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'To‘lash kerak',
            style: PaymentTextStyles.label.copyWith(
              color: Colors.white.withValues(alpha: 0.85),
              fontSize: 12,
              letterSpacing: 0.4,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            hasDebt ? _uzs(summary.debtAmount) : 'Qarzdorlik yo‘q',
            style: PaymentTextStyles.title.copyWith(
              color: Colors.white,
              fontSize: 26,
              height: 1.1,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            subtitle,
            style: PaymentTextStyles.body.copyWith(
              color: Colors.white.withValues(alpha: 0.82),
              fontSize: 13,
            ),
          ),
          if (deadlineLine != null) ...[
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.symmetric(
                horizontal: 10,
                vertical: 6,
              ),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.14),
                borderRadius: BorderRadius.circular(999),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(
                    Icons.event_outlined,
                    color: Colors.white,
                    size: 14,
                  ),
                  const SizedBox(width: 6),
                  Text(
                    deadlineLine,
                    style: PaymentTextStyles.body.copyWith(
                      color: Colors.white,
                      fontSize: 12.5,
                    ),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            height: 46,
            child: FilledButton.icon(
              onPressed: onPay,
              style: FilledButton.styleFrom(
                backgroundColor: Colors.white,
                foregroundColor: hasDebt
                    ? PaymentColors.primaryBlue
                    : PaymentColors.green,
                elevation: 0,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14),
                ),
              ),
              icon: const Icon(Icons.credit_card_rounded, size: 18),
              label: Text(
                'To‘lov qilish',
                style: PaymentTextStyles.link.copyWith(
                  fontSize: 14.5,
                  color: hasDebt
                      ? PaymentColors.primaryBlue
                      : PaymentColors.green,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ReminderInline extends StatelessWidget {
  const _ReminderInline({
    required this.reminderSettings,
    required this.hasDueDate,
    required this.onTap,
  });

  final ParentReminderSettingsModel? reminderSettings;
  final bool hasDueDate;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    if (!hasDueDate) {
      return const SizedBox.shrink();
    }
    final reminder = reminderSettings;
    final label = reminder == null
        ? 'Eslatma o‘rnatish'
        : 'Eslatma: ${Formatters.dateTime(reminder.scheduledAt)}';
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 6),
          child: Row(
            children: [
              Icon(
                reminder == null
                    ? Icons.alarm_add_rounded
                    : Icons.notifications_active_outlined,
                size: 16,
                color: PaymentColors.primaryBlue,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: PaymentTextStyles.body.copyWith(
                    color: PaymentColors.primaryBlue,
                    fontSize: 12.5,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              const Icon(
                Icons.chevron_right_rounded,
                size: 16,
                color: PaymentColors.primaryBlue,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _BalanceCard extends StatelessWidget {
  const _BalanceCard({required this.summary});

  final ParentPaymentSummaryModel summary;

  @override
  Widget build(BuildContext context) {
    return PaymentCard(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              value: summary.paidRatio,
              minHeight: 8,
              backgroundColor: const Color(0xFFEFF2F6),
              valueColor: const AlwaysStoppedAnimation<Color>(
                PaymentColors.green,
              ),
            ),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: _BalanceLine(
                  label: 'To‘langan',
                  value: _uzs(summary.paidTotal),
                  valueColor: PaymentColors.green,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _BalanceLine(
                  label: 'Qolgan',
                  value: _uzs(summary.debtAmount),
                  valueColor: summary.debtAmount > 0
                      ? PaymentColors.red
                      : PaymentColors.text,
                  alignEnd: true,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _BalanceLine extends StatelessWidget {
  const _BalanceLine({
    required this.label,
    required this.value,
    required this.valueColor,
    this.alignEnd = false,
  });

  final String label;
  final String value;
  final Color valueColor;
  final bool alignEnd;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: alignEnd
          ? CrossAxisAlignment.end
          : CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: PaymentTextStyles.body.copyWith(
            color: PaymentColors.secondaryText,
            fontSize: 12,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: PaymentTextStyles.title.copyWith(
            color: valueColor,
            fontSize: 15,
          ),
        ),
      ],
    );
  }
}

class _MonthsListCard extends StatelessWidget {
  const _MonthsListCard({required this.planItems, required this.onItemTap});

  final List<ParentPaymentPlanItemModel> planItems;
  final ValueChanged<ParentPaymentPlanItemModel> onItemTap;

  @override
  Widget build(BuildContext context) {
    return PaymentCard(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'To‘lov rejasi',
            style: PaymentTextStyles.title.copyWith(fontSize: 15),
          ),
          const SizedBox(height: 10),
          if (planItems.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Text(
                'To‘lov rejasi mavjud emas.',
                style: PaymentTextStyles.body.copyWith(
                  color: PaymentColors.secondaryText,
                  fontSize: 12.5,
                ),
              ),
            )
          else
            for (var i = 0; i < planItems.length; i++)
              Padding(
                padding: EdgeInsets.only(
                  bottom: i == planItems.length - 1 ? 0 : 8,
                ),
                child: _PlanPreviewTile(
                  item: planItems[i],
                  onTap: () => onItemTap(planItems[i]),
                ),
              ),
        ],
      ),
    );
  }
}

class _HistoryButton extends StatelessWidget {
  const _HistoryButton({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: 44,
      child: OutlinedButton.icon(
        onPressed: onTap,
        style: OutlinedButton.styleFrom(
          foregroundColor: PaymentColors.primaryBlue,
          side: const BorderSide(color: PaymentColors.border),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
        icon: const Icon(Icons.history_rounded, size: 18),
        label: Text(
          'To‘lov tarixini ko‘rish',
          style: PaymentTextStyles.link.copyWith(fontSize: 13.5),
        ),
      ),
    );
  }
}

class PaymentHistoryCard extends StatelessWidget {
  const PaymentHistoryCard({
    super.key,
    required this.items,
    required this.selectedFilter,
    required this.onFilterTap,
    required this.onItemTap,
  });

  final List<PaymentHistoryItem> items;
  final PaymentHistoryFilter selectedFilter;
  final VoidCallback onFilterTap;
  final ValueChanged<PaymentHistoryItem> onItemTap;

  @override
  Widget build(BuildContext context) {
    final rows = items;
    return PaymentCard(
      padding: EdgeInsets.zero,
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 10),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    'To‘lov tarixi',
                    style: PaymentTextStyles.title.copyWith(fontSize: 17),
                  ),
                ),
                _HistoryFilterButton(
                  label: selectedFilter.label,
                  onTap: onFilterTap,
                ),
              ],
            ),
          ),
          if (rows.isEmpty)
            const Padding(
              padding: EdgeInsets.fromLTRB(16, 4, 16, 20),
              child: _PaymentHistoryEmptyState(),
            )
          else
            for (int index = 0; index < rows.length; index++)
              PaymentHistoryRow(
                item: rows[index],
                showDivider: index != rows.length - 1,
                onTap: () => onItemTap(rows[index]),
              ),
          const SizedBox(height: 10),
        ],
      ),
    );
  }
}

class PaymentHistoryRow extends StatelessWidget {
  const PaymentHistoryRow({
    super.key,
    required this.item,
    required this.showDivider,
    this.onTap,
  });

  final PaymentHistoryItem item;
  final bool showDivider;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final compact = constraints.maxWidth < 330;
        final sidePadding = compact ? 12.0 : 16.0;
        final statusSize = compact ? 38.0 : 42.0;
        final rightMaxWidth = compact ? 104.0 : 124.0;

        return Column(
          children: [
            Material(
              color: Colors.transparent,
              child: InkWell(
                onTap: onTap,
                child: Padding(
                  padding: EdgeInsets.fromLTRB(sidePadding, 12, sidePadding, 12),
                  child: Row(
                    children: [
                      _PaymentStatusIcon(status: item.status, size: statusSize),
                      SizedBox(width: compact ? 10 : 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              item.title,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: PaymentTextStyles.title.copyWith(
                                fontSize: compact ? 13.4 : 14.6,
                              ),
                            ),
                            const SizedBox(height: 5),
                            Text(
                              item.subtitle.isEmpty
                                  ? item.date
                                  : '${item.subtitle} • ${item.date}',
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: PaymentTextStyles.body.copyWith(
                                color: PaymentColors.secondaryText,
                                fontSize: compact ? 12 : 12.8,
                              ),
                            ),
                          ],
                        ),
                      ),
                      SizedBox(width: compact ? 5 : 8),
                      ConstrainedBox(
                        constraints: BoxConstraints(maxWidth: rightMaxWidth),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            FittedBox(
                              fit: BoxFit.scaleDown,
                              alignment: Alignment.centerRight,
                              child: Text(
                                item.amount,
                                maxLines: 1,
                                style: PaymentTextStyles.title.copyWith(
                                  color: item.status.amountColor,
                                  fontSize: compact ? 12.6 : 13.8,
                                ),
                              ),
                            ),
                            const SizedBox(height: 5),
                            StatusPill(status: item.status, compact: compact),
                          ],
                        ),
                      ),
                      SizedBox(width: compact ? 4 : 8),
                      Icon(
                        Icons.chevron_right_rounded,
                        color: const Color(0xFF9AA4B2),
                        size: compact ? 18 : 20,
                      ),
                    ],
                  ),
                ),
              ),
            ),
            if (showDivider)
              Padding(
                padding: EdgeInsets.only(
                  left: compact ? 62 : 72,
                  right: sidePadding,
                ),
                child: const Divider(height: 1, color: PaymentColors.border),
              ),
          ],
        );
      },
    );
  }
}

class StatusPill extends StatelessWidget {
  const StatusPill({super.key, required this.status, this.compact = false});

  final PaymentStatus status;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: compact ? 8 : 11,
        vertical: compact ? 5 : 6,
      ),
      decoration: BoxDecoration(
        color: status.pillBackground,
        borderRadius: BorderRadius.circular(13),
      ),
      child: Text(
        status.label,
        maxLines: 1,
        style: PaymentTextStyles.body.copyWith(
          color: status.pillText,
          fontSize: compact ? 11 : 11.8,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class ParentBottomNav extends StatelessWidget {
  const ParentBottomNav({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        boxShadow: PaymentShadows.topNav,
      ),
      child: SafeArea(
        top: false,
        child: ClipRRect(
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
          child: BottomNavigationBar(
            currentIndex: 2,
            onTap: (_) {},
            type: BottomNavigationBarType.fixed,
            backgroundColor: Colors.white,
            elevation: 0,
            iconSize: 24,
            selectedItemColor: PaymentColors.primaryBlue,
            unselectedItemColor: PaymentColors.secondaryText,
            selectedLabelStyle: PaymentTextStyles.label.copyWith(
              fontSize: 11,
            ),
            unselectedLabelStyle: PaymentTextStyles.label.copyWith(
              fontSize: 11,
              fontWeight: FontWeight.w600,
            ),
            items: const [
              BottomNavigationBarItem(
                icon: Icon(Icons.home_rounded),
                label: 'Bosh sahifa',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.event_available_outlined),
                label: 'Davomat',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.account_balance_wallet_outlined),
                label: 'To‘lovlar',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.bar_chart_rounded),
                label: 'Progress',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.person_rounded),
                label: 'Profil',
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class PaymentCard extends StatelessWidget {
  const PaymentCard({super.key, required this.child, required this.padding});

  final Widget child;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(ParentUi.cardRadius),
        border: Border.all(color: PaymentColors.border),
        boxShadow: PaymentShadows.card,
      ),
      child: child,
    );
  }
}

class _NotificationButton extends StatelessWidget {
  const _NotificationButton({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final notifications = context.watch<NotificationsProvider>();
    final fallbackUnreadCount =
        context.watch<ParentDashboardProvider>().data?.unreadNotifications ?? 0;
    final unreadCount = ParentUi.resolveUnreadCount(
      notifications: notifications,
      fallback: fallbackUnreadCount,
    );
    return Stack(
      clipBehavior: Clip.none,
      children: [
        InkWell(
          onTap: onTap,
          customBorder: const CircleBorder(),
          child: Container(
            width: ParentUi.iconButtonSize,
            height: ParentUi.iconButtonSize,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: Colors.white,
              shape: BoxShape.circle,
              border: Border.all(color: PaymentColors.border),
              boxShadow: PaymentShadows.soft,
            ),
            child: const Icon(
              Icons.notifications_none_rounded,
              color: PaymentColors.text,
              size: 22,
            ),
          ),
        ),
        if (unreadCount > 0)
          Positioned(
            right: 4,
            top: 2,
            child: Container(
              constraints: const BoxConstraints(minWidth: 18),
              height: 18,
              alignment: Alignment.center,
              padding: const EdgeInsets.symmetric(horizontal: 4),
              decoration: BoxDecoration(
                color: PaymentColors.red,
                borderRadius: BorderRadius.circular(999),
                border: Border.all(color: Colors.white, width: 2),
              ),
              child: Text(
                unreadCount > 99 ? '99+' : '$unreadCount',
                style: PaymentTextStyles.label.copyWith(
                  color: Colors.white,
                  fontSize: 9,
                  height: 1,
                ),
              ),
            ),
          ),
      ],
    );
  }
}

class _HistoryFilterButton extends StatelessWidget {
  const _HistoryFilterButton({
    required this.label,
    required this.onTap,
  });

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return TextButton(
      onPressed: onTap,
      style: TextButton.styleFrom(
        backgroundColor: const Color(0xFFF4F6FA),
        foregroundColor: PaymentColors.secondaryText,
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(ParentUi.softRadius),
        ),
        minimumSize: const Size(0, 38),
        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.filter_list_rounded, size: 18),
          const SizedBox(width: 6),
          Text(
            label,
            style: PaymentTextStyles.body.copyWith(
              color: PaymentColors.text,
              fontSize: 12.2,
            ),
          ),
          const SizedBox(width: 2),
          const Icon(Icons.keyboard_arrow_down_rounded, size: 17),
        ],
      ),
    );
  }
}

class _PlanPreviewTile extends StatelessWidget {
  const _PlanPreviewTile({required this.item, this.onTap});

  final ParentPaymentPlanItemModel item;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final status = _paymentStatusFor(item.status);
    final trailingAmount = status == PaymentStatus.paid
        ? item.paidAmount
        : status == PaymentStatus.pending
        ? item.plannedAmount
        : item.remainingAmount;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
          decoration: BoxDecoration(
            color: const Color(0xFFF8FAFD),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Row(
            children: [
              _PaymentStatusIcon(status: status, size: 38),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      item.title.isNotEmpty ? item.title : 'To‘lov rejasi',
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: PaymentTextStyles.title.copyWith(fontSize: 13.8),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      [
                        if (item.groupName.isNotEmpty) item.groupName,
                        if (item.monthLabel.isNotEmpty) item.monthLabel,
                      ].join(' • '),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: PaymentTextStyles.body.copyWith(
                        color: PaymentColors.secondaryText,
                        fontSize: 12.2,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    _uzs(trailingAmount),
                    style: PaymentTextStyles.title.copyWith(
                      color: status.amountColor,
                      fontSize: 13.2,
                    ),
                  ),
                  const SizedBox(height: 4),
                  StatusPill(status: status, compact: true),
                ],
              ),
              const SizedBox(width: 6),
              const Icon(
                Icons.chevron_right_rounded,
                color: Color(0xFF9AA4B2),
                size: 18,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PaymentBottomSheet extends StatelessWidget {
  const _PaymentBottomSheet({
    required this.title,
    required this.child,
  });

  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Container(
        margin: const EdgeInsets.all(12),
        padding: const EdgeInsets.fromLTRB(18, 12, 18, 18),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(24),
          boxShadow: PaymentShadows.card,
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 44,
                  height: 5,
                  margin: const EdgeInsets.only(bottom: 16),
                  decoration: BoxDecoration(
                    color: const Color(0xFFD8E0EC),
                    borderRadius: BorderRadius.circular(999),
                  ),
                ),
              ),
              Text(
                title,
                style: PaymentTextStyles.title.copyWith(fontSize: 18),
              ),
              const SizedBox(height: 14),
              child,
            ],
          ),
        ),
      ),
    );
  }
}

class _ReminderOptionTile extends StatelessWidget {
  const _ReminderOptionTile({
    required this.icon,
    required this.iconBackground,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final IconData icon;
  final Color iconBackground;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: onTap,
      child: Container(
        width: double.infinity,
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        decoration: BoxDecoration(
          color: const Color(0xFFF8FAFD),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: PaymentColors.border),
        ),
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: iconBackground,
                shape: BoxShape.circle,
              ),
              child: Icon(
                icon,
                color: PaymentColors.primaryBlue,
                size: 21,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: PaymentTextStyles.title.copyWith(fontSize: 15.2),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    subtitle,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: PaymentTextStyles.body.copyWith(
                      color: PaymentColors.secondaryText,
                      fontSize: 12.8,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            const Icon(
              Icons.chevron_right_rounded,
              color: Color(0xFF9AA4B2),
            ),
          ],
        ),
      ),
    );
  }
}

class _FilterOptionTile extends StatelessWidget {
  const _FilterOptionTile({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: onTap,
      child: Container(
        width: double.infinity,
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        decoration: BoxDecoration(
          color: selected ? const Color(0xFFEAF4FF) : Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: selected
                ? PaymentColors.primaryBlue
                : PaymentColors.border,
          ),
        ),
        child: Row(
          children: [
            Expanded(
              child: Text(
                label,
                style: PaymentTextStyles.body.copyWith(
                  color: PaymentColors.text,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
            Icon(
              selected
                  ? Icons.check_circle_rounded
                  : Icons.chevron_right_rounded,
              color: selected
                  ? PaymentColors.primaryBlue
                  : const Color(0xFF9AA4B2),
            ),
          ],
        ),
      ),
    );
  }
}

class _PaymentContactSheet extends StatelessWidget {
  const _PaymentContactSheet({
    required this.data,
    required this.onCallTap,
    required this.onCopyTap,
  });

  final ParentPaymentsModel data;
  final VoidCallback onCallTap;
  final VoidCallback onCopyTap;

  @override
  Widget build(BuildContext context) {
    final contact = data.centerContactPhone.trim().isNotEmpty
        ? data.centerContactPhone
        : 'Telefon kiritilmagan';
    return _PaymentBottomSheet(
      title: 'To‘lov qilish',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 16),
            decoration: BoxDecoration(
              color: const Color(0xFFF8FAFD),
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: PaymentColors.border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Markaz bilan bog‘lanib to‘lov qiling',
                  style: PaymentTextStyles.title.copyWith(fontSize: 16),
                ),
                const SizedBox(height: 8),
                Text(
                  'Hozircha to‘lov markaz bilan bog‘lanish orqali amalga oshiriladi. Telefon raqamidan tez qo‘ng‘iroq qiling yoki uni nusxalang.',
                  style: PaymentTextStyles.body.copyWith(
                    color: PaymentColors.secondaryText,
                    fontSize: 13.5,
                  ),
                ),
                const SizedBox(height: 14),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Joriy qarzdorlik',
                      style: PaymentTextStyles.body.copyWith(
                        color: PaymentColors.secondaryText,
                        fontSize: 12.5,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      _uzs(data.summary.outstandingTotal),
                      style: PaymentTextStyles.title.copyWith(
                        color: PaymentColors.red,
                        fontSize: 15,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.fromLTRB(14, 14, 14, 14),
            decoration: BoxDecoration(
              color: const Color(0xFFEAF4FF),
              borderRadius: BorderRadius.circular(18),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  data.centerContactName.isNotEmpty
                      ? data.centerContactName
                      : 'O‘quv markazi',
                  style: PaymentTextStyles.title.copyWith(fontSize: 15),
                ),
                const SizedBox(height: 6),
                Text(
                  contact,
                  style: PaymentTextStyles.body.copyWith(
                    color: PaymentColors.secondaryText,
                    fontSize: 13.5,
                  ),
                ),
                if ((data.child.center?.address ?? '').trim().isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text(
                    data.child.center!.address.trim(),
                    style: PaymentTextStyles.body.copyWith(
                      color: PaymentColors.secondaryText,
                      fontSize: 12.8,
                    ),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: onCopyTap,
                  style: OutlinedButton.styleFrom(
                    foregroundColor: PaymentColors.primaryBlue,
                    side: const BorderSide(color: PaymentColors.border),
                    padding: const EdgeInsets.symmetric(vertical: 13),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                    ),
                  ),
                  icon: const Icon(Icons.copy_rounded, size: 18),
                  label: Text(
                    'Raqamni nusxalash',
                    style: PaymentTextStyles.link.copyWith(fontSize: 13.5),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: FilledButton.icon(
                  onPressed: data.centerContactPhone.trim().isEmpty
                      ? null
                      : onCallTap,
                  style: FilledButton.styleFrom(
                    backgroundColor: PaymentColors.primaryBlue,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 13),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                    ),
                  ),
                  icon: const Icon(Icons.call_rounded, size: 18),
                  label: Text(
                    'Qo‘ng‘iroq qilish',
                    style: PaymentTextStyles.link.copyWith(
                      fontSize: 13.5,
                      color: Colors.white,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _PaymentEntryDetailsSheet extends StatelessWidget {
  const _PaymentEntryDetailsSheet({
    required this.title,
    required this.status,
    required this.primaryAmount,
    required this.date,
    required this.course,
    required this.paymentType,
    required this.note,
    this.plannedAmount,
    this.paidAmount,
    this.remainingAmount,
  });

  final String title;
  final PaymentStatus status;
  final String primaryAmount;
  final String date;
  final String course;
  final String paymentType;
  final String note;
  final String? plannedAmount;
  final String? paidAmount;
  final String? remainingAmount;

  @override
  Widget build(BuildContext context) {
    return _PaymentBottomSheet(
      title: 'To‘lov tafsiloti',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.fromLTRB(14, 14, 14, 14),
            decoration: BoxDecoration(
              color: const Color(0xFFF8FAFD),
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: PaymentColors.border),
            ),
            child: Row(
              children: [
                _PaymentStatusIcon(status: status, size: 44),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: PaymentTextStyles.title.copyWith(fontSize: 16),
                      ),
                      const SizedBox(height: 6),
                      StatusPill(status: status, compact: true),
                    ],
                  ),
                ),
                Text(
                  primaryAmount,
                  style: PaymentTextStyles.title.copyWith(
                    color: status.amountColor,
                    fontSize: 18,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          _PaymentInfoTile(label: 'Sana', value: date),
          _PaymentInfoTile(label: 'Kurs yoki guruh', value: course),
          _PaymentInfoTile(label: 'To‘lov turi', value: paymentType),
          if (plannedAmount != null)
            _PaymentInfoTile(label: 'Rejalashtirilgan', value: plannedAmount!),
          if (paidAmount != null)
            _PaymentInfoTile(label: 'To‘langan', value: paidAmount!),
          if (remainingAmount != null)
            _PaymentInfoTile(label: 'Qoldiq', value: remainingAmount!),
          _PaymentInfoTile(label: 'Izoh', value: note, isLast: true),
        ],
      ),
    );
  }
}

class _CurrentReminderCard extends StatelessWidget {
  const _CurrentReminderCard({
    required this.settings,
    required this.onClear,
  });

  final ParentReminderSettingsModel settings;
  final VoidCallback onClear;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(14, 14, 14, 14),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFD),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: PaymentColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.notifications_active_outlined,
                color: PaymentColors.primaryBlue,
                size: 18,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Joriy eslatma: ${settings.label}',
                  style: PaymentTextStyles.title.copyWith(fontSize: 14.8),
                ),
              ),
              TextButton(
                onPressed: onClear,
                style: TextButton.styleFrom(
                  foregroundColor: PaymentColors.red,
                  padding: EdgeInsets.zero,
                  minimumSize: const Size(0, 28),
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
                child: Text(
                  'O‘chirish',
                  style: PaymentTextStyles.link.copyWith(
                    color: PaymentColors.red,
                    fontSize: 12.8,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            Formatters.dateTime(settings.scheduledAt),
            style: PaymentTextStyles.body.copyWith(
              color: PaymentColors.secondaryText,
              fontSize: 12.8,
            ),
          ),
        ],
      ),
    );
  }
}

class _PaymentInfoTile extends StatelessWidget {
  const _PaymentInfoTile({
    required this.label,
    required this.value,
    this.isLast = false,
  });

  final String label;
  final String value;
  final bool isLast;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: EdgeInsets.only(bottom: isLast ? 0 : 8),
      padding: const EdgeInsets.fromLTRB(14, 14, 14, 14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: PaymentColors.border),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Text(
              label,
              style: PaymentTextStyles.body.copyWith(
                color: PaymentColors.secondaryText,
                fontSize: 12.8,
              ),
            ),
          ),
          const SizedBox(width: 12),
          Flexible(
            child: Text(
              value,
              textAlign: TextAlign.right,
              style: PaymentTextStyles.title.copyWith(fontSize: 14.2),
            ),
          ),
        ],
      ),
    );
  }
}

class _PaymentHistoryEmptyState extends StatelessWidget {
  const _PaymentHistoryEmptyState();

  static const String title = 'To‘lov tarixi topilmadi';
  static const String message =
      'Hozircha tanlangan farzand uchun to‘lov harakati yoki kutilayotgan to‘lov topilmadi.';

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(18, 20, 18, 18),
      decoration: BoxDecoration(
        color: PaymentColors.emptySurface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: PaymentColors.border),
      ),
      child: Column(
        children: [
          Container(
            width: 54,
            height: 54,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(18),
            ),
            child: const Icon(
              Icons.receipt_long_rounded,
              color: PaymentColors.primaryBlue,
              size: 28,
            ),
          ),
          const SizedBox(height: 14),
          Text(
            title,
            textAlign: TextAlign.center,
            style: PaymentTextStyles.title.copyWith(fontSize: 17),
          ),
          const SizedBox(height: 8),
          Text(
            message,
            textAlign: TextAlign.center,
            style: PaymentTextStyles.body.copyWith(
              color: PaymentColors.secondaryText,
              fontSize: 13.5,
            ),
          ),
        ],
      ),
    );
  }
}

class _PaymentStatusIcon extends StatelessWidget {
  const _PaymentStatusIcon({required this.status, this.size = 54});

  final PaymentStatus status;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: status.iconBackground,
        shape: BoxShape.circle,
      ),
      child: Icon(status.icon, color: status.iconColor, size: size * 0.48),
    );
  }
}

class _PaymentStateCard extends StatelessWidget {
  const _PaymentStateCard({
    required this.title,
    required this.message,
    this.onPressed,
  }) : loading = false;

  const _PaymentStateCard.loading()
    : title = '',
      message = '',
      onPressed = null,
      loading = true;

  final String title;
  final String message;
  final VoidCallback? onPressed;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    return PaymentCard(
      padding: const EdgeInsets.fromLTRB(18, 36, 18, 36),
      child: loading
          ? const SizedBox(
              height: 220,
              child: Center(
                child: CircularProgressIndicator(
                  color: PaymentColors.primaryBlue,
                ),
              ),
            )
          : Column(
              children: [
                const Icon(
                  Icons.info_outline_rounded,
                  color: PaymentColors.primaryBlue,
                  size: 40,
                ),
                const SizedBox(height: 12),
                Text(
                  title,
                  textAlign: TextAlign.center,
                  style: PaymentTextStyles.title.copyWith(fontSize: 19),
                ),
                const SizedBox(height: 8),
                Text(
                  message,
                  textAlign: TextAlign.center,
                  style: PaymentTextStyles.body.copyWith(
                    color: PaymentColors.secondaryText,
                    fontSize: 14,
                  ),
                ),
                if (onPressed != null) ...[
                  const SizedBox(height: 16),
                  TextButton(
                    onPressed: onPressed,
                    style: TextButton.styleFrom(
                      backgroundColor: const Color(0xFFEAF4FF),
                      foregroundColor: PaymentColors.primaryBlue,
                    ),
                    child: const Text('Qayta urinish'),
                  ),
                ],
              ],
            ),
    );
  }
}

String _uzs(num value) => '${Formatters.number(value)} so‘m';

String _daysUntil(DateTime? date) {
  if (date == null) {
    return 'Sana belgilanmagan';
  }
  final today = DateTime.now();
  final current = DateTime(today.year, today.month, today.day);
  final target = DateTime(date.year, date.month, date.day);
  final days = target.difference(current).inDays;
  if (days == 0) {
    return 'Bugun';
  }
  if (days < 0) {
    return '${days.abs()} kun o‘tdi';
  }
  return '$days kun qoldi';
}

PaymentHistoryItem _historyItem(ParentPaymentHistoryModel item) {
  return PaymentHistoryItem(
    title: item.title,
    date: Formatters.date(item.date),
    amount: _uzs(item.amount),
    status: _paymentStatusFor(item.status),
    subtitle: item.groupName.isNotEmpty
        ? item.groupName
        : (item.paymentType.isNotEmpty ? item.paymentType : item.note),
    sortDate: item.date,
    historySource: item,
  );
}

PaymentHistoryItem _planHistoryItem(ParentPaymentPlanItemModel item) {
  final status = _paymentStatusFor(item.status);
  final amount = switch (status) {
    PaymentStatus.paid => item.paidAmount,
    PaymentStatus.pending => item.plannedAmount,
    PaymentStatus.unpaid => item.remainingAmount,
  };
  final subtitleParts = <String>[
    if (item.groupName.isNotEmpty) item.groupName,
    if (item.monthLabel.isNotEmpty) item.monthLabel,
  ];
  return PaymentHistoryItem(
    title: item.title.isNotEmpty ? item.title : 'To‘lov rejasi',
    date: Formatters.date(item.dueDate ?? item.month),
    amount: _uzs(amount),
    status: status,
    subtitle: subtitleParts.join(' • '),
    sortDate: item.dueDate ?? item.month,
    planSource: item,
  );
}

List<PaymentHistoryItem> _buildPaymentHistoryItems(
  ParentPaymentsModel data, {
  required PaymentHistoryFilter filter,
}) {
  final paidRows = data.history.map(_historyItem).toList(growable: false);
  final planRows = data.planItems.map(_planHistoryItem).toList(growable: false);

  List<PaymentHistoryItem> rows;
  switch (filter) {
    case PaymentHistoryFilter.all:
      rows = <PaymentHistoryItem>[
        ...paidRows,
        ...planRows.where((item) => item.status != PaymentStatus.paid),
      ];
      break;
    case PaymentHistoryFilter.paid:
      rows = paidRows.isNotEmpty
          ? paidRows
          : planRows.where((item) => item.status == PaymentStatus.paid).toList();
      break;
    case PaymentHistoryFilter.debt:
      rows = planRows.where((item) => item.status == PaymentStatus.unpaid).toList();
      break;
    case PaymentHistoryFilter.pending:
      rows = planRows.where((item) => item.status == PaymentStatus.pending).toList();
      break;
  }

  rows.sort((a, b) {
    final left = a.sortDate ?? DateTime.fromMillisecondsSinceEpoch(0);
    final right = b.sortDate ?? DateTime.fromMillisecondsSinceEpoch(0);
    return right.compareTo(left);
  });
  return rows;
}

PaymentStatus _paymentStatusFor(String status) {
  final normalized = status.toLowerCase();
  if (normalized.contains('pending') || normalized.contains('kutil')) {
    return PaymentStatus.pending;
  }
  if (normalized.contains('unpaid') ||
      normalized.contains('debt') ||
      normalized.contains('qarz')) {
    return PaymentStatus.unpaid;
  }
  return PaymentStatus.paid;
}

String _childGroupLine(ParentChildModel child) {
  final parts = <String>[
    if (child.fullName.trim().isNotEmpty) child.fullName.trim(),
    if (child.className.trim().isNotEmpty) child.className.trim(),
    if (child.groupName.trim().isNotEmpty) child.groupName.trim(),
  ];
  return parts.isEmpty ? 'Guruh biriktirilmagan' : parts.join(' • ');
}

class PaymentHistoryItem {
  const PaymentHistoryItem({
    required this.title,
    required this.date,
    required this.amount,
    required this.status,
    this.subtitle = '',
    this.sortDate,
    this.historySource,
    this.planSource,
  });

  final String title;
  final String date;
  final String amount;
  final PaymentStatus status;
  final String subtitle;
  final DateTime? sortDate;
  final ParentPaymentHistoryModel? historySource;
  final ParentPaymentPlanItemModel? planSource;
}

enum PaymentHistoryFilter { all, paid, debt, pending }

enum PaymentStatus { paid, pending, unpaid }

extension PaymentHistoryFilterStyle on PaymentHistoryFilter {
  String get label {
    return switch (this) {
      PaymentHistoryFilter.all => 'Barchasi',
      PaymentHistoryFilter.paid => 'To‘langan',
      PaymentHistoryFilter.debt => 'Qarzdorlik',
      PaymentHistoryFilter.pending => 'Kutilmoqda',
    };
  }
}

extension PaymentStatusStyle on PaymentStatus {
  String get label {
    return switch (this) {
      PaymentStatus.paid => 'To‘langan',
      PaymentStatus.pending => 'Kutilmoqda',
      PaymentStatus.unpaid => 'Qarzdorlik',
    };
  }

  IconData get icon {
    return switch (this) {
      PaymentStatus.paid => Icons.check_circle_outline_rounded,
      PaymentStatus.pending => Icons.access_time_rounded,
      PaymentStatus.unpaid => Icons.remove_circle_outline_rounded,
    };
  }

  Color get iconColor {
    return switch (this) {
      PaymentStatus.paid => PaymentColors.green,
      PaymentStatus.pending => const Color(0xFF6B7280),
      PaymentStatus.unpaid => PaymentColors.red,
    };
  }

  Color get iconBackground {
    return switch (this) {
      PaymentStatus.paid => const Color(0xFFE7F8EF),
      PaymentStatus.pending => const Color(0xFFF0F2F6),
      PaymentStatus.unpaid => const Color(0xFFFFE7E7),
    };
  }

  Color get pillBackground {
    return switch (this) {
      PaymentStatus.paid => const Color(0xFFE7F8EF),
      PaymentStatus.pending => const Color(0xFFFFF4DA),
      PaymentStatus.unpaid => const Color(0xFFFFE7E7),
    };
  }

  Color get pillText {
    return switch (this) {
      PaymentStatus.paid => const Color(0xFF047857),
      PaymentStatus.pending => const Color(0xFF9A6B17),
      PaymentStatus.unpaid => const Color(0xFFB85766),
    };
  }

  Color get amountColor {
    return switch (this) {
      PaymentStatus.paid => PaymentColors.green,
      PaymentStatus.pending => PaymentColors.orange,
      PaymentStatus.unpaid => PaymentColors.red,
    };
  }
}

class PaymentColors {
  const PaymentColors._();

  static const Color background = Color(0xFFF7FBFF);
  static const Color primaryBlue = Color(0xFF1E73F8);
  static const Color primaryBlueSoft = Color(0xFFEAF2FF);
  static const Color green = Color(0xFF1F9D73);
  static const Color red = Color(0xFFD97782);
  static const Color orange = Color(0xFFC28B34);
  static const Color text = Color(0xFF111827);
  static const Color secondaryText = Color(0xFF6B7280);
  static const Color border = Color(0xFFE5EAF2);
  static const Color emptySurface = Color(0xFFF6F8FC);
  static const Color paidOnHero = Color(0xFFA7F3D0);
  static const Color debtOnHero = Color(0xFFFECACA);
}

class PaymentTextStyles {
  const PaymentTextStyles._();

  static TextStyle get title {
    return GoogleFonts.inter(
      fontSize: 17,
      height: 1.16,
      fontWeight: FontWeight.w800,
      color: PaymentColors.text,
      letterSpacing: 0,
    );
  }

  static TextStyle get body {
    return GoogleFonts.inter(
      fontSize: 14,
      height: 1.28,
      fontWeight: FontWeight.w500,
      color: PaymentColors.text,
      letterSpacing: 0,
    );
  }

  static TextStyle get label {
    return GoogleFonts.inter(
      fontSize: 12.5,
      height: 1.16,
      fontWeight: FontWeight.w800,
      color: PaymentColors.text,
      letterSpacing: 0,
    );
  }

  static TextStyle get link {
    return GoogleFonts.inter(
      fontSize: 14,
      height: 1.16,
      fontWeight: FontWeight.w800,
      color: PaymentColors.primaryBlue,
      letterSpacing: 0,
    );
  }
}

class PaymentShadows {
  const PaymentShadows._();

  static const List<BoxShadow> soft = [
    BoxShadow(color: Color(0x0F0B1220), blurRadius: 18, offset: Offset(0, 8)),
  ];

  static const List<BoxShadow> card = [
    BoxShadow(color: Color(0x0D0B1220), blurRadius: 18, offset: Offset(0, 8)),
  ];

  static const List<BoxShadow> topNav = [
    BoxShadow(color: Color(0x140B1220), blurRadius: 24, offset: Offset(0, -8)),
  ];
}
