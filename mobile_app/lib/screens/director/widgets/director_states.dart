import 'package:flutter/material.dart';
import 'package:shimmer/shimmer.dart';

import '../../../core/design/ds_colors.dart';
import '../../../core/design/ds_components.dart';
import '../../../core/design/ds_tokens.dart';
import '../../../core/design/ds_typography.dart';

/// Yuklanish skeleti (shimmer).
class DirectorLoading extends StatelessWidget {
  const DirectorLoading({super.key});

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    Widget box(double h, {double? w, double r = DsRadius.card}) => Container(
          width: w,
          height: h,
          decoration: BoxDecoration(color: ds.card, borderRadius: DsRadius.all(r)),
        );

    return Shimmer.fromColors(
      baseColor: ds.card,
      highlightColor: ds.cardAlt,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(DsSpace.screen, DsSpace.x5, DsSpace.screen, DsSpace.x8),
        children: [
          Row(children: [
            box(18, w: 160, r: 6),
            const Spacer(),
            Container(width: 44, height: 44, decoration: BoxDecoration(color: ds.card, shape: BoxShape.circle)),
          ]),
          const SizedBox(height: DsSpace.x5),
          box(110),
          const SizedBox(height: 12),
          Row(children: [Expanded(child: box(96)), const SizedBox(width: 12), Expanded(child: box(96))]),
          const SizedBox(height: 12),
          box(72),
          const SizedBox(height: DsSpace.section),
          box(200),
        ],
      ),
    );
  }
}

/// Xatolik ko'rinishi — qayta urinish tugmasi bilan.
class DirectorErrorView extends StatelessWidget {
  const DirectorErrorView({super.key, required this.onRetry, this.message});
  final VoidCallback onRetry;
  final String? message;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(DsSpace.x6),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.cloud_off_rounded, size: 48, color: ds.textFaint),
            const SizedBox(height: 14),
            Text(
              message ?? 'Ma\'lumotni yuklab bo\'lmadi.\nInternetni tekshirib, qayta urinib ko\'ring.',
              textAlign: TextAlign.center,
              style: DsType.caption(ds.textMuted),
            ),
            const SizedBox(height: 18),
            DsButton(label: 'Qayta urinish', icon: Icons.refresh, expand: false, onPressed: onRetry),
          ],
        ),
      ),
    );
  }
}

/// Bo'sh holat.
class DirectorEmptyView extends StatelessWidget {
  const DirectorEmptyView({super.key, required this.icon, required this.text});
  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(DsSpace.x6),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 48, color: ds.textFaint),
            const SizedBox(height: 14),
            Text(text, textAlign: TextAlign.center, style: DsType.caption(ds.textMuted)),
          ],
        ),
      ),
    );
  }
}
