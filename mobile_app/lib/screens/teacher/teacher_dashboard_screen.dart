import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/teacher_provider.dart';
import 'package:chaqmoq_mobile/screens/teacher/teacher_attendance_screen.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class TeacherDashboardScreen extends StatefulWidget {
  const TeacherDashboardScreen({
    super.key,
    this.onGoGroups,
    this.onGoIncome,
  });

  final VoidCallback? onGoGroups;
  final VoidCallback? onGoIncome;

  @override
  State<TeacherDashboardScreen> createState() => _TeacherDashboardScreenState();
}

class _TeacherDashboardScreenState extends State<TeacherDashboardScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        context.read<TeacherProvider>().loadGroups();
        context.read<TeacherProvider>().loadIncome();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final teacher = context.watch<TeacherProvider>();
    final name = auth.user?.fullName ?? 'O\'qituvchi';
    final now = DateTime.now();
    final monthNames = [
      '', 'Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun',
      'Iyul', 'Avgust', 'Sentyabr', 'Oktyabr', 'Noyabr', 'Dekabr'
    ];

    return Scaffold(
      backgroundColor: const Color(0xFF0B1220),
      body: CustomScrollView(
        slivers: [
          SliverAppBar(
            backgroundColor: const Color(0xFF0B1220),
            expandedHeight: 130,
            pinned: true,
            flexibleSpace: FlexibleSpaceBar(
              background: Container(
                decoration: const BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [Color(0xFF1E1B4B), Color(0xFF0B1220)],
                  ),
                ),
                padding: const EdgeInsets.fromLTRB(20, 60, 20, 0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Xush kelibsiz! 👋',
                      style: TextStyle(color: Colors.white.withOpacity(0.6), fontSize: 13),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      name,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 22,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            actions: [
              Padding(
                padding: const EdgeInsets.only(right: 12),
                child: TextButton(
                  onPressed: () {
                    final now = DateTime.now();
                    context.read<TeacherProvider>().loadGroups();
                  },
                  child: const Icon(Icons.refresh_rounded, color: Colors.white54),
                ),
              ),
            ],
          ),

          SliverPadding(
            padding: const EdgeInsets.all(16),
            sliver: SliverList(
              delegate: SliverChildListDelegate([
                // Income card
                _buildIncomeCard(context, teacher, monthNames[now.month]),
                const SizedBox(height: 16),

                // Stats row
                _buildStatsRow(teacher),
                const SizedBox(height: 20),

                // Today's groups
                const Text(
                  'Bugungi guruhlar',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 10),
                if (teacher.groupsState == ViewState.loading)
                  const Center(child: Padding(
                    padding: EdgeInsets.all(32),
                    child: CircularProgressIndicator(color: Color(0xFF6366F1)),
                  ))
                else if (teacher.groups.isEmpty)
                  _EmptyGroups()
                else
                  ...teacher.groups.map((g) => _GroupTodayCard(
                        group: g,
                        onMark: () => Navigator.of(context).push(
                          MaterialPageRoute<void>(
                            builder: (_) => TeacherAttendanceScreen(group: g),
                          ),
                        ),
                      )),
                const SizedBox(height: 20),
              ]),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildIncomeCard(BuildContext context, TeacherProvider p, String month) {
    final income = p.income;
    final salary = income?.salary ?? 0;
    final expected = income?.expectedIncome ?? 0;
    final pct = income?.progressPct ?? 0;

    return GestureDetector(
      onTap: widget.onGoIncome,
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Color(0xFF4F46E5), Color(0xFF7C3AED)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(18),
          boxShadow: [
            BoxShadow(
              color: const Color(0xFF6366F1).withOpacity(0.35),
              blurRadius: 24,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Text(
                  'Bu oy daromadim',
                  style: TextStyle(color: Colors.white70, fontSize: 13, fontWeight: FontWeight.w600),
                ),
                const Spacer(),
                Text(
                  month,
                  style: const TextStyle(color: Colors.white54, fontSize: 12),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              Formatters.currency(salary),
              style: const TextStyle(
                color: Colors.white,
                fontSize: 26,
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Maksimal: ${Formatters.currency(expected)}',
                  style: const TextStyle(color: Colors.white60, fontSize: 11),
                ),
                Text(
                  '$pct%',
                  style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w700),
                ),
              ],
            ),
            const SizedBox(height: 6),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: pct / 100,
                backgroundColor: Colors.white24,
                valueColor: const AlwaysStoppedAnimation<Color>(Colors.white),
                minHeight: 5,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatsRow(TeacherProvider p) {
    final totalStudents = p.groups.fold<int>(0, (s, g) => s + g.studentCount);
    final totalGroups = p.groups.length;
    final todayAttended = p.groups.fold<int>(0, (s, g) => s + g.attendedToday);

    return Row(
      children: [
        Expanded(child: _StatCard(value: '$totalGroups', label: 'Guruh', icon: Icons.groups_rounded, color: const Color(0xFF10B981))),
        const SizedBox(width: 10),
        Expanded(child: _StatCard(value: '$totalStudents', label: "O'quvchi", icon: Icons.person_rounded, color: const Color(0xFF3B82F6))),
        const SizedBox(width: 10),
        Expanded(child: _StatCard(value: '$todayAttended', label: 'Bugun keldi', icon: Icons.check_circle_rounded, color: const Color(0xFFEAB308))),
      ],
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({required this.value, required this.label, required this.icon, required this.color});

  final String value;
  final String label;
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF162436),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white.withOpacity(0.06)),
      ),
      child: Column(
        children: [
          Icon(icon, color: color, size: 22),
          const SizedBox(height: 6),
          Text(value, style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w800)),
          const SizedBox(height: 2),
          Text(label, style: const TextStyle(color: Colors.white54, fontSize: 10), textAlign: TextAlign.center),
        ],
      ),
    );
  }
}

class _GroupTodayCard extends StatelessWidget {
  const _GroupTodayCard({required this.group, required this.onMark});

  final dynamic group;
  final VoidCallback onMark;

  @override
  Widget build(BuildContext context) {
    final pct = group.studentCount > 0 ? group.attendedToday / group.studentCount : 0.0;
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: const Color(0xFF162436),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white.withOpacity(0.06)),
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        leading: Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: const Color(0xFF6366F1).withOpacity(0.15),
            borderRadius: BorderRadius.circular(12),
          ),
          child: const Icon(Icons.groups_rounded, color: Color(0xFF6366F1), size: 22),
        ),
        title: Text(
          group.name,
          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 14),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 4),
            Text(
              '${group.attendedToday}/${group.studentCount} o\'quvchi keldi',
              style: const TextStyle(color: Colors.white54, fontSize: 12),
            ),
            const SizedBox(height: 4),
            LinearProgressIndicator(
              value: pct.toDouble(),
              backgroundColor: Colors.white12,
              valueColor: AlwaysStoppedAnimation<Color>(
                pct == 1.0 ? const Color(0xFF10B981) : const Color(0xFF6366F1),
              ),
              minHeight: 3,
              borderRadius: BorderRadius.circular(2),
            ),
          ],
        ),
        trailing: TextButton(
          onPressed: onMark,
          style: TextButton.styleFrom(
            backgroundColor: const Color(0xFF6366F1).withOpacity(0.15),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          ),
          child: const Text('Davomat', style: TextStyle(color: Color(0xFF818CF8), fontSize: 12, fontWeight: FontWeight.w700)),
        ),
      ),
    );
  }
}

class _EmptyGroups extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(32),
      decoration: BoxDecoration(
        color: const Color(0xFF162436),
        borderRadius: BorderRadius.circular(14),
      ),
      child: const Column(
        children: [
          Icon(Icons.groups_outlined, color: Colors.white24, size: 40),
          SizedBox(height: 10),
          Text("Guruhlar topilmadi", style: TextStyle(color: Colors.white38, fontSize: 14)),
        ],
      ),
    );
  }
}
