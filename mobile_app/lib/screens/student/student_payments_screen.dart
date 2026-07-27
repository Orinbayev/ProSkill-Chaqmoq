import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/payments_provider.dart';
import 'package:chaqmoq_mobile/screens/student/widgets/student_atmospheric_backdrop.dart';
import 'package:chaqmoq_mobile/screens/student/widgets/student_payment_action_sheet.dart';
import 'package:chaqmoq_mobile/widgets/app_badge.dart';
import 'package:chaqmoq_mobile/widgets/app_card.dart';
import 'package:chaqmoq_mobile/widgets/app_parent_app_bar.dart';
import 'package:chaqmoq_mobile/widgets/app_state_widgets.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

class StudentPaymentsScreen extends StatefulWidget {
  const StudentPaymentsScreen({super.key});

  @override
  State<StudentPaymentsScreen> createState() => _StudentPaymentsScreenState();
}

class _StudentPaymentsScreenState extends State<StudentPaymentsScreen> {
  bool _hydrated = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_hydrated) return;
    final user = context.read<AuthProvider>().user;
    if (user == null) return;
    _hydrated = true;

    // Build fazasida provider'ni xabardor qilib bo'lmaydi — kadrdan keyin.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      context.read<PaymentsProvider>().load(user);
    });
  }

  Future<void> _refresh() async {
    final user = context.read<AuthProvider>().user;
    if (user == null) return;
    await context.read<PaymentsProvider>().refresh(user);
  }

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final auth = context.watch<AuthProvider>();
    final provider = context.watch<PaymentsProvider>();
    final user = auth.user;
    if (user == null) return const SizedBox.shrink();

    return Scaffold(
      backgroundColor: tokens.bg,
      body: Stack(
        children: [
          const StudentAtmosphericBackdrop(),
          SafeArea(
            child: RefreshIndicator(
              color: tokens.primary,
              onRefresh: _refresh,
              child: _body(user, provider, tokens),
            ),
          ),
        ],
      ),
    );
  }

  Widget _body(UserModel user, PaymentsProvider provider, StudentTokens tokens) {
    if (provider.state == ViewState.loading && provider.allItems.isEmpty) {
      return AppLoadingState(dark: tokens.isDark);
    }
    if (provider.state == ViewState.error && provider.allItems.isEmpty) {
      return AppErrorState(
        title: "To‘lovlar yuklanmadi",
        message: provider.errorMessage ??
            'Server bilan aloqa yo‘q. Qayta urinib ko‘ring.',
        dark: tokens.isDark,
        onRetry: () => provider.refresh(user),
      );
    }

    final items = provider.filteredItems;
    final summary = provider.summary;
    final lastPaid = _lastPaid(provider.allItems);
    final nextDue = _nextDue(provider.allItems);
    final paidCount = provider.allItems.where((p) => !p.isDebt).length;
    final debtCount = provider.allItems.where((p) => p.isDebt).length;

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(parent: BouncingScrollPhysics()),
      padding: const EdgeInsets.fromLTRB(18, 8, 18, 110),
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                "To‘lovlar",
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: GoogleFonts.inter(
                  fontSize: 19,
                  fontWeight: FontWeight.w800,
                  color: tokens.text,
                  letterSpacing: -0.2,
                ),
              ),
            ),
            AppStudentIconButton(icon: Icons.history_rounded, onTap: () {}),
          ],
        ),
        const SizedBox(height: 14),
        _Hero(summary: summary, lastPaid: lastPaid, nextDue: nextDue),
        const SizedBox(height: 12),
        _PayCtaButton(
          summary: summary,
          onTap: () => StudentPaymentActionSheet.show(
            context,
            summary: summary,
            debtItems: provider.allItems.where((p) => p.isDebt).toList(),
            center: user.center,
          ),
        ),
        const SizedBox(height: 14),
        _MiniStats(summary: summary),
        const SizedBox(height: 12),
        _FilterChips(
          active: provider.filter,
          onChanged: provider.setFilter,
          allCount: provider.allItems.length,
          paidCount: paidCount,
          debtCount: debtCount,
        ),
        const SizedBox(height: 12),
        if (items.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 24),
            child: AppEmptyState(
              dark: tokens.isDark,
              title: _emptyTitle(provider.filter),
              subtitle: _emptySubtitle(provider.filter),
              icon: Icons.receipt_long_outlined,
            ),
          )
        else
          ...items.map((p) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: _PaymentRow(item: p),
              )),
      ],
    );
  }

  String _emptyTitle(String filter) {
    switch (filter) {
      case 'received':
        return "To‘langan to‘lov mavjud emas";
      case 'debt':
        return 'Qarz mavjud emas';
      default:
        return "To‘lov mavjud emas";
    }
  }

  String _emptySubtitle(String filter) {
    switch (filter) {
      case 'debt':
        return 'Hozirda hech qanday qarzingiz yo‘q. Yaxshi natija!';
      case 'received':
        return "Hozircha to‘langan yozuv yo‘q.";
      default:
        return "Yangi yozuvlar paydo bo‘lganda shu yerda ko‘rinadi.";
    }
  }

  PaymentModel? _lastPaid(List<PaymentModel> items) {
    final paid = items.where((p) => !p.isDebt).toList()
      ..sort((a, b) => b.date.compareTo(a.date));
    return paid.isEmpty ? null : paid.first;
  }

  DateTime? _nextDue(List<PaymentModel> items) {
    final debt = items.where((p) => p.isDebt).toList()
      ..sort((a, b) => a.date.compareTo(b.date));
    return debt.isEmpty ? null : debt.first.date;
  }
}

