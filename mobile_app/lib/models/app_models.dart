int jsonInt(dynamic value) {
  if (value is int) {
    return value;
  }
  if (value is double) {
    return value.round();
  }
  return int.tryParse('$value') ?? 0;
}

double jsonDouble(dynamic value) {
  if (value is double) {
    return value;
  }
  if (value is int) {
    return value.toDouble();
  }
  return double.tryParse('$value') ?? 0;
}

bool jsonBool(dynamic value) {
  if (value is bool) {
    return value;
  }
  if (value is num) {
    return value != 0;
  }
  return '$value'.toLowerCase() == 'true';
}

String jsonString(dynamic value) => value == null ? '' : '$value';

Map<String, dynamic> jsonMap(dynamic value) =>
    value is Map ? Map<String, dynamic>.from(value) : <String, dynamic>{};

List<Map<String, dynamic>> jsonMapList(dynamic value) => value is List
    ? value.map((item) => jsonMap(item)).toList()
    : <Map<String, dynamic>>[];

class CenterModel {
  const CenterModel({
    required this.id,
    required this.name,
    required this.slug,
    required this.status,
    required this.plan,
    required this.phone,
    required this.address,
    required this.maxUsers,
    required this.maxGroups,
    required this.maxStudents,
    required this.effectiveStudentLimit,
    required this.features,
  });

  final int id;
  final String name;
  final String slug;
  final String status;
  final String plan;
  final String phone;
  final String address;
  final int maxUsers;
  final int maxGroups;
  final int maxStudents;
  final int effectiveStudentLimit;
  final Map<String, dynamic> features;

  factory CenterModel.fromJson(Map<String, dynamic> json) {
    return CenterModel(
      id: jsonInt(json['id']),
      name: jsonString(json['name']),
      slug: jsonString(json['slug']),
      status: jsonString(json['status']),
      plan: jsonString(json['plan']),
      phone: jsonString(json['phone']),
      address: jsonString(json['address']),
      maxUsers: jsonInt(json['max_users']),
      maxGroups: jsonInt(json['max_groups']),
      maxStudents: jsonInt(json['max_students']),
      effectiveStudentLimit: jsonInt(json['effective_student_limit']),
      features: jsonMap(json['features']),
    );
  }
}

class UserPermissions {
  const UserPermissions({
    required this.canAccessTrash,
    required this.canAddStudent,
    required this.canRemoveStudent,
    required this.canViewDirectorDashboard,
    required this.canManageLeads,
    required this.canTakeAttendance,
  });

  final bool canAccessTrash;
  final bool canAddStudent;
  final bool canRemoveStudent;
  final bool canViewDirectorDashboard;
  final bool canManageLeads;
  final bool canTakeAttendance;

  factory UserPermissions.fromJson(Map<String, dynamic> json) {
    return UserPermissions(
      canAccessTrash: jsonBool(json['can_access_trash']),
      canAddStudent: jsonBool(json['can_add_student']),
      canRemoveStudent: jsonBool(json['can_remove_student']),
      canViewDirectorDashboard: jsonBool(json['can_view_director_dashboard']),
      canManageLeads: jsonBool(json['can_manage_leads']),
      canTakeAttendance: jsonBool(json['can_take_attendance']),
    );
  }
}

class AppUser {
  const AppUser({
    required this.id,
    required this.email,
    required this.phoneNumber,
    required this.telefon1,
    required this.telefon2,
    required this.fullName,
    required this.ism,
    required this.familya,
    required this.otchestvo,
    required this.role,
    required this.avatarUrl,
    required this.isTelegramLinked,
    required this.telegramUsername,
    required this.isSuperuser,
    required this.center,
    required this.permissions,
  });

  final int id;
  final String email;
  final String phoneNumber;
  final String telefon1;
  final String telefon2;
  final String fullName;
  final String ism;
  final String familya;
  final String otchestvo;
  final String role;
  final String avatarUrl;
  final bool isTelegramLinked;
  final String telegramUsername;
  final bool isSuperuser;
  final CenterModel? center;
  final UserPermissions permissions;

  String get effectiveRole => isSuperuser ? 'superadmin' : role;

