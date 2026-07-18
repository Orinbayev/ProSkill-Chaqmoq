import 'package:flutter/material.dart';

import '../../../core/design/ds_colors.dart';
import '../../../core/design/ds_components.dart';
import '../../../core/design/ds_tokens.dart';
import '../../../core/design/ds_typography.dart';
import '../data/director_data.dart';

/// Kunlik davomat nazorati — o'qituvchi davomat qilmagan guruhlarni ko'rsatadi.
/// Manager va Director panellarida ishlaydi (bir xil `DirectorData`).
class DirectorAttendanceCard extends StatelessWidget {
  const DirectorAttendanceCard({super.key, required this.monitor, this.onUnscheduledTap});

  final DirectorAttendanceMonitor monitor;
  final void Function(DirectorAttendanceUnscheduled group)? onUnscheduledTap;

  @override
  Widget build(BuildContext context) {
    if (monitor.isEmpty) return const SizedBox.shrink();
    final ds = context.ds;
    return DsCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const DsSectionHeader('Kunlik davomat nazorati'),
          const SizedBox(height: 10),
          Wrap(spacing: 6, runSpacing: 6, children: [
            DsBadge('${monitor.scheduled} guruh'),
            if (monitor.taken > 0) DsBadge('${monitor.taken} qilingan', status: DsStatus.success),
            if (monitor.missing > 0) DsBadge('${monitor.missing} unutilgan', status: DsStatus.danger),
            if (monitor.pending > 0) DsBadge('${monitor.pending} kutilmoqda', status: DsStatus.warning),
            if (monitor.unscheduled > 0) DsBadge('${monitor.unscheduled} jadvalsiz', status: DsStatus.info),
          ]),
          if (monitor.rows.isNotEmpty) const SizedBox(height: 12),
          for (final (i, r) in monitor.rows.indexed) ...[
            if (i > 0) const SizedBox(height: 8),
            _AttendanceRow(row: r),
          ],
          if (monitor.unscheduledGroups.isNotEmpty) ...[
            const SizedBox(height: 14),
            Row(children: [
              Icon(Icons.settings_rounded, size: 15, color: ds.primary),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  'Jadval belgilanmagan (${monitor.unscheduledGroups.length}) — dars kunlarini sozlang',
                  style: DsType.small(ds.primary),
                ),
              ),
            ]),
            const SizedBox(height: 8),
            for (final u in monitor.unscheduledGroups) ...[
              _UnscheduledRow(group: u, onTap: onUnscheduledTap),
              const SizedBox(height: 6),
            ],
          ],
        ],
      ),
    );
  }
}

class _AttendanceRow extends StatelessWidget {
  const _AttendanceRow({required this.row});
  final DirectorAttendanceRow row;

  ({DsStatus tone, Color color, IconData icon, String label}) _meta(BuildContext context) {
    final ds = context.ds;
    switch (row.status) {
      case 'taken':
        return (tone: DsStatus.success, color: ds.success, icon: Icons.check_circle_rounded, label: 'Davomat qilingan');
      case 'missing':
        return (tone: DsStatus.danger, color: ds.danger, icon: Icons.error_rounded, label: 'Davomat qilinmagan!');
      default:
        return (tone: DsStatus.warning, color: ds.warning, icon: Icons.schedule_rounded, label: 'Kutilmoqda');
    }
  }

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    final m = _meta(context);
    final meta = [
      row.teacherName,
      if (row.startTime.isNotEmpty) row.startTime,
    ].where((e) => e.isNotEmpty).join(' · ');
    return Container(
      padding: const EdgeInsets.all(DsSpace.x3),
      decoration: BoxDecoration(
        color: ds.cardAlt,
        borderRadius: DsRadius.all(DsRadius.md),
        border: Border(left: BorderSide(color: m.color, width: 3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(m.icon, size: 18, color: m.color),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(row.groupName, style: DsType.bodyStrong(ds.textPrimary), maxLines: 1, overflow: TextOverflow.ellipsis),
                  if (meta.isNotEmpty) Text(meta, style: DsType.small(ds.textMuted)),
                ],
              ),
            ),
            if (row.status != 'taken')
              Text(m.label, style: DsType.small(m.color).copyWith(fontWeight: FontWeight.w700)),
          ]),
          if (row.status == 'taken') ...[
            const SizedBox(height: 8),
            Wrap(spacing: 6, runSpacing: 6, children: [
              DsBadge('${row.present} keldi', status: DsStatus.success),
              if (row.late > 0) DsBadge('${row.late} kech', status: DsStatus.warning),
              if (row.absentExcused > 0) DsBadge('${row.absentExcused} sababli', status: DsStatus.info),
              if (row.absentUnexcused > 0) DsBadge('${row.absentUnexcused} sababsiz', status: DsStatus.danger),
            ]),
            if (row.absentees.isNotEmpty) ...[
              const SizedBox(height: 6),
              for (final a in row.absentees)
                Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: Text('• ${a.name} — ${a.statusLabel}', style: DsType.small(ds.textMuted)),
                ),
            ],
          ],
        ],
      ),
    );
  }
}

class _UnscheduledRow extends StatelessWidget {
  const _UnscheduledRow({required this.group, this.onTap});
  final DirectorAttendanceUnscheduled group;
  final void Function(DirectorAttendanceUnscheduled group)? onTap;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Material(
      color: ds.primarySoft,
      borderRadius: DsRadius.all(DsRadius.md),
      child: InkWell(
        onTap: onTap == null ? null : () => onTap!(group),
        borderRadius: DsRadius.all(DsRadius.md),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: DsSpace.x3, vertical: 10),
          child: Row(children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(group.groupName, style: DsType.bodyStrong(ds.primarySoftFg), maxLines: 1, overflow: TextOverflow.ellipsis),
                  if (group.teacherName.isNotEmpty) Text(group.teacherName, style: DsType.small(ds.textMuted)),
                ],
              ),
            ),
            Row(children: [
              Icon(Icons.calendar_month_rounded, size: 15, color: ds.primarySoftFg),
              const SizedBox(width: 4),
              Text('Jadval belgilash', style: DsType.small(ds.primarySoftFg).copyWith(fontWeight: FontWeight.w700)),
            ]),
          ]),
        ),
      ),
    );
  }
}
