import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:flutter/material.dart';

enum NotificationKind {
  rewardAdded,
  rewardRemoved,
  payment,
  attendance,
  comment,
  grade,
  broadcast,
  info,
}

class NotificationPresentation {
  const NotificationPresentation({
    required this.kind,
    required this.title,
    required this.description,
    required this.typeLabel,
    required this.readLabel,
    required this.timeLabel,
    required this.icon,
    required this.accentColor,
    required this.iconColor,
    required this.iconBackground,
    this.reason,
    this.actorName,
    this.childName,
    this.amountLabel,
  });

  final NotificationKind kind;
  final String title;
  final String description;
  final String typeLabel;
  final String readLabel;
  final String timeLabel;
  final IconData icon;
  final Color accentColor;
  final Color iconColor;
  final Color iconBackground;
  final String? reason;
  final String? actorName;
  final String? childName;
  final String? amountLabel;
}

NotificationPresentation buildNotificationPresentation(NotificationModel item) {
  final kind = resolveNotificationKind(item);
  final lines = item.body
      .split('\n')
      .map((line) => line.trim())
      .where((line) => line.isNotEmpty)
      .toList();
  String? reason;
  final summaryLines = <String>[];
  for (final line in lines) {
    if (reason == null && _looksLikeReason(line)) {
      reason = _normalizeReason(line);
    } else {
      summaryLines.add(line);
    }
  }

  final title = item.title.trim().isNotEmpty
      ? item.title.trim()
      : _defaultTitle(kind);
  final description = summaryLines.join(' ').trim().isNotEmpty
      ? summaryLines.join(' ').trim()
      : _defaultDescription(kind);
  final actorName = item.senderName.trim().isNotEmpty
      ? item.senderName.trim()
      : _extractActorName(description);
  final childName = item.recipientName.trim().isNotEmpty
      ? item.recipientName.trim()
      : null;
  final amountLabel = _extractAmountLabel(
    source: '$title\n${item.body}',
    kind: kind,
  );
  final visual = _visualFor(kind);

  return NotificationPresentation(
    kind: kind,
    title: title,
    description: description,
    reason: reason,
    actorName: actorName.isEmpty ? null : actorName,
    childName: childName == null || childName.isEmpty ? null : childName,
    amountLabel: amountLabel,
    typeLabel: _typeLabel(kind),
    readLabel: item.isRead ? 'O‘qilgan' : 'O‘qilmagan',
    timeLabel: _timeLabel(item.createdAt),
    icon: visual.icon,
    accentColor: visual.accentColor,
    iconColor: visual.iconColor,
    iconBackground: visual.iconBackground,
  );
}

NotificationKind resolveNotificationKind(NotificationModel item) {
  final raw = '${item.type} ${item.title} ${item.body}'.toLowerCase();
  final text = raw
      .replaceAll('`', "'")
      .replaceAll('’', "'")
      .replaceAll('‘', "'");

  bool hasAny(List<String> values) {
    for (final value in values) {
      if (text.contains(value)) {
        return true;
      }
    }
    return false;
  }

  final hasCoinSignal = item.type.toLowerCase().contains('coin') ||
      hasAny(const ['chaqmoq', 'lightning']);
  if (hasCoinSignal) {
    if (hasAny(const [
      'ayirildi',
      'ayrildi',
      'minus',
      'jarima',
      'removed',
      'penalty',
    ])) {
      return NotificationKind.rewardRemoved;
    }
    return NotificationKind.rewardAdded;
  }
  if (hasAny(const [
    'payment',
    "to'lov",
    'to‘lov',
    'tolov',
    'qarzdor',
  ])) {
    return NotificationKind.payment;
  }
  if (hasAny(const ['attendance', 'davomat', 'present', 'absent'])) {
    return NotificationKind.attendance;
  }
  if (hasAny(const ['comment', 'izoh', 'feedback', 'xabar qoldirdi'])) {
    return NotificationKind.comment;
  }
  if (hasAny(const ['grade', 'score', 'baho', 'imtihon'])) {
    return NotificationKind.grade;
  }
  if (item.type.toLowerCase().contains('broadcast') ||
      hasAny(const ['e’lon', "e'lon", 'broadcast', 'umumiy xabar'])) {
    return NotificationKind.broadcast;
  }
  return NotificationKind.info;
}

class _NotificationVisual {
  const _NotificationVisual({
    required this.icon,
    required this.accentColor,
    required this.iconColor,
    required this.iconBackground,
  });

  final IconData icon;
  final Color accentColor;
  final Color iconColor;
  final Color iconBackground;
}

