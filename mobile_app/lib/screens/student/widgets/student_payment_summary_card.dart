import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/widgets/app_badge.dart';
import 'package:chaqmoq_mobile/widgets/app_card.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class StudentPaymentSummaryCard extends StatelessWidget {
  const StudentPaymentSummaryCard({
    super.key,
    required this.summary,
    required this.lastPayment,
    required this.nextDue,
    this.onTap,
  });

  final PaymentSummaryModel summary;
  final PaymentModel? lastPayment;
  final DateTime? nextDue;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final hasDebt = summary.openDebt > 0;
    final lateDays = _lateDays(nextDue);
    final status = hasDebt
        ? (lateDays > 0 ? _PayStatus.late : _PayStatus.due)
        : _PayStatus.paid;

    return AppGCard(
      onTap: onTap,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Container(
                width: 36,
                height: 36,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: tokens.tonedSurface(tokens.primary),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(Icons.account_balance_wallet_rounded, color: tokens.primary, size: 20),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  "To‘lov holati",
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                    color: tokens.text,
                  ),
                ),
              ),
              _StatusBadge(status: status, lateDays: lateDays),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            hasDebt
                ? Formatters.currency(summary.openDebt)
                : 'Qarz yo‘q',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: GoogleFonts.inter(
              fontSize: 22,
              fontWeight: FontWeight.w800,
              color: hasDebt ? (lateDays > 0 ? tokens.danger : tokens.warning) : tokens.success,
              letterSpacing: -0.4,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'Joriy oy: ${Formatters.currency(summary.thisMonth)}',
            style: GoogleFonts.inter(
              fontSize: 11.5,
              fontWeight: FontWeight.w600,
              color: tokens.textMuted,
            ),
          ),
          const SizedBox(height: 12),
          Container(height: 1, color: tokens.border),
          const SizedBox(height: 10),
          _Row(
            label: "Oxirgi to‘lov",
            value: lastPayment == null
                ? 'Ma’lumot yo‘q'
                : '${Formatters.currency(lastPayment!.amount)} · ${Formatters.shortDayMonth(lastPayment!.date)}',
          ),
          const SizedBox(height: 4),
          _Row(
            label: "Keyingi to‘lov",
            value: nextDue == null ? '—' : Formatters.shortDayMonth(nextDue),
          ),
        ],
      ),
    );
  }

  static int _lateDays(DateTime? due) {
    if (due == null) return 0;
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final dueDay = DateTime(due.year, due.month, due.day);
    final diff = today.difference(dueDay).inDays;
    return diff > 0 ? diff : 0;
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.label, required this.value});

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

enum _PayStatus { paid, due, late }

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.status, required this.lateDays});

  final _PayStatus status;
  final int lateDays;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    switch (status) {
      case _PayStatus.paid:
        return AppBadge(label: "To‘langan", tone: AppBadgeTone.success, dark: tokens.isDark);
      case _PayStatus.due:
        return AppBadge(label: 'Qarz bor', tone: AppBadgeTone.warning, dark: tokens.isDark);
      case _PayStatus.late:
        return AppBadge(
          label: '$lateDays kun kechikkan',
          tone: AppBadgeTone.danger,
          dark: tokens.isDark,
        );
    }
  }
}
