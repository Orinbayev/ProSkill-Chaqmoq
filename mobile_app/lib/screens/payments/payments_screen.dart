import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/parent_models.dart';
import 'package:chaqmoq_mobile/providers/parent_dashboard_provider.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/parent_dashboard_service.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

class PaymentsScreen extends StatefulWidget {
  const PaymentsScreen({super.key, this.showBottomNav = true});

  final bool showBottomNav;

  @override
  State<PaymentsScreen> createState() => _PaymentsScreenState();
}

enum _PayFilter { all, paid, debt }

class _PaymentsScreenState extends State<PaymentsScreen> {
  ParentPaymentsModel? _data;
  ViewState _state = ViewState.idle;
  String? _errorMessage;
  int? _loadedChildId;
  _PayFilter _filter = _PayFilter.all;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final dashboard = context.watch<ParentDashboardProvider>();
    final childId =
        dashboard.selectedChildId ?? dashboard.data?.selectedChild.id;
    if (childId != null && childId > 0 && childId != _loadedChildId) {
      _loadedChildId = childId;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _load(force: true);
      });
    }
  }

  Future<void> _load({bool force = false}) async {
    if (_state == ViewState.loading && !force) return;
    setState(() {
      _state = ViewState.loading;
      _errorMessage = null;
    });
    try {
      final data = await context
          .read<ParentDashboardService>()
          .fetchPayments(childId: _loadedChildId);
      if (!mounted) return;
      setState(() {
        _data = data;
        _state = ViewState.success;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _state = ViewState.error;
        _errorMessage = error.message;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _state = ViewState.error;
        _errorMessage = 'To‘lovlar yuklanmadi';
      });
    }
  }

  List<_PayRow> _rows() {
    final data = _data;
    if (data == null) return const [];
    final out = <_PayRow>[];
    final childName = data.child.fullName.split(' ').first;
    for (final item in data.history) {
      out.add(_PayRow(
        month: _monthLabel(item.date),
        amount: item.amount,
        status: PaymentStatus.paid,
        childName: childName,
        infoLine: _buildPaidLine(item),
        sortDate: item.date,
      ));
    }
    for (final plan in data.planItems) {
      final status = _statusFor(plan.status);
      if (status == PaymentStatus.paid) {
        // Already covered by history
        continue;
      }
      final amount =
          plan.remainingAmount > 0 ? plan.remainingAmount : plan.plannedAmount;
      out.add(_PayRow(
        month: plan.monthLabel.isNotEmpty
            ? plan.monthLabel
            : (plan.month != null ? _monthLabel(plan.month!) : plan.title),
        amount: amount,
        status: status,
        childName: childName,
        infoLine:
            'Muddat: ${plan.dueDate != null ? Formatters.shortDayMonth(plan.dueDate!) : '-'}',
        sortDate: plan.dueDate ?? plan.month,
      ));
    }
    out.sort((a, b) {
      final l = a.sortDate ?? DateTime.fromMillisecondsSinceEpoch(0);
      final r = b.sortDate ?? DateTime.fromMillisecondsSinceEpoch(0);
      return r.compareTo(l);
    });
    return out;
  }

  String _buildPaidLine(ParentPaymentHistoryModel item) {
    final type = item.paymentType.trim().isNotEmpty
        ? item.paymentType.trim()
        : 'To‘lov';
    return '$type · ${Formatters.shortDayMonth(item.date)}';
  }

  PaymentStatus _statusFor(String raw) {
    final n = raw.toLowerCase();
    if (n.contains('paid') || n.contains('to‘lan')) return PaymentStatus.paid;
    if (n.contains('overdue') ||
        n.contains('debt') ||
        n.contains('qarz') ||
        n.contains('o‘tgan')) {
      return PaymentStatus.overdue;
    }
    return PaymentStatus.pending;
  }

  @override
  Widget build(BuildContext context) {
    final fallbackChild = context
        .watch<ParentDashboardProvider>()
        .data
        ?.selectedChild;
    final child = _data?.child ?? fallbackChild;
    final summary = _data?.summary ??
        const ParentPaymentSummaryModel(
          totalPlan: 0,
          totalBalance: 0,
          paidTotal: 0,
          debtAmount: 0,
        );
    final allRows = _rows();
    final paidCount = allRows.where((r) => r.status == PaymentStatus.paid).length;
    final debtCount = allRows.length - paidCount;
    final filtered = switch (_filter) {
      _PayFilter.all => allRows,
      _PayFilter.paid => allRows.where((r) => r.status == PaymentStatus.paid).toList(),
      _PayFilter.debt =>
          allRows.where((r) => r.status != PaymentStatus.paid).toList(),
    };

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.dark,
        statusBarBrightness: Brightness.light,
        systemNavigationBarColor: PaymentColors.background,
        systemNavigationBarIconBrightness: Brightness.dark,
      ),
      child: Scaffold(
        backgroundColor: PaymentColors.background,
        bottomNavigationBar:
            widget.showBottomNav ? const ParentBottomNav() : null,
        body: SafeArea(
          child: RefreshIndicator(
            color: PaymentColors.primaryBlue,
            onRefresh: () => _load(force: true),
            child: SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(
                parent: BouncingScrollPhysics(),
              ),
              padding: const EdgeInsets.fromLTRB(18, 8, 18, 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _Header(),
                  const SizedBox(height: 14),
                  if (_state == ViewState.loading && _data == null)
                    const _LoadingCard()
                  else if (_state == ViewState.error && _data == null)
                    _ErrorCard(
                      message: _errorMessage ?? 'Qayta urinib ko‘ring',
                      onRetry: () => _load(force: true),
                    )
                  else ...[
                    if (_state == ViewState.loading)
                      const Padding(
                        padding: EdgeInsets.only(bottom: 10),
                        child: LinearProgressIndicator(
                          minHeight: 3,
                          color: PaymentColors.primaryBlue,
                          backgroundColor: Color(0xFFEAF4FF),
                        ),
                      ),
                    _DebtHero(summary: summary, hasChild: child != null),
                    const SizedBox(height: 14),
                    _MiniStatsRow(summary: summary),
                    const SizedBox(height: 14),
                    _FilterChips(
                      filter: _filter,
                      total: allRows.length,
                      paid: paidCount,
                      debt: debtCount,
                      onChange: (f) => setState(() => _filter = f),
                    ),
                    const SizedBox(height: 12),
                    if (filtered.isEmpty)
                      _EmptyCard()
                    else
                      for (final row in filtered) ...[
                        _PaymentRow(row: row),
                        const SizedBox(height: 8),
                      ],
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

class _Header extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(
            "To'lovlar",
            style: GoogleFonts.inter(
              fontSize: 26,
              fontWeight: FontWeight.w800,
              color: PaymentColors.text,
              letterSpacing: -0.5,
            ),
          ),
        ),
        Container(
          width: 42,
          height: 42,
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(13),
            border: Border.all(color: PaymentColors.line),
          ),
          alignment: Alignment.center,
          child: const Icon(
            Icons.notifications_active_outlined,
            size: 22,
            color: PaymentColors.text,
          ),
        ),
      ],
    );
  }
}