class _Hero extends StatelessWidget {
  const _Hero({required this.summary, required this.lastPaid, required this.nextDue});

  final PaymentSummaryModel summary;
  final PaymentModel? lastPaid;
  final DateTime? nextDue;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final lateDays = _lateDays(nextDue);
    final hasDebt = summary.openDebt > 0;
    final amountColor = hasDebt ? tokens.danger : tokens.success;
    final now = DateTime.now();
    final monthName = _monthNameUz(now.month);
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: hasDebt
              ? [
                  tokens.danger.withValues(alpha: 0.16),
                  tokens.warning.withValues(alpha: 0.10),
                ]
              : [
                  tokens.primary.withValues(alpha: 0.20),
                  tokens.secondary.withValues(alpha: 0.18),
                ],
        ),
        borderRadius: BorderRadius.circular(AppRadius.xxl),
        border: Border.all(
          color: (hasDebt ? tokens.danger : tokens.primary).withValues(alpha: 0.32),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  hasDebt ? '$monthName OYI · QARZ' : 'JORIY HOLAT',
                  style: GoogleFonts.inter(
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    color: hasDebt ? tokens.danger : tokens.primary,
                    letterSpacing: 1.6,
                  ),
                ),
              ),
              AppBadge(
                label: !hasDebt
                    ? "To‘langan"
                    : (lateDays > 0 ? '$lateDays kun kechikkan' : 'Qarz bor'),
                tone: !hasDebt
                    ? AppBadgeTone.success
                    : (lateDays > 0 ? AppBadgeTone.danger : AppBadgeTone.warning),
                dark: tokens.isDark,
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            hasDebt ? Formatters.number(summary.openDebt) : 'Qarz yo‘q',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: GoogleFonts.inter(
              fontSize: 28,
              fontWeight: FontWeight.w800,
              color: amountColor,
              letterSpacing: -0.6,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            hasDebt
                ? '$monthName oyidagi qarzingiz'
                : 'Bu oy: ${Formatters.number(summary.thisMonth)}',
            style: GoogleFonts.inter(
              fontSize: 11.5,
              fontWeight: FontWeight.w600,
              color: tokens.textMuted,
            ),
          ),
          const SizedBox(height: 12),
          Container(height: 1, color: tokens.border),
          const SizedBox(height: 10),
          _HeroRow(
            label: "Oxirgi to‘lov",
            value: lastPaid == null
                ? 'Ma’lumot yo‘q'
                : '${Formatters.number(lastPaid!.amount)} · ${Formatters.shortDayMonth(lastPaid!.date)}',
          ),
          const SizedBox(height: 4),
          _HeroRow(
            label: "Keyingi to‘lov",
            value: Formatters.shortDayMonth(_firstOfNextMonth()),
          ),
        ],
      ),
    );
  }

  static DateTime _firstOfNextMonth() {
    final now = DateTime.now();
    return DateTime(now.year, now.month + 1, 1);
  }

  static int _lateDays(DateTime? due) {
    if (due == null) return 0;
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final dueDay = DateTime(due.year, due.month, due.day);
    final diff = today.difference(dueDay).inDays;
    return diff > 0 ? diff : 0;
  }

  static String _monthNameUz(int month) {
    const names = [
      'YANVAR',
      'FEVRAL',
      'MART',
      'APREL',
      'MAY',
      'IYUN',
      'IYUL',
      'AVGUST',
      'SENTABR',
      'OKTABR',
      'NOYABR',
      'DEKABR',
    ];
    if (month < 1 || month > 12) return '';
    return names[month - 1];
  }
}

