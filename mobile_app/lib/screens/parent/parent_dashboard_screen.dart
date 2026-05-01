import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/parent_colors.dart';
import 'package:chaqmoq_mobile/core/theme/parent_text_styles.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/parent_models.dart';
import 'package:chaqmoq_mobile/providers/notifications_provider.dart';
import 'package:chaqmoq_mobile/providers/parent_dashboard_provider.dart';
import 'package:chaqmoq_mobile/screens/parent/add_child_screen.dart';
import 'package:chaqmoq_mobile/screens/parent/parent_ui.dart';
import 'package:chaqmoq_mobile/widgets/app_avatar.dart';
import 'package:chaqmoq_mobile/widgets/app_badge.dart';
import 'package:chaqmoq_mobile/widgets/app_bottom_sheet.dart';
import 'package:chaqmoq_mobile/widgets/app_card.dart';
import 'package:chaqmoq_mobile/widgets/app_mini_line_chart.dart';
import 'package:chaqmoq_mobile/widgets/app_parent_app_bar.dart';
import 'package:chaqmoq_mobile/widgets/app_state_widgets.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

/// Redesigned Parent Dashboard — mirrors the JSX `ParentDashboard` layout:
/// header → blue gradient selected-child card → 2x2 stats → progress chart →
/// quick actions row.
class ParentDashboardScreen extends StatefulWidget {
  const ParentDashboardScreen({
    super.key,
    this.showBottomNav = true,
    this.onOpenDrawer,
    this.onOpenNotifications,
    this.onOpenAttendance,
    this.onOpenPayments,
    this.onOpenProgress,
    this.onOpenProfile,
  });

  final bool showBottomNav;
  final VoidCallback? onOpenDrawer;
  final VoidCallback? onOpenNotifications;
  final VoidCallback? onOpenAttendance;
  final VoidCallback? onOpenPayments;
  final VoidCallback? onOpenProgress;
  final VoidCallback? onOpenProfile;

  @override
  State<ParentDashboardScreen> createState() => _ParentDashboardScreenState();
}

