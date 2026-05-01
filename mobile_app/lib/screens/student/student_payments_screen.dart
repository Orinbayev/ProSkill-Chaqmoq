import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/student_colors.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:intl/intl.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/payments_provider.dart';
import 'package:chaqmoq_mobile/widgets/app_card.dart';
import 'package:chaqmoq_mobile/widgets/app_parent_app_bar.dart';
import 'package:chaqmoq_mobile/widgets/app_state_widgets.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

String _shortAmount(int value) {
  if (value == 0) return '0';
  if (value.abs() >= 1000000) {
    final n = value / 1000000;
    return '${n.toStringAsFixed(value % 1000000 == 0 ? 0 : 1)} mln';
  }
  if (value.abs() >= 1000) {
    final n = value / 1000;
    return '${n.toStringAsFixed(0)} ming';
  }
  return Formatters.number(value);
}

String _monthLabel(DateTime date) {
  return DateFormat('MMM yyyy', 'uz').format(date);
}

/// Student Payments — dark teal hero, mini stats, filter chips, glass list.
class StudentPaymentsScreen extends StatefulWidget {
  const StudentPaymentsScreen({super.key});

  @override
  State<StudentPaymentsScreen> createState() => _StudentPaymentsScreenState();
}

class _StudentPaymentsScreenState extends State<StudentPaymentsScreen> {
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final user = context.read<AuthProvider>().user;
    if (user != null) {
      context.read<PaymentsProvider>().load(user);
    }
  }

  Future<void> _refresh() async {
    final user = context.read<AuthProvider>().user;
    if (user == null) return;
    await context.read<PaymentsProvider>().refresh(user);
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final provider = context.watch<PaymentsProvider>();
    final user = auth.user;
    if (user == null) return const SizedBox.shrink();

    return Scaffold(
      backgroundColor: StudentColors.bg,
      body: Stack(
        children: [
          const _AtmosphericBackdrop(),
          SafeArea(
            child: RefreshIndicator(
              color: StudentColors.primary,
              onRefresh: _refresh,
              child: _body(user, provider),
            ),
          ),
        ],
      ),
    );
  }

  Widget _body(UserModel user, PaymentsProvider provider) {
    if (provider.state == ViewState.loading && provider.filteredItems.isEmpty) {
      return const AppLoadingState(dark: true);
    }
    if (provider.state == ViewState.error && provider.filteredItems.isEmpty) {
      return AppErrorState(
        title: "To‘lovlar yuklanmadi",
        message: provider.errorMessage ??
            'Server bilan aloqa yo‘q. Qayta urinib ko‘ring.',
        dark: true,
        onRetry: () => provider.refresh(user),
      );
    }

    final items = provider.filteredItems;

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(parent: BouncingScrollPhysics()),
      padding: const EdgeInsets.fromLTRB(18, 8, 18, 110),
      children: [
        Row(
          children: [
            Expanded(
              child: Text("To‘lovlar",
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 19,
                    fontWeight: FontWeight.w800,
                    color: StudentColors.text,
                    letterSpacing: -0.2,
                  )),
            ),
            AppStudentIconButton(icon: Icons.history_rounded, onTap: () {}),
          ],
        ),
        const SizedBox(height: 14),
        _Hero(summary: provider.summary),
        const SizedBox(height: 14),
        _MiniStats(summary: provider.summary),
        const SizedBox(height: 12),
        _FilterChips(
          active: provider.filter,
          onChanged: provider.setFilter,
        ),
        const SizedBox(height: 12),
        if (items.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 24),
            child: AppEmptyState(
              dark: true,
              title: "To‘lov mavjud emas",
              subtitle: 'Yangi yozuvlar paydo bo‘lganda shu yerda ko‘rinadi.',
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
}

class _AtmosphericBackdrop extends StatelessWidget {
  const _AtmosphericBackdrop();

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: Stack(children: [
        Positioned(
          top: 60,
          right: -40,
          child: Container(
            width: 200,
            height: 200,
            decoration: const BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(colors: [Color(0x3300D4AA), Color(0x0000D4AA)]),
            ),
          ),
        ),
      ]),
    );
  }
}

class _Hero extends StatelessWidget {
  const _Hero({required this.summary});