class _DebtHero extends StatelessWidget {
  const _DebtHero({required this.summary, required this.hasChild});
  final ParentPaymentSummaryModel summary;
  final bool hasChild;

  @override
  Widget build(BuildContext context) {
    final debt = summary.outstandingTotal;
    final due = summary.nextPaymentDate;
    return Container(
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 18),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF1E40AF), Color(0xFF3B82F6)],
        ),
        borderRadius: BorderRadius.circular(22),
        boxShadow: const [
          BoxShadow(
            color: Color(0x471E40AF),
            blurRadius: 32,
            offset: Offset(0, 14),
          ),
        ],
      ),
      child: Stack(
        clipBehavior: Clip.hardEdge,
        children: [
          Positioned(
            top: -50,
            right: -50,
            child: Container(
              width: 180,
              height: 180,
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.08),
                shape: BoxShape.circle,
              ),
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'JORIY QARZDORLIK',
                style: GoogleFonts.inter(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  color: Colors.white.withValues(alpha: 0.85),
                  letterSpacing: 1.4,
                ),
              ),
              const SizedBox(height: 6),
              Row(
                crossAxisAlignment: CrossAxisAlignment.baseline,
                textBaseline: TextBaseline.alphabetic,
                children: [
                  Text(
                    _fmtFull(debt),
                    style: GoogleFonts.inter(
                      fontSize: 30,
                      fontWeight: FontWeight.w800,
                      color: Colors.white,
                      letterSpacing: -0.6,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Text(
                    "so'm",
                    style: GoogleFonts.inter(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: Colors.white.withValues(alpha: 0.85),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              Row(
                children: [
                  Icon(
                    Icons.event_outlined,
                    size: 16,
                    color: Colors.white.withValues(alpha: 0.95),
                  ),
                  const SizedBox(width: 6),
                  Text(
                    "Keyingi to'lov: ${due == null ? '—' : Formatters.shortDayMonth(due)}",
                    style: GoogleFonts.inter(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: Colors.white.withValues(alpha: 0.95),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              Material(
                color: Colors.white.withValues(alpha: 0.16),
                borderRadius: BorderRadius.circular(14),
                child: InkWell(
                  onTap: () => _showPayProviders(context),
                  borderRadius: BorderRadius.circular(14),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 10,
                    ),
                    child: Row(
                      children: [
                        const Icon(
                          Icons.credit_card_rounded,
                          color: Colors.white,
                          size: 22,
                        ),
                        const SizedBox(width: 10),
                        Text(
                          "Hozir to'lash",
                          style: GoogleFonts.inter(
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                            color: Colors.white,
                          ),
                        ),
                        const Spacer(),
                        const Icon(
                          Icons.chevron_right_rounded,
                          color: Colors.white,
                          size: 22,
                        ),
                      ],
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

void _showPayProviders(BuildContext context) {
  showModalBottomSheet<void>(
    context: context,
    backgroundColor: Colors.transparent,
    isScrollControlled: false,
    builder: (sheetContext) {
      return SafeArea(
        top: false,
        child: Container(
          margin: const EdgeInsets.all(12),
          padding: const EdgeInsets.fromLTRB(18, 12, 18, 18),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(24),
            boxShadow: const [
              BoxShadow(
                color: Color(0x1A0B1220),
                blurRadius: 22,
                offset: Offset(0, 12),
              ),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 44,
                  height: 5,
                  margin: const EdgeInsets.only(bottom: 14),
                  decoration: BoxDecoration(
                    color: const Color(0xFFD8E0EC),
                    borderRadius: BorderRadius.circular(999),
                  ),
                ),
              ),
              Text(
                "To'lov usulini tanlang",
                style: GoogleFonts.inter(
                  fontSize: 16,
                  fontWeight: FontWeight.w800,
                  color: const Color(0xFF111827),
                  letterSpacing: -0.2,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                'Quyidagi xizmatlar orqali to‘lov qilishingiz mumkin.',
                style: GoogleFonts.inter(
                  fontSize: 12.5,
                  fontWeight: FontWeight.w500,
                  color: const Color(0xFF6B7280),
                  height: 1.35,
                ),
              ),
              const SizedBox(height: 14),
              _PayProviderTile(
                name: 'Click',
                shortLabel: 'Click orqali to‘lash',
                background: const Color(0xFFE9F2FF),
                accent: const Color(0xFF1E73F8),
                onTap: () {
                  Navigator.of(sheetContext).pop();
                  _showComingSoon(context, 'Click');
                },
              ),
              const SizedBox(height: 10),
              _PayProviderTile(
                name: 'Payme',
                shortLabel: 'Payme orqali to‘lash',
                background: const Color(0xFFEAF8EF),
                accent: const Color(0xFF15803D),
                onTap: () {
                  Navigator.of(sheetContext).pop();
                  _showComingSoon(context, 'Payme');
                },
              ),
            ],
          ),
        ),
      );
    },
  );
}

void _showComingSoon(BuildContext context, String providerName) {
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(
      behavior: SnackBarBehavior.floating,
      backgroundColor: const Color(0xFF111827),
      duration: const Duration(seconds: 2),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
      content: Row(
        children: [
          const Icon(
            Icons.access_time_rounded,
            color: Colors.white,
            size: 18,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              '$providerName tez orada qo‘shiladi',
              style: GoogleFonts.inter(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: Colors.white,
              ),
            ),
          ),
        ],
      ),
    ),
  );
}

class _PayProviderTile extends StatelessWidget {
  const _PayProviderTile({
    required this.name,
    required this.shortLabel,
    required this.background,
    required this.accent,
    required this.onTap,
  });

  final String name;
  final String shortLabel;
  final Color background;
  final Color accent;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          padding: const EdgeInsets.fromLTRB(12, 12, 14, 12),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: const Color(0xFFE5EAF2)),
          ),
          child: Row(
            children: [
              Container(
                width: 46,
                height: 46,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: background,
                  borderRadius: BorderRadius.circular(13),
                ),
                child: Text(
                  name,
                  style: GoogleFonts.inter(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w800,
                    color: accent,
                    letterSpacing: -0.2,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      name,
                      style: GoogleFonts.inter(
                        fontSize: 14.5,
                        fontWeight: FontWeight.w800,
                        color: const Color(0xFF111827),
                        letterSpacing: -0.2,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      shortLabel,
                      style: GoogleFonts.inter(
                        fontSize: 11.5,
                        fontWeight: FontWeight.w500,
                        color: const Color(0xFF6B7280),
                      ),
                    ),
                  ],
                ),
              ),
              const Icon(
                Icons.chevron_right_rounded,
                color: Color(0xFF8B95A1),
                size: 20,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MiniStatsRow extends StatelessWidget {
  const _MiniStatsRow({required this.summary});
  final ParentPaymentSummaryModel summary;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _MiniStat(
            label: "JAMI TO'LANGAN",
            value: _fmtShort(summary.paidTotal),
            valueColor: PaymentColors.green,
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _MiniStat(
            label: 'BU OY',
            value: '0',
            valueColor: PaymentColors.primaryBlue,
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _MiniStat(
            label: 'QARZDORLIK',
            value: _fmtShort(summary.outstandingTotal),
            valueColor: PaymentColors.red,
          ),
        ),
      ],
    );
  }
}

class _MiniStat extends StatelessWidget {
  const _MiniStat({
    required this.label,
    required this.value,
    required this.valueColor,
  });
  final String label;
  final String value;
  final Color valueColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: PaymentColors.line),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0A0B1220),
            blurRadius: 14,
            offset: Offset(0, 6),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label,
            style: GoogleFonts.inter(
              fontSize: 9.5,
              fontWeight: FontWeight.w700,
              color: PaymentColors.textMuted,
              letterSpacing: 0.5,
            ),
          ),
          const SizedBox(height: 6),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(
              value,
              style: GoogleFonts.inter(
                fontSize: 16,
                fontWeight: FontWeight.w800,
                color: valueColor,
                letterSpacing: -0.4,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _FilterChips extends StatelessWidget {
  const _FilterChips({
    required this.filter,
    required this.total,
    required this.paid,
    required this.debt,
    required this.onChange,
  });
  final _PayFilter filter;
  final int total;
  final int paid;
  final int debt;
  final ValueChanged<_PayFilter> onChange;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        _Chip(
          label: 'Barchasi',
          count: total,
          active: filter == _PayFilter.all,
          onTap: () => onChange(_PayFilter.all),
        ),
        const SizedBox(width: 8),
        _Chip(
          label: "To'langan",
          count: paid,
          active: filter == _PayFilter.paid,
          onTap: () => onChange(_PayFilter.paid),
        ),
        const SizedBox(width: 8),
        _Chip(
          label: 'Qarzlar',
          count: debt,
          active: filter == _PayFilter.debt,
          onTap: () => onChange(_PayFilter.debt),
        ),
      ],
    );
  }
}

class _Chip extends StatelessWidget {
  const _Chip({
    required this.label,
    required this.count,
    required this.active,
    required this.onTap,
  });
  final String label;
  final int count;
  final bool active;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final bg = active ? PaymentColors.primaryBlue : Colors.white;
    final fg = active ? Colors.white : PaymentColors.textSoft;
    return Material(
      color: bg,
      borderRadius: BorderRadius.circular(100),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(100),
        child: Container(
          padding:
              const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(100),
            border: Border.all(
              color: active ? Colors.transparent : PaymentColors.line,
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                label,
                style: GoogleFonts.inter(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  color: fg,
                ),
              ),
              const SizedBox(width: 6),
              Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 6, vertical: 1),
                decoration: BoxDecoration(
                  color: active
                      ? Colors.white.withValues(alpha: 0.2)
                      : const Color(0xFFEAF1F9),
                  borderRadius: BorderRadius.circular(100),
                ),
                child: Text(
                  '$count',
                  style: GoogleFonts.inter(
                    fontSize: 10,
                    fontWeight: FontWeight.w800,
                    color: active ? Colors.white : PaymentColors.textMuted,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PaymentRow extends StatelessWidget {
  const _PaymentRow({required this.row});
  final _PayRow row;

  @override
  Widget build(BuildContext context) {
    final isOverdue = row.status == PaymentStatus.overdue;
    final isPaid = row.status == PaymentStatus.paid;
    final iconBg = isPaid
        ? const Color(0xFFDCFCE7)
        : isOverdue
            ? const Color(0xFFFEE2E2)
            : const Color(0xFFFEF3C7);
    final iconFg = isPaid
        ? const Color(0xFF10B981)
        : isOverdue
            ? const Color(0xFFEF4444)
            : const Color(0xFFB45309);
    final icon = isPaid
        ? Icons.check_circle_outline_rounded
        : isOverdue
            ? Icons.error_outline_rounded
            : Icons.schedule_rounded;
    final amountColor =
        isOverdue ? const Color(0xFFEF4444) : PaymentColors.text;

    return Container(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: PaymentColors.line),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0A0B1220),
            blurRadius: 14,
            offset: Offset(0, 6),
          ),
        ],
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: iconBg,
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(icon, color: iconFg, size: 22),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  row.month,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w800,
                    color: PaymentColors.text,
                    letterSpacing: -0.1,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  '${row.childName} · ${row.infoLine}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 11.5,
                    fontWeight: FontWeight.w600,
                    color: PaymentColors.textMuted,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                _fmtShort(row.amount),
                style: GoogleFonts.inter(
                  fontSize: 14,
                  fontWeight: FontWeight.w800,
                  color: amountColor,
                  letterSpacing: -0.2,
                ),
              ),
              const SizedBox(height: 1),
              Text(
                "so'm",
                style: GoogleFonts.inter(
                  fontSize: 10,
                  fontWeight: FontWeight.w600,
                  color: PaymentColors.textMuted,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _EmptyCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(14, 22, 14, 22),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: PaymentColors.line),
      ),
      alignment: Alignment.center,
      child: Text(
        "Hozircha to'lov yozuvlari yo'q",
        style: GoogleFonts.inter(
          fontSize: 13,
          fontWeight: FontWeight.w600,
          color: PaymentColors.textMuted,
        ),
      ),
    );
  }
}

class _LoadingCard extends StatelessWidget {
  const _LoadingCard();
  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 60),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: PaymentColors.line),
      ),
      alignment: Alignment.center,
      child: const CircularProgressIndicator(
        color: PaymentColors.primaryBlue,
      ),
    );
  }
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(18, 28, 18, 24),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: PaymentColors.line),
      ),
      child: Column(
        children: [
          const Icon(
            Icons.info_outline_rounded,
            color: PaymentColors.primaryBlue,
            size: 36,
          ),
          const SizedBox(height: 10),
          Text(
            message,
            textAlign: TextAlign.center,
            style: GoogleFonts.inter(
              fontSize: 13.5,
              fontWeight: FontWeight.w600,
              color: PaymentColors.textSoft,
            ),
          ),
          const SizedBox(height: 14),
          TextButton(
            onPressed: onRetry,
            style: TextButton.styleFrom(
              backgroundColor: const Color(0xFFEFF6FF),
              foregroundColor: PaymentColors.primaryBlue,
              padding:
                  const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
            ),
            child: const Text('Qayta urinish'),
          ),
        ],
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
        boxShadow: [
          BoxShadow(
            color: Color(0x140B1220),
            blurRadius: 24,
            offset: Offset(0, -8),
          ),
        ],
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
            selectedItemColor: PaymentColors.primaryBlue,
            unselectedItemColor: PaymentColors.textMuted,
            iconSize: 24,
            selectedFontSize: 11,
            unselectedFontSize: 11,
            items: const [
              BottomNavigationBarItem(
                icon: Icon(Icons.home_rounded),
                label: 'Bosh',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.fact_check_outlined),
                label: 'Davomat',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.account_balance_wallet_outlined),
                label: "To'lovlar",
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.auto_graph_rounded),
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

