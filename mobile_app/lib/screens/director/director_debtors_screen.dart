import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/design/ds_colors.dart';
import '../../core/design/ds_components.dart';
import '../../core/design/ds_format.dart';
import '../../core/design/ds_tokens.dart';
import '../../core/design/ds_typography.dart';
import 'data/director_data.dart';
import 'data/director_provider.dart';
import 'widgets/director_payment_sheet.dart';
import 'widgets/director_states.dart';

class DirectorDebtorsScreen extends StatefulWidget {
  const DirectorDebtorsScreen({super.key, this.embedded = false});

  /// Tab ichida ko'rsatilsa `true` (o'z AppBar'isiz).
  final bool embedded;

  @override
  State<DirectorDebtorsScreen> createState() => _DirectorDebtorsScreenState();
}

class _DirectorDebtorsScreenState extends State<DirectorDebtorsScreen> {
  int _chip = 0;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    final provider = context.watch<DirectorProvider>();
    final debtors = provider.debtors;
    final totalDebt = debtors.fold<int>(0, (s, d) => s + d.totalDebt);

    Widget content;
    if (provider.state == DirectorLoadState.loading && provider.data == null) {
      content = const DirectorLoading();
    } else if (provider.state == DirectorLoadState.error && provider.data == null) {
      content = DirectorErrorView(onRetry: () => provider.load(force: true));
    } else if (debtors.isEmpty) {
      content = const DirectorEmptyView(icon: Icons.verified_rounded, text: 'Qarzdorlar yo\'q — barcha to\'lovlar joyida');
    } else {
      content = ListView(
        padding: const EdgeInsets.fromLTRB(DsSpace.screen, DsSpace.x3, DsSpace.screen, DsSpace.x8),
        children: [
          Row(children: [
            Text('Qarzdorlar', style: DsType.h1(ds.textPrimary)),
            const Spacer(),
            DsBadge('${debtors.length} ta · ${dsSom(totalDebt)}', status: DsStatus.danger),
          ]),
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final (i, label) in ['Joriy oy', 'Guruh: barchasi', 'Qidiruv'].indexed)
                DsChip(label: label, selected: _chip == i, onTap: () => setState(() => _chip = i)),
            ],
          ),
          const SizedBox(height: DsSpace.x5),
          for (final d in debtors) ...[
            _DebtorCard(debtor: d),
            const SizedBox(height: 12),
          ],
        ],
      );
    }

    if (widget.embedded) return SafeArea(bottom: false, child: content);
    return Scaffold(appBar: AppBar(title: const Text('Qarzdorlar')), body: content);
  }
}

class _DebtorCard extends StatelessWidget {
  const _DebtorCard({required this.debtor});
  final DirectorDebtor debtor;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    final hasTable = debtor.months.length > 1;
    return DsCard(
      padding: const EdgeInsets.all(DsSpace.x4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              DsAvatar(debtor.name, tone: debtor.tone),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(debtor.name, style: DsType.bodyStrong(ds.textPrimary)),
                    Text(
                      [debtor.group, debtor.phone].where((s) => s.isNotEmpty).join(' · '),
                      style: DsType.small(ds.textMuted),
                    ),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(dsSom(-debtor.totalDebt), style: DsType.bodyStrong(ds.danger)),
                  Text('jami qarz', style: DsType.small(ds.textFaint)),
                ],
              ),
            ],
          ),
          if (hasTable) ...[
            const SizedBox(height: 14),
            _BreakdownTable(months: debtor.months),
          ],
          const SizedBox(height: 14),
          DsButton(
            label: 'To\'lov kiritish',
            onPressed: () async {
              final provider = context.read<DirectorProvider>();
              final ok = await showDirectorPaymentSheet(context, debtor, methods: provider.data?.paymentMethods ?? const []);
              if (ok == true) provider.refresh();
            },
          ),
        ],
      ),
    );
  }
}

class _BreakdownTable extends StatelessWidget {
  const _BreakdownTable({required this.months});
  final List<DirectorDebtorMonth> months;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    Widget cell(String text, {int flex = 1, Alignment align = Alignment.centerLeft, TextStyle? style}) =>
        Expanded(flex: flex, child: Align(alignment: align, child: Text(text, style: style ?? DsType.small(ds.textSecondary))));

    return Container(
      decoration: BoxDecoration(color: ds.cardAlt, borderRadius: DsRadius.all(DsRadius.md)),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Column(
        children: [
          Row(children: [
            cell('OY', flex: 2, style: DsType.micro(ds.textFaint)),
            cell('OYLIK', align: Alignment.centerRight, style: DsType.micro(ds.textFaint)),
            cell('TO\'LANGAN', align: Alignment.centerRight, style: DsType.micro(ds.textFaint)),
            cell('QARZ', align: Alignment.centerRight, style: DsType.micro(ds.textFaint)),
            cell('HOLAT', flex: 2, align: Alignment.centerRight, style: DsType.micro(ds.textFaint)),
          ]),
          const SizedBox(height: 8),
          for (final (i, m) in months.indexed) ...[
            if (i > 0) Padding(padding: const EdgeInsets.symmetric(vertical: 6), child: Container(height: 1, color: ds.border)),
            Row(children: [
              cell(m.month, flex: 2, style: DsType.small(ds.textPrimary).copyWith(fontWeight: FontWeight.w600)),
              cell(dsSom(m.monthly), align: Alignment.centerRight),
              cell(m.paid == 0 ? '0' : dsSom(m.paid), align: Alignment.centerRight),
              cell(m.debt == 0 ? '0' : dsSom(m.debt), align: Alignment.centerRight,
                  style: DsType.small(m.debt > 0 ? ds.danger : ds.textMuted).copyWith(fontWeight: FontWeight.w600)),
              Expanded(
                flex: 2,
                child: Align(
                  alignment: Alignment.centerRight,
                  child: DsBadge(
                    m.isPaid ? 'To\'landi' : (m.isPartial ? 'Qisman' : 'Qarzdor'),
                    status: m.isPaid ? DsStatus.success : (m.isPartial ? DsStatus.warning : DsStatus.danger),
                  ),
                ),
              ),
            ]),
          ],
        ],
      ),
    );
  }
}