class _HeroRow extends StatelessWidget {
  const _HeroRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Row(
      children: [
        Text(label,
            style: GoogleFonts.inter(
              fontSize: 11.5,
              fontWeight: FontWeight.w600,
              color: tokens.textMuted,
            )),
        const Spacer(),
        Flexible(
          child: Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            textAlign: TextAlign.right,
            style: GoogleFonts.inter(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: tokens.text,
            ),
          ),
        ),
      ],
    );
  }
}

class _MiniStats extends StatelessWidget {
  const _MiniStats({required this.summary});

  final PaymentSummaryModel summary;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Row(
      children: [
        Expanded(
          child: _MiniCard(
            label: "Jami to‘langan",
            value: Formatters.number(summary.totalReceived),
            color: tokens.primary,
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _MiniCard(
            label: 'Bu oy',
            value: Formatters.number(summary.thisMonth),
            color: tokens.text,
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _MiniCard(
            label: 'Qarzdorlik',
            value: Formatters.number(summary.openDebt),
            color: summary.openDebt > 0 ? tokens.danger : tokens.success,
          ),
        ),
      ],
    );
  }
}

class _MiniCard extends StatelessWidget {
  const _MiniCard({required this.label, required this.value, required this.color});

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return AppGCard(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: GoogleFonts.inter(
                fontSize: 10,
                fontWeight: FontWeight.w700,
                color: tokens.textMuted,
                letterSpacing: 0.3,
              )),
          const SizedBox(height: 4),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(value,
                maxLines: 1,
                style: GoogleFonts.inter(
                  fontSize: 15,
                  fontWeight: FontWeight.w800,
                  color: color,
                  letterSpacing: -0.3,
                )),
          ),
        ],
      ),
    );
  }
}

class _FilterChips extends StatelessWidget {
  const _FilterChips({
    required this.active,
    required this.onChanged,
    required this.allCount,
    required this.paidCount,
    required this.debtCount,
  });

  final String active;
  final ValueChanged<String> onChanged;
  final int allCount;
  final int paidCount;
  final int debtCount;

  @override
  Widget build(BuildContext context) {
    final items = [
      ('all', 'Barchasi', allCount),
      ('received', "To‘langan", paidCount),
      ('debt', 'Qarz', debtCount),
    ];
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          for (var i = 0; i < items.length; i++) ...[
            if (i > 0) const SizedBox(width: 8),
            _Chip(
              label: items[i].$2,
              count: items[i].$3,
              isActive: items[i].$1 == active,
              onTap: () => onChanged(items[i].$1),
            ),
          ],
        ],
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  const _Chip({
    required this.label,
    required this.count,
    required this.isActive,
    required this.onTap,
  });

