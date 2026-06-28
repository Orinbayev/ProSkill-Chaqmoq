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

class _State extends State<TeacherAttendanceScreen>
    with SingleTickerProviderStateMixin {
  DateTime _date = DateTime.now();
  late final TabController _tabCtrl = TabController(length: 2, vsync: this);

  static const _indigo = Color(0xFF6366F1);
  static const _amber = Color(0xFFF59E0B);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        _load();
        context.read<TeacherProvider>().loadChaqmoqRules();
      }
    });
  }

  @override
  void dispose() {
    _tabCtrl.dispose();
    super.dispose();
  }

  void _load() {
    context.read<TeacherProvider>().loadAttendance(widget.group.id, date: _date);
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: DateTime(_date.year, _date.month - 3),
      lastDate: DateTime.now(),
      builder: (ctx, child) => Theme(
        data: ThemeData.dark().copyWith(
          colorScheme: const ColorScheme.dark(
            primary: _indigo,
            surface: Color(0xFF1E2D40),
          ),
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

  bool get _isToday {
    final now = DateTime.now();
    return _date.year == now.year &&
        _date.month == now.month &&
        _date.day == now.day;
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bg = isDark ? const Color(0xFF0B1220) : const Color(0xFFF5F7FB);
    final navBg = isDark ? const Color(0xFF0F1B2A) : Colors.white;
    final borderColor =
        isDark ? Colors.white.withValues(alpha: 0.07) : Colors.black.withValues(alpha: 0.06);

    return Scaffold(
      backgroundColor: bg,
      appBar: AppBar(
        backgroundColor: navBg,
        elevation: 0,
        surfaceTintColor: Colors.transparent,
        leading: IconButton(
          icon: Icon(Icons.arrow_back_rounded,
              color: isDark ? Colors.white : Colors.black87),
          onPressed: () => Navigator.pop(context),
        ),
        title: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(
            widget.group.name,
            style: TextStyle(
              color: isDark ? Colors.white : const Color(0xFF0F172A),
              fontWeight: FontWeight.w800,
              fontSize: 15,
            ),
          ),
          Text(
            'Davomat & Chaqmoq',
            style: TextStyle(
              color: isDark ? Colors.white54 : Colors.black45,
              fontSize: 11,
            ),
          ),
        ]),
        actions: [
          TextButton.icon(
            onPressed: _pickDate,
            icon: Icon(Icons.calendar_today_rounded,
                size: 13,
                color: _isToday ? _indigo : _amber),
            label: Text(
              _isToday ? 'Bugun' : Formatters.date(_date),
              style: TextStyle(
                color: _isToday ? _indigo : _amber,
                fontWeight: FontWeight.w700,
                fontSize: 12,
              ),
            ),
          ),
        ],
        bottom: TabBar(
          controller: _tabCtrl,
          indicatorColor: _indigo,
          indicatorWeight: 3,
          labelColor: _indigo,
          unselectedLabelColor: isDark ? Colors.white38 : Colors.black38,
          labelStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13),
          unselectedLabelStyle:
              const TextStyle(fontWeight: FontWeight.w500, fontSize: 13),
          tabs: const [
            Tab(icon: Icon(Icons.how_to_reg_rounded, size: 18), text: 'Davomat'),
            Tab(icon: Icon(Icons.bolt_rounded, size: 18), text: 'Chaqmoq'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabCtrl,
        children: [
          _AttendanceTab(
            group: widget.group,
            date: _date,
            isToday: _isToday,
            isDark: isDark,
            bg: bg,
            borderColor: borderColor,
            onMarkAll: _markAll,
            onReload: _load,
          ),
          _ChaqmoqTab(
            group: widget.group,
            isDark: isDark,
            bg: bg,
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// DAVOMAT TAB
// ─────────────────────────────────────────────────────────────────────────────

class _AttendanceTab extends StatelessWidget {
  const _AttendanceTab({
    required this.group,
    required this.date,
    required this.isToday,
    required this.isDark,
    required this.bg,
    required this.borderColor,
    required this.onMarkAll,
    required this.onReload,
  });

  final TeacherGroupModel group;
  final DateTime date;
  final bool isToday;
  final bool isDark;
  final Color bg;
  final Color borderColor;
  final ValueChanged<bool> onMarkAll;
  final VoidCallback onReload;

  @override
  Widget build(BuildContext context) {
    final p = context.watch<TeacherProvider>();
    final att = p.attendance;
    final students = att?.students ?? <TeacherStudentModel>[];
    final presentCount = students.where((s) => s.isPresent).length;
    final navBg = isDark ? const Color(0xFF0F1B2A) : Colors.white;

    return Column(children: [
      // Stats bar
      Container(
        color: navBg,
        padding: const EdgeInsets.fromLTRB(16, 10, 16, 12),
        child: Column(children: [
          Row(children: [
            _StatChip('$presentCount', 'Keldi', const Color(0xFF10B981)),
            const SizedBox(width: 8),
            _StatChip('${students.length - presentCount}', 'Kelmadi',
                const Color(0xFFEF4444)),
            const SizedBox(width: 8),
            _StatChip('${students.length}', 'Jami', const Color(0xFF6366F1)),
            const Spacer(),
            if (students.isNotEmpty)
              Text(
                '${students.isEmpty ? 0 : (presentCount / students.length * 100).round()}%',
                style: TextStyle(
                  color: isDark ? Colors.white70 : Colors.black54,
                  fontWeight: FontWeight.w800,
                  fontSize: 14,
                ),
              ),
          ]),
          if (students.isNotEmpty) ...[
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: students.isEmpty
                    ? 0
                    : presentCount / students.length,
                backgroundColor: isDark
                    ? Colors.white12
                    : Colors.black.withValues(alpha: 0.06),
                valueColor:
                    const AlwaysStoppedAnimation(Color(0xFF10B981)),
                minHeight: 5,
              ),
            ),
            const SizedBox(height: 10),
            Row(children: [
              Expanded(
                child: _QuickBtn(
                  icon: Icons.check_circle_rounded,
                  label: 'Barchasi keldi',
                  color: const Color(0xFF10B981),
                  onTap: () => onMarkAll(true),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _QuickBtn(
                  icon: Icons.cancel_rounded,
                  label: 'Barchasi kelmadi',
                  color: const Color(0xFFEF4444),
                  onTap: () => onMarkAll(false),
                ),
              ),
            ]),
          ],
        ]),
      ),

      // List
      Expanded(child: () {
        if (p.attendanceState == ViewState.loading) {
          return const Center(
              child: CircularProgressIndicator(
                  color: Color(0xFF6366F1)));
        }
        if (p.attendanceState == ViewState.error) {
          return _ErrorView(message: p.attendanceError, onRetry: onReload);
        }
        if (students.isEmpty) {
          return _EmptyView(
            icon: Icons.person_off_rounded,
            message: "O'quvchilar topilmadi",
            isDark: isDark,
          );
        }
        return RefreshIndicator(
          color: const Color(0xFF6366F1),
          onRefresh: () async => onReload(),
          child: ListView.separated(
            padding: const EdgeInsets.all(12),
            itemCount: students.length,
            separatorBuilder: (_, __) => const SizedBox(height: 6),
            itemBuilder: (ctx, i) => _AttendanceRow(
              student: students[i],
              isDark: isDark,
              onToggle: (v) {
                HapticFeedback.lightImpact();
                context.read<TeacherProvider>().toggleAttendance(
                    students[i].id, v);
              },
            ),
          ),
        );
      }()),
    ]);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// CHAQMOQ TAB
// ─────────────────────────────────────────────────────────────────────────────

class _ChaqmoqTab extends StatelessWidget {
  const _ChaqmoqTab({
    required this.group,
    required this.isDark,
    required this.bg,
  });

  final TeacherGroupModel group;
  final bool isDark;
  final Color bg;

  @override
  Widget build(BuildContext context) {
    final p = context.watch<TeacherProvider>();
    final students = p.attendance?.students ?? <TeacherStudentModel>[];

    if (p.attendanceState == ViewState.loading) {
      return const Center(
          child: CircularProgressIndicator(color: Color(0xFF6366F1)));
    }
    if (p.attendanceState == ViewState.error) {
      return _ErrorView(message: p.attendanceError, onRetry: () {
        context.read<TeacherProvider>().loadAttendance(group.id);
      });
    }
    if (students.isEmpty) {
      return _EmptyView(
        icon: Icons.bolt_rounded,
        message: "O'quvchilar topilmadi",
        isDark: isDark,
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.all(12),
      itemCount: students.length,
      separatorBuilder: (_, __) => const SizedBox(height: 6),
      itemBuilder: (ctx, i) => _ChaqmoqRow(
        student: students[i],
        isDark: isDark,
        onAward: () => _openAwardSheet(ctx, students[i]),
      ),
    );
  }

  void _openAwardSheet(BuildContext context, TeacherStudentModel student) {
    final provider = context.read<TeacherProvider>();
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => Provider.value(
        value: provider,
        child: _AwardSheet(student: student, isDark: isDark),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Award bottom sheet
// ─────────────────────────────────────────────────────────────────────────────

class _AwardSheet extends StatefulWidget {
  const _AwardSheet({required this.student, required this.isDark});

  final TeacherStudentModel student;
  final bool isDark;

  @override
  State<_AwardSheet> createState() => _AwardSheetState();
}

class _AwardSheetState extends State<_AwardSheet> {
  ChaqmoqRule? _selectedRule;
  int _ball = 1;
  bool _loading = false;
  String? _error;

  static const _indigo = Color(0xFF6366F1);
  static const _green = Color(0xFF10B981);
  static const _red = Color(0xFFEF4444);

  @override
  Widget build(BuildContext context) {
    final p = context.watch<TeacherProvider>();
    final rules = p.chaqmoqRules.cast<ChaqmoqRule>();
    final isDark = widget.isDark;
    final sheetBg = isDark ? const Color(0xFF0F1B2A) : Colors.white;
    final cardBg = isDark ? const Color(0xFF162436) : const Color(0xFFF8FAFC);

    final plusRules = rules.where((r) => r.isPlus).toList();
    final minusRules = rules.where((r) => !r.isPlus).toList();

    return Padding(
      padding: EdgeInsets.only(
          bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        decoration: BoxDecoration(
          color: sheetBg,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
        ),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          // Handle
          Container(
            margin: const EdgeInsets.only(top: 12),
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: isDark ? Colors.white24 : Colors.black12,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(height: 16),

          // Header
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Row(children: [
              CircleAvatar(
                radius: 22,
                backgroundColor: _indigo.withValues(alpha: 0.15),
                child: Text(
                  _initials(widget.student.fullName),
                  style: const TextStyle(
                    color: _indigo,
                    fontWeight: FontWeight.w800,
                    fontSize: 14,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      widget.student.fullName,
                      style: TextStyle(
                        color: isDark ? Colors.white : const Color(0xFF0F172A),
                        fontWeight: FontWeight.w800,
                        fontSize: 16,
                      ),
                    ),
                    Row(children: [
                      const Icon(Icons.bolt_rounded,
                          size: 14, color: Color(0xFFF59E0B)),
                      const SizedBox(width: 3),
                      Text(
                        '${widget.student.chaqmoqBalance} chaqmoq',
                        style: const TextStyle(
                          color: Color(0xFFF59E0B),
                          fontWeight: FontWeight.w700,
                          fontSize: 12,
                        ),
                      ),
                    ]),
                  ],
                ),
              ),
            ]),
          ),
          const SizedBox(height: 16),
          Divider(
            color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06),
            height: 1,
          ),

          // Rules section
          ConstrainedBox(
            constraints: BoxConstraints(
              maxHeight: MediaQuery.of(context).size.height * 0.55,
            ),
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (rules.isEmpty) ...[
                    Center(
                      child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 24),
                        child: Column(children: [
                          Icon(Icons.info_outline,
                              color: isDark ? Colors.white38 : Colors.black26,
                              size: 36),
                          const SizedBox(height: 8),
                          Text(
                            "Chaqmoq qoidalari topilmadi.\nAdmin panelidан qoida qo'shing.",
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: isDark ? Colors.white38 : Colors.black38,
                              fontSize: 13,
                            ),
                          ),
                        ]),
                      ),
                    ),
                  ] else ...[
                    if (plusRules.isNotEmpty) ...[
                      _SectionLabel(
                        icon: Icons.add_circle_rounded,
                        label: 'Chaqmoq qo\'shish',
                        color: _green,
                        isDark: isDark,
                      ),
                      const SizedBox(height: 8),
                      ...plusRules.map((r) => _RuleCard(
                            rule: r,
                            selected: _selectedRule?.id == r.id,
                            isDark: isDark,
                            cardBg: cardBg,
                            onTap: () => setState(() {
                              _selectedRule = r;
                              _ball = r.maxBaho;
                            }),
                          )),
                    ],
                    if (minusRules.isNotEmpty) ...[
                      const SizedBox(height: 16),
                      _SectionLabel(
                        icon: Icons.remove_circle_rounded,
                        label: 'Chaqmoq olish',
                        color: _red,
                        isDark: isDark,
                      ),
                      const SizedBox(height: 8),
                      ...minusRules.map((r) => _RuleCard(
                            rule: r,
                            selected: _selectedRule?.id == r.id,
                            isDark: isDark,
                            cardBg: cardBg,
                            onTap: () => setState(() {
                              _selectedRule = r;
                              _ball = r.minBaho;
                            }),
                          )),
                    ],

                    // Ball selector
                    if (_selectedRule != null) ...[
                      const SizedBox(height: 20),
                      _BallSelector(
                        rule: _selectedRule!,
                        ball: _ball,
                        isDark: isDark,
                        onChanged: (v) => setState(() => _ball = v),
                      ),
                    ],

                    if (_error != null) ...[
                      const SizedBox(height: 12),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: _red.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Row(children: [
                          const Icon(Icons.error_outline,
                              color: _red, size: 16),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(_error!,
                                style: const TextStyle(
                                    color: _red, fontSize: 12)),
                          ),
                        ]),
                      ),
                    ],

                    const SizedBox(height: 20),
                    SizedBox(
                      width: double.infinity,
                      height: 52,
                      child: ElevatedButton(
                        onPressed: (_selectedRule == null || _loading)
                            ? null
                            : _submit,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: _selectedRule?.isPlus == true
                              ? _green
                              : _red,
                          foregroundColor: Colors.white,
                          disabledBackgroundColor: isDark
                              ? Colors.white12
                              : Colors.black12,
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(14)),
                          elevation: 0,
                        ),
                        child: _loading
                            ? const SizedBox(
                                width: 22,
                                height: 22,
                                child: CircularProgressIndicator(
                                  color: Colors.white,
                                  strokeWidth: 2.5,
                                ),
                              )
                            : Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(
                                    _selectedRule?.isPlus == true
                                        ? Icons.add_rounded
                                        : Icons.remove_rounded,
                                    size: 20,
                                  ),
                                  const SizedBox(width: 6),
                                  Text(
                                    _selectedRule?.isPlus == true
                                        ? '$_ball chaqmoq berish'
                                        : '$_ball chaqmoq olish',
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w800,
                                      fontSize: 15,
                                    ),
                                  ),
                                ],
                              ),
                      ),
                    ),
                    const SizedBox(height: 8),
                  ],
                ],
              ),
            ),
          ),
        ]),
      ),
    );
  }

  Future<void> _submit() async {
    if (_selectedRule == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await context.read<TeacherProvider>().awardChaqmoq(
            studentId: widget.student.id,
            ruleId: _selectedRule!.id,
            ball: _ball,
          );
      HapticFeedback.heavyImpact();
      if (mounted) Navigator.pop(context);
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  static String _initials(String n) {
    final parts = n.trim().split(RegExp(r'\s+')).where((e) => e.isNotEmpty).toList();
    if (parts.isEmpty) return '?';
    return parts.take(2).map((e) => e[0].toUpperCase()).join();
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Small widgets
// ─────────────────────────────────────────────────────────────────────────────

class _AttendanceRow extends StatelessWidget {
  const _AttendanceRow({
    required this.student,
    required this.isDark,
    required this.onToggle,
  });

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
              : (isDark
                  ? Colors.white.withValues(alpha: 0.06)
                  : Colors.black.withValues(alpha: 0.05)),
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
              color: present
                  ? const Color(0xFF10B981)
                  : (isDark ? Colors.white54 : Colors.black45),
            ),
          ),
        ),
        title: Text(
          student.fullName,
          style: TextStyle(
            color: isDark ? Colors.white : const Color(0xFF0F172A),
            fontWeight: FontWeight.w700,
            fontSize: 14,
          ),
        ),
        subtitle: student.balance < 0
            ? Text(
                'Qarzi: ${Formatters.currency(student.balance.abs())}',
                style: const TextStyle(
                  color: Color(0xFFEF4444),
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                ),
              )
            : null,
        trailing: GestureDetector(
          onTap: () => onToggle(!present),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 220),
            width: 52,
            height: 28,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(14),
              color: present
                  ? const Color(0xFF10B981)
                  : (isDark
                      ? const Color(0xFF1E2D40)
                      : const Color(0xFFE2E8F0)),
            ),
            child: AnimatedAlign(
              duration: const Duration(milliseconds: 220),
              curve: Curves.easeInOut,
              alignment:
                  present ? Alignment.centerRight : Alignment.centerLeft,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 3),
                child: Container(
                  width: 22,
                  height: 22,
                  decoration: const BoxDecoration(
                    shape: BoxShape.circle,
                    color: Colors.white,
                  ),
                  child: Icon(
                    present ? Icons.check_rounded : Icons.close_rounded,
                    size: 12,
                    color: present
                        ? const Color(0xFF10B981)
                        : Colors.grey,
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
    final parts =
        n.trim().split(RegExp(r'\s+')).where((e) => e.isNotEmpty).toList();
    if (parts.isEmpty) return '?';
    return parts.take(2).map((e) => e[0].toUpperCase()).join();
  }
}