_NotificationVisual _visualFor(NotificationKind kind) {
  switch (kind) {
    case NotificationKind.rewardAdded:
      return const _NotificationVisual(
        icon: Icons.bolt_rounded,
        accentColor: Color(0xFF16A34A),
        iconColor: Color(0xFF15803D),
        iconBackground: Color(0xFFEAF8EF),
      );
    case NotificationKind.rewardRemoved:
      return const _NotificationVisual(
        icon: Icons.bolt_outlined,
        accentColor: Color(0xFFEF4444),
        iconColor: Color(0xFFDC2626),
        iconBackground: Color(0xFFFDECEC),
      );
    case NotificationKind.payment:
      return const _NotificationVisual(
        icon: Icons.calendar_month_rounded,
        accentColor: Color(0xFF2563EB),
        iconColor: Color(0xFF1D4ED8),
        iconBackground: Color(0xFFEAF2FF),
      );
    case NotificationKind.attendance:
      return const _NotificationVisual(
        icon: Icons.fact_check_rounded,
        accentColor: Color(0xFF0EA5A4),
        iconColor: Color(0xFF0F766E),
        iconBackground: Color(0xFFE8FBFA),
      );
    case NotificationKind.comment:
      return const _NotificationVisual(
        icon: Icons.chat_bubble_outline_rounded,
        accentColor: Color(0xFF1E73F8),
        iconColor: Color(0xFF1D4ED8),
        iconBackground: Color(0xFFEAF4FF),
      );
    case NotificationKind.grade:
      return const _NotificationVisual(
        icon: Icons.star_rounded,
        accentColor: Color(0xFFF59E0B),
        iconColor: Color(0xFFD97706),
        iconBackground: Color(0xFFFFF5DE),
      );
    case NotificationKind.broadcast:
      return const _NotificationVisual(
        icon: Icons.campaign_outlined,
        accentColor: Color(0xFF7C3AED),
        iconColor: Color(0xFF6D28D9),
        iconBackground: Color(0xFFF2ECFF),
      );
    case NotificationKind.info:
      return const _NotificationVisual(
        icon: Icons.notifications_active_outlined,
        accentColor: Color(0xFF1E73F8),
        iconColor: Color(0xFF1D4ED8),
        iconBackground: Color(0xFFEAF4FF),
      );
  }
}

String _typeLabel(NotificationKind kind) {
  switch (kind) {
    case NotificationKind.rewardAdded:
      return 'Chaqmoq qo‘shildi';
    case NotificationKind.rewardRemoved:
      return 'Chaqmoq ayrildi';
    case NotificationKind.payment:
      return 'To‘lov';
    case NotificationKind.attendance:
      return 'Davomat';
    case NotificationKind.comment:
      return 'Izoh';
    case NotificationKind.grade:
      return 'Baholash';
    case NotificationKind.broadcast:
      return 'Umumiy xabar';
    case NotificationKind.info:
      return 'Bildirishnoma';
  }
}

String _defaultTitle(NotificationKind kind) {
  switch (kind) {
    case NotificationKind.rewardAdded:
      return 'Chaqmoq qo‘shildi ⚡';
    case NotificationKind.rewardRemoved:
      return 'Chaqmoq ayrildi ⚡';
    case NotificationKind.payment:
      return 'To‘lov eslatmasi';
    case NotificationKind.attendance:
      return 'Davomat yangilandi';
    case NotificationKind.comment:
      return 'Yangi izoh qo‘shildi';
    case NotificationKind.grade:
      return 'Natija yangilandi';
    case NotificationKind.broadcast:
      return 'Muhim xabar';
    case NotificationKind.info:
      return 'Bildirishnoma';
  }
}

String _defaultDescription(NotificationKind kind) {
  switch (kind) {
    case NotificationKind.rewardAdded:
      return 'Chaqmoq balida ijobiy o‘zgarish qayd etildi.';
    case NotificationKind.rewardRemoved:
      return 'Chaqmoq balida kamayish qayd etildi.';
    case NotificationKind.payment:
      return 'To‘lov bo‘yicha yangi eslatma mavjud.';
    case NotificationKind.attendance:
      return 'Davomat bilan bog‘liq ma’lumot yangilandi.';
    case NotificationKind.comment:
      return 'Yangi izoh qoldirildi.';
    case NotificationKind.grade:
      return 'Baholash bilan bog‘liq yangilik mavjud.';
    case NotificationKind.broadcast:
      return 'Markaz tomonidan umumiy xabar yuborildi.';
    case NotificationKind.info:
      return 'Qo‘shimcha izoh mavjud emas.';
  }
}

String _timeLabel(DateTime value) {
  final difference = DateTime.now().difference(value);
  if (difference.inDays < 7) {
    return Formatters.relative(value);
  }
  return Formatters.dateTime(value);
}

bool _looksLikeReason(String line) {
  final normalized = line.toLowerCase().replaceAll('’', "'").replaceAll('‘', "'");
  return normalized.startsWith('sabab:') ||
      normalized.startsWith('izoh:') ||
      normalized.startsWith('comment:');
}

String _normalizeReason(String line) {
  final value = line.replaceFirst(
    RegExp(r'^(Sabab|Izoh|Comment)\s*:\s*', caseSensitive: false),
    '',
  ).trim();
  return value.isEmpty ? 'Qo‘shimcha izoh mavjud emas' : value;
}

String _extractActorName(String description) {
  const patterns = [
    r'Sizga\s+(.+?)\s+tomonidan',
    r'Sizdan\s+(.+?)\s+tomonidan',
  ];
  for (final pattern in patterns) {
    final match = RegExp(pattern, caseSensitive: false).firstMatch(description);
    if (match != null) {
      final value = (match.group(1) ?? '').trim();
      if (value.isNotEmpty) {
        return value;
      }
    }
  }
  return '';
}

String? _extractAmountLabel({
  required String source,
  required NotificationKind kind,
}) {
  final normalized = source.replaceAll('’', "'").replaceAll('‘', "'");
  if (kind == NotificationKind.rewardAdded || kind == NotificationKind.rewardRemoved) {
    final match = RegExp(r'(\d+)\s*chaqmoq', caseSensitive: false).firstMatch(
      normalized,
    );
    if (match != null) {
      return '${match.group(1)} chaqmoq';
    }
  }
  if (kind == NotificationKind.payment) {
    final match = RegExp(r"(\d[\d\s]*)\s*so['‘’`]?m", caseSensitive: false)
        .firstMatch(normalized);
    if (match != null) {
      return '${match.group(1)?.trim()} so‘m';
    }
  }
  return null;
}