  factory AppUser.fromJson(Map<String, dynamic> json) {
    return AppUser(
      id: jsonInt(json['id']),
      email: jsonString(json['email']),
      phoneNumber: jsonString(json['phone_number']),
      telefon1: jsonString(json['telefon1']),
      telefon2: jsonString(json['telefon2']),
      fullName: jsonString(json['full_name']),
      ism: jsonString(json['ism']),
      familya: jsonString(json['familya']),
      otchestvo: jsonString(json['otchestvo']),
      role: jsonString(json['role']),
      avatarUrl: jsonString(json['avatar_url']),
      isTelegramLinked: jsonBool(json['is_telegram_linked']),
      telegramUsername: jsonString(json['telegram_username']),
      isSuperuser: jsonBool(json['is_superuser']),
      center: json['center'] == null
          ? null
          : CenterModel.fromJson(jsonMap(json['center'])),
      permissions: UserPermissions.fromJson(jsonMap(json['permissions'])),
    );
  }
}

class AuthSession {
  const AuthSession({
    required this.accessToken,
    required this.slug,
    required this.user,
  });

  final String accessToken;
  final String slug;
  final AppUser user;

  AuthSession copyWith({String? accessToken, String? slug, AppUser? user}) {
    return AuthSession(
      accessToken: accessToken ?? this.accessToken,
      slug: slug ?? this.slug,
      user: user ?? this.user,
    );
  }
}

class RoleHomeModel {
  const RoleHomeModel({
    required this.role,
    required this.center,
    required this.unreadNotifications,
    required this.summary,
  });

  final String role;
  final CenterModel? center;
  final int unreadNotifications;
  final Map<String, dynamic> summary;

  factory RoleHomeModel.fromJson(Map<String, dynamic> json) {
    return RoleHomeModel(
      role: jsonString(json['role']),
      center: json['center'] == null
          ? null
          : CenterModel.fromJson(jsonMap(json['center'])),
      unreadNotifications: jsonInt(json['unread_notifications']),
      summary: jsonMap(json['summary']),
    );
  }
}

class CenterOverview {
  const CenterOverview({
    required this.id,
    required this.name,
    required this.slug,
    required this.status,
    required this.plan,
    required this.studentsCount,
    required this.teachersCount,
    required this.groupsCount,
    required this.todayPayments,
  });

  final int id;
  final String name;
  final String slug;
  final String status;
  final String plan;
  final int studentsCount;
  final int teachersCount;
  final int groupsCount;
  final int todayPayments;

  factory CenterOverview.fromJson(Map<String, dynamic> json) {
    return CenterOverview(
      id: jsonInt(json['id']),
      name: jsonString(json['name']),
      slug: jsonString(json['slug']),
      status: jsonString(json['status']),
      plan: jsonString(json['plan']),
      studentsCount: jsonInt(json['students_count']),
      teachersCount: jsonInt(json['teachers_count']),
      groupsCount: jsonInt(json['groups_count']),
      todayPayments: jsonInt(json['today_payments']),
    );
  }
}

class SuperadminHomeModel {
  const SuperadminHomeModel({required this.summary, required this.centers});

  final Map<String, dynamic> summary;
  final List<CenterOverview> centers;

  factory SuperadminHomeModel.fromJson(Map<String, dynamic> json) {
    return SuperadminHomeModel(
      summary: jsonMap(json['summary']),
      centers: jsonMapList(
        json['centers'],
      ).map(CenterOverview.fromJson).toList(),
    );
  }
}

class AttendanceStats {
  const AttendanceStats({
    required this.totalLessons,
    required this.presentLessons,
    required this.attendanceRate,
    required this.recentTotalLessons,
    required this.recentPresentLessons,
    required this.recentAttendanceRate,
  });

  final int totalLessons;
  final int presentLessons;
  final double attendanceRate;
  final int recentTotalLessons;
  final int recentPresentLessons;
  final double recentAttendanceRate;

  factory AttendanceStats.fromJson(Map<String, dynamic> json) {
    return AttendanceStats(
      totalLessons: jsonInt(json['total_lessons']),
      presentLessons: jsonInt(json['present_lessons']),
      attendanceRate: jsonDouble(json['attendance_rate']),
      recentTotalLessons: jsonInt(json['recent_total_lessons']),
      recentPresentLessons: jsonInt(json['recent_present_lessons']),
      recentAttendanceRate: jsonDouble(json['recent_attendance_rate']),
    );
  }
}

