import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/teacher_models.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/teacher_provider.dart';
import 'package:chaqmoq_mobile/screens/teacher/teacher_attendance_screen.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class TeacherDashboardScreen extends StatefulWidget {
  const TeacherDashboardScreen({super.key, this.onGoGroups, this.onGoIncome});

  final VoidCallback? onGoGroups;
  final VoidCallback? onGoIncome;

  @override
  State<TeacherDashboardScreen> createState() => _State();
}

class _State extends State<TeacherDashboardScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      context.read<TeacherProvider>()
        ..loadGroups()
        ..loadIncome();
    });
  }

  Future<void> _refresh() async {
    final p = context.read<TeacherProvider>();
    await Future.wait([p.loadGroups(), p.forceReloadIncome()]);
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final auth = context.watch<AuthProvider>();
    final p = context.watch<TeacherProvider>();
    final name = auth.user?.firstName.isNotEmpty == true
        ? auth.user!.firstName
        : (auth.user?.fullName ?? "O'qituvchi");
    final now = DateTime.now();
    final months = ['', 'Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun', 'Iyul', 'Avgust', 'Sentyabr', 'Oktyabr', 'Noyabr', 'Dekabr'];

    return Scaffold(
      backgroundColor: isDark ? const Color(0xFF0B1220) : const Color(0xFFF5F7FB),
      body: RefreshIndicator(
        color: const Color(0xFF6366F1),
        onRefresh: _refresh,
        child: CustomScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          slivers: [
            _buildAppBar(context, name, isDark),
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 100),
              sliver: SliverList(
                delegate: SliverChildListDelegate([
                  _IncomeCard(p: p, month: months[now.month], onTap: widget.onGoIncome),
                  const SizedBox(height: 14),
                  _StatsRow(p: p),
                  const SizedBox(height: 20),
                  _SectionHeader(
                    title: "Bugungi guruhlar",
                    action: p.groups.isNotEmpty ? TextButton(onPressed: widget.onGoGroups, child: const Text("Barchasi")) : null,
                  ),
                  const SizedBox(height: 8),
                  if (p.groupsState == ViewState.loading)
                    const _LoadingCard()
                  else if (p.groupsState == ViewState.error)
                    _ErrorCard(message: p.groupsError, onRetry: p.loadGroups)
                  else if (p.groups.isEmpty)
                    _EmptyCard(isDark: isDark)
                  else
                    ...p.groups.map((g) => _GroupCard(group: g, isDark: isDark)),
                  const SizedBox(height: 16),
                ]),
              ),
            ),
          ],
        ),
      ),
    );
  }

  SliverAppBar _buildAppBar(BuildContext context, String name, bool isDark) {
    return SliverAppBar(
      backgroundColor: isDark ? const Color(0xFF0B1220) : const Color(0xFFF5F7FB),
      expandedHeight: 120,
      pinned: true,
      elevation: 0,
      flexibleSpace: FlexibleSpaceBar(
        background: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: isDark
                  ? [const Color(0xFF1E1B4B), const Color(0xFF0B1220)]
                  : [const Color(0xFFEEF2FF), const Color(0xFFF5F7FB)],
            ),
          ),
          padding: const EdgeInsets.fromLTRB(20, 60, 20, 12),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text("Xush kelibsiz 👋",
                style: TextStyle(color: isDark ? Colors.white60 : Colors.black45, fontSize: 13, fontWeight: FontWeight.w500)),
            const SizedBox(height: 4),
            Text(name,
                style: TextStyle(
                    color: isDark ? Colors.white : const Color(0xFF0F172A),
                    fontSize: 22,
                    fontWeight: FontWeight.w800)),
          ]),
        ),
      ),
      actions: [
        IconButton(
          icon: Icon(Icons.refresh_rounded, color: isDark ? Colors.white60 : Colors.black45),
          onPressed: _refresh,
        ),
      ],
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title, this.action});

  final String title;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Row(children: [
      Text(title,
          style: TextStyle(
              color: isDark ? Colors.white : const Color(0xFF0F172A),
              fontSize: 16,
              fontWeight: FontWeight.w800)),
      const Spacer(),
      if (action != null) action!,
    ]);
  }
}

class _IncomeCard extends StatelessWidget {
  const _IncomeCard({required this.p, required this.month, this.onTap});

  final TeacherProvider p;
  final String month;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final salary = p.income?.salary ?? 0;
    final expected = p.income?.expectedIncome ?? 0;
    final pct = p.income?.progressPct ?? 0;
    final loading = p.incomeState == ViewState.loading;

    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Color(0xFF4F46E5), Color(0xFF7C3AED)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color: const Color(0xFF6366F1).withValues(alpha: 0.35),
              blurRadius: 24,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const Icon(Icons.account_balance_wallet_rounded, color: Colors.white70, size: 16),
            const SizedBox(width: 6),
            Text("Bu oy daromadim — $month",
                style: const TextStyle(color: Colors.white70, fontSize: 12, fontWeight: FontWeight.w600)),
            const Spacer(),
            const Icon(Icons.chevron_right_rounded, color: Colors.white38, size: 18),
          ]),
          const SizedBox(height: 10),
          loading
              ? const SizedBox(height: 36, child: Center(child: LinearProgressIndicator(color: Colors.white30, backgroundColor: Colors.white12)))
              : Text(Formatters.currency(salary),
                  style: const TextStyle(color: Colors.white, fontSize: 28, fontWeight: FontWeight.w900, letterSpacing: -0.5)),
          const SizedBox(height: 14),
          Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
            Text("Maksimal: ${Formatters.currency(expected)}",
                style: const TextStyle(color: Colors.white54, fontSize: 11)),
            Text("$pct%",
                style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w800)),
          ]),
          const SizedBox(height: 6),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: (pct / 100).clamp(0.0, 1.0),
              backgroundColor: Colors.white24,
              valueColor: AlwaysStoppedAnimation<Color>(
                  pct >= 100 ? const Color(0xFF34D399) : Colors.white),
              minHeight: 6,
            ),
          ),
        ]),
      ),
    );
  }
}

