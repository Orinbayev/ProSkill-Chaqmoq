import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/teacher_models.dart';
import 'package:chaqmoq_mobile/providers/teacher_provider.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

class TeacherAttendanceScreen extends StatefulWidget {
  const TeacherAttendanceScreen({super.key, required this.group});

  final TeacherGroupModel group;

  @override
  State<TeacherAttendanceScreen> createState() => _State();
}

class _State extends State<TeacherAttendanceScreen> {
  DateTime _date = DateTime.now();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _load();
    });
  }

  void _load() {
    context.read<TeacherProvider>().loadAttendance(widget.group.id, date: _date);
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: DateTime(_date.year, _date.month - 2),
      lastDate: DateTime.now(),
      builder: (ctx, child) => Theme(
        data: ThemeData.dark().copyWith(
          colorScheme: const ColorScheme.dark(primary: Color(0xFF6366F1), surface: Color(0xFF1E2D40)),
        ),
        child: child!,
      ),
    );
    if (picked != null && mounted) {
      setState(() => _date = picked);
      _load();
    }
  }

  void _markAll(bool present) {
    final students = context.read<TeacherProvider>().attendance?.students ?? [];
    for (final s in students) {
      if (s.isPresent != present) {
        context.read<TeacherProvider>().toggleAttendance(s.id, present);
      }
    }
    HapticFeedback.mediumImpact();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final p = context.watch<TeacherProvider>();
    final att = p.attendance;
    final students = att?.students ?? <TeacherStudentModel>[];
    final presentCount = students.where((s) => s.isPresent).length;
    final isToday = _date.year == DateTime.now().year &&
        _date.month == DateTime.now().month &&
        _date.day == DateTime.now().day;

    return Scaffold(
      backgroundColor: isDark ? const Color(0xFF0B1220) : const Color(0xFFF5F7FB),
      appBar: AppBar(
        backgroundColor: isDark ? const Color(0xFF0F1B2A) : Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back_rounded, color: isDark ? Colors.white : Colors.black87),
          onPressed: () => Navigator.pop(context),
        ),
        title: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(widget.group.name,
              style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A),
                  fontWeight: FontWeight.w800, fontSize: 15)),
          Text("Davomat belgilash",
              style: TextStyle(color: isDark ? Colors.white54 : Colors.black45, fontSize: 11)),
        ]),
        actions: [
          TextButton.icon(
            onPressed: _pickDate,
            icon: Icon(Icons.calendar_today_rounded, size: 14,
                color: isToday ? const Color(0xFF818CF8) : const Color(0xFFF59E0B)),
            label: Text(
              isToday ? "Bugun" : Formatters.date(_date),
              style: TextStyle(
                color: isToday ? const Color(0xFF818CF8) : const Color(0xFFF59E0B),
                fontWeight: FontWeight.w700, fontSize: 12,
              ),
            ),
          ),
        ],
      ),
      body: Column(children: [
        // Stats + quick actions bar
        Container(
          color: isDark ? const Color(0xFF0F1B2A) : Colors.white,
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
          child: Column(children: [
            Row(children: [
              _Badge("$presentCount", "Keldi", const Color(0xFF10B981)),
              const SizedBox(width: 8),
              _Badge("${students.length - presentCount}", "Kelmadi", const Color(0xFFEF4444)),
              const SizedBox(width: 8),
              _Badge("${students.length}", "Jami", const Color(0xFF6366F1)),
              const Spacer(),
              if (students.isNotEmpty) ...[
                Text("${students.length > 0 ? (presentCount / students.length * 100).round() : 0}%",
                    style: TextStyle(color: isDark ? Colors.white70 : Colors.black54,
                        fontWeight: FontWeight.w800, fontSize: 13)),
              ],
            ]),
            if (students.isNotEmpty) ...[
              const SizedBox(height: 8),
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: students.isEmpty ? 0 : presentCount / students.length,
                  backgroundColor: isDark ? Colors.white12 : Colors.black.withValues(alpha: 0.06),
                  valueColor: const AlwaysStoppedAnimation(Color(0xFF10B981)),
                  minHeight: 5,
                ),
              ),
              const SizedBox(height: 10),
              Row(children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => _markAll(true),
                    icon: const Icon(Icons.check_circle_rounded, size: 15),
                    label: const Text("Barchasi keldi", style: TextStyle(fontSize: 12)),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: const Color(0xFF10B981),
                      side: const BorderSide(color: Color(0xFF10B981)),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      padding: const EdgeInsets.symmetric(vertical: 8),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => _markAll(false),
                    icon: const Icon(Icons.cancel_rounded, size: 15),
                    label: const Text("Barchasi kelmadi", style: TextStyle(fontSize: 12)),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: const Color(0xFFEF4444),
                      side: const BorderSide(color: Color(0xFFEF4444)),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      padding: const EdgeInsets.symmetric(vertical: 8),
                    ),
                  ),
                ),
              ]),
            ],
          ]),
        ),

        Expanded(
          child: () {
            if (p.attendanceState == ViewState.loading) {
              return const Center(child: CircularProgressIndicator(color: Color(0xFF6366F1)));
            }
            if (p.attendanceState == ViewState.error) {
              return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
                const Icon(Icons.error_outline, color: Colors.red, size: 40),
                const SizedBox(height: 12),
                Text(p.attendanceError,
                    style: const TextStyle(color: Colors.red, fontSize: 13), textAlign: TextAlign.center),
                const SizedBox(height: 16),
                ElevatedButton(onPressed: _load, child: const Text("Qayta")),
              ]));
            }
            if (students.isEmpty) {
              return Center(
                child: Column(mainAxisSize: MainAxisSize.min, children: [
                  Icon(Icons.person_off_rounded, color: isDark ? Colors.white24 : Colors.black26, size: 48),
                  const SizedBox(height: 12),
                  Text("O'quvchilar topilmadi",
                      style: TextStyle(color: isDark ? Colors.white38 : Colors.black38, fontSize: 15)),
                ]),
              );
            }
            return ListView.separated(
              padding: const EdgeInsets.all(12),
              itemCount: students.length,
              separatorBuilder: (_, __) => const SizedBox(height: 6),
              itemBuilder: (_, i) => _StudentRow(
                student: students[i],
                isDark: isDark,
                onToggle: (v) {
                  HapticFeedback.lightImpact();
                  context.read<TeacherProvider>().toggleAttendance(students[i].id, v);
                },
              ),
            );
          }(),
        ),
      ]),
    );
  }
}