class _ChaqmoqRow extends StatelessWidget {
  const _ChaqmoqRow({
    required this.student,
    required this.isDark,
    required this.onAward,
  });

  final TeacherStudentModel student;
  final bool isDark;
  final VoidCallback onAward;

  static const _amber = Color(0xFFF59E0B);
  static const _indigo = Color(0xFF6366F1);

  @override
  Widget build(BuildContext context) {
    final balance = student.chaqmoqBalance;
    final balanceColor = balance > 0 ? _amber : balance < 0
        ? const Color(0xFFEF4444) : (isDark ? Colors.white38 : Colors.black38);

    return Container(
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF162436) : Colors.white,
        borderRadius: BorderRadius.circular(13),
        border: Border.all(
          color: isDark
              ? Colors.white.withValues(alpha: 0.06)
              : Colors.black.withValues(alpha: 0.05),
        ),
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.fromLTRB(14, 4, 10, 4),
        leading: CircleAvatar(
          radius: 20,
          backgroundColor: _amber.withValues(alpha: 0.12),
          child: Text(
            _initials(student.fullName),
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w800,
              color: _amber,
            ),
          ),
        ),
        title: Text(
          student.fullName,
          style: TextStyle(
            color: isDark ? Colors.white : const Color(0xFF0F172A),
            fontWeight: FontWeight.w700,
            fontSize: 14,
          ),
        ),
        subtitle: Row(children: [
          const Icon(Icons.bolt_rounded, size: 13, color: _amber),
          const SizedBox(width: 3),
          Text(
            '$balance chaqmoq',
            style: TextStyle(
              color: balanceColor,
              fontSize: 12,
              fontWeight: FontWeight.w700,
            ),
          ),
        ]),
        trailing: GestureDetector(
          onTap: () {
            HapticFeedback.lightImpact();
            onAward();
          },
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            decoration: BoxDecoration(
              color: _indigo.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Row(mainAxisSize: MainAxisSize.min, children: [
              Icon(Icons.bolt_rounded, size: 15, color: _indigo),
              SizedBox(width: 4),
              Text(
                'Berish',
                style: TextStyle(
                  color: _indigo,
                  fontWeight: FontWeight.w700,
                  fontSize: 12,
                ),
              ),
            ]),
          ),
        ),
      ),
    );
  }

  static String _initials(String n) {
    final parts =
        n.trim().split(RegExp(r'\s+')).where((e) => e.isNotEmpty).toList();
    if (parts.isEmpty) return '?';
    return parts.take(2).map((e) => e[0].toUpperCase()).join();
  }
}

