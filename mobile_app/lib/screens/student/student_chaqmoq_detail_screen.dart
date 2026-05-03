import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/screens/student/widgets/student_atmospheric_backdrop.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

/// Bitta o'quvchining barcha chaqmoq tarixi — admin paneldagi
/// student_detail sahifasiga mos.
class StudentChaqmoqDetailScreen extends StatefulWidget {
  const StudentChaqmoqDetailScreen({
    super.key,
    required this.studentId,
    required this.fallbackName,
  });

  final int studentId;
  final String fallbackName;

  @override
  State<StudentChaqmoqDetailScreen> createState() => _StudentChaqmoqDetailScreenState();
}

class _StudentChaqmoqDetailScreenState extends State<StudentChaqmoqDetailScreen> {
  ChaqmoqStudentDetailData? _data;
  bool _loading = true;
  String? _error;
  int _page = 1;
  static const int _perPage = 20;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load({int? page}) async {
    setState(() {
      _loading = true;
      _error = null;
      if (page != null) _page = page;
    });
    try {
      final service = context.read<DashboardService>();
      final data = await service.fetchChaqmoqStudentDetail(
        widget.studentId,
        page: _page,
        perPage: _perPage,
      );
      if (!mounted) return;
      setState(() {
        _data = data;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.code == 'not_found'
            ? "O‘quvchi topilmadi"
            : e.message;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = "Tarix yuklanmadi";
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Scaffold(
      backgroundColor: tokens.bg,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        foregroundColor: tokens.text,
        title: Text(
          _data?.studentName.isNotEmpty == true ? _data!.studentName : widget.fallbackName,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: GoogleFonts.inter(
            fontSize: 16,
            fontWeight: FontWeight.w800,
            color: tokens.text,
          ),
        ),
      ),
      body: Stack(
        children: [
          const StudentAtmosphericBackdrop(),
          SafeArea(
            top: false,
            child: RefreshIndicator(
              color: tokens.primary,
              onRefresh: () => _load(page: 1),
              child: _body(tokens),
            ),
          ),
        ],
      ),
    );
  }

  Widget _body(StudentTokens tokens) {
    if (_loading && _data == null) {
      return Center(
        child: CircularProgressIndicator(color: tokens.primary, strokeWidth: 2.4),
      );
    }
    if (_error != null && _data == null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline_rounded, color: tokens.danger, size: 36),
            const SizedBox(height: 8),
            Text(
              _error!,
              style: GoogleFonts.inter(color: tokens.text, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 12),
            FilledButton.tonal(
              onPressed: () => _load(page: 1),
              child: const Text('Qayta urinish'),
            ),
          ],
        ),
      );
    }
    final data = _data!;
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(parent: BouncingScrollPhysics()),
      padding: const EdgeInsets.fromLTRB(18, 8, 18, 24),
      children: [
        _SummaryHero(
          name: data.studentName.isEmpty ? widget.fallbackName : data.studentName,
          totalPlus: data.totalPlus,
          totalMinus: data.totalMinus,
          balance: data.balance,
        ),
        const SizedBox(height: 14),
        if (data.teacherStats.isNotEmpty) ...[
          Text(
            'KIM TOMONIDAN',
            style: GoogleFonts.inter(
              fontSize: 11,
              fontWeight: FontWeight.w800,
              color: tokens.textMuted,
              letterSpacing: 1.6,
            ),
          ),
          const SizedBox(height: 8),
          Container(
            decoration: BoxDecoration(
              color: tokens.glass,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: tokens.border),
            ),
            child: Column(
              children: [
                for (var i = 0; i < data.teacherStats.length; i++) ...[
                  _TeacherRow(stat: data.teacherStats[i]),
                  if (i < data.teacherStats.length - 1)
                    Container(height: 1, color: tokens.border),
                ],
              ],
            ),
          ),
          const SizedBox(height: 18),
        ],
        Row(
          children: [
            Text(
              'CHAQMOQ TARIXI',
              style: GoogleFonts.inter(
                fontSize: 11,
                fontWeight: FontWeight.w800,
                color: tokens.textMuted,
                letterSpacing: 1.6,
              ),
            ),
            const Spacer(),
            Text(
              'Jami: ${data.totalItems}',
              style: GoogleFonts.inter(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                color: tokens.textMuted,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        if (data.items.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 24),
            child: Center(
              child: Text(
                'Hozircha chaqmoq tarixi yo‘q',
                style: GoogleFonts.inter(
                  color: tokens.textMuted,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          )
        else
          ...data.items.map((e) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: _LedgerRow(entry: e),
              )),
        if (data.totalPages > 1) ...[
          const SizedBox(height: 8),
          _PageNav(
            current: data.page,
            totalPages: data.totalPages,
            onChange: (p) => _load(page: p),
          ),
        ],
      ],
    );
  }
}

class _SummaryHero extends StatelessWidget {
  const _SummaryHero({
    required this.name,
    required this.totalPlus,
    required this.totalMinus,
    required this.balance,
  });

  final String name;
  final int totalPlus;
  final int totalMinus;
  final int balance;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: tokens.heroGradient,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: tokens.primary.withValues(alpha: 0.28)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 52,
                height: 52,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: tokens.violetTealGradient,
                ),
                child: const Icon(Icons.bolt_rounded, color: Colors.white, size: 26),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'JAMI BALANS',
                      style: GoogleFonts.inter(
                        fontSize: 10.5,
                        fontWeight: FontWeight.w800,
                        color: tokens.textMuted,
                        letterSpacing: 1.4,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: [
                        Text(
                          Formatters.number(balance),
                          style: GoogleFonts.inter(
                            fontSize: 22,
                            fontWeight: FontWeight.w800,
                            color: tokens.text,
                            letterSpacing: -0.4,
                          ),
                        ),
                        const SizedBox(width: 4),
                        Icon(Icons.bolt_rounded, color: tokens.primary, size: 18),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: _StatBox(
                  label: "Qo‘shilgan",
                  value: '+${Formatters.number(totalPlus)}',
                  color: tokens.success,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _StatBox(
                  label: 'Ayrilgan',
                  value: '-${Formatters.number(totalMinus)}',
                  color: tokens.danger,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _StatBox extends StatelessWidget {
  const _StatBox({required this.label, required this.value, required this.color});

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: tokens.tonedSurface(color),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: GoogleFonts.inter(
              fontSize: 10.5,
              fontWeight: FontWeight.w700,
              color: tokens.textMuted,
              letterSpacing: 0.4,
            ),
          ),
          const SizedBox(height: 2),
          Row(
            children: [
              Text(
                value,
                style: GoogleFonts.inter(
                  fontSize: 16,
                  fontWeight: FontWeight.w800,
                  color: color,
                  letterSpacing: -0.3,
                ),
              ),
              const SizedBox(width: 3),
              Icon(Icons.bolt_rounded, color: color, size: 14),
            ],
          ),
        ],
      ),
    );
  }
}

class _TeacherRow extends StatelessWidget {
  const _TeacherRow({required this.stat});

