import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/chaqmoq_history_provider.dart';
import 'package:chaqmoq_mobile/providers/dashboard_provider.dart';
import 'package:chaqmoq_mobile/providers/notifications_provider.dart';
import 'package:chaqmoq_mobile/providers/payments_provider.dart';
import 'package:chaqmoq_mobile/screens/student/widgets/student_activity_chart.dart';
import 'package:chaqmoq_mobile/screens/student/widgets/student_atmospheric_backdrop.dart';
import 'package:chaqmoq_mobile/screens/student/widgets/student_attendance_card.dart';
import 'package:chaqmoq_mobile/screens/student/widgets/student_dashboard_header.dart';
import 'package:chaqmoq_mobile/screens/student/widgets/student_hero_card.dart';
import 'package:chaqmoq_mobile/screens/student/widgets/student_payment_summary_card.dart';
import 'package:chaqmoq_mobile/screens/student/widgets/student_rating_card.dart';
import 'package:chaqmoq_mobile/screens/student/widgets/student_stats_grid.dart';
import 'package:chaqmoq_mobile/widgets/app_section_header.dart';
import 'package:chaqmoq_mobile/widgets/app_state_widgets.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class StudentDashboardScreen extends StatefulWidget {
  const StudentDashboardScreen({
    super.key,
    this.onOpenPayments,
    this.onOpenAttendance,
    this.onOpenNotifications,
    this.onOpenProfile,
  });

  final VoidCallback? onOpenPayments;
  final VoidCallback? onOpenAttendance;
  final VoidCallback? onOpenNotifications;
  final VoidCallback? onOpenProfile;

  @override
  State<StudentDashboardScreen> createState() => _StudentDashboardScreenState();
}