class _ParentDashboardScreenState extends State<ParentDashboardScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      context.read<ParentDashboardProvider>().load();
      context.read<NotificationsProvider>().load();
    });
  }

  Future<void> _refresh() async {
    await Future.wait([
      context.read<ParentDashboardProvider>().refresh(),
      context.read<NotificationsProvider>().refresh(),
    ]);
  }

  Future<void> _openSelector(ParentDashboardModel data) async {
    await AppBottomSheet.show<void>(
      context: context,
      title: 'Farzandni tanlang',
      builder: (sheetContext) => _ChildSelectorContent(
        children: data.children,
        selectedId: data.selectedChild.id,
        onPick: (child) async {
          Navigator.of(sheetContext).pop();
          await context.read<ParentDashboardProvider>().selectChild(child.id);
        },
        onAdd: () async {
          Navigator.of(sheetContext).pop();
          final ParentChildModel? created = await Navigator.of(context)
              .push<ParentChildModel>(
                MaterialPageRoute<ParentChildModel>(
                  builder: (_) => const AddChildScreen(),
                ),
              );
          if (created != null && mounted) {
            await context
                .read<ParentDashboardProvider>()
                .selectChild(created.id);
            if (!mounted) return;
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Farzand muvaffaqiyatli qo‘shildi')),
            );
          }
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final dashboard = context.watch<ParentDashboardProvider>();
    final notifications = context.watch<NotificationsProvider>();
    final data = dashboard.data;
    final hasData = data != null && data.selectedChild.id > 0;
    final unreadCount = ParentUi.resolveUnreadCount(
      notifications: notifications,
      fallback: data?.unreadNotifications ?? 0,
    );

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.dark,
        statusBarBrightness: Brightness.light,
        systemNavigationBarColor: Colors.white,
        systemNavigationBarIconBrightness: Brightness.dark,
      ),
      child: Scaffold(
        backgroundColor: ParentColors.bg,
        body: SafeArea(
          child: RefreshIndicator(
            color: ParentColors.primary,
            onRefresh: _refresh,
            child: _buildBody(context, dashboard, data, hasData, unreadCount),
          ),
        ),
      ),
    );
  }

  Widget _buildBody(
    BuildContext context,
    ParentDashboardProvider dashboard,
    ParentDashboardModel? data,
    bool hasData,
    int unreadCount,
  ) {
    if (dashboard.state == ViewState.loading && data == null) {
      return const AppLoadingState();
    }

    if (dashboard.state == ViewState.error && data == null) {
      return AppErrorState(
        title: 'Bosh sahifa yuklanmadi',
        message:
            dashboard.errorMessage ??
            'Server bilan aloqa yo‘q. Qayta urinib ko‘ring.',
        onRetry: () => dashboard.load(force: true),
      );
    }

    if (!hasData) {
      return AppEmptyState(
        title: 'Farzand topilmadi',
        subtitle:
            'Bu profilga bog‘langan farzand ma’lumotlari hali topilmadi.',
        icon: Icons.child_care_rounded,
        ctaLabel: 'Farzand qo‘shish',
        ctaIcon: Icons.add_rounded,
        onCta: () => _openAddChildScreen(),
      );
    }

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(
        parent: BouncingScrollPhysics(),
      ),
      padding: const EdgeInsets.fromLTRB(18, 4, 18, 100),
      children: [
        _Header(
          parent: data!.parent,
          unreadCount: unreadCount,
          onMenuTap: widget.onOpenDrawer,
          onBellTap: widget.onOpenNotifications,
          onAvatarTap: widget.onOpenProfile,
        ),
        const SizedBox(height: 14),
        _SelectedChildCard(
          child: data.selectedChild,
          stats: data.stats,
          onTap: () => _openSelector(data),
        ),
        const SizedBox(height: 14),
        _StatsGrid(
          stats: data.stats,
          onAttendance: widget.onOpenAttendance,
          onPayments: widget.onOpenPayments,
          onProgress: widget.onOpenProgress,
        ),
        const SizedBox(height: 14),
        _ProgressChartCard(
          series: data.progressChart,
          score: data.stats.averageScore,
        ),
        const SizedBox(height: 14),
        Text('Tezkor amallar', style: ParentTextStyles.sectionTitle),
        const SizedBox(height: 10),
        _QuickActions(
          onAttendance: widget.onOpenAttendance,
          onPayments: widget.onOpenPayments,
          onProgress: widget.onOpenProgress,
          onMessages: widget.onOpenNotifications,
        ),
      ],
    );
  }

  Future<void> _openAddChildScreen() async {
    final ParentChildModel? child = await Navigator.of(context)
        .push<ParentChildModel>(
          MaterialPageRoute<ParentChildModel>(
            builder: (_) => const AddChildScreen(),
          ),
        );
    if (child != null && mounted) {
      await context.read<ParentDashboardProvider>().selectChild(child.id);
    }
  }
}

class _Header extends StatelessWidget {
  const _Header({
    required this.parent,
    required this.unreadCount,
    this.onMenuTap,
    this.onBellTap,
    this.onAvatarTap,
  });

  final UserModel parent;
  final int unreadCount;
  final VoidCallback? onMenuTap;
  final VoidCallback? onBellTap;
  final VoidCallback? onAvatarTap;