class _RuleCard extends StatelessWidget {
  const _RuleCard({
    required this.rule,
    required this.selected,
    required this.isDark,
    required this.cardBg,
    required this.onTap,
  });

  final ChaqmoqRule rule;
  final bool selected;
  final bool isDark;
  final Color cardBg;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = rule.isPlus ? const Color(0xFF10B981) : const Color(0xFFEF4444);
    return GestureDetector(
      onTap: () {
        HapticFeedback.selectionClick();
        onTap();
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        margin: const EdgeInsets.only(bottom: 6),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
        decoration: BoxDecoration(
          color: selected ? color.withValues(alpha: 0.12) : cardBg,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: selected
                ? color.withValues(alpha: 0.5)
                : (isDark
                    ? Colors.white.withValues(alpha: 0.06)
                    : Colors.black.withValues(alpha: 0.06)),
            width: selected ? 1.5 : 1,
          ),
        ),
        child: Row(children: [
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(
              rule.isPlus ? Icons.add_rounded : Icons.remove_rounded,
              color: color,
              size: 18,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(
                rule.nom,
                style: TextStyle(
                  color: isDark ? Colors.white : const Color(0xFF0F172A),
                  fontWeight: FontWeight.w700,
                  fontSize: 13,
                ),
              ),
              Text(
                '${rule.minBaho}–${rule.maxBaho} chaqmoq',
                style: TextStyle(
                  color: color,
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ]),
          ),
          if (selected)
            Icon(Icons.check_circle_rounded, color: color, size: 20),
        ]),
      ),
    );
  }
}

