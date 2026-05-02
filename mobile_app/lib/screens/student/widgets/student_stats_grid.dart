import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/widgets/app_badge.dart';
import 'package:chaqmoq_mobile/widgets/app_card.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class StudentStatsGrid extends StatelessWidget {
  const StudentStatsGrid({
    super.key,
    required this.metrics,
    required this.fallbackAttendance,
    this.openDebt,
  });

  final List<DashboardMetric> metrics;
  final double fallbackAttendance;
  final int? openDebt;

  @override
  Widget build(BuildContext context) {
    final tiles = <_TileData>[];
    for (final m in metrics.take(4)) {
      tiles.add(
        _TileData(
          title: m.title,
          value: _formatValue(m.value, m.id, m.title),
          subtitle: m.subtitle,
          tone: _toneFor(m.colorKey, m.id),
          icon: _iconFor(m.id),
          trend: m.trend,
        ),
      );
    }
    while (tiles.length < 4) {
      switch (tiles.length) {
        case 0:
          tiles.add(
            _TileData(
              title: 'Davomat',
              value: fallbackAttendance > 0
                  ? '${fallbackAttendance.round()}%'
                  : '—',
              subtitle: 'Shu oy',
              tone: AppBadgeTone.teal,
              icon: Icons.fact_check_outlined,
            ),
          );
          break;
        case 1:
          tiles.add(
            _TileData(
              title: 'Qarzdorlik',
              value: openDebt != null && openDebt! > 0
                  ? _shortAmount(openDebt!)
                  : (openDebt != null ? '0' : '—'),
              subtitle: "To‘lov holati",
              tone: openDebt != null && openDebt! > 0
                  ? AppBadgeTone.warning
                  : AppBadgeTone.success,
              icon: Icons.account_balance_wallet_outlined,
            ),
          );
          break;
        case 2:
          tiles.add(
            const _TileData(
              title: "O‘rtacha ball",
              value: '—',
              subtitle: 'Statistika',
              tone: AppBadgeTone.violet,
              icon: Icons.grade_outlined,
            ),
          );
          break;
        case 3:
          tiles.add(
            const _TileData(
              title: 'Faollik',
              value: '—',
              subtitle: 'Hafta',
              tone: AppBadgeTone.warning,
              icon: Icons.trending_up_rounded,
            ),
          );
          break;
      }
    }

    return LayoutBuilder(
      builder: (context, constraints) {
        const spacing = 10.0;
        final tileWidth = (constraints.maxWidth - spacing) / 2;
        // Fixed tile height keeps all four cards aligned and gives us
        // exactly enough room for icon + title + value + subtitle.
        const tileHeight = 124.0;
        return GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: spacing,
          crossAxisSpacing: spacing,
          childAspectRatio: tileWidth / tileHeight,
          children: tiles.map((t) => _Tile(data: t)).toList(),
        );
      },
    );
  }

  AppBadgeTone _toneFor(String colorKey, String id) {
    final raw = '$colorKey $id'.toLowerCase();
    if (raw.contains('teal') ||
        raw.contains('attend') ||
        raw.contains('davomat')) {
      return AppBadgeTone.teal;
    }
    if (raw.contains('success') ||
        raw.contains('green') ||
        raw.contains('debt') ||
        raw.contains('balance') ||
        raw.contains('qarz')) {
      return AppBadgeTone.success;
    }
    if (raw.contains('violet') ||
        raw.contains('purple') ||
        raw.contains('score') ||
        raw.contains('grade') ||
        raw.contains('ball')) {
      return AppBadgeTone.violet;
    }
    if (raw.contains('warn') ||
        raw.contains('amber') ||
        raw.contains('streak') ||
        raw.contains('faol')) {
      return AppBadgeTone.warning;
    }
    if (raw.contains('danger') || raw.contains('red')) {
      return AppBadgeTone.danger;
    }
    return AppBadgeTone.info;
  }

  IconData _iconFor(String id) {
    final raw = id.toLowerCase();
    if (raw.contains('attend') || raw.contains('davomat')) {
      return Icons.fact_check_outlined;
    }
    if (raw.contains('debt') ||
        raw.contains('balance') ||
        raw.contains('qarz')) {
      return Icons.account_balance_wallet_outlined;
    }
    if (raw.contains('score') ||
        raw.contains('grade') ||
        raw.contains('ball')) {
      return Icons.grade_outlined;
    }
    if (raw.contains('streak') || raw.contains('faol')) {
      return Icons.trending_up_rounded;
    }
    return Icons.insights_outlined;
  }

  static String _shortAmount(int value) {
    if (value.abs() >= 1000000) {
      final n = value / 1000000;
      return '${n.toStringAsFixed(value % 1000000 == 0 ? 0 : 1)} mln';
    }
    if (value.abs() >= 1000) return '${(value / 1000).toStringAsFixed(0)} ming';
    return '$value';
  }

  /// Reformat raw server values: numbers with 4+ digits get thousand separators,
  /// debt/balance metrics get a `so'm` suffix, attendance/percent metrics get `%`.
  String _formatValue(String raw, String id, String title) {
    final trimmed = raw.trim();
    if (trimmed.isEmpty) return '—';
    if (trimmed.endsWith('%')) return trimmed;
    final lower = '${id.toLowerCase()} ${title.toLowerCase()}';
    final isMoney =
        lower.contains('debt') ||
        lower.contains('qarz') ||
        lower.contains('balance') ||
        lower.contains('to‘lov') ||
        lower.contains('tolov');
    final isPercent = lower.contains('attend') || lower.contains('davomat');
    final cleaned = trimmed.replaceAll(' ', '');
    final parsed = int.tryParse(cleaned);
    if (parsed == null) return trimmed;
    if (isMoney) {
      return Formatters.currency(parsed, compact: parsed.abs() >= 100000);
    }
    if (isPercent && parsed >= 0 && parsed <= 100) return '$parsed%';
    if (parsed.abs() >= 1000) return Formatters.number(parsed);
    return trimmed;
  }
}

