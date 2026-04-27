import 'dart:math';

import 'package:chaqmoq_mobile/core/theme/app_colors.dart';
import 'package:intl/intl.dart';

class Formatters {
  const Formatters._();

  static final NumberFormat _moneyFormat = NumberFormat('#,###', 'uz');
  static final DateFormat _dateFormat = DateFormat('dd.MM.yyyy');
  static final DateFormat _monthFormat = DateFormat('MMMM yyyy', 'uz');
  static final DateFormat _dayMonthFormat = DateFormat('d MMM', 'uz');
  static final DateFormat _dateTimeFormat = DateFormat('d MMM, HH:mm', 'uz');

  static String currency(num value, {bool compact = false}) {
    if (compact) {
      if (value.abs() >= 1000000) {
        return '${(value / 1000000).toStringAsFixed(value % 1000000 == 0 ? 0 : 1)} mln';
      }
      if (value.abs() >= 1000) {
        return '${(value / 1000).toStringAsFixed(value % 1000 == 0 ? 0 : 1)} ming';
      }
    }
    return '${_moneyFormat.format(value)} so\'m';
  }

  static String number(num value) => _moneyFormat.format(value);

  static String percent(num value) => '${value.toStringAsFixed(0)}%';

  static String date(DateTime? value) {
    if (value == null) {
      return '—';
    }
    return _dateFormat.format(value);
  }

  static String month(DateTime? value) {
    if (value == null) {
      return '—';
    }
    return _monthFormat.format(value);
  }

  static String shortDayMonth(DateTime? value) {
    if (value == null) {
      return '—';
    }
    return _dayMonthFormat.format(value);
  }

  static String dateTime(DateTime? value) {
    if (value == null) {
      return '—';
    }
    return _dateTimeFormat.format(value);
  }

  static String relative(DateTime? value, {DateTime? now}) {
    if (value == null) {
      return 'Hozir';
    }

    final reference = now ?? DateTime.now();
    final difference = reference.difference(value);
    if (difference.inSeconds < 60) {
      return 'Hozirgina';
    }
    if (difference.inMinutes < 60) {
      return '${difference.inMinutes} daqiqa oldin';
    }
    if (difference.inHours < 24) {
      return '${difference.inHours} soat oldin';
    }
    if (difference.inDays < 7) {
      return '${difference.inDays} kun oldin';
    }
    return date(value);
  }

  static String initials(String fullName) {
    final parts = fullName
        .trim()
        .split(RegExp(r'\s+'))
        .where((part) => part.isNotEmpty)
        .toList();
    if (parts.isEmpty) {
      return 'CH';
    }
    if (parts.length == 1) {
      return parts.first.substring(0, min(2, parts.first.length)).toUpperCase();
    }
    return '${parts.first[0]}${parts.last[0]}'.toUpperCase();
  }

  static String firstName(String fullName) {
    final parts = fullName.trim().split(RegExp(r'\s+'));
    return parts.isEmpty ? fullName : parts.first;
  }

  static int hashSeed(String value) {
    return value.runes.fold<int>(0, (previous, element) => previous + element);
  }

  static int avatarColor(String value) {
    final colors = <int>[
      AppColors.primary.toARGB32(),
      AppColors.secondary.toARGB32(),
      AppColors.success.toARGB32(),
      AppColors.warning.toARGB32(),
      AppColors.danger.toARGB32(),
    ];
    return colors[hashSeed(value) % colors.length];
  }

  static String weekdayShortUz(DateTime date) {
    const days = ['Du', 'Se', 'Cho', 'Pa', 'Ju', 'Sha', 'Ya'];
    return days[date.weekday - 1];
  }
}
