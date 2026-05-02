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
import 'package:chaqmoq_mobile/widgets/app_bottom_sheet.dart';
import 'package:chaqmoq_mobile/widgets/app_card.dart';
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
        _ChaqmoqStatsCard(
          chaqmoq: data.chaqmoq,
          onTap: widget.onOpenProgress,
        ),
        const SizedBox(height: 14),
        _StatsGrid(
          stats: data.stats,
          onAttendance: widget.onOpenAttendance,
          onPayments: widget.onOpenPayments,
          onProgress: widget.onOpenProgress,
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

class _ChaqmoqStatsCard extends StatelessWidget {
  const _ChaqmoqStatsCard({required this.chaqmoq, this.onTap});

  final ParentChaqmoqStatsModel chaqmoq;
  final VoidCallback? onTap;

  static const List<String> _ozMonthsShort = <String>[
    'Yan', 'Fev', 'Mar', 'Apr', 'May', 'Iyn',
    'Iyl', 'Avg', 'Sen', 'Okt', 'Noy', 'Dek',
  ];

  @override
  Widget build(BuildContext context) {
    final months = chaqmoq.monthly;
    final maxValue = months.fold<int>(
      1,
      (acc, m) => m.earned > acc ? m.earned : acc,
    );
    final lastIndex = months.length - 1;

    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: Container(
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(20),
            gradient: const LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: <Color>[Color(0xFF1E73F8), Color(0xFF4F8FFA)],
            ),
            boxShadow: const <BoxShadow>[
              BoxShadow(
                color: Color(0x331E73F8),
                blurRadius: 20,
                offset: Offset(0, 8),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                children: <Widget>[
                  Container(
                    width: 30,
                    height: 30,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.18),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(
                      Icons.bolt_rounded,
                      color: Colors.white,
                      size: 17,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: <Widget>[
                        Text(
                          'Chaqmoq balansi',
                          style: ParentTextStyles.label.copyWith(
                            color: const Color(0xFFE0EBFF),
                            fontSize: 11,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 0.4,
                          ),
                        ),
                        const SizedBox(height: 1),
                        Text(
                          '${chaqmoq.balance}',
                          style: ParentTextStyles.title.copyWith(
                            color: Colors.white,
                            fontSize: 26,
                            height: 1.05,
                            letterSpacing: -0.4,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  _ThisMonthDelta(
                    earned: chaqmoq.thisMonthEarned,
                    lost: chaqmoq.thisMonthLost,
                  ),
                ],
              ),
              const SizedBox(height: 12),
              LayoutBuilder(
                builder: (context, constraints) {
                  // Card kengligi mobil ekranda 320..480 atrofida bo'ladi.
                  // Tor ekranlarda oy yorlig'ini qisqartirib (3 harf), katta
                  // ekranlarda esa to'la qisqa nomda chiqaramiz.
                  final showLabels = constraints.maxWidth > 220;
                  // Diagramma uchun yetarli, lekin overflow qilmaydigan
                  // baland mezon. Adaptiv: bar 36..44 oralig'ida.
                  final chartHeight = constraints.maxWidth < 320 ? 64.0 : 72.0;
                  return SizedBox(
                    height: chartHeight,
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: <Widget>[
                        for (var i = 0; i < months.length; i++) ...<Widget>[
                          if (i > 0) const SizedBox(width: 6),
                          Expanded(
                            child: _ChaqmoqMonthBar(
                              month: months[i],
                              maxValue: maxValue,
                              isCurrent: i == lastIndex,
                              monthShortLabel: showLabels
                                  ? _ozMonthsShort[(months[i].month - 1) % 12]
                                  : '',
                            ),
                          ),
                        ],
                      ],
                    ),
                  );
                },
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ThisMonthDelta extends StatelessWidget {
  const _ThisMonthDelta({required this.earned, required this.lost});

  final int earned;
  final int lost;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.end,
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        Text(
          'Bu oy',
          style: ParentTextStyles.label.copyWith(
            color: const Color(0xFFC2DDFF),
            fontSize: 10.5,
            fontWeight: FontWeight.w700,
            letterSpacing: 0.4,
          ),
        ),
        const SizedBox(height: 4),
        Row(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
              decoration: BoxDecoration(
                color: const Color(0xFF10B981).withValues(alpha: 0.22),
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text(
                '+$earned',
                style: ParentTextStyles.label.copyWith(
                  color: const Color(0xFFB7F7DC),
                  fontSize: 11,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
            const SizedBox(width: 4),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
              decoration: BoxDecoration(
                color: const Color(0xFFEF4444).withValues(alpha: 0.22),
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text(
                '−$lost',
                style: ParentTextStyles.label.copyWith(
                  color: const Color(0xFFFFC7C7),
                  fontSize: 11,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _ChaqmoqMonthBar extends StatelessWidget {
  const _ChaqmoqMonthBar({
    required this.month,
    required this.maxValue,
    required this.isCurrent,
    required this.monthShortLabel,
  });

  final ParentChaqmoqMonth month;
  final int maxValue;
  final bool isCurrent;
  final String monthShortLabel;

  @override
  Widget build(BuildContext context) {
    final ratio = maxValue <= 0
        ? 0.0
        : (month.earned / maxValue).clamp(0.0, 1.0).toDouble();
    final barColor = isCurrent
        ? Colors.white
        : Colors.white.withValues(alpha: 0.45);
    final textColor = isCurrent
        ? Colors.white
        : const Color(0xFFC2DDFF);
    return LayoutBuilder(
      builder: (context, constraints) {
        // Matn satrlari uchun aniq joy (FittedBox bilan ham himoyalangan).
        // Overflow qilmasligi uchun real font geometriyasidan ham ko'proq
        // joy ajratamiz.
        const valueLineHeight = 13.0;
        const labelLineHeight = 13.0;
        const verticalGap = 2.0;
        final hasMonthLabel = monthShortLabel.isNotEmpty;
        final reserved = valueLineHeight +
            verticalGap +
            verticalGap +
            (hasMonthLabel ? labelLineHeight : 0.0);
        final available = constraints.maxHeight - reserved;
        final maxBar = available.isFinite
            ? available.clamp(4.0, 44.0)
            : 32.0;
        final barHeight = ratio == 0
            ? 4.0
            : (maxBar * ratio).clamp(4.0, maxBar);
        return Column(
          mainAxisAlignment: MainAxisAlignment.end,
          mainAxisSize: MainAxisSize.max,
          children: <Widget>[
            SizedBox(
              height: valueLineHeight,
              child: FittedBox(
                fit: BoxFit.scaleDown,
                child: Text(
                  '${month.earned}',
                  maxLines: 1,
                  textAlign: TextAlign.center,
                  style: ParentTextStyles.label.copyWith(
                    color: textColor,
                    fontSize: 10.5,
                    height: 1.0,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ),
            const SizedBox(height: verticalGap),
            Container(
              height: barHeight,
              decoration: BoxDecoration(
                color: barColor,
                borderRadius: BorderRadius.circular(6),
              ),
            ),
            if (hasMonthLabel) ...<Widget>[
              const SizedBox(height: verticalGap),
              SizedBox(
                height: labelLineHeight,
                child: FittedBox(
                  fit: BoxFit.scaleDown,
                  child: Text(
                    monthShortLabel,
                    maxLines: 1,
                    textAlign: TextAlign.center,
                    style: ParentTextStyles.label.copyWith(
                      color: textColor,
                      fontSize: 10.5,
                      height: 1.0,
                      fontWeight:
                          isCurrent ? FontWeight.w800 : FontWeight.w600,
                    ),
                  ),
                ),
              ),
            ],
          ],
        );
      },
    );
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
        sub: stats.debtAmount <= 0 ? 'To‘liq to‘langan' : 'Qarzdor',
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
