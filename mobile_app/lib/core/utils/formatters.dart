import 'package:intl/intl.dart';

class AppFormatters {
  static final NumberFormat _number = NumberFormat.decimalPattern('en_US');

  static String formatMoney(num value) {
    return '${_number.format(value)} so\'m';
  }

  static String formatNumber(num value) {
    return _number.format(value);
  }

  static String formatCompact(num value) {
    final abs = value.abs();
    if (abs >= 1000000000) {
      return '${(value / 1000000000).toStringAsFixed(1)} mlrd';
    }
    if (abs >= 1000000) {
      return '${(value / 1000000).toStringAsFixed(1)} mln';
    }
    if (abs >= 1000) {
      return '${(value / 1000).toStringAsFixed(1)} ming';
    }
    return formatNumber(value);
  }

  static String formatDate(DateTime? value, {String pattern = 'dd.MM.yyyy'}) {
    if (value == null) {
      return 'Sana yo\'q';
    }
    return DateFormat(pattern).format(value.toLocal());
  }

  static String formatDateTime(DateTime? value) {
    return formatDate(value, pattern: 'dd.MM.yyyy HH:mm');
  }

  static String formatMonthYear(DateTime? value) {
    return formatDate(value, pattern: 'MM.yyyy');
  }

  static String formatPercent(num? value, {bool signed = false}) {
    if (value == null) {
      return '0%';
    }
    final prefix = signed && value > 0 ? '+' : '';
    return '$prefix${value.toStringAsFixed(value % 1 == 0 ? 0 : 1)}%';
  }

  static String roleLabel(String role) {
    switch (role) {
      case 'superadmin':
        return 'Bosh admin';
      case 'director':
        return 'Direktor';
      case 'manager':
        return 'Menejer';
      case 'teacher':
        return 'O\'qituvchi';
      case 'student':
        return 'O\'quvchi';
      case 'parent':
        return 'Ota-ona';
      default:
        return role;
    }
  }

  static String yesNo(bool value) {
    return value ? 'Ha' : 'Yo\'q';
  }

  static String healthLabel(String value) {
    switch (value.toLowerCase()) {
      case 'strong':
        return 'Kuchli';
      case 'stable':
        return 'Barqaror';
      case 'risky':
        return 'Xavfli';
      case 'weak':
        return 'Zaif';
      default:
        return value;
    }
  }

  static String paymentTypeLabel(String value) {
    switch (value.toLowerCase()) {
      case 'cash':
        return 'Naqd';
      case 'card':
        return 'Karta';
      case 'mixed':
        return 'Aralash';
      default:
        return value;
    }
  }

  static String attendanceStatusLabel(String value) {
    switch (value.toLowerCase()) {
      case 'present':
        return 'Qatnashdi';
      case 'absent_excused':
        return 'Sababli';
      case 'absent_unexcused':
        return 'Sababsiz';
      default:
        return value;
    }
  }

  static String notificationTypeLabel(String value) {
    switch (value.toLowerCase()) {
      case 'system':
        return 'Tizim';
      case 'payment':
        return 'To\'lov';
      case 'attendance':
        return 'Davomat';
      case 'lead':
        return 'Lid';
      default:
        return value.isEmpty ? 'Ma\'lumot' : value;
    }
  }
}