class _BallSelector extends StatelessWidget {
  const _BallSelector({
    required this.rule,
    required this.ball,
    required this.isDark,
    required this.onChanged,
  });

  final ChaqmoqRule rule;
  final int ball;
  final bool isDark;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    final color = rule.isPlus ? const Color(0xFF10B981) : const Color(0xFFEF4444);
    final steps = rule.maxBaho - rule.minBaho;

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Text(
          'Ball miqdori:',
          style: TextStyle(
            color: isDark ? Colors.white70 : Colors.black54,
            fontSize: 13,
            fontWeight: FontWeight.w600,
          ),
        ),
        const Spacer(),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(Icons.bolt_rounded, size: 14, color: color),
            const SizedBox(width: 4),
            Text(
              '$ball',
              style: TextStyle(
                color: color,
                fontWeight: FontWeight.w800,
                fontSize: 16,
              ),
            ),
          ]),
        ),
      ]),
      if (steps > 0) ...[
        const SizedBox(height: 6),
        SliderTheme(
          data: SliderThemeData(
            activeTrackColor: color,
            thumbColor: color,
            inactiveTrackColor: color.withValues(alpha: 0.2),
            overlayColor: color.withValues(alpha: 0.1),
            trackHeight: 4,
          ),
          child: Slider(
            value: ball.toDouble(),
            min: rule.minBaho.toDouble(),
            max: rule.maxBaho.toDouble(),
            divisions: steps > 0 ? steps : null,
            onChanged: (v) => onChanged(v.round()),
          ),
        ),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text('${rule.minBaho}',
                style: TextStyle(
                    color: isDark ? Colors.white38 : Colors.black38,
                    fontSize: 11)),
            Text('${rule.maxBaho}',
                style: TextStyle(
                    color: isDark ? Colors.white38 : Colors.black38,
                    fontSize: 11)),
          ],
        ),
      ],
    ]);
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel({
    required this.icon,
    required this.label,
    required this.color,
    required this.isDark,
  });

  final IconData icon;
  final String label;
  final Color color;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Row(children: [
      Icon(icon, size: 15, color: color),
      const SizedBox(width: 6),
      Text(
        label,
        style: TextStyle(
          color: color,
          fontWeight: FontWeight.w700,
          fontSize: 13,
        ),
      ),
    ]);
  }
}

