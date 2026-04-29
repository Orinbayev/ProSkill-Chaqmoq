import 'dart:math' as math;

import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/parent_models.dart';
import 'package:chaqmoq_mobile/providers/parent_dashboard_provider.dart';
import 'package:chaqmoq_mobile/screens/parent/add_child_screen.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

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
      if (mounted) {
        context.read<ParentDashboardProvider>().load();
      }
    });
  }

  Future<void> _selectChild(ParentChildModel child) async {
    Navigator.of(context).pop();
    await context.read<ParentDashboardProvider>().selectChild(child.id);
  }

  Future<void> _openAddChildScreen(BuildContext sheetContext) async {
    Navigator.of(sheetContext).pop();
    final ParentChildModel? child = await Navigator.of(context)
        .push<ParentChildModel>(
          MaterialPageRoute<ParentChildModel>(
            builder: (_) => const AddChildScreen(),
          ),
        );
    if (child != null && mounted) {
      await context.read<ParentDashboardProvider>().selectChild(child.id);
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Farzand muvaffaqiyatli qo‘shildi')),
      );
    }
  }

  void _showChildSelector(ParentDashboardModel data) {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) {
        return SafeArea(
          top: false,
          child: ConstrainedBox(
            constraints: BoxConstraints(
              maxHeight: MediaQuery.sizeOf(sheetContext).height * 0.72,
            ),
            child: Container(
              margin: const EdgeInsets.all(12),
              padding: const EdgeInsets.fromLTRB(18, 12, 18, 18),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(24),
                boxShadow: _ParentShadows.card,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 44,
                    height: 5,
                    margin: const EdgeInsets.only(bottom: 16),
                    decoration: BoxDecoration(
                      color: const Color(0xFFD8E0EC),
                      borderRadius: BorderRadius.circular(999),
                    ),
                  ),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      'Farzandni tanlang',
                      style: _ParentTextStyles.title.copyWith(fontSize: 18),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Flexible(
                    child: SingleChildScrollView(
                      child: Column(
                        children: [
                          for (final child in data.children)
                            Padding(
                              padding: const EdgeInsets.only(top: 8),
                              child: _ChildSelectorTile(
                                child: child,
                                selected: child.id == data.selectedChild.id,
                                onTap: () => _selectChild(child),
                              ),
                            ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 14),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton.icon(
                      onPressed: () => _openAddChildScreen(sheetContext),
                      style: FilledButton.styleFrom(
                        backgroundColor: const Color(0xFFEAF4FF),
                        foregroundColor: _ParentColors.primaryBlue,
                        elevation: 0,
                        padding: const EdgeInsets.symmetric(vertical: 15),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                      ),
                      icon: const Icon(Icons.add_rounded, size: 20),
                      label: Text(
                        'Farzand qo‘shish',
                        style: _ParentTextStyles.body.copyWith(
                          color: _ParentColors.primaryBlue,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final dashboard = context.watch<ParentDashboardProvider>();
    final data = dashboard.data;
    final hasData = data != null && data.selectedChild.id > 0;

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.dark,
        statusBarBrightness: Brightness.light,
        systemNavigationBarColor: Colors.white,
        systemNavigationBarIconBrightness: Brightness.dark,
      ),
      child: Scaffold(
        backgroundColor: _ParentColors.background,
        bottomNavigationBar: widget.showBottomNav ? const BottomNav() : null,
        body: SafeArea(
          child: RefreshIndicator(
            color: _ParentColors.primaryBlue,
            onRefresh: dashboard.refresh,
            child: SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(
                parent: BouncingScrollPhysics(),
              ),
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 32),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  HeaderBar(
                    parent: data?.parent,
                    unreadCount: data?.unreadNotifications ?? 0,
                    onMenuTap: widget.onOpenDrawer,
                    onBellTap: widget.onOpenNotifications,
                    onAvatarTap: widget.onOpenProfile,
                  ),
                  const SizedBox(height: 16),
                  if (dashboard.state == ViewState.loading && data == null)
                    const _DashboardLoading()
                  else if (dashboard.state == ViewState.error && data == null)
                    _DashboardStateCard(
                      title: 'Dashboard yuklanmadi',
                      message:
                          dashboard.errorMessage ??
                          'Server bilan aloqa yo‘q. Qayta urinib ko‘ring.',
                      buttonText: 'Qayta urinish',
                      onPressed: () => dashboard.load(force: true),
                    )
                  else if (!hasData)
                    const _DashboardStateCard(
                      title: 'Farzand topilmadi',
                      message:
                          'Bu profilga bog‘langan farzand ma’lumotlari hali topilmadi.',
                    )
                  else ...[
                    if (dashboard.state == ViewState.loading) ...[
                      const LinearProgressIndicator(
                        minHeight: 3,
                        color: _ParentColors.primaryBlue,
                        backgroundColor: Color(0xFFEAF4FF),
                      ),
                      const SizedBox(height: 10),
                    ],
                    ChildProfileCard(
                      child: data.selectedChild,
                      onTap: () => _showChildSelector(data),
                    ),
                    const SizedBox(height: 18),
                    SectionHeader(
                      title: 'Umumiy ko‘rsatkichlar',
                      actionText: 'Batafsil',
                      onTap: widget.onOpenProgress,
                    ),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        for (final entry in _statsFor(
                          data.stats,
                        ).asMap().entries) ...[
                          Expanded(child: StatCard(data: entry.value)),
                          if (entry.key != 3) const SizedBox(width: 8),
                        ],
                      ],
                    ),
                    const SizedBox(height: 18),
                    ProgressChartCard(
                      series: data.progressChart,
                      onDetailsTap: widget.onOpenProgress,
                    ),
                    const SizedBox(height: 18),
                    NotificationCard(
                      notifications: data.latestNotifications,
                      onSeeAll: widget.onOpenNotifications,
                      onNotificationTap: widget.onOpenNotifications,
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  List<StatCardData> _statsFor(ParentStatsModel stats) {
    final nextDate = _dateParts(stats.nextPaymentDate);
    return [
      StatCardData(
        icon: Icons.event_available_outlined,
        title: 'Davomat',
        value: '${stats.attendancePercent}%',
        subtitle: _attendanceStatus(stats.attendancePercent),
        accent: _ParentColors.green,
        background: const Color(0xFFF1FCF6),
        onTap: widget.onOpenAttendance,
      ),
      StatCardData(
        icon: Icons.account_balance_wallet_outlined,
        title: 'Qarzdorlik',
        value: Formatters.number(stats.debtAmount),
        subtitle: stats.debtAmount <= 0 ? 'Qarz yo‘q' : 'UZS',
        accent: stats.debtAmount <= 0
            ? _ParentColors.green
            : _ParentColors.purple,
        subtitleColor: stats.debtAmount <= 0
            ? _ParentColors.green
            : _ParentColors.secondaryText,
        background: const Color(0xFFF7F5FF),
        onTap: widget.onOpenPayments,
      ),
      StatCardData(
        icon: Icons.bar_chart_rounded,
        title: 'O‘rtacha ball',
        value: '${stats.averageScore}%',
        subtitle: _scoreStatus(stats.averageScore),
        accent: _ParentColors.orange,
        background: const Color(0xFFFFFAF0),
        onTap: widget.onOpenProgress,
      ),
      StatCardData(
        icon: Icons.assignment_turned_in_outlined,
        title: 'Keyingi to‘lov',
        value: nextDate.$1,
        subtitle: nextDate.$2,
        accent: _ParentColors.primaryBlue,
        background: const Color(0xFFF4F9FF),
        onTap: widget.onOpenPayments,
      ),
    ];
  }
}

class HeaderBar extends StatelessWidget {
  const HeaderBar({
    super.key,
    this.parent,
    this.unreadCount = 0,
    this.onMenuTap,
    this.onBellTap,
    this.onAvatarTap,
  });

  final UserModel? parent;
  final int unreadCount;
  final VoidCallback? onMenuTap;
  final VoidCallback? onBellTap;
  final VoidCallback? onAvatarTap;

  @override
  Widget build(BuildContext context) {
    final parentName = parent?.fullName.trim().isNotEmpty == true
        ? parent!.fullName
        : 'Ota-ona';
    return Row(
      children: [
        _CircleIconButton(
          icon: Icons.menu_rounded,
          iconSize: 26,
          onTap: onMenuTap ?? () {},
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 6,
                ),
                decoration: BoxDecoration(
                  color: const Color(0xFFEAF4FF),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  'Ota-ona paneli',
                  style: _ParentTextStyles.label.copyWith(
                    color: _ParentColors.primaryBlue,
                    fontSize: 11.5,
                  ),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Salom,',
                style: _ParentTextStyles.body.copyWith(
                  fontSize: 12.5,
                  color: _ParentColors.secondaryText,
                ),
              ),
              const SizedBox(height: 3),
              FittedBox(
                fit: BoxFit.scaleDown,
                alignment: Alignment.centerLeft,
                child: Text(
                  '$parentName 👋',
                  maxLines: 1,
                  style: _ParentTextStyles.title.copyWith(fontSize: 18),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(width: 8),
        Stack(
          clipBehavior: Clip.none,
          children: [
            _CircleIconButton(
              icon: Icons.notifications_none_rounded,
              iconSize: 25,
              onTap: onBellTap ?? () {},
            ),
            if (unreadCount > 0)
              Positioned(
                right: 4,
                top: 2,
                child: Container(
                  constraints: const BoxConstraints(minWidth: 18),
                  height: 18,
                  alignment: Alignment.center,
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  decoration: BoxDecoration(
                    color: _ParentColors.red,
                    borderRadius: BorderRadius.circular(999),
                    border: Border.all(color: Colors.white, width: 2),
                  ),
                  child: Text(
                    unreadCount > 99 ? '99+' : '$unreadCount',
                    style: _ParentTextStyles.label.copyWith(
                      color: Colors.white,
                      fontSize: 9.5,
                      height: 1,
                    ),
                  ),
                ),
              ),
          ],
        ),
        const SizedBox(width: 8),
        _ProfileAvatar(parent: parent, onTap: onAvatarTap ?? () {}),
      ],
    );
  }
}

class ChildProfileCard extends StatelessWidget {
  const ChildProfileCard({super.key, required this.child, required this.onTap});

  final ParentChildModel child;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final isCompact = MediaQuery.sizeOf(context).width < 380;
    final avatarSize = isCompact ? 56.0 : 64.0;
    final cardHeight = isCompact ? 92.0 : 102.0;
    final horizontalPadding = isCompact ? 14.0 : 18.0;
    final textGap = isCompact ? 12.0 : 16.0;
    final dropdownSize = isCompact ? 38.0 : 44.0;
    final groupLine = _childGroupLine(child);

    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(18),
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: onTap,
        child: Ink(
          height: cardHeight,
          padding: EdgeInsets.symmetric(
            horizontal: horizontalPadding,
            vertical: isCompact ? 14.0 : 16.0,
          ),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(18),
            gradient: const LinearGradient(
              begin: Alignment.centerLeft,
              end: Alignment.centerRight,
              colors: [Color(0xFF2F78FF), Color(0xFF2468F2)],
            ),
            boxShadow: const [
              BoxShadow(
                color: Color(0x332467F2),
                blurRadius: 24,
                offset: Offset(0, 12),
              ),
            ],
          ),
          child: Row(
            children: [
              Stack(
                clipBehavior: Clip.none,
                children: [
                  Container(
                    width: avatarSize,
                    height: avatarSize,
                    padding: const EdgeInsets.all(4),
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: Colors.white.withValues(alpha: 0.22),
                      border: Border.all(
                        color: Colors.white.withValues(alpha: 0.72),
                        width: 2.5,
                      ),
                    ),
                    child: _AvatarImage(
                      imageUrl: child.avatarUrl,
                      initials: Formatters.initials(child.fullName),
                      fallbackAsset: 'assets/images/parent_child_avatar.png',
                    ),
                  ),
                  Positioned(
                    right: -1,
                    bottom: 4,
                    child: Container(
                      width: isCompact ? 17 : 19,
                      height: isCompact ? 17 : 19,
                      decoration: BoxDecoration(
                        color: _ParentColors.green,
                        shape: BoxShape.circle,
                        border: Border.all(color: Colors.white, width: 4),
                      ),
                    ),
                  ),
                ],
              ),
              SizedBox(width: textGap),
              Expanded(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    FittedBox(
                      fit: BoxFit.scaleDown,
                      alignment: Alignment.centerLeft,
                      child: Text(
                        child.fullName,
                        maxLines: 1,
                        style: _ParentTextStyles.title.copyWith(
                          color: Colors.white,
                          fontSize: isCompact ? 18 : 20,
                        ),
                      ),
                    ),
                    SizedBox(height: isCompact ? 5 : 7),
                    FittedBox(
                      fit: BoxFit.scaleDown,
                      alignment: Alignment.centerLeft,
                      child: Text(
                        groupLine,
                        maxLines: 1,
                        style: _ParentTextStyles.body.copyWith(
                          color: Colors.white.withValues(alpha: 0.92),
                          fontSize: isCompact ? 13.5 : 15,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              SizedBox(width: isCompact ? 8 : 12),
              Container(
                width: dropdownSize,
                height: dropdownSize,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: Colors.white.withValues(alpha: 0.16),
                ),
                child: Icon(
                  Icons.keyboard_arrow_down_rounded,
                  color: Colors.white,
                  size: isCompact ? 27 : 30,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class SectionHeader extends StatelessWidget {
  const SectionHeader({
    super.key,
    required this.title,
    required this.actionText,
    this.onTap,
  });

  final String title;
  final String actionText;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(
            title,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: _ParentTextStyles.title.copyWith(fontSize: 18),
          ),
        ),
        TextButton(
          onPressed: onTap,
          style: TextButton.styleFrom(
            foregroundColor: _ParentColors.primaryBlue,
            padding: EdgeInsets.zero,
            minimumSize: const Size(0, 30),
            tapTargetSize: MaterialTapTargetSize.shrinkWrap,
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                actionText,
                style: _ParentTextStyles.link.copyWith(fontSize: 14.5),
              ),
              const SizedBox(width: 3),
              const Icon(Icons.chevron_right_rounded, size: 21),
            ],
          ),
        ),
      ],
    );
  }
}

class StatCard extends StatelessWidget {
  const StatCard({super.key, required this.data});

  final StatCardData data;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(18),
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: data.onTap,
        child: Ink(
          height: 118,
          padding: const EdgeInsets.fromLTRB(7, 10, 7, 9),
          decoration: BoxDecoration(
            color: data.background,
            borderRadius: BorderRadius.circular(18),
            border: Border.all(
              color: _ParentColors.border.withValues(alpha: 0.72),
            ),
            boxShadow: _ParentShadows.card,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    color: data.accent.withValues(alpha: 0.16),
                    shape: BoxShape.circle,
                  ),
                  child: Icon(data.icon, color: data.accent, size: 20),
                ),
              ),
              const Spacer(),
              SizedBox(
                height: 17,
                child: FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: Text(
                    data.title,
                    maxLines: 1,
                    style: _ParentTextStyles.body.copyWith(
                      color: _ParentColors.secondaryText,
                      fontSize: 11.5,
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 3),
              SizedBox(
                height: 23,
                child: FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: Text(
                    data.value,
                    maxLines: 1,
                    style: _ParentTextStyles.title.copyWith(
                      color: data.accent,
                      fontSize: 20,
                      letterSpacing: 0,
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 2),
              Text(
                data.subtitle,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: _ParentTextStyles.body.copyWith(
                  color: data.subtitleColor ?? _ParentColors.secondaryText,
                  fontSize: 11.5,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class ProgressChartCard extends StatelessWidget {
  const ProgressChartCard({
    super.key,
    required this.series,
    required this.onDetailsTap,
  });

  final List<ParentProgressSeries> series;
  final VoidCallback? onDetailsTap;

  @override
  Widget build(BuildContext context) {
    final chartSeries = _chartSeries(series);
    final months = _chartMonths(series);

    return _DashboardCard(
      padding: const EdgeInsets.fromLTRB(14, 14, 14, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeader(
            title: 'O‘quvdagi yutuqlar',
            actionText: 'Batafsil',
            onTap: onDetailsTap,
          ),
          const SizedBox(height: 12),
          if (chartSeries.isEmpty)
            const _InlineEmptyState(text: 'Progress ma’lumoti yo‘q')
          else
            LayoutBuilder(
              builder: (context, constraints) {
                final isNarrow = constraints.maxWidth < 320;
                if (isNarrow) {
                  return Column(
                    children: [
                      _ChartWithAxes(series: chartSeries, months: months),
                      const SizedBox(height: 10),
                      _ChartLegend(series: chartSeries, compact: true),
                    ],
                  );
                }

                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: _ChartWithAxes(
                        series: chartSeries,
                        months: months,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Padding(
                      padding: const EdgeInsets.only(top: 2),
                      child: _ChartLegend(series: chartSeries),
                    ),
                  ],
                );
              },
            ),
        ],
      ),
    );
  }
}

class NotificationCard extends StatelessWidget {
  const NotificationCard({
    super.key,
    required this.notifications,
    required this.onSeeAll,
    required this.onNotificationTap,
  });

  final List<ParentNotificationModel> notifications;
  final VoidCallback? onSeeAll;
  final VoidCallback? onNotificationTap;

  @override
  Widget build(BuildContext context) {
    return _DashboardCard(
      padding: const EdgeInsets.fromLTRB(14, 14, 14, 14),
      child: Column(
        children: [
          SectionHeader(
            title: 'So‘nggi bildirishnomalar',
            actionText: 'Barchasi',
            onTap: onSeeAll,
          ),
          const SizedBox(height: 8),
          Container(
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: _ParentColors.border),
            ),
            child: Column(
              children: [
                if (notifications.isEmpty)
                  const _InlineEmptyState(text: 'Bildirishnoma yo‘q')
                else
                  for (
                    int index = 0;
                    index < notifications.length;
                    index++
                  ) ...[
                    _NotificationTile(
                      data: _notificationData(notifications[index]),
                      unread: !notifications[index].isRead,
                      onTap: onNotificationTap,
                    ),
                    if (index != notifications.length - 1)
                      const Padding(
                        padding: EdgeInsets.only(left: 86, right: 14),
                        child: Divider(height: 1, color: _ParentColors.border),
                      ),
                  ],
                const SizedBox(height: 8),
                Padding(
                  padding: const EdgeInsets.fromLTRB(14, 0, 14, 14),
                  child: SizedBox(
                    height: 46,
                    width: double.infinity,
                    child: TextButton(
                      onPressed: onSeeAll,
                      style: TextButton.styleFrom(
                        backgroundColor: const Color(0xFFEAF4FF),
                        foregroundColor: _ParentColors.primaryBlue,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(14),
                        ),
                      ),
                      child: Row(
                        children: [
                          const Spacer(),
                          Text(
                            'Barcha bildirishnomalar',
                            style: _ParentTextStyles.link.copyWith(
                              fontSize: 14.5,
                            ),
                          ),
                          const Spacer(),
                          const Icon(Icons.chevron_right_rounded, size: 22),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class BottomNav extends StatelessWidget {
  const BottomNav({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        boxShadow: [
          BoxShadow(
            color: Color(0x140B1220),
            blurRadius: 24,
            offset: Offset(0, -8),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
        child: BottomNavigationBar(
          currentIndex: 0,
          onTap: (_) {},
          type: BottomNavigationBarType.fixed,
          backgroundColor: Colors.white,
          elevation: 0,
          selectedItemColor: _ParentColors.primaryBlue,
          unselectedItemColor: _ParentColors.secondaryText,
          iconSize: 24,
          selectedFontSize: 11.5,
          unselectedFontSize: 11.5,
          selectedLabelStyle: _ParentTextStyles.label.copyWith(fontSize: 11.5),
          unselectedLabelStyle: _ParentTextStyles.label.copyWith(
            fontSize: 11.5,
            fontWeight: FontWeight.w600,
          ),
          items: const [
            BottomNavigationBarItem(
              icon: Icon(Icons.home_rounded),
              label: 'Bosh sahifa',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.event_available_outlined),
              label: 'Davomat',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.account_balance_wallet_outlined),
              label: 'To‘lovlar',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.bar_chart_rounded),
              label: 'Yutuqlar',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.person_rounded),
              label: 'Profil',
            ),
          ],
        ),
      ),
    );
  }
}

class _ChildSelectorTile extends StatelessWidget {
  const _ChildSelectorTile({
    required this.child,
    required this.selected,
    required this.onTap,
  });

  final ParentChildModel child;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            color: selected ? const Color(0xFFF4F9FF) : Colors.white,
            borderRadius: BorderRadius.circular(18),
            border: Border.all(
              color: selected
                  ? _ParentColors.primaryBlue
                  : const Color(0xFFE5EAF2),
            ),
          ),
          child: Row(
            children: [
              SizedBox(
                width: 44,
                height: 44,
                child: _AvatarImage(
                  imageUrl: child.avatarUrl,
                  initials: Formatters.initials(child.fullName),
                  fallbackAsset: 'assets/images/parent_child_avatar.png',
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      child.fullName,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: _ParentTextStyles.title.copyWith(fontSize: 15.5),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      _childGroupLine(child),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: _ParentTextStyles.body.copyWith(
                        color: _ParentColors.secondaryText,
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Icon(
                selected ? Icons.check_circle : Icons.chevron_right_rounded,
                color: selected
                    ? _ParentColors.primaryBlue
                    : const Color(0xFF9AA4B2),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ProfileAvatar extends StatelessWidget {
  const _ProfileAvatar({required this.parent, required this.onTap});

  final UserModel? parent;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final name = parent?.fullName.trim().isNotEmpty == true
        ? parent!.fullName
        : 'Ota-ona';
    return Material(
      color: Colors.transparent,
      shape: const CircleBorder(),
      child: InkWell(
        customBorder: const CircleBorder(),
        onTap: onTap,
        child: Container(
          width: 46,
          height: 46,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: const Color(0xFFEAF0F7),
            boxShadow: _ParentShadows.soft,
          ),
          clipBehavior: Clip.antiAlias,
          child: _AvatarImage(
            imageUrl: parent?.avatarUrl ?? '',
            initials: Formatters.initials(name),
            fallbackAsset: 'assets/images/parent_avatar.png',
          ),
        ),
      ),
    );
  }
}

class _AvatarImage extends StatelessWidget {
  const _AvatarImage({
    required this.imageUrl,
    required this.initials,
    required this.fallbackAsset,
  });

  final String imageUrl;
  final String initials;
  final String fallbackAsset;

  @override
  Widget build(BuildContext context) {
    final placeholder = Container(
      alignment: Alignment.center,
      decoration: const BoxDecoration(
        color: Color(0xFFEAF4FF),
        shape: BoxShape.circle,
      ),
      child: Text(
        initials,
        style: _ParentTextStyles.label.copyWith(
          color: _ParentColors.primaryBlue,
          fontSize: 14,
        ),
      ),
    );

    if (imageUrl.trim().isNotEmpty) {
      return ClipOval(
        child: Image.network(
          imageUrl,
          fit: BoxFit.cover,
          errorBuilder: (context, error, stackTrace) => placeholder,
        ),
      );
    }

    return ClipOval(
      child: Image.asset(
        fallbackAsset,
        fit: BoxFit.cover,
        errorBuilder: (context, error, stackTrace) => placeholder,
      ),
    );
  }
}

class _CircleIconButton extends StatelessWidget {
  const _CircleIconButton({
    required this.icon,
    required this.onTap,
    this.iconSize = 26,
  });

  final IconData icon;
  final VoidCallback onTap;
  final double iconSize;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white,
      shape: const CircleBorder(),
      elevation: 0,
      shadowColor: Colors.transparent,
      child: InkWell(
        customBorder: const CircleBorder(),
        onTap: onTap,
        child: Container(
          width: 46,
          height: 46,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: Colors.white,
            border: Border.all(color: _ParentColors.border),
            boxShadow: _ParentShadows.soft,
          ),
          child: Icon(icon, color: _ParentColors.text, size: iconSize),
        ),
      ),
    );
  }
}

class _DashboardCard extends StatelessWidget {
  const _DashboardCard({
    required this.child,
    this.padding = const EdgeInsets.all(18),
  });

  final Widget child;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _ParentColors.border),
        boxShadow: _ParentShadows.card,
      ),
      child: child,
    );
  }
}

class _DashboardLoading extends StatelessWidget {
  const _DashboardLoading();

  @override
  Widget build(BuildContext context) {
    return const SizedBox(
      height: 520,
      child: Center(
        child: CircularProgressIndicator(color: _ParentColors.primaryBlue),
      ),
    );
  }
}

class _DashboardStateCard extends StatelessWidget {
  const _DashboardStateCard({
    required this.title,
    required this.message,
    this.buttonText,
    this.onPressed,
  });

  final String title;
  final String message;
  final String? buttonText;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return _DashboardCard(
      padding: const EdgeInsets.fromLTRB(22, 32, 22, 32),
      child: Column(
        children: [
          const Icon(
            Icons.info_outline_rounded,
            color: _ParentColors.primaryBlue,
            size: 42,
          ),
          const SizedBox(height: 14),
          Text(
            title,
            textAlign: TextAlign.center,
            style: _ParentTextStyles.title.copyWith(fontSize: 20),
          ),
          const SizedBox(height: 8),
          Text(
            message,
            textAlign: TextAlign.center,
            style: _ParentTextStyles.body.copyWith(
              color: _ParentColors.secondaryText,
            ),
          ),
          if (buttonText != null && onPressed != null) ...[
            const SizedBox(height: 18),
            TextButton(
              onPressed: onPressed,
              style: TextButton.styleFrom(
                backgroundColor: const Color(0xFFEAF4FF),
                foregroundColor: _ParentColors.primaryBlue,
                padding: const EdgeInsets.symmetric(
                  horizontal: 22,
                  vertical: 12,
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14),
                ),
              ),
              child: Text(buttonText!, style: _ParentTextStyles.link),
            ),
          ],
        ],
      ),
    );
  }
}

class _InlineEmptyState extends StatelessWidget {
  const _InlineEmptyState({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: 72,
      child: Center(
        child: Text(
          text,
          style: _ParentTextStyles.body.copyWith(
            color: _ParentColors.secondaryText,
          ),
        ),
      ),
    );
  }
}

class _ChartWithAxes extends StatelessWidget {
  const _ChartWithAxes({required this.series, required this.months});

  final List<_ChartSeries> series;
  final List<String> months;

  @override
  Widget build(BuildContext context) {
    final pointCount = series.fold<int>(
      0,
      (previous, item) => math.max(previous, item.points.length),
    );
    final maxX = math.max(pointCount - 1, 1).toDouble();

    return SizedBox(
      height: 176,
      child: LineChart(
        LineChartData(
          minX: 0,
          maxX: maxX,
          minY: 0,
          maxY: 100,
          clipData: const FlClipData.all(),
          lineTouchData: LineTouchData(
            touchTooltipData: LineTouchTooltipData(
              getTooltipColor: (_) => _ParentColors.text,
              getTooltipItems: (spots) {
                return spots
                    .map(
                      (spot) => LineTooltipItem(
                        '${spot.y.toStringAsFixed(0)}%',
                        _ParentTextStyles.label.copyWith(color: Colors.white),
                      ),
                    )
                    .toList(growable: false);
              },
            ),
          ),
          gridData: FlGridData(
            show: true,
            drawVerticalLine: false,
            horizontalInterval: 25,
            getDrawingHorizontalLine: (_) {
              return const FlLine(color: _ParentColors.border, strokeWidth: 1);
            },
          ),
          borderData: FlBorderData(show: false),
          titlesData: FlTitlesData(
            topTitles: const AxisTitles(
              sideTitles: SideTitles(showTitles: false),
            ),
            rightTitles: const AxisTitles(
              sideTitles: SideTitles(showTitles: false),
            ),
            leftTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 36,
                interval: 25,
                getTitlesWidget: (value, meta) {
                  return Text(
                    '${value.toInt()}%',
                    style: _ParentTextStyles.body.copyWith(
                      color: _ParentColors.secondaryText,
                      fontSize: 11,
                    ),
                  );
                },
              ),
            ),
            bottomTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 24,
                interval: 1,
                getTitlesWidget: (value, meta) {
                  final index = value.round();
                  if (index < 0 || index >= pointCount) {
                    return const SizedBox.shrink();
                  }
                  final label = index < months.length
                      ? months[index]
                      : '${index + 1}';
                  return Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text(
                      label,
                      style: _ParentTextStyles.body.copyWith(
                        color: _ParentColors.secondaryText,
                        fontSize: 11,
                      ),
                    ),
                  );
                },
              ),
            ),
          ),
          lineBarsData: [
            for (final item in series)
              if (item.points.length > 1)
                LineChartBarData(
                  spots: [
                    for (var index = 0; index < item.points.length; index++)
                      FlSpot(
                        index.toDouble(),
                        item.points[index].clamp(0, 100),
                      ),
                  ],
                  isCurved: true,
                  preventCurveOverShooting: true,
                  color: item.color,
                  barWidth: 2.4,
                  isStrokeCapRound: true,
                  dotData: FlDotData(
                    show: true,
                    getDotPainter: (spot, percent, barData, index) {
                      return FlDotCirclePainter(
                        radius: 3.4,
                        color: Colors.white,
                        strokeWidth: 2,
                        strokeColor: item.color,
                      );
                    },
                  ),
                  belowBarData: BarAreaData(
                    show: true,
                    color: item.color.withValues(alpha: 0.06),
                  ),
                ),
          ],
        ),
      ),
    );
  }
}

class _ChartLegend extends StatelessWidget {
  const _ChartLegend({required this.series, this.compact = false});

  final List<_ChartSeries> series;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    if (compact) {
      return Wrap(
        spacing: 12,
        runSpacing: 8,
        children: series.map(_legendItem).toList(growable: false),
      );
    }

    return SizedBox(
      width: 98,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: series
            .map(
              (item) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: _legendItem(item),
              ),
            )
            .toList(growable: false),
      ),
    );
  }

  Widget _legendItem(_ChartSeries item) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 10,
          height: 10,
          margin: const EdgeInsets.only(top: 4),
          decoration: BoxDecoration(color: item.color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 7),
        Flexible(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                item.label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: _ParentTextStyles.body.copyWith(
                  fontSize: 14,
                  color: _ParentColors.secondaryText,
                ),
              ),
              const SizedBox(height: 3),
              Text(
                item.percent,
                style: _ParentTextStyles.title.copyWith(
                  color: item.color,
                  fontSize: 14.5,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _NotificationTile extends StatelessWidget {
  const _NotificationTile({
    required this.data,
    required this.unread,
    required this.onTap,
  });

  final _NotificationData data;
  final bool unread;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final compact = constraints.maxWidth < 290;
        final horizontalPadding = compact ? 10.0 : 14.0;
        final iconSize = compact ? 36.0 : 40.0;
        final gap = compact ? 7.0 : 10.0;

        return Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: onTap,
            child: Padding(
              padding: EdgeInsets.fromLTRB(
                horizontalPadding,
                12,
                horizontalPadding,
                12,
              ),
              child: Row(
                children: [
                  Container(
                    width: compact ? 7 : 8,
                    height: compact ? 7 : 8,
                    decoration: BoxDecoration(
                      color: unread
                          ? _ParentColors.primaryBlue
                          : const Color(0xFFCBD5E1),
                      shape: BoxShape.circle,
                    ),
                  ),
                  SizedBox(width: gap),
                  Container(
                    width: iconSize,
                    height: iconSize,
                    decoration: BoxDecoration(
                      color: data.iconBackground,
                      shape: BoxShape.circle,
                    ),
                    child: Icon(
                      data.icon,
                      color: data.iconColor,
                      size: compact ? 20 : 22,
                    ),
                  ),
                  SizedBox(width: gap),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          data.title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: _ParentTextStyles.title.copyWith(
                            fontSize: compact ? 15.5 : 17,
                            height: 1.15,
                          ),
                        ),
                        const SizedBox(height: 3),
                        Text(
                          data.subtitle,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: _ParentTextStyles.body.copyWith(
                            color: _ParentColors.secondaryText,
                            fontSize: compact ? 12 : 12.8,
                            height: 1.2,
                          ),
                        ),
                      ],
                    ),
                  ),
                  SizedBox(width: compact ? 5 : 8),
                  SizedBox(
                    width: compact ? 54 : 66,
                    child: Text(
                      data.time,
                      maxLines: 2,
                      textAlign: TextAlign.right,
                      overflow: TextOverflow.ellipsis,
                      style: _ParentTextStyles.body.copyWith(
                        color: _ParentColors.secondaryText,
                        fontSize: compact ? 10.8 : 11.5,
                        height: 1.18,
                      ),
                    ),
                  ),
                  SizedBox(width: compact ? 2 : 4),
                  Icon(
                    Icons.chevron_right_rounded,
                    color: const Color(0xFF9AA4B2),
                    size: compact ? 18 : 20,
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

class StatCardData {
  const StatCardData({
    required this.icon,
    required this.title,
    required this.value,
    required this.subtitle,
    required this.accent,
    required this.background,
    this.subtitleColor,
    this.onTap,
  });

  final IconData icon;
  final String title;
  final String value;
  final String subtitle;
  final Color accent;
  final Color background;
  final Color? subtitleColor;
  final VoidCallback? onTap;
}

class _ChartSeries {
  const _ChartSeries({
    required this.label,
    required this.percent,
    required this.color,
    required this.points,
  });

  final String label;
  final String percent;
  final Color color;
  final List<double> points;
}

class _NotificationData {
  const _NotificationData({
    required this.icon,
    required this.iconColor,
    required this.iconBackground,
    required this.title,
    required this.subtitle,
    required this.time,
  });

  final IconData icon;
  final Color iconColor;
  final Color iconBackground;
  final String title;
  final String subtitle;
  final String time;
}

class _ParentColors {
  const _ParentColors._();

  static const Color background = Color(0xFFF7FBFF);
  static const Color primaryBlue = Color(0xFF1E73F8);
  static const Color text = Color(0xFF111827);
  static const Color secondaryText = Color(0xFF6B7280);
  static const Color border = Color(0xFFE5EAF2);
  static const Color green = Color(0xFF14B879);
  static const Color purple = Color(0xFF594EF3);
  static const Color orange = Color(0xFFF59E0B);
  static const Color red = Color(0xFFFF3B43);
}

class _ParentTextStyles {
  const _ParentTextStyles._();

  static TextStyle get title {
    return GoogleFonts.inter(
      fontSize: 18,
      height: 1.15,
      fontWeight: FontWeight.w800,
      color: _ParentColors.text,
      letterSpacing: 0,
    );
  }

  static TextStyle get body {
    return GoogleFonts.inter(
      fontSize: 15,
      height: 1.28,
      fontWeight: FontWeight.w500,
      color: _ParentColors.text,
      letterSpacing: 0,
    );
  }

  static TextStyle get label {
    return GoogleFonts.inter(
      fontSize: 13,
      height: 1.15,
      fontWeight: FontWeight.w800,
      color: _ParentColors.text,
      letterSpacing: 0,
    );
  }

  static TextStyle get link {
    return GoogleFonts.inter(
      fontSize: 15,
      height: 1.15,
      fontWeight: FontWeight.w700,
      color: _ParentColors.primaryBlue,
      letterSpacing: 0,
    );
  }
}

class _ParentShadows {
  const _ParentShadows._();

  static const List<BoxShadow> soft = [
    BoxShadow(color: Color(0x0F0B1220), blurRadius: 18, offset: Offset(0, 8)),
  ];

  static const List<BoxShadow> card = [
    BoxShadow(color: Color(0x0D0B1220), blurRadius: 18, offset: Offset(0, 8)),
  ];
}

String _childGroupLine(ParentChildModel child) {
  final parts = <String>[
    if (child.className.trim().isNotEmpty) child.className.trim(),
    if (child.groupName.trim().isNotEmpty) child.groupName.trim(),
  ];
  return parts.isEmpty ? 'Guruh biriktirilmagan' : parts.join(' • ');
}

(String, String) _dateParts(DateTime? date) {
  if (date == null) {
    return ('—', '');
  }
  const months = [
    'Yan',
    'Fev',
    'Mar',
    'Apr',
    'May',
    'Iyun',
    'Iyul',
    'Avg',
    'Sen',
    'Okt',
    'Noy',
    'Dek',
  ];
  return ('${date.day} ${months[date.month - 1]}', '${date.year}');
}

String _attendanceStatus(int percent) {
  if (percent >= 90) {
    return 'Yaxshi';
  }
  if (percent >= 75) {
    return 'O‘rtacha';
  }
  return 'E’tibor kerak';
}

String _scoreStatus(int percent) {
  if (percent >= 85) {
    return 'Yaxshi';
  }
  if (percent >= 65) {
    return 'O‘rtacha';
  }
  return 'E’tibor kerak';
}

List<_ChartSeries> _chartSeries(List<ParentProgressSeries> series) {
  const colors = [
    _ParentColors.primaryBlue,
    _ParentColors.green,
    _ParentColors.orange,
    _ParentColors.purple,
    Color(0xFFEC4899),
  ];

  return [
    for (var index = 0; index < series.length; index++)
      if (series[index].points.isNotEmpty)
        _ChartSeries(
          label: series[index].label,
          percent: '${series[index].percent}%',
          color: colors[index % colors.length],
          points: series[index].points,
        ),
  ];
}

List<String> _chartMonths(List<ParentProgressSeries> series) {
  for (final item in series) {
    if (item.months.isNotEmpty) {
      return item.months;
    }
  }
  return const ['Yan', 'Fev', 'Mar', 'Apr', 'May'];
}

_NotificationData _notificationData(ParentNotificationModel notification) {
  final type = notification.type.toLowerCase();
  if (type.contains('payment') || type.contains('tolov')) {
    return _NotificationData(
      icon: Icons.account_balance_wallet_outlined,
      iconColor: _ParentColors.purple,
      iconBackground: const Color(0xFFF0ECFF),
      title: notification.title,
      subtitle: notification.message,
      time: Formatters.relative(notification.createdAt),
    );
  }
  if (type.contains('grade') ||
      type.contains('score') ||
      type.contains('baho')) {
    return _NotificationData(
      icon: Icons.star_border_rounded,
      iconColor: _ParentColors.orange,
      iconBackground: const Color(0xFFFFF5DE),
      title: notification.title,
      subtitle: notification.message,
      time: Formatters.relative(notification.createdAt),
    );
  }
  if (type.contains('comment') || type.contains('izoh')) {
    return _NotificationData(
      icon: Icons.chat_bubble_outline_rounded,
      iconColor: _ParentColors.primaryBlue,
      iconBackground: const Color(0xFFEAF4FF),
      title: notification.title,
      subtitle: notification.message,
      time: Formatters.relative(notification.createdAt),
    );
  }
  return _NotificationData(
    icon: Icons.event_available_outlined,
    iconColor: _ParentColors.green,
    iconBackground: const Color(0xFFE8FAF1),
    title: notification.title,
    subtitle: notification.message,
    time: Formatters.relative(notification.createdAt),
  );
}
