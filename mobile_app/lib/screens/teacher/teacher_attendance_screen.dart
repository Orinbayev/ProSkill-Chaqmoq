import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/teacher_models.dart';
import 'package:chaqmoq_mobile/providers/teacher_provider.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class TeacherAttendanceScreen extends StatefulWidget {
  const TeacherAttendanceScreen({super.key, required this.group});

  final TeacherGroupModel group;

  @override
  State<TeacherAttendanceScreen> createState() => _TeacherAttendanceScreenState();
}

class _TeacherAttendanceScreenState extends State<TeacherAttendanceScreen> {
  DateTime _selectedDate = DateTime.now();

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        context.read<TeacherProvider>().loadAttendance(widget.group.id, date: _selectedDate);
      }
    });
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDate,
      firstDate: DateTime(_selectedDate.year, _selectedDate.month - 2, 1),
      lastDate: DateTime.now(),
      builder: (context, child) => Theme(
        data: ThemeData.dark().copyWith(
          colorScheme: const ColorScheme.dark(primary: Color(0xFF6366F1)),
        ),
        child: child!,
      ),
    );
    if (picked != null && picked != _selectedDate) {
      setState(() => _selectedDate = picked);
      if (!mounted) return;
      context.read<TeacherProvider>().loadAttendance(widget.group.id, date: _selectedDate);
    }
  }

  void _markAll(bool present) {
    final p = context.read<TeacherProvider>();
    final students = p.attendance?.students ?? [];
    for (final s in students) {
      if (s.isPresent != present) {
        p.toggleAttendance(s.id, present);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = context.watch<TeacherProvider>();
    final att = p.attendance;
    final students = att?.students ?? <TeacherStudentModel>[];
    final presentCount = students.where((s) => s.isPresent).length;

    return Scaffold(
      backgroundColor: const Color(0xFF0B1220),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0F1B2A),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded, color: Colors.white),
          onPressed: () => Navigator.pop(context),
        ),
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(widget.group.name, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 15)),
            Text('Davomat', style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 11)),
          ],
        ),
        actions: [
          TextButton.icon(
            onPressed: _pickDate,
            icon: const Icon(Icons.calendar_today_rounded, size: 14, color: Color(0xFF818CF8)),
            label: Text(
              Formatters.date(_selectedDate),
              style: const TextStyle(color: Color(0xFF818CF8), fontWeight: FontWeight.w700, fontSize: 12),
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          // Stats bar
          Container(
            color: const Color(0xFF0F1B2A),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            child: Row(
              children: [
                _StatBadge('$presentCount', 'Keldi', const Color(0xFF10B981)),
                const SizedBox(width: 10),
                _StatBadge('${students.length - presentCount}', 'Kelmadi', const Color(0xFFEF4444)),
                const SizedBox(width: 10),
                _StatBadge('${students.length}', 'Jami', const Color(0xFF6366F1)),
                const Spacer(),
                // Mark all present/absent
                if (p.attendanceState == ViewState.success && students.isNotEmpty)
                  Row(children: [
                    _QuickButton('Barchasi keldi', const Color(0xFF10B981), () => _markAll(true)),
                    const SizedBox(width: 6),
                    _QuickButton('Barchasi kelmadi', const Color(0xFFEF4444), () => _markAll(false)),
                  ]),
              ],
            ),
          ),

          // Students list
          Expanded(
            child: () {
              if (p.attendanceState == ViewState.loading) {
                return const Center(child: CircularProgressIndicator(color: Color(0xFF6366F1)));
              }
              if (p.attendanceState == ViewState.error) {
                return Center(
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                    const Icon(Icons.error_outline, color: Colors.red, size: 40),
                    const SizedBox(height: 12),
                    Text(p.attendanceError, style: const TextStyle(color: Colors.white54, fontSize: 13)),
                    const SizedBox(height: 16),
                    ElevatedButton(
                      onPressed: () => p.loadAttendance(widget.group.id, date: _selectedDate),
                      child: const Text('Qayta urinish'),
                    ),
                  ]),
                );
              }
              if (students.isEmpty) {
                return const Center(
                  child: Text("O'quvchilar topilmadi", style: TextStyle(color: Colors.white38, fontSize: 15)),
                );
              }
              return ListView.separated(
                padding: const EdgeInsets.all(12),
                itemCount: students.length,
                separatorBuilder: (_, __) => const SizedBox(height: 6),
                itemBuilder: (_, i) => _StudentAttRow(
                  student: students[i],
                  onToggle: (present) => context.read<TeacherProvider>().toggleAttendance(students[i].id, present),
                ),
              );
            }(),
          ),
        ],
      ),
    );
  }
}