class _TileData {
  const _TileData({
    required this.title,
    required this.value,
    required this.subtitle,
    required this.tone,
    required this.icon,
    this.trend = 0,
  });

  final String title;
  final String value;
  final String subtitle;
  final AppBadgeTone tone;
  final IconData icon;
  final double trend;
}

class _Tile extends StatelessWidget {
  const _Tile({required this.data});

  final _TileData data;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final palette = _palette(tokens, data.tone);
    final trendUp = data.trend > 0.05;
    final trendDown = data.trend < -0.05;
    return AppGCard(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 30,
                height: 30,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: palette.$1,
                  borderRadius: BorderRadius.circular(9),
                ),
                child: Icon(data.icon, size: 17, color: palette.$2),
              ),
              const Spacer(),
              if (trendUp || trendDown)
                Icon(
                  trendUp
                      ? Icons.trending_up_rounded
                      : Icons.trending_down_rounded,
                  size: 14,
                  color: trendUp ? tokens.success : tokens.danger,
                ),
            ],
          ),
          const Spacer(),
          Text(
            data.title,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: GoogleFonts.inter(
              fontSize: 11,
              height: 1.1,
              fontWeight: FontWeight.w600,
              color: tokens.textMuted,
            ),
          ),
          const SizedBox(height: 2),
          Align(
            alignment: Alignment.centerLeft,
            child: FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerLeft,
              child: Text(
                data.value,
                maxLines: 1,
                style: GoogleFonts.inter(
                  fontSize: 19,
                  height: 1.1,
                  fontWeight: FontWeight.w800,
                  color: tokens.text,
                  letterSpacing: -0.4,
                ),
              ),
            ),
          ),
          const SizedBox(height: 2),
          Text(
            data.subtitle,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: GoogleFonts.inter(
              fontSize: 10.5,
              height: 1.1,
              fontWeight: FontWeight.w600,
              color: tokens.textMuted,
            ),
          ),
        ],
      ),
    );
  }

  (Color, Color) _palette(StudentTokens t, AppBadgeTone tone) {
    switch (tone) {
      case AppBadgeTone.teal:
        return (t.tonedSurface(t.primary), t.primary);
      case AppBadgeTone.violet:
        return (t.tonedSurface(t.secondary), t.secondary);
      case AppBadgeTone.success:
        return (t.tonedSurface(t.success), t.success);
      case AppBadgeTone.warning:
        return (t.tonedSurface(t.warning), t.warning);
      case AppBadgeTone.danger:
        return (t.tonedSurface(t.danger), t.danger);
      case AppBadgeTone.info:
        return (t.tonedSurface(t.info), t.info);
      case AppBadgeTone.neutral:
        return (t.glassStrong, t.textMuted);
    }
  }
}
