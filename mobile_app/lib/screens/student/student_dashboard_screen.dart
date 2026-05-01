import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/parent_text_styles.dart';
import 'package:chaqmoq_mobile/core/theme/student_colors.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/dashboard_provider.dart';
import 'package:chaqmoq_mobile/providers/notifications_provider.dart';
import 'package:chaqmoq_mobile/widgets/app_badge.dart';
import 'package:chaqmoq_mobile/widgets/app_card.dart';
import 'package:chaqmoq_mobile/widgets/app_mini_bar_chart.dart';
import 'package:chaqmoq_mobile/widgets/app_parent_app_bar.dart';
import 'package:chaqmoq_mobile/widgets/app_state_widgets.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

/// Student Dashboard — dark teal/violet glass theme.
/// Mirrors StudentDashboard JSX: atmospheric blobs, hero glass + quick actions,
/// rating GCard, 4 metric GCards, 12-week activity bars.
class StudentDashboardScreen extends StatefulWidget {
  const StudentDashboardScreen({
    super.key,
    this.onOpenPayments,
    this.onOpenNotifications,
    this.onOpenProfile,
  });

  final VoidCallback? onOpenPayments;
  final VoidCallback? onOpenNotifications;
  final VoidCallback? onOpenProfile;

  @override
  State<StudentDashboardScreen> createState() => _StudentDashboardScreenState();
}

class _StudentDashboardScreenState extends State<StudentDashboardScreen> {
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final user = context.read<AuthProvider>().user;
    if (user != null) {
      context.read<DashboardProvider>().load(user);
    }
  }

  Future<void> _refresh() async {
    final user = context.read<AuthProvider>().user;
    if (user == null) return;
    await Future.wait([
      context.read<DashboardProvider>().refresh(user),
      context.read<NotificationsProvider>().refresh(),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final dashboard = context.watch<DashboardProvider>();
    final notifications = context.watch<NotificationsProvider>();
    final user = auth.user;

    if (user == null) {
      return const SizedBox.shrink();
    }

    return Scaffold(
      backgroundColor: StudentColors.bg,
      body: Stack(
        children: [
          const _AtmosphericBackdrop(),
          SafeArea(
            child: RefreshIndicator(
              color: StudentColors.primary,
              onRefresh: _refresh,
              child: _body(
                user,
                dashboard,
                unread: notifications.unreadCount,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _body(UserModel user, DashboardProvider dashboard, {required int unread}) {
    if (dashboard.state == ViewState.loading && dashboard.data.metrics.isEmpty) {
      return const AppLoadingState(dark: true);
    }

    if (dashboard.state == ViewState.error && dashboard.data.metrics.isEmpty) {
      return AppErrorState(
        title: 'Panel yuklanmadi',
        message: 'Server bilan aloqa yo‘q. Qayta urinib ko‘ring.',
        dark: true,
        onRetry: () => dashboard.refresh(user),
      );
    }

    final metrics = dashboard.data.metrics;
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(parent: BouncingScrollPhysics()),
      padding: const EdgeInsets.fromLTRB(18, 8, 18, 110),
      children: [
        _Header(
          unread: unread,
          onBell: widget.onOpenNotifications ?? () {},
        ),
        const SizedBox(height: 14),
        _Hero(
          name: user.fullName.isEmpty ? 'O‘quvchi' : user.fullName,
          centerName: user.center?.name ?? '',
          onPay: widget.onOpenPayments,
          onMessages: widget.onOpenNotifications,
          onProfile: widget.onOpenProfile,
        ),
        const SizedBox(height: 14),
        _RatingCard(
          score: dashboard.data.studentScore,
          rank: dashboard.data.studentRank,
        ),
        const SizedBox(height: 14),
        _MetricsGrid(
          metrics: metrics,
          fallbackAttendance: dashboard.data.teacherAttendanceRate,
        ),
        const SizedBox(height: 14),
        _ActivityCard(points: dashboard.data.revenueTrend),
      ],
    );
  }
}

class _AtmosphericBackdrop extends StatelessWidget {
  const _AtmosphericBackdrop();

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: Stack(
        children: [
          Positioned(
            top: 70,
            right: -60,
            child: Container(
              width: 220,
              height: 220,
              decoration: const BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: [Color(0x3800D4AA), Color(0x0000D4AA)],
                ),
              ),
            ),
          ),
          Positioned(
            top: 220,
            left: -60,
            child: Container(
              width: 200,
              height: 200,
              decoration: const BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: [Color(0x2E6C63FF), Color(0x006C63FF)],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.unread, required this.onBell});

  final int unread;
  final VoidCallback onBell;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 36,
          height: 36,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(10),
            gradient: const LinearGradient(
              colors: [Color(0x3300D4AA), Color(0x336C63FF)],
            ),
            border: Border.all(color: const Color(0x5200D4AA)),
          ),
          child: const Icon(Icons.bolt_rounded, color: StudentColors.primary, size: 22),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'ChaqmoqApp ⚡',
                style: GoogleFonts.inter(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: StudentColors.textMuted,
                ),
              ),
              const SizedBox(height: 1),
              Text(
                "O‘quvchi paneli",
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: GoogleFonts.inter(
                  fontSize: 14,
                  fontWeight: FontWeight.w800,
                  color: StudentColors.text,
                ),
              ),
            ],
          ),
        ),
        AppStudentIconButton(
          icon: Icons.notifications_outlined,
          onTap: onBell,
          badgeCount: unread,
        ),
      ],
    );
  }
}