class _StudentDashboardScreenState extends State<StudentDashboardScreen> {
  bool _hydrated = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_hydrated) return;
    final user = context.read<AuthProvider>().user;
    if (user != null) {
      _hydrated = true;
      context.read<DashboardProvider>().load(user);
      context.read<PaymentsProvider>().load(user);
      context.read<ChaqmoqHistoryProvider>().load();
    }
  }

  Future<void> _refresh() async {
    final user = context.read<AuthProvider>().user;
    if (user == null) return;
    await Future.wait<void>([
      context.read<DashboardProvider>().refresh(user),
      context.read<NotificationsProvider>().refresh(),
      context.read<PaymentsProvider>().refresh(user),
      context.read<ChaqmoqHistoryProvider>().refresh(),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final auth = context.watch<AuthProvider>();
    final dashboard = context.watch<DashboardProvider>();
    final payments = context.watch<PaymentsProvider>();
    final notifications = context.watch<NotificationsProvider>();
    final history = context.watch<ChaqmoqHistoryProvider>();
    final user = auth.user;

    if (user == null) {
      return const SizedBox.shrink();
    }

    return Scaffold(
      backgroundColor: tokens.bg,
      body: Stack(
        children: [
          const StudentAtmosphericBackdrop(),
          SafeArea(
            child: RefreshIndicator(
              color: tokens.primary,
              onRefresh: _refresh,
              child: _body(
                user,
                dashboard,
                payments,
                history,
                unread: notifications.unreadCount,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _body(
    UserModel user,
    DashboardProvider dashboard,
    PaymentsProvider payments,
    ChaqmoqHistoryProvider history, {
    required int unread,
  }) {
    final isLoading = dashboard.state == ViewState.loading && dashboard.data.metrics.isEmpty;
    if (isLoading) {
      return AppLoadingState(dark: StudentTokens.of(context).isDark);
    }
    final hasFatalError = dashboard.state == ViewState.error && dashboard.data.metrics.isEmpty;
    if (hasFatalError) {
      return AppErrorState(
        title: 'Panel yuklanmadi',
        message: 'Server bilan aloqa yo‘q. Qayta urinib ko‘ring.',
        dark: StudentTokens.of(context).isDark,
        onRetry: () => dashboard.refresh(user),
      );
    }

    final data = dashboard.data;
    final lastPayment = _findLastPayment(payments.filteredItems);
    final nextDue = _findNextDue(payments.filteredItems);
    final attendance = _attendanceFromHistory(history);

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(parent: BouncingScrollPhysics()),
      padding: const EdgeInsets.fromLTRB(18, 8, 18, 110),
      children: [
        StudentDashboardHeader(
          unread: unread,
          onBell: widget.onOpenNotifications ?? () {},
        ),
        const SizedBox(height: 14),
        StudentHeroCard(
          name: user.fullName.isEmpty ? 'O‘quvchi' : user.fullName,
          centerName: user.center?.name ?? '',
          onPay: widget.onOpenPayments,
          onMessages: widget.onOpenNotifications,
          onProfile: widget.onOpenProfile,
        ),
        const SizedBox(height: 14),
        StudentRatingCard(
          score: data.studentScore,
          rank: data.studentRank,
        ),
        const SizedBox(height: 14),
        StudentStatsGrid(
          metrics: data.metrics,
          fallbackAttendance: data.teacherAttendanceRate,
          openDebt: payments.summary.openDebt,
        ),
        const SizedBox(height: 14),
        const AppSectionHeader(title: 'FAOLLIK'),
        const SizedBox(height: 8),
        StudentActivityChart(points: data.revenueTrend),
        const SizedBox(height: 14),
        const AppSectionHeader(title: "DAVOMAT VA TO‘LOV"),
        const SizedBox(height: 8),
        StudentAttendanceCard(
          attendancePct: attendance.percent,
          monthlyTotal: attendance.totalDays,
          monthlyAttended: attendance.attendedDays,
          weeklyAttended: attendance.weeklyAttended,
          weeklyTotal: attendance.weeklyTotal,
          onTap: widget.onOpenAttendance,
        ),
        const SizedBox(height: 10),
        StudentPaymentSummaryCard(
          summary: payments.summary,
          lastPayment: lastPayment,
          nextDue: nextDue,
          onTap: widget.onOpenPayments,
        ),
      ],
    );
  }

  PaymentModel? _findLastPayment(List<PaymentModel> items) {
    final paid = items.where((p) => !p.isDebt).toList()
      ..sort((a, b) => b.date.compareTo(a.date));
    return paid.isEmpty ? null : paid.first;
  }

  DateTime? _findNextDue(List<PaymentModel> items) {
    final debt = items.where((p) => p.isDebt).toList()
      ..sort((a, b) => a.date.compareTo(b.date));
    return debt.isEmpty ? null : debt.first.date;
  }

  /// Derive this-month attendance counts directly from the chaqmoq ledger:
  /// every distinct day with a positive entry counts as Kelgan; days with
  /// only negative entries count as Kelmagan; their sum is the recorded total.
  _AttendanceSnapshot _attendanceFromHistory(ChaqmoqHistoryProvider history) {
    final now = DateTime.now();
    final monthStart = DateTime(now.year, now.month);
    final monthEnd = DateTime(now.year, now.month + 1, 0);
    final weekStart = DateTime(now.year, now.month, now.day - (now.weekday - 1));

    final monthlyAttended = <DateTime>{};
    final monthlyAbsent = <DateTime>{};
    final weeklyAttended = <DateTime>{};
    final weeklyAbsent = <DateTime>{};

    final byDay = <DateTime, List<int>>{};
    for (final e in history.items) {
      final d = DateTime(e.createdAt.year, e.createdAt.month, e.createdAt.day);
      byDay.putIfAbsent(d, () => <int>[]).add(e.points);
    }

    byDay.forEach((day, pts) {
      if (day.isBefore(monthStart) || day.isAfter(monthEnd)) return;
      final hasPos = pts.any((p) => p > 0);
      final hasNeg = pts.any((p) => p < 0);
      final attended = hasPos;
      final absent = !hasPos && hasNeg;
      if (attended) monthlyAttended.add(day);
      if (absent) monthlyAbsent.add(day);
      if (!day.isBefore(weekStart)) {
        if (attended) weeklyAttended.add(day);
        if (absent) weeklyAbsent.add(day);
      }
    });

    final monthTotal = monthlyAttended.length + monthlyAbsent.length;
    final weekTotal = weeklyAttended.length + weeklyAbsent.length;
    final pct = monthTotal == 0 ? 0.0 : monthlyAttended.length / monthTotal;
    return _AttendanceSnapshot(
      attendedDays: monthlyAttended.length,
      totalDays: monthTotal,
      weeklyAttended: weeklyAttended.length,
      weeklyTotal: weekTotal,
      percent: pct,
    );
  }
}

class _AttendanceSnapshot {
  const _AttendanceSnapshot({
    required this.attendedDays,
    required this.totalDays,
    required this.weeklyAttended,
    required this.weeklyTotal,
    required this.percent,
  });

  final int attendedDays;
  final int totalDays;
  final int weeklyAttended;
  final int weeklyTotal;
  final double percent;
}