  final ChaqmoqTeacherStat stat;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final roleLabel = _roleLabel(stat.role);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: tokens.tonedSurface(tokens.primary),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(Icons.person_rounded, color: tokens.primary, size: 18),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  stat.fullName.isEmpty ? '—' : stat.fullName,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                    color: tokens.text,
                  ),
                ),
                if (roleLabel.isNotEmpty)
                  Text(
                    roleLabel,
                    style: GoogleFonts.inter(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: tokens.textMuted,
                    ),
                  ),
              ],
            ),
          ),
          if (stat.coinPlus > 0) ...[
            Text(
              '+${Formatters.number(stat.coinPlus)}',
              style: GoogleFonts.inter(
                fontSize: 12.5,
                fontWeight: FontWeight.w800,
                color: tokens.success,
              ),
            ),
            const SizedBox(width: 3),
            Icon(Icons.bolt_rounded, color: tokens.success, size: 13),
          ],
          if (stat.coinMinus > 0) ...[
            const SizedBox(width: 8),
            Text(
              '-${Formatters.number(stat.coinMinus)}',
              style: GoogleFonts.inter(
                fontSize: 12.5,
                fontWeight: FontWeight.w800,
                color: tokens.danger,
              ),
            ),
            const SizedBox(width: 3),
            Icon(Icons.bolt_rounded, color: tokens.danger, size: 13),
          ],
        ],
      ),
    );
  }

  String _roleLabel(String role) {
    switch (role.toLowerCase()) {
      case 'teacher':
        return "O‘qituvchi";
      case 'manager':
        return 'Manager';
      case 'director':
        return 'Direktor';
      case 'parent':
        return 'Ota-ona';
      case 'student':
        return "O‘quvchi";
      default:
        return role;
    }
  }
}

