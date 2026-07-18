// Director paneli uchun ko'rinish (view) modellari — real API va mock uchun umumiy.
import '../../../core/design/ds_components.dart' show DsStatus;

/// Grafik uchun bitta nuqta.
class DirectorChartPoint {
  const DirectorChartPoint(this.label, this.value);
  final String label;
  final double value;
}

/// Daromad vs xarajat — bitta oy.
class DirectorMonthPair {
  const DirectorMonthPair(this.label, this.income, this.expense);
  final String label;
  final double income;
  final double expense;
}

/// So'nggi to'lov / faollik yozuvi.
class DirectorPayment {
  const DirectorPayment({
    required this.name,
    required this.subtitle,
    required this.amount,
    required this.time,
    this.tone = DsStatus.info,
  });
  final String name;
  final String subtitle;
  final int amount;
  final String time;
  final DsStatus tone;
}

/// Qarzdor o'quvchi (oylik breakdown ixtiyoriy).
class DirectorDebtor {
  const DirectorDebtor({
    required this.id,
    required this.name,
    required this.group,
    required this.phone,
    required this.totalDebt,
    this.months = const [],
    this.tone = DsStatus.info,
  });
  final int id;
  final String name;
  final String group;
  final String phone;
  final int totalDebt;
  final List<DirectorDebtorMonth> months;
  final DsStatus tone;

  DsStatus get status => totalDebt > 0 ? DsStatus.danger : DsStatus.success;
  String get statusLabel => totalDebt > 0 ? 'Qarzdor' : 'To\'langan';
}

class DirectorDebtorMonth {
  const DirectorDebtorMonth({
    required this.month,
    required this.monthly,
    required this.paid,
    required this.debt,
  });
  final String month;
  final int monthly;
  final int paid;
  final int debt;
  bool get isPaid => debt <= 0;
  bool get isPartial => paid > 0 && debt > 0;
}

/// Dashboard + Hisobot uchun barcha ko'rsatkichlar (bitta /api/boshqaruv/ dan).
// ── Kunlik davomat nazorati ──
class DirectorAttendanceAbsentee {
  const DirectorAttendanceAbsentee({required this.name, required this.status, required this.statusLabel});
  final String name;
  final String status; // absent_excused / absent_unexcused / late
  final String statusLabel;
  factory DirectorAttendanceAbsentee.fromJson(Map<String, dynamic> j) => DirectorAttendanceAbsentee(
        name: (j['name'] ?? '').toString(),
        status: (j['status'] ?? '').toString(),
        statusLabel: (j['status_label'] ?? '').toString(),
      );
}

class DirectorAttendanceRow {
  const DirectorAttendanceRow({
    required this.groupId,
    required this.groupName,
    required this.teacherName,
    required this.startTime,
    required this.hasTime,
    required this.status,
    required this.present,
    required this.late,
    required this.absentExcused,
    required this.absentUnexcused,
    required this.absentees,
  });
  final int groupId;
  final String groupName;
  final String teacherName;
  final String startTime;
  final bool hasTime;
  final String status; // taken / missing / pending
  final int present, late, absentExcused, absentUnexcused;
  final List<DirectorAttendanceAbsentee> absentees;
  factory DirectorAttendanceRow.fromJson(Map<String, dynamic> j) => DirectorAttendanceRow(
        groupId: int.tryParse('${j['group_id']}') ?? 0,
        groupName: (j['group_name'] ?? '').toString(),
        teacherName: (j['teacher_name'] ?? '').toString(),
        startTime: (j['start_time'] ?? '').toString(),
        hasTime: j['has_time'] == true,
        status: (j['status'] ?? 'pending').toString(),
        present: int.tryParse('${j['present']}') ?? 0,
        late: int.tryParse('${j['late']}') ?? 0,
        absentExcused: int.tryParse('${j['absent_excused']}') ?? 0,
        absentUnexcused: int.tryParse('${j['absent_unexcused']}') ?? 0,
        absentees: [
          for (final a in (j['absentees'] as List? ?? const []))
            if (a is Map) DirectorAttendanceAbsentee.fromJson(a.cast<String, dynamic>()),
        ],
      );
}

class DirectorAttendanceUnscheduled {
  const DirectorAttendanceUnscheduled({required this.groupId, required this.groupName, required this.teacherName});
  final int groupId;
  final String groupName;
  final String teacherName;
  factory DirectorAttendanceUnscheduled.fromJson(Map<String, dynamic> j) => DirectorAttendanceUnscheduled(
        groupId: int.tryParse('${j['group_id']}') ?? 0,
        groupName: (j['group_name'] ?? '').toString(),
        teacherName: (j['teacher_name'] ?? '').toString(),
      );
}

class DirectorAttendanceMonitor {
  const DirectorAttendanceMonitor({
    required this.scheduled,
    required this.taken,
    required this.missing,
    required this.pending,
    required this.unscheduled,
    required this.rows,
    required this.unscheduledGroups,
  });
  final int scheduled, taken, missing, pending, unscheduled;
  final List<DirectorAttendanceRow> rows;
  final List<DirectorAttendanceUnscheduled> unscheduledGroups;