  final String label;
  final int count;
  final bool isActive;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final fg = isActive ? tokens.onPrimary : tokens.textMuted;
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(100),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(100),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
          decoration: BoxDecoration(
            color: isActive ? tokens.primary : tokens.glass,
            borderRadius: BorderRadius.circular(100),
            border: Border.all(
              color: isActive ? Colors.transparent : tokens.border,
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
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                decoration: BoxDecoration(
                  color: isActive
                      ? Colors.white.withValues(alpha: 0.22)
                      : tokens.tonedSurface(tokens.primary),
                  borderRadius: BorderRadius.circular(100),
                ),
                child: Text(
                  '$count',
                  style: GoogleFonts.inter(
                    fontSize: 10.5,
                    fontWeight: FontWeight.w800,
                    color: isActive ? tokens.onPrimary : tokens.primary,
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
  const _PaymentRow({required this.item});

  final PaymentModel item;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final isPaid = !item.isDebt;
    final lateDays = isPaid ? 0 : _lateDays(item.date);
    final iconBg = isPaid
        ? tokens.tonedSurface(tokens.success)
        : tokens.tonedSurface(tokens.danger);
    final iconFg = isPaid ? tokens.success : tokens.danger;
    final amountColor = isPaid ? tokens.text : tokens.danger;
    final monthLabel = DateFormat('MMM yyyy', 'uz').format(item.date);
    return AppGCard(
      padding: const EdgeInsets.all(14),
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: iconBg,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(
              isPaid
                  ? Icons.check_circle_outline_rounded
                  : (lateDays > 0 ? Icons.error_outline_rounded : Icons.schedule_rounded),
              color: iconFg,
              size: 22,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        monthLabel,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: GoogleFonts.inter(
                          fontSize: 13.5,
                          fontWeight: FontWeight.w800,
                          color: tokens.text,
                        ),
                      ),
                    ),
                    if (isPaid)
                      AppBadge(label: "To‘langan", tone: AppBadgeTone.success, dark: tokens.isDark)
                    else if (lateDays > 0)
                      AppBadge(label: 'Kechikkan', tone: AppBadgeTone.danger, dark: tokens.isDark)
                    else
                      AppBadge(label: 'Qarz', tone: AppBadgeTone.danger, dark: tokens.isDark),
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  isPaid
                      ? '${item.method.isEmpty ? 'Naqd' : item.method} · ${Formatters.shortDayMonth(item.date)}'
                      : (lateDays > 0
                          ? 'Muddati: ${Formatters.shortDayMonth(item.date)} · $lateDays kun'
                          : 'Muddati: ${Formatters.shortDayMonth(item.date)}'),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: tokens.textMuted,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Text(
            Formatters.number(item.amount),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: GoogleFonts.inter(
              fontSize: 13.5,
              fontWeight: FontWeight.w800,
              color: amountColor,
              letterSpacing: -0.2,
            ),
          ),
        ],
      ),
    );
  }

  static int _lateDays(DateTime due) {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final dueDay = DateTime(due.year, due.month, due.day);
    final diff = today.difference(dueDay).inDays;
    return diff > 0 ? diff : 0;
  }
}

class _PayCtaButton extends StatelessWidget {
  const _PayCtaButton({required this.summary, required this.onTap});

  final PaymentSummaryModel summary;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final hasDebt = summary.openDebt > 0;
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          decoration: BoxDecoration(
            gradient: tokens.primaryGradient,
            borderRadius: BorderRadius.circular(16),
            boxShadow: [
              BoxShadow(
                color: tokens.primary.withValues(alpha: 0.32),
                blurRadius: 18,
                offset: const Offset(0, 8),
              ),
            ],
          ),
          child: Row(
            children: [
              Container(
                width: 38,
                height: 38,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.18),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(Icons.payments_rounded, color: tokens.onPrimary, size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      "To‘lov qilish",
                      style: GoogleFonts.inter(
                        fontSize: 14,
                        fontWeight: FontWeight.w800,
                        color: tokens.onPrimary,
                      ),
                    ),
                    Text(
                      hasDebt
                          ? 'Click · Payme · Karta · Naqd'
                          : 'Qarz yo‘q — usullarni ko‘rish',
                      style: GoogleFonts.inter(
                        fontSize: 11.5,
                        fontWeight: FontWeight.w600,
                        color: tokens.onPrimary.withValues(alpha: 0.78),
                      ),
                    ),
                  ],
                ),
              ),
              Icon(Icons.arrow_forward_rounded, color: tokens.onPrimary, size: 22),
            ],
          ),
        ),
      ),
    );
  }
}