// ---- Helpers ----
String _fmtShort(int n) {
  if (n <= 0) return '0';
  if (n >= 1000000) {
    final v = n / 1000000;
    final s =
        n % 1000000 == 0 ? v.toStringAsFixed(0) : v.toStringAsFixed(1);
    return '$s mln';
  }
  if (n >= 1000) {
    final v = n / 1000;
    return '${v.toStringAsFixed(0)} K';
  }
  return '$n';
}

String _fmtFull(int n) {
  final s = n.toString();
  final buf = StringBuffer();
  for (var i = 0; i < s.length; i++) {
    final fromEnd = s.length - i;
    buf.write(s[i]);
    if (fromEnd > 1 && (fromEnd - 1) % 3 == 0) buf.write(' ');
  }
  return buf.toString();
}

String _monthLabel(DateTime d) {
  const m = [
    'Yan',
    'Fev',
    'Mar',
    'Apr',
    'May',
    'Iyun',
    'Iyul',
    'Avg',
    'Sen',
    'Okt',
    'Noy',
    'Dek',
  ];
  return '${m[d.month - 1]} ${d.year}';
}

class _PayRow {
  _PayRow({
    required this.month,
    required this.amount,
    required this.status,
    required this.childName,
    required this.infoLine,
    this.sortDate,
  });

  final String month;
  final int amount;
  final PaymentStatus status;
  final String childName;
  final String infoLine;
  final DateTime? sortDate;
}

enum PaymentStatus { paid, pending, overdue }

class PaymentColors {
  const PaymentColors._();
  static const Color background = Color(0xFFF4F7FB);
  static const Color text = Color(0xFF0F1E33);
  static const Color textSoft = Color(0xFF4B5B72);
  static const Color textMuted = Color(0xFF8090A8);
  static const Color line = Color(0xFFE4ECF5);
  static const Color primaryBlue = Color(0xFF3B82F6);
  static const Color green = Color(0xFF10B981);
  static const Color red = Color(0xFFEF4444);
}
