import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/teacher_models.dart';
import 'package:chaqmoq_mobile/providers/teacher_provider.dart';
import 'package:chaqmoq_mobile/screens/teacher/teacher_attendance_screen.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class TeacherGroupsScreen extends StatefulWidget {
  const TeacherGroupsScreen({super.key});

  @override
  State<TeacherGroupsScreen> createState() => _TeacherGroupsScreenState();
}

class _TeacherGroupsScreenState extends State<TeacherGroupsScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) context.read<TeacherProvider>().loadGroups();
    });
  }

  @override
  Widget build(BuildContext context) {
    final p = context.watch<TeacherProvider>();
    return Scaffold(
      backgroundColor: const Color(0xFF0B1220),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0F1B2A),
        title: const Text('Mening guruhlarim', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 17)),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded, color: Colors.white60),
            onPressed: () => context.read<TeacherProvider>().loadGroups(),
          ),
        ],
      ),
      body: () {
        if (p.groupsState == ViewState.loading) {
          return const Center(child: CircularProgressIndicator(color: Color(0xFF6366F1)));
        }
        if (p.groupsState == ViewState.error) {
          return Center(
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              const Icon(Icons.error_outline, color: Colors.red, size: 40),
              const SizedBox(height: 12),
              Text(p.groupsError, style: const TextStyle(color: Colors.white54, fontSize: 13)),
              const SizedBox(height: 16),
              ElevatedButton(onPressed: () => p.loadGroups(), child: const Text('Qayta urinish')),
            ]),
          );
        }
        if (p.groups.isEmpty) {
          return const Center(
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Icon(Icons.groups_outlined, color: Colors.white24, size: 48),
              SizedBox(height: 12),
              Text("Hech qanday guruh yo'q", style: TextStyle(color: Colors.white38, fontSize: 15)),
            ]),
          );
        }
        return RefreshIndicator(
          color: const Color(0xFF6366F1),
          onRefresh: p.loadGroups,
          child: ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: p.groups.length,
            separatorBuilder: (_, __) => const SizedBox(height: 10),
            itemBuilder: (_, i) => _GroupCard(group: p.groups[i]),
          ),
        );
      }(),
    );
  }
}

class _GroupCard extends StatelessWidget {
  const _GroupCard({required this.group});

  final TeacherGroupModel group;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: () => Navigator.of(context).push(
        MaterialPageRoute<void>(builder: (_) => TeacherAttendanceScreen(group: group)),
      ),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: const Color(0xFF162436),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: Colors.white.withOpacity(0.06)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    group.name,
                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 16),
                  ),
                ),
                if (group.isClosed)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: Colors.red.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Text('Yopiq', style: TextStyle(color: Colors.red, fontSize: 11, fontWeight: FontWeight.w700)),
                  ),
              ],
            ),
            if (group.category.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(group.category, style: const TextStyle(color: Color(0xFF6366F1), fontSize: 12, fontWeight: FontWeight.w600)),
            ],
            const SizedBox(height: 12),
            Row(
              children: [
                _Chip(Icons.person_rounded, '${group.studentCount} o\'quvchi', const Color(0xFF3B82F6)),
                const SizedBox(width: 8),
                _Chip(Icons.calendar_today_rounded, '${group.monthlyLessons} dars/oy', const Color(0xFF10B981)),
                const SizedBox(width: 8),
                _Chip(Icons.percent_rounded, '${group.teacherSharePercent}%', const Color(0xFFEAB308)),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Oylik: ${Formatters.currency(group.monthlyPrice)}',
                  style: const TextStyle(color: Colors.white54, fontSize: 12),
                ),
                Text(
                  'Bugun: ${group.attendedToday}/${group.studentCount}',
                  style: TextStyle(
                    color: group.attendedToday == group.studentCount && group.studentCount > 0
                        ? const Color(0xFF10B981)
                        : Colors.white54,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(builder: (_) => TeacherAttendanceScreen(group: group)),
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF6366F1),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  padding: const EdgeInsets.symmetric(vertical: 10),
                ),
                icon: const Icon(Icons.fact_check_rounded, size: 16),
                label: const Text('Davomat belgilash', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  const _Chip(this.icon, this.text, this.color);

  final IconData icon;
  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 11, color: color),
        const SizedBox(width: 4),
        Text(text, style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w700)),
      ]),
    );
  }
}