class GroupModel {
  const GroupModel({
    required this.id,
    required this.name,
    required this.category,
    required this.teacherId,
    required this.teacherName,
    required this.monthlyPrice,
    required this.teacherSharePercent,
    required this.monthlyLessons,
    required this.isClosed,
    required this.studentCount,
    required this.todayAttendanceCount,
  });

  final int id;
  final String name;
  final String category;
  final int? teacherId;
  final String teacherName;
  final int monthlyPrice;
  final int teacherSharePercent;
  final int monthlyLessons;
  final bool isClosed;
  final int? studentCount;
  final int? todayAttendanceCount;

  factory GroupModel.fromJson(Map<String, dynamic> json) {
    final teacherIdValue = json['teacher_id'];
    return GroupModel(
      id: jsonInt(json['id']),
      name: jsonString(json['name']),
      category: jsonString(json['category']),
      teacherId: teacherIdValue == null ? null : jsonInt(teacherIdValue),
      teacherName: jsonString(json['teacher_name']),
      monthlyPrice: jsonInt(json['monthly_price']),
      teacherSharePercent: jsonInt(json['teacher_share_percent']),
      monthlyLessons: jsonInt(json['monthly_lessons']),
      isClosed: jsonBool(json['is_closed']),
      studentCount: json['student_count'] == null
          ? null
          : jsonInt(json['student_count']),
      todayAttendanceCount: json['today_attendance_count'] == null
          ? null
          : jsonInt(json['today_attendance_count']),
    );
  }
}

class GroupEnrollment {
  const GroupEnrollment({
    required this.group,
    required this.enrollmentId,
    required this.isActive,
    required this.paidTotal,
    required this.coursePrice,
  });

  final GroupModel group;
  final int enrollmentId;
  final bool isActive;
  final int paidTotal;
  final int coursePrice;

  factory GroupEnrollment.fromJson(Map<String, dynamic> json) {
    return GroupEnrollment(
      group: GroupModel.fromJson(json),
      enrollmentId: jsonInt(json['enrollment_id']),
      isActive: jsonBool(json['is_active']),
      paidTotal: jsonInt(json['paid_total']),
      coursePrice: jsonInt(json['course_price']),
    );
  }
}

class PaymentModel {
  const PaymentModel({
    required this.id,
    required this.studentId,
    required this.studentName,
    required this.groupId,
    required this.groupName,
    required this.amount,
    required this.paymentType,
    required this.cashAmount,
    required this.cardAmount,
    required this.paidDate,
    required this.note,
    required this.createdBy,
  });

  final int id;
  final int? studentId;
  final String studentName;
  final int? groupId;
  final String groupName;
  final int amount;
  final String paymentType;
  final int cashAmount;
  final int cardAmount;
  final DateTime paidDate;
  final String note;
  final String createdBy;

  factory PaymentModel.fromJson(Map<String, dynamic> json) {
    final dateRaw = jsonString(json['paid_date']).isNotEmpty
        ? jsonString(json['paid_date'])
        : jsonString(json['date']);
    return PaymentModel(
      id: jsonInt(json['id']),
      studentId: json['student_id'] == null
          ? null
          : jsonInt(json['student_id']),
      studentName: jsonString(json['student_name']),
      groupId: json['group_id'] == null ? null : jsonInt(json['group_id']),
      groupName: jsonString(json['group_name']),
      amount: jsonInt(json['amount']),
      paymentType: jsonString(json['payment_type']).isEmpty
          ? jsonString(json['method'])
          : jsonString(json['payment_type']),
      cashAmount: jsonInt(json['cash_amount']),
      cardAmount: jsonInt(json['card_amount']),
      paidDate: DateTime.tryParse(dateRaw) ?? DateTime.now(),
      note: jsonString(json['note']),
      createdBy: jsonString(json['created_by']),
    );
  }
}

class StudentModel {
  const StudentModel({
    required this.id,
    required this.fullName,
    required this.email,
    required this.phone,
    required this.balance,
    required this.debt,
    required this.attendance,
    required this.groups,
    required this.payments,
    required this.lastPayment,
    required this.certificates,
  });

  final int id;
  final String fullName;
  final String email;
  final String phone;
  final int balance;
  final int debt;
  final AttendanceStats attendance;
  final List<GroupEnrollment> groups;
  final List<PaymentModel> payments;
  final PaymentModel? lastPayment;
  final List<Map<String, dynamic>> certificates;