  final PaymentSummaryModel summary;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0x3300D4AA), Color(0x296C63FF)],
        ),
        borderRadius: BorderRadius.circular(AppRadius.xxl),
        border: Border.all(color: const Color(0x4700D4AA)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'JORIY HOLAT',
            style: GoogleFonts.inter(
              fontSize: 11,
              fontWeight: FontWeight.w700,
              color: StudentColors.primary,
              letterSpacing: 1.6,
            ),
          ),
          const SizedBox(height: 4),
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Flexible(
                child: Text(
                  _shortAmount(summary.openDebt),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 28,
                    fontWeight: FontWeight.w800,
                    color: StudentColors.text,
                    letterSpacing: -0.6,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Text(
                "so‘m qarzdorlik",
                style: GoogleFonts.inter(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: StudentColors.textMuted,
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            "Bu oy: ${_shortAmount(summary.thisMonth)} so‘m",
            style: GoogleFonts.inter(
              fontSize: 11.5,
              fontWeight: FontWeight.w600,
              color: StudentColors.textMuted,
            ),
          ),
        ],
      ),
    );
  }
}

class _MiniStats extends StatelessWidget {
  const _MiniStats({required this.summary});

  final PaymentSummaryModel summary;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _MiniCard(
            label: "Jami to‘langan",
            value: _shortAmount(summary.totalReceived),
            color: StudentColors.primary,
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _MiniCard(
            label: 'Bu oy',
            value: _shortAmount(summary.thisMonth),
            color: StudentColors.text,
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _MiniCard(
            label: 'Qarzdorlik',
            value: _shortAmount(summary.openDebt),
            color: summary.openDebt > 0 ? StudentColors.danger : StudentColors.success,
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
                color: StudentColors.textMuted,
                letterSpacing: 0.3,
              )),
          const SizedBox(height: 4),
          Text(value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: GoogleFonts.inter(
                fontSize: 16,
                fontWeight: FontWeight.w800,
                color: color,
                letterSpacing: -0.3,
              )),
        ],
      ),
    );
  }
}

class _FilterChips extends StatelessWidget {
  const _FilterChips({required this.active, required this.onChanged});

  final String active;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    final items = const [
      ('all', 'Barchasi'),
      ('received', "To‘langan"),
      ('debt', 'Qarzlar'),
    ];
    return Row(
      children: [
        for (var i = 0; i < items.length; i++) ...[
          if (i > 0) const SizedBox(width: 8),
          _Chip(
            id: items[i].$1,
            label: items[i].$2,
            isActive: items[i].$1 == active,
            onTap: () => onChanged(items[i].$1),
          ),
        ],
      ],
    );
  }
}

class _Chip extends StatelessWidget {
  const _Chip({
    required this.id,
    required this.label,
    required this.isActive,
    required this.onTap,
  });

  final String id;
  final String label;
  final bool isActive;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(100),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(100),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
          decoration: BoxDecoration(
            color: isActive ? StudentColors.primary : StudentColors.glass,
            borderRadius: BorderRadius.circular(100),
            border: Border.all(
              color: isActive ? Colors.transparent : StudentColors.border,
            ),
          ),
          child: Text(
            label,
            style: GoogleFonts.inter(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: isActive ? StudentColors.onPrimary : StudentColors.textMuted,
            ),
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
    final isPaid = !item.isDebt;
    final iconBg = isPaid ? const Color(0x292ED573) : const Color(0x29FFA502);
    final iconFg = isPaid ? StudentColors.success : StudentColors.warning;
    final monthLabel = _monthLabel(item.date);
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
            child: Icon(isPaid ? Icons.check_circle_outline_rounded : Icons.schedule_rounded, color: iconFg, size: 22),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(monthLabel,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: GoogleFonts.inter(
                      fontSize: 13.5,
                      fontWeight: FontWeight.w800,
                      color: StudentColors.text,
                    )),
                const SizedBox(height: 2),
                Text(
                  isPaid
                      ? '${item.method.isEmpty ? 'Naqd' : item.method} · ${Formatters.shortDayMonth(item.date)}'
                      : 'Muddati: ${Formatters.shortDayMonth(item.date)}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: StudentColors.textMuted,
                  ),
                ),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                _shortAmount(item.amount),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: GoogleFonts.inter(
                  fontSize: 14,
                  fontWeight: FontWeight.w800,
                  color: StudentColors.text,
                ),
              ),
              Text(
                "so‘m",
                style: GoogleFonts.inter(
                  fontSize: 10,
                  fontWeight: FontWeight.w600,
                  color: StudentColors.textMuted,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