class _LedgerRow extends StatelessWidget {
  const _LedgerRow({required this.entry});

  final ChaqmoqLedgerEntry entry;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final positive = entry.points >= 0;
    final color = positive ? tokens.success : tokens.danger;
    final dateLabel = DateFormat('d MMM yyyy · HH:mm', 'uz').format(entry.createdAt);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      decoration: BoxDecoration(
        color: tokens.glass,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: tokens.border),
      ),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: tokens.tonedSurface(color),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(
              positive ? Icons.add_rounded : Icons.remove_rounded,
              color: color,
              size: 18,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  entry.ruleName.isEmpty ? '—' : entry.ruleName,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                    color: tokens.text,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  _subtitle(entry),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 11.5,
                    fontWeight: FontWeight.w600,
                    color: tokens.textMuted,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  dateLabel,
                  style: GoogleFonts.inter(
                    fontSize: 10.5,
                    fontWeight: FontWeight.w600,
                    color: tokens.textDim,
                  ),
                ),
              ],
            ),
          ),
          Text(
            '${positive ? '+' : ''}${entry.points}',
            style: GoogleFonts.inter(
              fontSize: 14.5,
              fontWeight: FontWeight.w800,
              color: color,
            ),
          ),
          const SizedBox(width: 3),
          Icon(Icons.bolt_rounded, color: color, size: 15),
        ],
      ),
    );
  }

  String _subtitle(ChaqmoqLedgerEntry e) {
    final parts = <String>[];
    if (e.giverName.isNotEmpty) parts.add(e.giverName);
    if (e.groupName.isNotEmpty) parts.add(e.groupName);
    return parts.isEmpty ? '—' : parts.join(' · ');
  }
}

class _PageNav extends StatelessWidget {
  const _PageNav({
    required this.current,
    required this.totalPages,
    required this.onChange,
  });

  final int current;
  final int totalPages;
  final ValueChanged<int> onChange;

  @override
  Widget build(BuildContext context) {
    final start = (current - 2).clamp(1, totalPages);
    final end = (current + 2).clamp(1, totalPages);
    final pages = [for (var i = start; i <= end; i++) i];
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        _PageBtn(
          icon: Icons.chevron_left_rounded,
          enabled: current > 1,
          onTap: () => onChange(current - 1),
        ),
        const SizedBox(width: 6),
        for (final p in pages) ...[
          _PageNumber(
            label: '$p',
            isActive: p == current,
            onTap: () => onChange(p),
          ),
          const SizedBox(width: 4),
        ],
        const SizedBox(width: 2),
        _PageBtn(
          icon: Icons.chevron_right_rounded,
          enabled: current < totalPages,
          onTap: () => onChange(current + 1),
        ),
      ],
    );
  }
}

class _PageBtn extends StatelessWidget {
  const _PageBtn({required this.icon, required this.enabled, required this.onTap});

  final IconData icon;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Opacity(
      opacity: enabled ? 1 : 0.4,
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(10),
        child: InkWell(
          onTap: enabled ? onTap : null,
          borderRadius: BorderRadius.circular(10),
          child: Container(
            width: 32,
            height: 32,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: tokens.glass,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: tokens.border),
            ),
            child: Icon(icon, size: 18, color: tokens.text),
          ),
        ),
      ),
    );
  }
}

class _PageNumber extends StatelessWidget {
  const _PageNumber({required this.label, required this.isActive, required this.onTap});

  final String label;
  final bool isActive;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(10),
      child: InkWell(
        onTap: isActive ? null : onTap,
        borderRadius: BorderRadius.circular(10),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          constraints: const BoxConstraints(minWidth: 32),
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: isActive ? tokens.primary : tokens.glass,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color: isActive ? Colors.transparent : tokens.border,
            ),
          ),
          child: Text(
            label,
            style: GoogleFonts.inter(
              fontSize: 12.5,
              fontWeight: FontWeight.w800,
              color: isActive ? tokens.onPrimary : tokens.text,
            ),
          ),
        ),
      ),
    );
  }
}