class _Hero extends StatelessWidget {
  const _Hero({
    required this.name,
    required this.centerName,
    this.onPay,
    this.onMessages,
    this.onProfile,
  });

  final String name;
  final String centerName;
  final VoidCallback? onPay;
  final VoidCallback? onMessages;
  final VoidCallback? onProfile;

  @override
  Widget build(BuildContext context) {
    final firstName = name.split(RegExp(r'\s+')).first;
    final subtitle = centerName.isEmpty ? 'Markaz topilmadi' : centerName;
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: StudentColors.heroGradient,
        borderRadius: BorderRadius.circular(AppRadius.xxl),
        border: Border.all(color: const Color(0x3800D4AA)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            "O‘QUVCHI PANELI",
            style: GoogleFonts.inter(
              fontSize: 11,
              fontWeight: FontWeight.w700,
              color: StudentColors.primary,
              letterSpacing: 1.6,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'Salom, $firstName 👋',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: StudentTextStyles.hero,
          ),
          const SizedBox(height: 4),
          Text(
            subtitle,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: GoogleFonts.inter(
              fontSize: 12.5,
              fontWeight: FontWeight.w500,
              color: StudentColors.textMuted,
            ),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(child: _HeroQuickAction(icon: Icons.payments_rounded, label: "To‘lovlar", onTap: onPay)),
              const SizedBox(width: 8),
              Expanded(child: _HeroQuickAction(icon: Icons.forum_rounded, label: 'Xabarlar', onTap: onMessages)),
              const SizedBox(width: 8),
              Expanded(child: _HeroQuickAction(icon: Icons.person_rounded, label: 'Profil', onTap: onProfile)),
            ],
          ),
        ],
      ),
    );
  }
}

class _HeroQuickAction extends StatelessWidget {
  const _HeroQuickAction({required this.icon, required this.label, this.onTap});