  @override
  Widget build(BuildContext context) {
    final firstName = Formatters.firstName(parent.fullName);
    final greeting = firstName.isEmpty ? 'Ota-ona' : firstName;

    return Row(
      children: [
        AppParentIconButton(icon: Icons.menu_rounded, onTap: onMenuTap ?? () {}),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'Assalomu alaykum,',
                style: GoogleFonts.inter(
                  fontSize: 11.5,
                  fontWeight: FontWeight.w600,
                  color: ParentColors.textMuted,
                ),
              ),
              const SizedBox(height: 1),
              Text(
                '$greeting aka 👋',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: GoogleFonts.inter(
                  fontSize: 16,
                  fontWeight: FontWeight.w800,
                  color: ParentColors.text,
                  letterSpacing: -0.2,
                ),
              ),
            ],
          ),
        ),
        AppParentIconButton(
          icon: Icons.notifications_outlined,
          onTap: onBellTap ?? () {},
          badgeCount: unreadCount,
        ),
        const SizedBox(width: 8),
        GestureDetector(
          onTap: onAvatarTap,
          child: AppAvatar(
            name: parent.fullName.isEmpty ? 'Ota-ona' : parent.fullName,
            size: 40,
            color: AppAvatarColor.slate,
            imageUrl: parent.avatarUrl,
          ),
        ),
      ],
    );
  }
}

class _SelectedChildCard extends StatelessWidget {
  const _SelectedChildCard({
    required this.child,
    required this.stats,
    required this.onTap,
  });