class _StatChip extends StatelessWidget {
  const _StatChip(this.value, this.label, this.color);

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
        Text(value,
            style: TextStyle(
                color: color, fontWeight: FontWeight.w800, fontSize: 13)),
        const SizedBox(width: 4),
        Text(label,
            style: TextStyle(
                color: color.withValues(alpha: 0.7), fontSize: 11)),
      ]),
    );
  }
}

class _QuickBtn extends StatelessWidget {
  const _QuickBtn({
    required this.icon,
    required this.label,
    required this.color,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return OutlinedButton.icon(
      onPressed: onTap,
      icon: Icon(icon, size: 15),
      label: Text(label, style: const TextStyle(fontSize: 12)),
      style: OutlinedButton.styleFrom(
        foregroundColor: color,
        side: BorderSide(color: color),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        padding: const EdgeInsets.symmetric(vertical: 8),
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        const Icon(Icons.error_outline, color: Colors.red, size: 40),
        const SizedBox(height: 12),
        Text(message,
            style: const TextStyle(color: Colors.red, fontSize: 13),
            textAlign: TextAlign.center),
        const SizedBox(height: 16),
        ElevatedButton(onPressed: onRetry, child: const Text('Qayta')),
      ]),
    );
  }
}

class _EmptyView extends StatelessWidget {
  const _EmptyView({
    required this.icon,
    required this.message,
    required this.isDark,
  });

  final IconData icon;
  final String message;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon,
            color: isDark ? Colors.white24 : Colors.black26, size: 48),
        const SizedBox(height: 12),
        Text(message,
            style: TextStyle(
                color: isDark ? Colors.white38 : Colors.black38,
                fontSize: 15)),
      ]),
    );
  }
}
