import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/widgets/app_badge.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';

/// Single chaqmoq event for one day.
class StudentBallEvent {
  const StudentBallEvent({
    required this.subject,
    required this.teacher,
    required this.points,
    this.time,
    this.note,
  });

  final String subject;
  final String teacher;
  final int points;
  final DateTime? time;
  final String? note;
}

/// Bottom sheet showing one day's chaqmoq events: subject, teacher, time, ball.
class StudentDayDetailSheet extends StatelessWidget {
  const StudentDayDetailSheet({
    super.key,
    required this.date,
    required this.events,
    this.status,
  });

  final DateTime date;
  final List<StudentBallEvent> events;
  final DayStatus? status;

  static Future<void> show(
    BuildContext context, {
    required DateTime date,
    required List<StudentBallEvent> events,
    DayStatus? status,
  }) {
    return showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (_) => StudentDayDetailSheet(
        date: date,
        events: events,
        status: status,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final added = events.where((e) => e.points > 0).fold<int>(0, (s, e) => s + e.points);
    final removed = events.where((e) => e.points < 0).fold<int>(0, (s, e) => s + e.points.abs());
    final net = added - removed;
    final inferred = status ?? _inferStatus(net.toDouble(), events);

    return SafeArea(
      top: false,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxHeight: MediaQuery.of(context).size.height * 0.85,
        ),
        child: Container(
          margin: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 20),
          decoration: BoxDecoration(
            color: tokens.isDark ? tokens.surfaceElevated : tokens.surface,
            borderRadius: BorderRadius.circular(22),
            border: Border.all(color: tokens.border),
            boxShadow: [
              BoxShadow(color: tokens.shadow, blurRadius: 28, offset: const Offset(0, 8)),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 36,
                  height: 4,
                  decoration: BoxDecoration(
                    color: tokens.textDim,
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
              ),
              const SizedBox(height: 14),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          DateFormat('EEEE, d MMMM yyyy', 'uz').format(date),
                          style: GoogleFonts.inter(
                            fontSize: 15,
                            fontWeight: FontWeight.w800,
                            color: tokens.text,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          events.isEmpty
                              ? 'Bu sanada chaqmoq qayd etilmagan'
                              : '${events.length} ta voqea',
                          style: GoogleFonts.inter(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: tokens.textMuted,
                          ),
                        ),
                      ],
                    ),
                  ),
                  _StatusBadge(status: inferred, dark: tokens.isDark),
                ],
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(child: _StatBlock(label: "Qo‘shilgan", value: '+$added', color: tokens.success)),
                  const SizedBox(width: 10),
                  Expanded(child: _StatBlock(label: 'Ayrilgan', value: '-$removed', color: tokens.danger)),
                  const SizedBox(width: 10),
                  Expanded(
                    child: _StatBlock(
                      label: 'Sof',
                      value: '${net >= 0 ? '+' : ''}$net',
                      color: net > 0
                          ? tokens.primary
                          : (net < 0 ? tokens.danger : tokens.textMuted),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              if (events.isEmpty)
                _EmptyEvents(tokens: tokens)
              else ...[
                Text(
                  'CHAQMOQLAR TARIXI',
                  style: GoogleFonts.inter(
                    fontSize: 10.5,
                    fontWeight: FontWeight.w800,
                    color: tokens.textMuted,
                    letterSpacing: 1.4,
                  ),
                ),
                const SizedBox(height: 8),
                Flexible(
                  child: ListView.separated(
                    shrinkWrap: true,
                    physics: const ClampingScrollPhysics(),
                    itemBuilder: (_, i) => _EventTile(event: events[i]),
                    separatorBuilder: (_, _) => Container(
                      height: 1,
                      margin: const EdgeInsets.symmetric(horizontal: 4),
                      color: tokens.border,
                    ),
                    itemCount: events.length,
                  ),
                ),
              ],
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: () => Navigator.of(context).pop(),
                  style: FilledButton.styleFrom(
                    backgroundColor: tokens.primary,
                    foregroundColor: tokens.onPrimary,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                    padding: const EdgeInsets.symmetric(vertical: 12),
                  ),
                  child: Text(
                    'Yopish',
                    style: GoogleFonts.inter(fontSize: 13, fontWeight: FontWeight.w700),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  static DayStatus _inferStatus(double net, List<StudentBallEvent> events) {
    if (events.isEmpty) return DayStatus.noClass;
    if (net > 0) return DayStatus.attended;
    if (net < 0) return DayStatus.absent;
    return DayStatus.attended;
  }

}

class _EventTile extends StatelessWidget {
  const _EventTile({required this.event});

  final StudentBallEvent event;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final positive = event.points >= 0;
    final color = positive ? tokens.success : tokens.danger;
    final timeText = event.time == null
        ? null
        : DateFormat('HH:mm', 'uz').format(event.time!);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 38,
            height: 38,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: tokens.tonedSurface(color),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(
              positive ? Icons.bolt_rounded : Icons.trending_down_rounded,
              color: color,
              size: 20,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  event.subject,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                    color: tokens.text,
                  ),
                ),
                const SizedBox(height: 2),
                Row(
                  children: [
                    Icon(Icons.person_outline_rounded, size: 12, color: tokens.textMuted),
                    const SizedBox(width: 4),
                    Flexible(
                      child: Text(
                        event.teacher,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: GoogleFonts.inter(
                          fontSize: 11.5,
                          fontWeight: FontWeight.w600,
                          color: tokens.textMuted,
                        ),
                      ),
                    ),
                    if (timeText != null) ...[
                      const SizedBox(width: 8),
                      Icon(Icons.schedule_rounded, size: 12, color: tokens.textDim),
                      const SizedBox(width: 3),
                      Text(
                        timeText,
                        style: GoogleFonts.inter(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: tokens.textDim,
                        ),
                      ),
                    ],
                  ],
                ),
                if (event.note != null && event.note!.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(
                    event.note!,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: GoogleFonts.inter(
                      fontSize: 11.5,
                      fontWeight: FontWeight.w500,
                      color: tokens.textMuted,
                      height: 1.35,
                    ),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(width: 8),
          Text(
            '${positive ? '+' : ''}${event.points}',
            style: GoogleFonts.inter(
              fontSize: 15,
              fontWeight: FontWeight.w800,
              color: color,
              letterSpacing: -0.4,
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyEvents extends StatelessWidget {
  const _EmptyEvents({required this.tokens});

  final StudentTokens tokens;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: tokens.glass,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: tokens.border),
      ),
      child: Row(
        children: [
          Icon(Icons.event_busy_rounded, color: tokens.textDim, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              'Bu sanada dars yoki faollik qayd etilmagan',
              style: GoogleFonts.inter(
                fontSize: 12.5,
                fontWeight: FontWeight.w600,
                color: tokens.textMuted,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.status, required this.dark});

  final DayStatus status;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    switch (status) {
      case DayStatus.attended:
        return AppBadge(label: 'Kelgan', tone: AppBadgeTone.success, dark: dark);
      case DayStatus.late:
        return AppBadge(label: 'Kechikkan', tone: AppBadgeTone.warning, dark: dark);
      case DayStatus.absent:
        return AppBadge(label: 'Kelmagan', tone: AppBadgeTone.danger, dark: dark);
      case DayStatus.noClass:
        return AppBadge(label: 'Dars yo‘q', tone: AppBadgeTone.neutral, dark: dark);
    }
  }
}

class _StatBlock extends StatelessWidget {
  const _StatBlock({required this.label, required this.value, required this.color});

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
      decoration: BoxDecoration(
        color: tokens.tonedSurface(color),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: tokens.tonedBorder(color)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label,
              style: GoogleFonts.inter(
                fontSize: 10,
                fontWeight: FontWeight.w700,
                color: tokens.textMuted,
                letterSpacing: 0.4,
              )),
          const SizedBox(height: 2),
          Text(value,
              style: GoogleFonts.inter(
                fontSize: 17,
                fontWeight: FontWeight.w800,
                color: color,
                letterSpacing: -0.4,
              )),
        ],
      ),
    );
  }
}

enum DayStatus { attended, late, absent, noClass }