  final ParentChildModel child;
  final ParentStatsModel stats;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final groupLine = _groupLine(child);
    final nextLessonText = _nextLessonText(stats.nextPaymentDate);

    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(AppRadius.xxl),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppRadius.xxl),
        child: Stack(
          children: [
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                gradient: ParentColors.heroBlueGradient,
                borderRadius: BorderRadius.circular(AppRadius.xxl),
                boxShadow: const [
                  BoxShadow(
                    color: Color(0x522563EB),
                    blurRadius: 30,
                    offset: Offset(0, 14),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          'TANLANGAN FARZAND',
                          style: GoogleFonts.inter(
                            fontSize: 11,
                            fontWeight: FontWeight.w800,
                            color: Colors.white.withAlpha((0.85 * 255).round()),
                            letterSpacing: 1.5,
                          ),
                        ),
                      ),
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            'Almashtirish',
                            style: GoogleFonts.inter(
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                              color: Colors.white,
                            ),
                          ),
                          const SizedBox(width: 4),
                          const Icon(
                            Icons.swap_horiz_rounded,
                            color: Colors.white,
                            size: 16,
                          ),
                        ],
                      ),
                    ],
                  ),
                  const SizedBox(height: 14),
                  Row(
                    children: [
                      Container(
                        width: 56,
                        height: 56,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          color: Colors.white.withAlpha((0.2 * 255).round()),
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: Colors.white.withAlpha((0.4 * 255).round()),
                            width: 2,
                          ),
                        ),
                        child: Text(
                          _initials(child.fullName),
                          style: GoogleFonts.inter(
                            fontSize: 18,
                            fontWeight: FontWeight.w800,
                            color: Colors.white,
                          ),
                        ),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              child.fullName.isEmpty
                                  ? 'Farzand'
                                  : child.fullName,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: GoogleFonts.inter(
                                fontSize: 19,
                                fontWeight: FontWeight.w800,
                                color: Colors.white,
                                letterSpacing: -0.2,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              groupLine,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: GoogleFonts.inter(
                                fontSize: 12.5,
                                fontWeight: FontWeight.w500,
                                color: Colors.white.withAlpha((0.9 * 255).round()),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 14),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 10,
                    ),
                    decoration: BoxDecoration(
                      color: Colors.white.withAlpha((0.14 * 255).round()),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Row(
                      children: [
                        const Icon(
                          Icons.schedule_rounded,
                          color: Colors.white,
                          size: 18,
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            nextLessonText,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: GoogleFonts.inter(
                              fontSize: 12.5,
                              fontWeight: FontWeight.w600,
                              color: Colors.white,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            // decorative blobs
            Positioned(
              top: -40,
              right: -30,
              child: IgnorePointer(
                child: Container(
                  width: 160,
                  height: 160,
                  decoration: BoxDecoration(
                    color: Colors.white.withAlpha((0.1 * 255).round()),
                    shape: BoxShape.circle,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  static String _initials(String name) {
    return Formatters.initials(name);
  }

  static String _groupLine(ParentChildModel child) {
    final parts = <String>[
      if (child.className.trim().isNotEmpty) child.className.trim(),
      if (child.groupName.trim().isNotEmpty) child.groupName.trim(),
    ];
    return parts.isEmpty ? 'Guruh biriktirilmagan' : parts.join(' · ');
  }

  static String _nextLessonText(DateTime? next) {
    if (next == null) return 'Keyingi dars: jadval kelishi kutilmoqda';
    return 'Keyingi to‘lov: ${Formatters.shortDayMonth(next)}';
  }
}

class _StatsGrid extends StatelessWidget {
  const _StatsGrid({
    required this.stats,
    this.onAttendance,
    this.onPayments,
    this.onProgress,
  });

  final ParentStatsModel stats;
  final VoidCallback? onAttendance;
  final VoidCallback? onPayments;
  final VoidCallback? onProgress;

  @override
  Widget build(BuildContext context) {
    final tiles = <_StatTile>[
      _StatTile(
        icon: Icons.fact_check_outlined,
        iconBg: ParentColors.successBg,
        iconFg: ParentColors.success,
        label: 'Davomat',
        value: '${stats.attendancePercent}%',
        sub: 'Bu oy',
        trendUp: stats.attendancePercent >= 80,
        onTap: onAttendance,
      ),
      _StatTile(
        icon: Icons.account_balance_wallet_outlined,
        iconBg: stats.debtAmount <= 0
            ? ParentColors.successBg
            : ParentColors.dangerBg,
        iconFg: stats.debtAmount <= 0
            ? ParentColors.success
            : ParentColors.danger,
        label: 'Qarzdorlik',
        value: stats.debtAmount <= 0
            ? '0 so‘m'
            : '${_compactSom(stats.debtAmount)} so‘m',
        sub: stats.debtAmount <= 0 ? 'To‘liq to‘langan' : 'Muddati o‘tgan',
        onTap: onPayments,
      ),
      _StatTile(
        icon: Icons.grade_outlined,
        iconBg: ParentColors.amberBg,
        iconFg: ParentColors.amberDeep,
        label: 'O‘rtacha ball',
        value: '${stats.averageScore}%',
        sub: '5 dan',
        trendUp: stats.averageScore >= 70,
        onTap: onProgress,
      ),
      _StatTile(
        icon: Icons.event_outlined,
        iconBg: ParentColors.infoBg,
        iconFg: ParentColors.primaryDeep,
        label: 'Keyingi to‘lov',
        value: stats.nextPaymentDate == null
            ? '—'
            : Formatters.shortDayMonth(stats.nextPaymentDate),
        sub: stats.debtAmount > 0
            ? '${_compactSom(stats.debtAmount)} so‘m'
            : 'To‘lov yo‘q',
        onTap: onPayments,
      ),
    ];

    return GridView.count(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisCount: 2,
      mainAxisSpacing: 10,
      crossAxisSpacing: 10,
      childAspectRatio: 1.42,
      children: tiles,
    );
  }
}

class _StatTile extends StatelessWidget {
  const _StatTile({
    required this.icon,
    required this.iconBg,
    required this.iconFg,
    required this.label,
    required this.value,
    required this.sub,
    this.trendUp,
    this.onTap,
  });

  final IconData icon;
  final Color iconBg;
  final Color iconFg;
  final String label;
  final String value;
  final String sub;
  final bool? trendUp;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return AppPCard(
      onTap: onTap,
      borderRadius: BorderRadius.circular(18),
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Container(
                width: 32,
                height: 32,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: iconBg,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: iconFg, size: 18),
              ),
              const Spacer(),
              if (trendUp != null)
                Icon(
                  trendUp! ? Icons.trending_up_rounded : Icons.trending_down_rounded,
                  color: trendUp! ? ParentColors.success : ParentColors.danger,
                  size: 16,
                ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: ParentTextStyles.bodySm,
          ),
          const SizedBox(height: 1),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(value, style: ParentTextStyles.value),
          ),
          const SizedBox(height: 1),
          Text(
            sub,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: GoogleFonts.inter(
              fontSize: 10.5,
              fontWeight: FontWeight.w600,
              color: ParentColors.textMuted,
            ),
          ),
        ],
      ),
    );
  }
}

class _ProgressChartCard extends StatelessWidget {
  const _ProgressChartCard({required this.series, required this.score});

  final List<ParentProgressSeries> series;
  final int score;

  @override
  Widget build(BuildContext context) {
    final points = series.isNotEmpty && series.first.points.isNotEmpty
        ? series.first.points
        : <double>[];
    return AppPCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Bilim darajasi', style: ParentTextStyles.bodySm),
                    const SizedBox(height: 4),
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text(
                          score > 0 ? (score / 20).toStringAsFixed(1) : '—',
                          style: GoogleFonts.inter(
                            fontSize: 22,
                            fontWeight: FontWeight.w800,
                            color: ParentColors.text,
                            letterSpacing: -0.4,
                          ),
                        ),
                        const SizedBox(width: 4),
                        Padding(
                          padding: const EdgeInsets.only(bottom: 2),
                          child: Text(
                            '/ 5',
                            style: GoogleFonts.inter(
                              fontSize: 13,
                              fontWeight: FontWeight.w600,
                              color: ParentColors.textMuted,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const AppBadge(
                label: '+0.3 oy ichida',
                tone: AppBadgeTone.success,
                icon: Icons.trending_up_rounded,
              ),
            ],
          ),
          const SizedBox(height: 8),
          if (points.length >= 2)
            AppMiniLineChart(
              values: points,
              color: ParentColors.primary,
              height: 70,
            )
          else
            SizedBox(
              height: 70,
              child: Center(
                child: Text(
                  'Progress ma’lumoti yo‘q',
                  style: ParentTextStyles.bodyMuted,
                ),
              ),
            ),
          const SizedBox(height: 4),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              for (final m in const ['Yan', 'Fev', 'Mar', 'Apr', 'May'])
                Text(
                  m,
                  style: GoogleFonts.inter(
                    fontSize: 10.5,
                    fontWeight: FontWeight.w600,
                    color: ParentColors.textMuted,
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _QuickActions extends StatelessWidget {
  const _QuickActions({
    this.onAttendance,
    this.onPayments,
    this.onProgress,
    this.onMessages,
  });

  final VoidCallback? onAttendance;
  final VoidCallback? onPayments;
  final VoidCallback? onProgress;
  final VoidCallback? onMessages;

  @override
  Widget build(BuildContext context) {
    final tiles = <_QuickActionTile>[
      _QuickActionTile(
        icon: Icons.fact_check_outlined,
        label: 'Davomat',
        bg: ParentColors.successBg,
        fg: ParentColors.success,
        onTap: onAttendance,
      ),
      _QuickActionTile(
        icon: Icons.payments_outlined,
        label: 'To‘lov',
        bg: ParentColors.infoBg,
        fg: ParentColors.primaryDeep,
        onTap: onPayments,
      ),
      _QuickActionTile(
        icon: Icons.insights_outlined,
        label: 'Progress',
        bg: ParentColors.amberBg,
        fg: ParentColors.amberDeep,
        onTap: onProgress,
      ),
      _QuickActionTile(
        icon: Icons.forum_outlined,
        label: 'Xabar',
        bg: ParentColors.violetBg,
        fg: ParentColors.violet,
        onTap: onMessages,
      ),
    ];

    return Row(
      children: [
        for (var i = 0; i < tiles.length; i++) ...[
          Expanded(child: tiles[i]),
          if (i < tiles.length - 1) const SizedBox(width: 8),
        ],
      ],
    );
  }
}

class _QuickActionTile extends StatelessWidget {
  const _QuickActionTile({
    required this.icon,
    required this.label,
    required this.bg,
    required this.fg,
    this.onTap,
  });

  final IconData icon;
  final String label;
  final Color bg;
  final Color fg;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return AppPCard(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 12),
      borderRadius: BorderRadius.circular(16),
      onTap: onTap,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 36,
            height: 36,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: bg,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, color: fg, size: 20),
          ),
          const SizedBox(height: 6),
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: GoogleFonts.inter(
              fontSize: 11.5,
              fontWeight: FontWeight.w700,
              color: ParentColors.text,
            ),
          ),
        ],
      ),
    );
  }
}

class _ChildSelectorContent extends StatelessWidget {
  const _ChildSelectorContent({
    required this.children,
    required this.selectedId,
    required this.onPick,
    required this.onAdd,
  });

  final List<ParentChildModel> children;
  final int selectedId;
  final void Function(ParentChildModel) onPick;
  final VoidCallback onAdd;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        for (final child in children) ...[
          _ChildOptionTile(
            child: child,
            selected: child.id == selectedId,
            onTap: () => onPick(child),
          ),
          const SizedBox(height: 10),
        ],
        Material(
          color: Colors.transparent,
          borderRadius: BorderRadius.circular(16),
          child: InkWell(
            onTap: onAdd,
            borderRadius: BorderRadius.circular(16),
            child: Container(
              padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 16),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color: ParentColors.lineStrong,
                  width: 1.5,
                  style: BorderStyle.solid,
                ),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(
                    Icons.add_rounded,
                    color: ParentColors.primary,
                    size: 20,
                  ),
                  const SizedBox(width: 8),
                  Text(
                    'Yangi farzand qo‘shish',
                    style: GoogleFonts.inter(
                      fontSize: 13.5,
                      fontWeight: FontWeight.w700,
                      color: ParentColors.primary,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _ChildOptionTile extends StatelessWidget {
  const _ChildOptionTile({
    required this.child,
    required this.selected,
    required this.onTap,
  });

  final ParentChildModel child;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final groupLine = _groupLine(child);
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
          decoration: BoxDecoration(
            color: selected ? ParentColors.primaryTint : ParentColors.card,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: selected ? ParentColors.primary : ParentColors.line,
              width: 1.5,
            ),
          ),
          child: Row(
            children: [
              AppAvatar(
                name: child.fullName,
                size: 44,
                color: _avatarColor(child),
                imageUrl: child.avatarUrl,
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      child.fullName,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: GoogleFonts.inter(
                        fontSize: 14,
                        fontWeight: FontWeight.w800,
                        color: ParentColors.text,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      groupLine,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: ParentTextStyles.bodyMuted,
                    ),
                  ],
                ),
              ),
              if (selected)
                Container(
                  width: 24,
                  height: 24,
                  alignment: Alignment.center,
                  decoration: const BoxDecoration(
                    color: ParentColors.primary,
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(Icons.check_rounded, color: Colors.white, size: 16),
                ),
            ],
          ),
        ),
      ),
    );
  }

  static String _groupLine(ParentChildModel child) {
    final parts = <String>[
      if (child.className.trim().isNotEmpty) child.className.trim(),
      if (child.groupName.trim().isNotEmpty) child.groupName.trim(),
    ];
    return parts.isEmpty ? 'Guruh biriktirilmagan' : parts.join(' · ');
  }
}

AppAvatarColor _avatarColor(ParentChildModel child) {
  // Stable mapping based on id
  const palette = [
    AppAvatarColor.blue,
    AppAvatarColor.amber,
    AppAvatarColor.teal,
    AppAvatarColor.violet,
    AppAvatarColor.rose,
  ];
  return palette[child.id.abs() % palette.length];
}

String _compactSom(int v) {
  if (v == 0) return '0';
  if (v >= 1000000) {
    return (v / 1000000).toStringAsFixed(v % 1000000 == 0 ? 0 : 1) + ' mln';
  }
  return (v / 1000).toStringAsFixed(0) + ' K';
}