class _Badge extends StatelessWidget {
  const _Badge(this.value, this.label, this.color);

  final String value;
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Text(value, style: TextStyle(color: color, fontWeight: FontWeight.w800, fontSize: 13)),
        const SizedBox(width: 4),
        Text(label, style: TextStyle(color: color.withValues(alpha: 0.7), fontSize: 11)),
      ]),
    );
  }
}

class _StudentRow extends StatelessWidget {
  const _StudentRow({required this.student, required this.isDark, required this.onToggle});

  final TeacherStudentModel student;
  final bool isDark;
  final ValueChanged<bool> onToggle;

  @override
  Widget build(BuildContext context) {
    final present = student.isPresent;
    return AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      decoration: BoxDecoration(
        color: present
            ? const Color(0xFF10B981).withValues(alpha: isDark ? 0.10 : 0.07)
            : (isDark ? const Color(0xFF162436) : Colors.white),
        borderRadius: BorderRadius.circular(13),
        border: Border.all(
          color: present
              ? const Color(0xFF10B981).withValues(alpha: 0.3)
              : (isDark ? Colors.white.withValues(alpha: 0.06) : Colors.black.withValues(alpha: 0.05)),
        ),
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 2),
        leading: CircleAvatar(
          radius: 20,
          backgroundColor: present
              ? const Color(0xFF10B981).withValues(alpha: 0.2)
              : (isDark ? const Color(0xFF1E2D40) : const Color(0xFFE8EDF2)),
          child: Text(
            _initials(student.fullName),
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w800,
              color: present ? const Color(0xFF10B981) : (isDark ? Colors.white54 : Colors.black45),
            ),
          ),
        ),
        title: Text(student.fullName,
            style: TextStyle(
                color: isDark ? Colors.white : const Color(0xFF0F172A),
                fontWeight: FontWeight.w700, fontSize: 14)),
        subtitle: student.balance < 0
            ? Text("Qarzi: ${Formatters.currency(student.balance.abs())}",
                style: const TextStyle(color: Color(0xFFEF4444), fontSize: 11, fontWeight: FontWeight.w600))
            : null,
        trailing: GestureDetector(
          onTap: () => onToggle(!present),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 220),
            width: 52, height: 28,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(14),
              color: present ? const Color(0xFF10B981) : (isDark ? const Color(0xFF1E2D40) : const Color(0xFFE2E8F0)),
              border: Border.all(color: present ? const Color(0xFF10B981) : Colors.transparent),
            ),
            child: AnimatedAlign(
              duration: const Duration(milliseconds: 220),
              curve: Curves.easeInOut,
              alignment: present ? Alignment.centerRight : Alignment.centerLeft,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 3),
                child: Container(
                  width: 22, height: 22,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: present ? Colors.white : Colors.white60,
                  ),
                  child: Icon(
                    present ? Icons.check_rounded : Icons.close_rounded,
                    size: 12,
                    color: present ? const Color(0xFF10B981) : Colors.grey,
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  static String _initials(String n) {
    final parts = n.trim().split(RegExp(r'\s+')).where((e) => e.isNotEmpty).toList();
    if (parts.isEmpty) return '?';
    return parts.take(2).map((e) => e[0].toUpperCase()).join();
  }
}
