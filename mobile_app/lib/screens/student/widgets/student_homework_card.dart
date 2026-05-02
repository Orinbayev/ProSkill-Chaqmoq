import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/widgets/app_badge.dart';
import 'package:chaqmoq_mobile/widgets/app_card.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class StudentHomeworkItem {
  const StudentHomeworkItem({
    required this.title,
    required this.subject,
    required this.deadline,
    required this.status,
  });

  final String title;
  final String subject;
  final DateTime? deadline;
  final HomeworkStatus status;
}

enum HomeworkStatus { done, pending, overdue }

class StudentHomeworkCard extends StatelessWidget {
  const StudentHomeworkCard({super.key, required this.items});

  final List<StudentHomeworkItem> items;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final pending = items.where((h) => h.status == HomeworkStatus.pending).length;
    final done = items.where((h) => h.status == HomeworkStatus.done).length;
    final overdue = items.where((h) => h.status == HomeworkStatus.overdue).length;
    return AppGCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Container(
                width: 36,
                height: 36,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: tokens.tonedSurface(tokens.secondary),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(Icons.assignment_outlined, color: tokens.secondary, size: 20),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Vazifalar',
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                    color: tokens.text,
                  ),
                ),
              ),
              Wrap(
                spacing: 4,
                children: [
                  if (pending > 0)
                    AppBadge(label: '$pending kutilmoqda', tone: AppBadgeTone.warning, dark: tokens.isDark),
                  if (overdue > 0)
                    AppBadge(label: '$overdue muddati o‘tgan', tone: AppBadgeTone.danger, dark: tokens.isDark),
                  if (overdue == 0 && pending == 0 && done > 0)
                    AppBadge(label: '$done bajarilgan', tone: AppBadgeTone.success, dark: tokens.isDark),
                ],
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (items.isEmpty)
            _Empty(tokens: tokens)
          else
            for (var i = 0; i < items.take(4).length; i++) ...[
              _Item(item: items[i]),
              if (i < items.take(4).length - 1)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Container(height: 1, color: tokens.border),
                ),
            ],
        ],
      ),
    );
  }
}

class _Empty extends StatelessWidget {
  const _Empty({required this.tokens});

  final StudentTokens tokens;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: tokens.glass,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: tokens.border),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.task_alt_rounded, color: tokens.textDim, size: 18),
          const SizedBox(width: 8),
          Text(
            'Hozircha vazifa yo‘q',
            style: GoogleFonts.inter(
              fontSize: 12.5,
              fontWeight: FontWeight.w600,
              color: tokens.textMuted,
            ),
          ),
        ],
      ),
    );
  }
}

class _Item extends StatelessWidget {
  const _Item({required this.item});

  final StudentHomeworkItem item;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final iconColor = item.status == HomeworkStatus.done
        ? tokens.success
        : (item.status == HomeworkStatus.overdue ? tokens.danger : tokens.warning);
    final iconData = item.status == HomeworkStatus.done
        ? Icons.check_circle_rounded
        : (item.status == HomeworkStatus.overdue
            ? Icons.error_outline_rounded
            : Icons.schedule_rounded);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Icon(iconData, color: iconColor, size: 18),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  item.title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w700,
                    color: tokens.text,
                  ),
                ),
                Text(
                  item.subject,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 10.5,
                    fontWeight: FontWeight.w600,
                    color: tokens.textMuted,
                  ),
                ),
              ],
            ),
          ),
          if (item.deadline != null)
            Text(
              Formatters.shortDayMonth(item.deadline),
              style: GoogleFonts.inter(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                color: iconColor,
              ),
            ),
        ],
      ),
    );
  }
}