class _StatBadge extends StatelessWidget {
  const _StatBadge(this.value, this.label, this.color);

  final String value;
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Text(value, style: TextStyle(color: color, fontWeight: FontWeight.w800, fontSize: 13)),
        const SizedBox(width: 4),
        Text(label, style: TextStyle(color: color.withOpacity(0.7), fontSize: 11)),
      ]),
    );
  }
}

class _QuickButton extends StatelessWidget {
  const _QuickButton(this.label, this.color, this.onTap);

  final String label;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
        decoration: BoxDecoration(
          color: color.withOpacity(0.12),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: color.withOpacity(0.3)),
        ),
        child: Text(label, style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w700)),
      ),
    );
  }
}

class _StudentAttRow extends StatelessWidget {
  const _StudentAttRow({required this.student, required this.onToggle});

  final TeacherStudentModel student;
  final ValueChanged<bool> onToggle;

  @override
  Widget build(BuildContext context) {
    final isPresent = student.isPresent;
    return Container(
      decoration: BoxDecoration(
        color: isPresent ? const Color(0xFF10B981).withOpacity(0.08) : const Color(0xFF162436),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isPresent ? const Color(0xFF10B981).withOpacity(0.3) : Colors.white.withOpacity(0.06),
        ),
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 2),
        leading: CircleAvatar(
          radius: 20,
          backgroundColor: isPresent
              ? const Color(0xFF10B981).withOpacity(0.2)
              : const Color(0xFF1E2D40),
          child: Text(
            _initials(student.fullName),
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w800,
              color: isPresent ? const Color(0xFF10B981) : Colors.white54,
            ),
          ),
        ),
        title: Text(
          student.fullName,
          style: TextStyle(
            color: isPresent ? Colors.white : Colors.white70,
            fontWeight: FontWeight.w700,
            fontSize: 14,
          ),
        ),
        subtitle: student.balance < 0
            ? Text(
                'Qarzi: ${Formatters.currency(student.balance.abs())}',
                style: const TextStyle(color: Color(0xFFEF4444), fontSize: 11, fontWeight: FontWeight.w600),
              )
            : null,
        trailing: GestureDetector(
          onTap: () => onToggle(!isPresent),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            width: 52,
            height: 28,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(14),
              color: isPresent ? const Color(0xFF10B981) : const Color(0xFF1E2D40),
              border: Border.all(
                color: isPresent ? const Color(0xFF10B981) : Colors.white24,
              ),
            ),
            child: AnimatedAlign(
              duration: const Duration(milliseconds: 200),
              curve: Curves.easeInOut,
              alignment: isPresent ? Alignment.centerRight : Alignment.centerLeft,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 3),
                child: Container(
                  width: 22,
                  height: 22,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: isPresent ? Colors.white : Colors.white38,
                  ),
                  child: Icon(
                    isPresent ? Icons.check_rounded : Icons.close_rounded,
                    size: 12,
                    color: isPresent ? const Color(0xFF10B981) : Colors.white54,
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  static String _initials(String name) {
    final parts = name.trim().split(RegExp(r'\s+')).where((e) => e.isNotEmpty).toList();
    if (parts.isEmpty) return '?';
    return parts.take(2).map((e) => e[0].toUpperCase()).join();
  }
}