class _StatsRow extends StatelessWidget {
  const _StatsRow({required this.p});

  final TeacherProvider p;

  @override
  Widget build(BuildContext context) {
    final groups = p.groups.length;
    final students = p.groups.fold<int>(0, (s, g) => s + g.studentCount);
    final today = p.groups.fold<int>(0, (s, g) => s + g.attendedToday);
    return Row(children: [
      _Stat(value: '$groups', label: 'Guruh', icon: Icons.groups_rounded, color: const Color(0xFF10B981)),
      const SizedBox(width: 10),
      _Stat(value: '$students', label: "O'quvchi", icon: Icons.person_rounded, color: const Color(0xFF3B82F6)),
      const SizedBox(width: 10),
      _Stat(value: '$today', label: 'Bugun', icon: Icons.fact_check_rounded, color: const Color(0xFFF59E0B)),
    ]);
  }
}

class _Stat extends StatelessWidget {
  const _Stat({required this.value, required this.label, required this.icon, required this.color});

  final String value;
  final String label;
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 10),
        decoration: BoxDecoration(
          color: isDark ? const Color(0xFF162436) : Colors.white,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: isDark ? Colors.white.withValues(alpha: 0.06) : Colors.black.withValues(alpha: 0.05)),
        ),
        child: Column(children: [
          Icon(icon, color: color, size: 22),
          const SizedBox(height: 6),
          Text(value, style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A), fontSize: 18, fontWeight: FontWeight.w800)),
          const SizedBox(height: 2),
          Text(label, style: TextStyle(color: isDark ? Colors.white38 : Colors.black45, fontSize: 10), textAlign: TextAlign.center),
        ]),
      ),
    );
  }
}

class _GroupCard extends StatelessWidget {
  const _GroupCard({required this.group, required this.isDark});

  final TeacherGroupModel group;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    final pct = group.studentCount > 0 ? group.attendedToday / group.studentCount : 0.0;
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF162436) : Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: isDark ? Colors.white.withValues(alpha: 0.06) : Colors.black.withValues(alpha: 0.05)),
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.fromLTRB(16, 8, 12, 8),
        leading: Container(
          width: 44, height: 44,
          decoration: BoxDecoration(
            color: const Color(0xFF6366F1).withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(12),
          ),
          child: const Icon(Icons.groups_rounded, color: Color(0xFF6366F1), size: 22),
        ),
        title: Text(group.name,
            style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A),
                fontWeight: FontWeight.w700, fontSize: 14)),
        subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const SizedBox(height: 4),
          Text("${group.attendedToday}/${group.studentCount} keldi",
              style: TextStyle(color: isDark ? Colors.white54 : Colors.black45, fontSize: 12)),
          const SizedBox(height: 4),
          ClipRRect(
            borderRadius: BorderRadius.circular(2),
            child: LinearProgressIndicator(
              value: pct,
              backgroundColor: isDark ? Colors.white12 : Colors.black12,
              valueColor: AlwaysStoppedAnimation<Color>(
                  pct >= 1.0 ? const Color(0xFF10B981) : const Color(0xFF6366F1)),
              minHeight: 3,
            ),
          ),
        ]),
        trailing: TextButton(
          onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => TeacherAttendanceScreen(group: group))),
          style: TextButton.styleFrom(
            backgroundColor: const Color(0xFF6366F1).withValues(alpha: 0.12),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          ),
          child: const Text("Davomat",
              style: TextStyle(color: Color(0xFF818CF8), fontSize: 11, fontWeight: FontWeight.w700)),
        ),
      ),
    );
  }
}

class _LoadingCard extends StatelessWidget {
  const _LoadingCard();

  @override
  Widget build(BuildContext context) {
    return const SizedBox(height: 80, child: Center(child: CircularProgressIndicator(color: Color(0xFF6366F1))));
  }
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.red.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.red.withValues(alpha: 0.2)),
      ),
      child: Column(children: [
        const Icon(Icons.wifi_off_rounded, color: Colors.red, size: 32),
        const SizedBox(height: 8),
        Text(message, style: const TextStyle(color: Colors.red, fontSize: 12), textAlign: TextAlign.center),
        const SizedBox(height: 10),
        TextButton(onPressed: onRetry, child: const Text("Qayta urinish")),
      ]),
    );
  }
}

class _EmptyCard extends StatelessWidget {
  const _EmptyCard({required this.isDark});

  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(32),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF162436) : Colors.white,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(children: [
        Icon(Icons.groups_outlined, color: isDark ? Colors.white24 : Colors.black26, size: 40),
        const SizedBox(height: 10),
        Text("Guruhlar topilmadi",
            style: TextStyle(color: isDark ? Colors.white38 : Colors.black38, fontSize: 14)),
      ]),
    );
  }
}