  bool get isEmpty => rows.isEmpty && unscheduledGroups.isEmpty;

  static const empty = DirectorAttendanceMonitor(
    scheduled: 0, taken: 0, missing: 0, pending: 0, unscheduled: 0,
    rows: [], unscheduledGroups: [],
  );

  factory DirectorAttendanceMonitor.fromJson(Map<String, dynamic>? j) {
    if (j == null) return empty;
    final s = (j['summary'] as Map?)?.cast<String, dynamic>() ?? const {};
    return DirectorAttendanceMonitor(
      scheduled: int.tryParse('${s['scheduled']}') ?? 0,
      taken: int.tryParse('${s['taken']}') ?? 0,
      missing: int.tryParse('${s['missing']}') ?? 0,
      pending: int.tryParse('${s['pending']}') ?? 0,
      unscheduled: int.tryParse('${s['unscheduled']}') ?? 0,
      rows: [
        for (final r in (j['rows'] as List? ?? const []))
          if (r is Map) DirectorAttendanceRow.fromJson(r.cast<String, dynamic>()),
      ],
      unscheduledGroups: [
        for (final u in (j['unscheduled'] as List? ?? const []))
          if (u is Map) DirectorAttendanceUnscheduled.fromJson(u.cast<String, dynamic>()),
      ],
    );
  }
}

class DirectorData {
  const DirectorData({
    required this.centerName,
    required this.directorName,
    required this.periodRevenue,
    required this.revenueChange,
    required this.activeStudents,
    required this.studentsChange,
    required this.avgAttendance,
    required this.totalDebt,
    required this.totalDebtors,
    required this.netProfit,
    required this.expenses,
    required this.teacherSalary,
    required this.revenueTrend,
    required this.incomeVsExpense,
    required this.recentPayments,
    required this.debtors,
    this.teacherSalaries = const [],
    this.expensesList = const [],
    this.paymentMethods = const [],
    this.attendanceMonitor = DirectorAttendanceMonitor.empty,
  });

  final String centerName;
  final String directorName;

  final int periodRevenue;
  final double revenueChange;
  final int activeStudents;
  final double studentsChange;
  final int avgAttendance;
  final int totalDebt;
  final int totalDebtors;

  final int netProfit;
  final int expenses;
  final int teacherSalary;

  final List<DirectorChartPoint> revenueTrend;
  final List<DirectorMonthPair> incomeVsExpense;
  final List<DirectorPayment> recentPayments;
  final List<DirectorDebtor> debtors;

  /// O'qituvchi maoshlari (ism, summa).
  final List<(String, int)> teacherSalaries;

  /// Xarajatlar (izoh, summa).
  final List<(String, int)> expensesList;

  /// Markazda yoqilgan to'lov usullari (NAQD, CLICK, ...).
  final List<String> paymentMethods;

  /// Kunlik davomat nazorati (o'qituvchi davomat qilmagan guruhlar).
  final DirectorAttendanceMonitor attendanceMonitor;
}

/// Oy kesimi bo'yicha moliyaviy hisobot.
class DirectorReport {
  const DirectorReport({
    required this.month,
    required this.monthLabel,
    required this.revenue,
    required this.netProfit,
    required this.expenses,
    required this.teacherSalary,
    required this.teacherSalaries,
    required this.expensesList,
    required this.incomeVsExpense,
    required this.payments,
  });
  final String month;
  final String monthLabel;
  final int revenue;
  final int netProfit;
  final int expenses;
  final int teacherSalary;
  final List<(String, int)> teacherSalaries;
  final List<(String, int)> expensesList;
  final List<DirectorMonthPair> incomeVsExpense;
  final List<DirectorPayment> payments;
}

/// Bitta bildirishnoma.
class DirectorNotification {
  const DirectorNotification({
    required this.id,
    required this.title,
    required this.message,
    required this.isRead,
    required this.createdAt,
    this.kind = '',
  });
  final int id;
  final String title;
  final String message;
  final bool isRead;
  final String createdAt;
  final String kind;
}

/// Markazdagi mavjud guruh (qo'shish uchun).
class AvailableGroup {
  const AvailableGroup({required this.id, required this.name, required this.price, required this.teacherPercent});
  final int id;
  final String name;
  final int price;
  final int teacherPercent;
}

/// O'quvchining bitta guruhi (enrollment) — narx bilan.
class StudentGroup {
  const StudentGroup({
    required this.enrollmentId,
    required this.groupId,
    required this.group,
    required this.monthlyPrice,
    required this.teacherPercent,
  });
  final int enrollmentId;
  final int groupId;
  final String group;
  final int monthlyPrice;
  final int teacherPercent;
}

/// Bitta o'quvchi tafsiloti.
class DirectorStudentDetail {
  const DirectorStudentDetail({
    required this.id,
    required this.name,
    required this.group,
    required this.phone,
    required this.totalDebt,
    required this.payments,
    this.groups = const [],
  });
  final int id;
  final String name;
  final String group;
  final String phone;
  final int totalDebt;
  final List<DirectorPayment> payments;
  final List<StudentGroup> groups;
}