  final IconData icon;
  final String label;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 6),
          decoration: BoxDecoration(
            color: StudentColors.glassStrong,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: StudentColors.borderStrong),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 18, color: StudentColors.primary),
              const SizedBox(height: 4),
              Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: GoogleFonts.inter(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  color: StudentColors.text,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RatingCard extends StatelessWidget {
  const _RatingCard({required this.score, required this.rank});

  final int score;
  final int rank;

  @override
  Widget build(BuildContext context) {
    final hasData = score > 0 || rank > 0;
    return AppGCard(
      borderColor: const Color(0x526C63FF),
      child: Stack(
        clipBehavior: Clip.hardEdge,
        children: [
          Positioned(
            top: -30,
            right: -30,
            child: IgnorePointer(
              child: Container(
                width: 110,
                height: 110,
                decoration: const BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [Color(0x526C63FF), Color(0x006C63FF)],
                  ),
                ),
              ),
            ),
          ),
          Row(
            children: [
              Container(
                width: 64,
                height: 64,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: const LinearGradient(
                    colors: [Color(0xFF6C63FF), Color(0xFF00D4AA)],
                  ),
                  boxShadow: StudentColors.glowViolet,
                ),
                child: const Icon(Icons.bolt_rounded, color: Colors.white, size: 32),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      'CHAQMOQ REYTING',
                      style: GoogleFonts.inter(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        color: StudentColors.textMuted,
                        letterSpacing: 1.6,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.baseline,
                      textBaseline: TextBaseline.alphabetic,
                      children: [
                        Text(
                          hasData ? '$score' : '—',
                          style: StudentTextStyles.valueLg,
                        ),
                        const SizedBox(width: 6),
                        Text(
                          'ball',
                          style: GoogleFonts.inter(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: StudentColors.textMuted,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    if (rank > 0)
                      AppBadge(
                        label: '#$rank reyting',
                        tone: AppBadgeTone.success,
                        dark: true,
                      )
                    else
                      const AppBadge(
                        label: 'Reyting tayyor emas',
                        tone: AppBadgeTone.neutral,
                        dark: true,
                      ),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MetricsGrid extends StatelessWidget {
  const _MetricsGrid({required this.metrics, required this.fallbackAttendance});

  final List<DashboardMetric> metrics;
  final double fallbackAttendance;

  @override
  Widget build(BuildContext context) {
    final tiles = <_MetricTileData>[];
    for (final m in metrics.take(4)) {
      tiles.add(_MetricTileData(
        title: m.title,
        value: m.value,
        subtitle: m.subtitle,
        tone: _toneFor(m.colorKey, m.id),
        icon: _iconFor(m.id),
      ));
    }
    while (tiles.length < 4) {
      switch (tiles.length) {
        case 0:
          tiles.add(_MetricTileData(
            title: 'Davomat',
            value: fallbackAttendance > 0 ? '${fallbackAttendance.round()}%' : '—',
            subtitle: 'Shu oy',
            tone: AppBadgeTone.teal,
            icon: Icons.fact_check_outlined,
          ));
          break;
        case 1:
          tiles.add(const _MetricTileData(
            title: 'Qarzdorlik',
            value: '—',
            subtitle: "To‘lov holati",
            tone: AppBadgeTone.success,
            icon: Icons.account_balance_wallet_outlined,
          ));
          break;
        case 2:
          tiles.add(const _MetricTileData(
            title: "O‘rtacha ball",
            value: '—',
            subtitle: 'Statistika',
            tone: AppBadgeTone.violet,
            icon: Icons.grade_outlined,
          ));
          break;
        case 3:
          tiles.add(const _MetricTileData(
            title: 'Faollik',
            value: '—',
            subtitle: 'Hafta',
            tone: AppBadgeTone.warning,
            icon: Icons.trending_up_rounded,
          ));
          break;
      }
    }

    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 10,
      crossAxisSpacing: 10,
      childAspectRatio: 1.55,
      children: tiles.map((t) => _MetricTile(data: t)).toList(),
    );
  }

  AppBadgeTone _toneFor(String colorKey, String id) {
    final raw = '$colorKey $id'.toLowerCase();
    if (raw.contains('teal') || raw.contains('attend') || raw.contains('davomat')) return AppBadgeTone.teal;
    if (raw.contains('success') || raw.contains('green') || raw.contains('debt') || raw.contains('balance') || raw.contains('qarz')) return AppBadgeTone.success;
    if (raw.contains('violet') || raw.contains('purple') || raw.contains('score') || raw.contains('grade') || raw.contains('ball')) return AppBadgeTone.violet;
    if (raw.contains('warn') || raw.contains('amber') || raw.contains('streak') || raw.contains('faol')) return AppBadgeTone.warning;
    if (raw.contains('danger') || raw.contains('red')) return AppBadgeTone.danger;
    return AppBadgeTone.info;
  }

  IconData _iconFor(String id) {
    final raw = id.toLowerCase();
    if (raw.contains('attend') || raw.contains('davomat')) return Icons.fact_check_outlined;
    if (raw.contains('debt') || raw.contains('balance') || raw.contains('qarz')) return Icons.account_balance_wallet_outlined;
    if (raw.contains('score') || raw.contains('grade') || raw.contains('ball')) return Icons.grade_outlined;
    if (raw.contains('streak') || raw.contains('faol')) return Icons.trending_up_rounded;
    return Icons.insights_outlined;
  }
}

class _MetricTileData {
  const _MetricTileData({
    required this.title,
    required this.value,
    required this.subtitle,
    required this.tone,
    required this.icon,
  });

  final String title;
  final String value;
  final String subtitle;
  final AppBadgeTone tone;
  final IconData icon;
}

class _MetricTile extends StatelessWidget {
  const _MetricTile({required this.data});

  final _MetricTileData data;

  @override
  Widget build(BuildContext context) {
    final palette = _palette(data.tone);
    return AppGCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 32,
            height: 32,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: palette.$1,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(data.icon, size: 18, color: palette.$2),
          ),
          const SizedBox(height: 8),
          Text(data.title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: GoogleFonts.inter(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: StudentColors.textMuted,
              )),
          Text(data.value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: GoogleFonts.inter(
                fontSize: 19,
                fontWeight: FontWeight.w800,
                color: StudentColors.text,
                letterSpacing: -0.4,
              )),
          Text(data.subtitle,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: GoogleFonts.inter(
                fontSize: 10.5,
                fontWeight: FontWeight.w600,
                color: StudentColors.textMuted,
              )),
        ],
      ),
    );
  }

  (Color, Color) _palette(AppBadgeTone tone) {
    switch (tone) {
      case AppBadgeTone.teal:
        return (const Color(0x2900D4AA), StudentColors.primary);
      case AppBadgeTone.violet:
        return (const Color(0x2E6C63FF), StudentColors.secondarySoft);
      case AppBadgeTone.success:
        return (const Color(0x292ED573), StudentColors.success);
      case AppBadgeTone.warning:
        return (const Color(0x29FFA502), StudentColors.warning);
      case AppBadgeTone.danger:
        return (const Color(0x29FF4757), StudentColors.danger);
      case AppBadgeTone.info:
        return (const Color(0x244FC3F7), StudentColors.info);
      case AppBadgeTone.neutral:
        return (const Color(0x14FFFFFF), StudentColors.textMuted);
    }
  }
}

class _ActivityCard extends StatelessWidget {
  const _ActivityCard({required this.points});

  final List<ChartPointModel> points;

  @override
  Widget build(BuildContext context) {
    final values = points.isEmpty
        ? <double>[3, 5, 4, 6, 5, 7, 6, 8, 6, 7, 8, 9]
        : points.map((p) => p.value).toList();
    final labels = points.isEmpty
        ? List<String>.generate(values.length, (i) => '${i + 1}')
        : points.map((p) => p.label).toList();
    return AppGCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'Faollik · ${values.length} hafta',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                    color: StudentColors.text,
                  ),
                ),
              ),
              const AppBadge(label: 'Live', tone: AppBadgeTone.teal, dark: true),
            ],
          ),
          const SizedBox(height: 8),
          AppMiniBarChart(
            values: values,
            labels: labels,
            color: StudentColors.primary,
            height: 80,
            labelColor: StudentColors.textMuted,
          ),
        ],
      ),
    );
  }
}