  factory StudentModel.fromJson(Map<String, dynamic> json) {
    final paymentList = jsonMapList(
      json['payments'],
    ).map(PaymentModel.fromJson).toList();
    final lastPaymentMap = json['last_payment'];
    return StudentModel(
      id: jsonInt(json['id']),
      fullName: jsonString(json['full_name']),
      email: jsonString(json['email']),
      phone: jsonString(json['phone']),
      balance: jsonInt(json['balance']),
      debt: jsonInt(json['debt']),
      attendance: AttendanceStats.fromJson(jsonMap(json['attendance'])),
      groups: jsonMapList(
        json['groups'],
      ).map(GroupEnrollment.fromJson).toList(),
      payments: paymentList,
      lastPayment: lastPaymentMap == null
          ? null
          : PaymentModel.fromJson(jsonMap(lastPaymentMap)),
      certificates: jsonMapList(json['certificates']),
    );
  }
}

class TeacherModel {
  const TeacherModel({
    required this.id,
    required this.fullName,
    required this.email,
    required this.phone,
    required this.groupsCount,
    required this.studentsCount,
    required this.todayAttendanceCount,
    required this.expectedIncome,
    required this.groups,
  });

  final int id;
  final String fullName;
  final String email;
  final String phone;
  final int groupsCount;
  final int studentsCount;
  final int todayAttendanceCount;
  final Map<String, dynamic> expectedIncome;
  final List<GroupModel> groups;

  factory TeacherModel.fromJson(Map<String, dynamic> json) {
    return TeacherModel(
      id: jsonInt(json['id']),
      fullName: jsonString(json['full_name']),
      email: jsonString(json['email']),
      phone: jsonString(json['phone']),
      groupsCount: jsonInt(json['groups_count']),
      studentsCount: jsonInt(json['students_count']),
      todayAttendanceCount: jsonInt(json['today_attendance_count']),
      expectedIncome: jsonMap(json['expected_income']),
      groups: jsonMapList(json['groups']).map(GroupModel.fromJson).toList(),
    );
  }
}

class AttendanceMember {
  const AttendanceMember({
    required this.id,
    required this.fullName,
    required this.phone,
    required this.balance,
    required this.debt,
    required this.attendanceStatus,
    required this.forced,
    required this.groupId,
    required this.groupName,
  });

  final int id;
  final String fullName;
  final String phone;
  final int balance;
  final int debt;
  final String attendanceStatus;
  final bool forced;
  final int groupId;
  final String groupName;

  factory AttendanceMember.fromJson(Map<String, dynamic> json) {
    return AttendanceMember(
      id: jsonInt(json['id']),
      fullName: jsonString(json['full_name']),
      phone: jsonString(json['phone']),
      balance: jsonInt(json['balance']),
      debt: jsonInt(json['debt']),
      attendanceStatus: jsonString(json['attendance_status']),
      forced: jsonBool(json['forced']),
      groupId: jsonInt(json['group_id']),
      groupName: jsonString(json['group_name']),
    );
  }
}

class AttendanceSheetData {
  const AttendanceSheetData({
    required this.date,
    required this.group,
    required this.items,
  });

  final DateTime date;
  final GroupModel group;
  final List<AttendanceMember> items;

  factory AttendanceSheetData.fromJson(Map<String, dynamic> json) {
    return AttendanceSheetData(
      date: DateTime.tryParse(jsonString(json['date'])) ?? DateTime.now(),
      group: GroupModel.fromJson(jsonMap(json['group'])),
      items: jsonMapList(json['items']).map(AttendanceMember.fromJson).toList(),
    );
  }
}

class AppNotification {
  const AppNotification({
    required this.id,
    required this.title,
    required this.message,
    required this.type,
    required this.isRead,
    required this.createdAt,
  });

  final int id;
  final String title;
  final String message;
  final String type;
  final bool isRead;
  final DateTime createdAt;

  factory AppNotification.fromJson(Map<String, dynamic> json) {
    return AppNotification(
      id: jsonInt(json['id']),
      title: jsonString(json['title']),
      message: jsonString(json['message']),
      type: jsonString(json['type']),
      isRead: jsonBool(json['is_read']),
      createdAt:
          DateTime.tryParse(jsonString(json['created_at'])) ?? DateTime.now(),
    );
  }
}
