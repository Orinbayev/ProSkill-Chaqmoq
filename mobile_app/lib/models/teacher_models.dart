import 'package:chaqmoq_mobile/models/app_models.dart';

class TeacherGroupModel {
  const TeacherGroupModel({
    required this.id,
    required this.name,
    this.category = '',
    this.studentCount = 0,
    this.monthlyPrice = 0,
    this.teacherSharePercent = 0,
    this.monthlyLessons = 12,
    this.attendedToday = 0,
    this.isClosed = false,
  });

  final int id;
  final String name;
  final String category;
  final int studentCount;
  final int monthlyPrice;
  final int teacherSharePercent;
  final int monthlyLessons;
  final int attendedToday;
  final bool isClosed;

  factory TeacherGroupModel.fromJson(Map<String, dynamic> j) => TeacherGroupModel(
        id: jsonInt(j['id']),
        name: jsonString(j['name']),
        category: jsonString(j['category']),
        studentCount: jsonInt(j['student_count']),
        monthlyPrice: jsonInt(j['monthly_price']),
        teacherSharePercent: jsonInt(j['teacher_share_percent']),
        monthlyLessons: jsonInt(j['monthly_lessons'] ?? 12),
        attendedToday: jsonInt(j['attended_today']),
        isClosed: jsonBool(j['is_closed']),
      );
}

class TeacherStudentModel {
  const TeacherStudentModel({
    required this.id,
    required this.fullName,
    this.phone = '',
    this.balance = 0,
    this.attendanceStatus = 'none',
  });

  final int id;
  final String fullName;
  final String phone;
  final int balance;

  // 'none' | 'present' | 'absent' | 'excused'
  final String attendanceStatus;

  bool get isPresent => attendanceStatus == 'present';

  factory TeacherStudentModel.fromJson(Map<String, dynamic> j) => TeacherStudentModel(
        id: jsonInt(j['id']),
        fullName: jsonString(j['full_name']),
        phone: jsonString(j['phone']),
        balance: jsonInt(j['balance']),
        attendanceStatus: jsonString(j['attendance_status']),
      );

  TeacherStudentModel copyWith({String? attendanceStatus}) => TeacherStudentModel(
        id: id,
        fullName: fullName,
        phone: phone,
        balance: balance,
        attendanceStatus: attendanceStatus ?? this.attendanceStatus,
      );
}

class TeacherAttendanceDay {
  const TeacherAttendanceDay({
    required this.group,
    required this.date,
    required this.students,
  });

  final TeacherGroupModel group;
  final DateTime date;
  final List<TeacherStudentModel> students;

  int get presentCount => students.where((s) => s.isPresent).length;
  int get totalCount => students.length;
}

class TeacherIncomeModel {
  const TeacherIncomeModel({
    required this.year,
    required this.month,
    this.salary = 0,
    this.expectedIncome = 0,
    this.progressPct = 0,
    this.isLocked = false,
    this.details = const [],
    this.yearly = const [],
    this.breakdown = const [],
  });

  final int year;
  final int month;
  final int salary;
  final int expectedIncome;
  final int progressPct;
  final bool isLocked;
  final List<Map<String, dynamic>> details;
  final List<int> yearly;
  final List<Map<String, dynamic>> breakdown;

  factory TeacherIncomeModel.fromJson(Map<String, dynamic> j) => TeacherIncomeModel(
        year: jsonInt(j['year']),
        month: jsonInt(j['month']),
        salary: jsonInt(j['salary']),
        expectedIncome: jsonInt(j['expected_income']),
        progressPct: jsonInt(j['progress_pct']),
        isLocked: jsonBool(j['is_locked']),
        details: (j['details'] as List? ?? []).cast<Map<String, dynamic>>(),
        yearly: (j['yearly'] as List? ?? []).map((e) => jsonInt(e)).toList(),
        breakdown: (j['breakdown'] as List? ?? []).cast<Map<String, dynamic>>(),
      );
}
