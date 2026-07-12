import 'package:flutter/material.dart';

import '../../core/design/ds_colors.dart';
import '../../core/design/ds_components.dart';
import '../../core/design/ds_format.dart';
import '../../core/design/ds_tokens.dart';
import '../../core/design/ds_typography.dart';
import 'data/director_data.dart';

class DirectorPaymentsScreen extends StatelessWidget {
  const DirectorPaymentsScreen({super.key, required this.data});
  final DirectorData data;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return SafeArea(
      bottom: false,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(DsSpace.screen, DsSpace.x3, DsSpace.screen, DsSpace.x8),
        children: [
          Text('To\'lovlar', style: DsType.h1(ds.textPrimary)),
          const SizedBox(height: DsSpace.x4),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(DsSpace.x5),
            decoration: BoxDecoration(
              gradient: LinearGradient(colors: ds.primaryGradient, begin: Alignment.topLeft, end: Alignment.bottomRight),
              borderRadius: DsRadius.all(DsRadius.lg),
              boxShadow: DsShadow.primaryGlow(ds.primary),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  Text('Davr tushumi, so\'m', style: DsType.caption(Colors.white.withValues(alpha: 0.9))),
                  const Spacer(),
                  const Icon(Icons.bolt, color: Colors.white, size: 20),
                ]),
                const SizedBox(height: 6),
                Text(dsSom(data.periodRevenue), style: DsType.display(Colors.white)),
                const SizedBox(height: 2),
                Text('${data.recentPayments.length} ta so\'nggi to\'lov', style: DsType.small(Colors.white.withValues(alpha: 0.85))),
              ],
            ),
          ),
          const SizedBox(height: DsSpace.section),
          DsSectionHeader('So\'nggi to\'lovlar'),
          const SizedBox(height: 8),
          if (data.recentPayments.isEmpty)
            _empty(ds, 'Hozircha to\'lov qayd etilmagan')
          else
            DsCard(
              padding: const EdgeInsets.symmetric(horizontal: DsSpace.x5, vertical: DsSpace.x2),
              child: Column(
                children: [
                  for (final (i, p) in data.recentPayments.indexed) ...[
                    if (i > 0) Container(height: 1, color: ds.border),
                    DsListRow(
                      leading: DsAvatar(p.name, tone: p.tone),
                      title: p.name,
                      subtitle: '${p.subtitle}${p.time.isNotEmpty ? ' · ${p.time}' : ''}',
                      trailing: Text(dsSom(p.amount, sign: true), style: DsType.bodyStrong(ds.success)),
                    ),
                  ],
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _empty(DsColors ds, String text) => Container(
        padding: const EdgeInsets.symmetric(vertical: 40),
        alignment: Alignment.center,
        child: Column(children: [
          Icon(Icons.receipt_long_outlined, size: 40, color: ds.textFaint),
          const SizedBox(height: 10),
          Text(text, style: DsType.caption(ds.textMuted)),
        ]),
      );
}
