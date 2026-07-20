import 'package:chaqmoq_mobile/core/theme/panel_tokens.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/teacher_models.dart';
import 'package:chaqmoq_mobile/providers/teacher_provider.dart';
import 'package:chaqmoq_mobile/screens/teacher/teacher_attendance_screen.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class TeacherGroupsScreen extends StatefulWidget {
  const TeacherGroupsScreen({super.key});

  @override
  State<TeacherGroupsScreen> createState() => _State();
}

class _State extends State<TeacherGroupsScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) context.read<TeacherProvider>().loadGroups();
    });
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final p = context.watch<TeacherProvider>();

    return Scaffold(
      backgroundColor: PanelTokens.bg(isDark),
      appBar: AppBar(
        backgroundColor: isDark ? const Color(0xFF0F1B2A) : Colors.white,
        elevation: 0,
        title: Text("Guruhlarim",
            style: TextStyle(
                color: isDark ? Colors.white : const Color(0xFF0F172A),
                fontWeight: FontWeight.w800, fontSize: 17)),
        actions: [
          IconButton(
            icon: Icon(Icons.refresh_rounded, color: isDark ? Colors.white60 : Colors.black45),
            onPressed: p.loadGroups,
          ),
        ],
      ),
      body: () {
        if (p.groupsState == ViewState.loading) {
          return const Center(child: CircularProgressIndicator(color: Color(0xFF0EA5E9)));
        }
        if (p.groupsState == ViewState.error) {
          return Center(child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              const Icon(Icons.wifi_off_rounded, color: Colors.red, size: 48),
              const SizedBox(height: 14),
              Text(p.groupsError,
                  style: const TextStyle(color: Colors.red, fontSize: 13), textAlign: TextAlign.center),
              const SizedBox(height: 16),
              ElevatedButton.icon(
                onPressed: p.loadGroups,
                icon: const Icon(Icons.refresh_rounded, size: 16),
                label: const Text("Qayta urinish"),
                style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF0EA5E9)),
              ),
            ]),
          ));
        }
        if (p.groups.isEmpty) {
          return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
            Icon(Icons.groups_outlined, size: 56, color: isDark ? Colors.white24 : Colors.black26),
            const SizedBox(height: 14),
            Text("Guruhlar topilmadi",
                style: TextStyle(color: isDark ? Colors.white38 : Colors.black38, fontSize: 16)),
          ]));
        }
        return RefreshIndicator(
          color: const Color(0xFF0EA5E9),
          onRefresh: p.loadGroups,
          child: ListView.separated(
            padding: const EdgeInsets.all(14),
            itemCount: p.groups.length,
            separatorBuilder: (_, __) => const SizedBox(height: 10),
            itemBuilder: (_, i) => _GroupCard(group: p.groups[i], isDark: isDark),
          ),
        );
      }(),
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
    final color = isDark ? const Color(0xFF162436) : Colors.white;
    final borderColor = isDark ? Colors.white.withValues(alpha: 0.06) : Colors.black.withValues(alpha: 0.05);

    return Container(
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: borderColor),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: isDark ? 0.15 : 0.04),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Container(
              width: 46, height: 46,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF38BDF8), Color(0xFF0EA5E9)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(13),
              ),
              child: const Icon(Icons.groups_rounded, color: Colors.white, size: 22),
            ),
            const SizedBox(width: 12),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(group.name,
                  style: TextStyle(
                      color: isDark ? Colors.white : const Color(0xFF0F172A),
                      fontWeight: FontWeight.w800, fontSize: 15)),
              if (group.category.isNotEmpty)
                Text(group.category,
                    style: TextStyle(color: isDark ? Colors.white54 : Colors.black45, fontSize: 12)),
            ])),
          ]),
          const SizedBox(height: 14),
          Row(children: [
            _Chip(Icons.person_rounded, "${group.studentCount} o'quvchi", const Color(0xFF3B82F6)),
            const SizedBox(width: 8),
            _Chip(Icons.calendar_month_rounded, "${group.monthlyLessons} dars/oy", const Color(0xFF10B981)),
            const SizedBox(width: 8),
            _Chip(Icons.percent_rounded, "${group.teacherSharePercent}%", const Color(0xFFF59E0B)),
          ]),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text("Bugungi davomat",
                  style: TextStyle(color: isDark ? Colors.white54 : Colors.black45, fontSize: 11)),
              const SizedBox(height: 4),
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: pct,
                  backgroundColor: isDark ? Colors.white12 : Colors.black.withValues(alpha: 0.08),
                  valueColor: AlwaysStoppedAnimation<Color>(
                      pct >= 1.0 ? const Color(0xFF10B981) : const Color(0xFF0EA5E9)),
                  minHeight: 6,
                ),
              ),
            ])),
            const SizedBox(width: 10),
            Text("${group.attendedToday}/${group.studentCount}",
                style: TextStyle(
                    color: isDark ? Colors.white70 : Colors.black54,
                    fontWeight: FontWeight.w800, fontSize: 13)),
          ]),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute<void>(
                      builder: (_) => TeacherAttendanceScreen(group: group))),
              icon: const Icon(Icons.fact_check_rounded, size: 16),
              label: const Text("Davomat belgilash", style: TextStyle(fontWeight: FontWeight.w700)),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF0EA5E9),
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                padding: const EdgeInsets.symmetric(vertical: 11),
                elevation: 0,
              ),
            ),
          ),
        ]),
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  const _Chip(this.icon, this.label, this.color);

  final IconData icon;
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(7),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 11, color: color),
        const SizedBox(width: 4),
        Text(label, style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w700)),
      ]),
    );
  }
}
