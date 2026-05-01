enum ViewState { idle, loading, success, error }

int jsonInt(dynamic value) {
  if (value is int) {
    return value;
  }
  if (value is double) {
    return value.round();
  }
  if (value is num) {
    return value.toInt();
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
  if (value is num) {
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
  final normalized = '$value'.trim().toLowerCase();
  return normalized == 'true' ||
      normalized == '1' ||
      normalized == 'yes' ||
      normalized == 'ha';
}

String jsonString(dynamic value) => value == null ? '' : '$value';

String cleanHtmlText(dynamic value) {
  var text = jsonString(value);
  if (text.isEmpty) {
    return '';
  }
  text = text.replaceAll(RegExp(r'<\s*br\b[^>]*>', caseSensitive: false), '\n');
  text = text.replaceAll(
    RegExp(r'</\s*(p|div|li|ul|ol|h[1-6])\s*>', caseSensitive: false),
    '\n',
  );
  text = text.replaceAll(RegExp(r'<[^>]*>'), '');
  text = _decodeHtmlEntities(text);
  return text
      .replaceAll(RegExp(r'\r\n?'), '\n')
      .replaceAll(RegExp(r'[ \t\r\f\v]+'), ' ')
      .replaceAll(RegExp(r' *\n *'), '\n')
      .replaceAll(RegExp(r'\n{3,}'), '\n\n')
      .trim();
}

String _decodeHtmlEntities(String text) {
  const entities = <String, String>{
    '&nbsp;': ' ',
    '&amp;': '&',
    '&lt;': '<',
    '&gt;': '>',
    '&quot;': '"',
    '&apos;': "'",
    '&#39;': "'",
    '&#x27;': "'",
    '&ldquo;': '"',
    '&rdquo;': '"',
    '&lsquo;': "'",
    '&rsquo;': "'",
    '&hellip;': '...',
    '&ndash;': '-',
    '&mdash;': '-',
  };
  for (final entry in entities.entries) {
    text = text.replaceAll(entry.key, entry.value);
  }
  return text.replaceAllMapped(RegExp(r'&#(\d+);|&#x([0-9a-fA-F]+);'), (match) {
    final decimal = match.group(1);
    final hex = match.group(2);
    final codePoint = decimal != null
        ? int.tryParse(decimal)
        : int.tryParse(hex ?? '', radix: 16);
    return codePoint == null
        ? match.group(0) ?? ''
        : String.fromCharCode(codePoint);
  });
}

DateTime? jsonDate(dynamic value) {
  if (value is DateTime) {
    return value;
  }
  if (value == null || '$value'.trim().isEmpty) {
    return null;
  }
  return DateTime.tryParse('$value');
}

Map<String, dynamic> jsonMap(dynamic value) {
  if (value is Map<String, dynamic>) {
    return value;
  }
  if (value is Map) {
    return value.map(
      (key, dynamic mapValue) => MapEntry(key.toString(), mapValue),
    );
  }
  return <String, dynamic>{};
}

List<Map<String, dynamic>> jsonMapList(dynamic value) {
  if (value is List) {
    return value.map((item) => jsonMap(item)).toList();
  }
  return <Map<String, dynamic>>[];
}

List<String> jsonStringList(dynamic value) {
  if (value is List) {
    return value
        .map((item) => jsonString(item))
        .where((item) => item.isNotEmpty)
        .toList();
  }
  return <String>[];
}

class CenterModel {
  const CenterModel({
    required this.id,
    required this.slug,
    required this.name,
    this.phone = '',
    this.address = '',
  });

  final int id;
  final String slug;
  final String name;
  final String phone;
  final String address;

  factory CenterModel.fromJson(Map<String, dynamic> json) {
    return CenterModel(
      id: jsonInt(json['id']),
      slug: jsonString(json['slug']),
      name: jsonString(json['name']),
      phone: jsonString(json['phone']),
      address: jsonString(json['address']),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'slug': slug,
    'name': name,
    'phone': phone,
    'address': address,
  };
}

class UserModel {
  const UserModel({
    required this.id,
    required this.fullName,
    required this.role,
    required this.center,
    this.firstName = '',
    this.lastName = '',
    this.phone = '',
    this.email = '',
    this.joinedDate,
    this.avatarUrl = '',
  });

  final int id;
  final String fullName;
  final String role;
  final CenterModel? center;
  final String firstName;
  final String lastName;
  final String phone;
  final String email;
  final DateTime? joinedDate;
  final String avatarUrl;

  factory UserModel.fromJson(Map<String, dynamic> json) {
    final firstName = jsonString(json['ism']);
    final lastName = jsonString(json['familya']);
    return UserModel(
      id: jsonInt(json['id']),
      fullName: jsonString(json['full_name']).isNotEmpty
          ? jsonString(json['full_name'])
          : [
              firstName,
              lastName,
            ].where((part) => part.isNotEmpty).join(' ').trim(),
      role: jsonString(json['role']),
      center: json['center'] == null
          ? null
          : CenterModel.fromJson(jsonMap(json['center'])),
      firstName: firstName,
      lastName: lastName,
      phone: jsonString(json['phone']).isNotEmpty
          ? jsonString(json['phone'])
          : jsonString(json['phone_number']).isNotEmpty
          ? jsonString(json['phone_number'])
          : jsonString(json['telefon1']),
      email: jsonString(json['email']),
      joinedDate: jsonDate(json['joined_date'] ?? json['date_joined']),
      avatarUrl: jsonString(json['avatar_url']),
    );
  }

  UserModel copyWith({
    int? id,
    String? fullName,
    String? role,
    CenterModel? center,
    String? firstName,
    String? lastName,
    String? phone,
    String? email,
    DateTime? joinedDate,
    String? avatarUrl,
  }) {
    return UserModel(
      id: id ?? this.id,
      fullName: fullName ?? this.fullName,
      role: role ?? this.role,
      center: center ?? this.center,
      firstName: firstName ?? this.firstName,
      lastName: lastName ?? this.lastName,
      phone: phone ?? this.phone,
      email: email ?? this.email,
      joinedDate: joinedDate ?? this.joinedDate,
      avatarUrl: avatarUrl ?? this.avatarUrl,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'full_name': fullName,
    'role': role,
    'center': center?.toJson(),
    'ism': firstName,
    'familya': lastName,
    'phone': phone,
    'email': email,
    'joined_date': joinedDate?.toIso8601String(),
    'avatar_url': avatarUrl,
  };
}

class AuthSession {
  const AuthSession({
    required this.accessToken,
    required this.slug,
    required this.user,
    this.isOffline = false,
  });

  final String accessToken;
  final String slug;
  final UserModel user;
  final bool isOffline;

  factory AuthSession.fromJson(Map<String, dynamic> json) {
    return AuthSession(
      accessToken: jsonString(json['access_token']),
      slug: jsonString(json['slug']),
      user: UserModel.fromJson(jsonMap(json['user'])),
      isOffline: jsonBool(json['is_offline']),
    );
  }

  AuthSession copyWith({
    String? accessToken,
    String? slug,
    UserModel? user,
    bool? isOffline,
  }) {
    return AuthSession(
      accessToken: accessToken ?? this.accessToken,
      slug: slug ?? this.slug,
      user: user ?? this.user,
      isOffline: isOffline ?? this.isOffline,
    );
  }

  Map<String, dynamic> toJson() => {
    'access_token': accessToken,
    'slug': slug,
    'user': user.toJson(),
    'is_offline': isOffline,
  };
}

class DashboardMetric {
  const DashboardMetric({
    required this.id,
    required this.title,
    required this.value,
    required this.subtitle,
    required this.trend,
    required this.colorKey,
  });

  final String id;
  final String title;
  final String value;
  final String subtitle;
  final double trend;
  final String colorKey;

  factory DashboardMetric.fromJson(Map<String, dynamic> json) {
    return DashboardMetric(
      id: jsonString(json['id']),
      title: jsonString(json['title']),
      value: jsonString(json['value']),
      subtitle: jsonString(json['subtitle']),
      trend: jsonDouble(json['trend']),
      colorKey: jsonString(json['color_key']),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'title': title,
    'value': value,
    'subtitle': subtitle,
    'trend': trend,
    'color_key': colorKey,
  };
}

class ChartPointModel {
  const ChartPointModel({required this.label, required this.value});

  final String label;
  final double value;

  factory ChartPointModel.fromJson(Map<String, dynamic> json) {
    return ChartPointModel(
      label: jsonString(json['label']),
      value: jsonDouble(json['value']),
    );
  }

  Map<String, dynamic> toJson() => {'label': label, 'value': value};
}

class ChildSummaryModel {
  const ChildSummaryModel({
    required this.id,
    required this.fullName,
    this.groupName = '',
    this.balance = 0,
    this.debt = 0,
    this.attendanceRate = 0,
    this.rank = 0,
  });

  final int id;
  final String fullName;
  final String groupName;
  final int balance;
  final int debt;
  final double attendanceRate;
  final int rank;

  factory ChildSummaryModel.fromJson(Map<String, dynamic> json) {
    final groups = jsonMapList(json['groups']);
    return ChildSummaryModel(
      id: jsonInt(json['id']),
      fullName: jsonString(json['full_name']),
      groupName: groups.isEmpty
          ? jsonString(json['group_name'])
          : jsonString(groups.first['name']),
      balance: jsonInt(json['balance']),
      debt: jsonInt(json['debt']),
      attendanceRate: jsonDouble(
        jsonMap(json['attendance'])['attendance_rate'],
      ),
      rank: jsonInt(json['rank']),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'full_name': fullName,
    'group_name': groupName,
    'balance': balance,
    'debt': debt,
    'attendance_rate': attendanceRate,
    'rank': rank,
  };
}

class DashboardData {
  const DashboardData({
    required this.metrics,
    required this.revenueTrend,
    required this.children,
    required this.unreadCount,
    this.teacherAttendanceRate = 0,
    this.studentScore = 0,
    this.studentRank = 0,
  });

  final List<DashboardMetric> metrics;
  final List<ChartPointModel> revenueTrend;
  final List<ChildSummaryModel> children;
  final int unreadCount;
  final double teacherAttendanceRate;
  final int studentScore;
  final int studentRank;

  factory DashboardData.empty() {
    return const DashboardData(
      metrics: <DashboardMetric>[],
      revenueTrend: <ChartPointModel>[],
      children: <ChildSummaryModel>[],
      unreadCount: 0,
    );
  }

  DashboardData copyWith({
    List<DashboardMetric>? metrics,
    List<ChartPointModel>? revenueTrend,
    List<ChildSummaryModel>? children,
    int? unreadCount,
    double? teacherAttendanceRate,
    int? studentScore,
    int? studentRank,
  }) {
    return DashboardData(
      metrics: metrics ?? this.metrics,
      revenueTrend: revenueTrend ?? this.revenueTrend,
      children: children ?? this.children,
      unreadCount: unreadCount ?? this.unreadCount,
      teacherAttendanceRate:
          teacherAttendanceRate ?? this.teacherAttendanceRate,
      studentScore: studentScore ?? this.studentScore,
      studentRank: studentRank ?? this.studentRank,
    );
  }
}

class StudentModel {
  const StudentModel({
    required this.id,
    required this.fullName,
    this.phone = '',
    this.email = '',
    this.groupName = '',
    this.groupId = 0,
    this.balance = 0,
    this.status = 'active',
    this.isActive = true,
    this.registrationDate,
    this.avatarUrl = '',
    this.attendanceRate = 0,
    this.chaqmoqScore = 0,
    this.rank = 0,
  });

  final int id;
  final String fullName;
  final String phone;
  final String email;
  final String groupName;
  final int groupId;
  final int balance;
  final String status;
  final bool isActive;
  final DateTime? registrationDate;
  final String avatarUrl;
  final double attendanceRate;
  final int chaqmoqScore;
  final int rank;

  factory StudentModel.fromJson(Map<String, dynamic> json) {
    final groups = jsonMapList(json['groups']);
    final attendance = jsonMap(json['attendance']);
    return StudentModel(
      id: jsonInt(json['id']),
      fullName: jsonString(json['full_name']).isNotEmpty
          ? jsonString(json['full_name'])
          : jsonString(json['name']),
      phone: jsonString(json['phone']).isNotEmpty
          ? jsonString(json['phone'])
          : jsonString(json['telefon1']),
      email: jsonString(json['email']),
      groupName: jsonString(json['group_name']).isNotEmpty
          ? jsonString(json['group_name'])
          : (groups.isNotEmpty ? jsonString(groups.first['name']) : ''),
      groupId: jsonInt(
        json['group_id'] ?? (groups.isNotEmpty ? groups.first['id'] : null),
      ),
      balance: jsonInt(json['balance']),
      status: jsonString(json['status']).isNotEmpty
          ? jsonString(json['status'])
          : (jsonBool(json['is_active']) ? 'active' : 'inactive'),
      isActive: jsonString(json['status']) == 'inactive'
          ? false
          : (json.containsKey('is_active')
                ? jsonBool(json['is_active'])
                : true),
      registrationDate: jsonDate(
        json['registration_date'] ?? json['created_at'] ?? json['date_joined'],
      ),
      avatarUrl: jsonString(json['avatar_url']),
      attendanceRate: jsonDouble(
        json['attendance_rate'] ?? attendance['attendance_rate'],
      ),
      chaqmoqScore: jsonInt(json['chaqmoq_score'] ?? json['balance']),
      rank: jsonInt(json['rank']),
    );
  }

  StudentModel copyWith({
    int? id,
    String? fullName,
    String? phone,
    String? email,
    String? groupName,
    int? groupId,
    int? balance,
    String? status,
    bool? isActive,
    DateTime? registrationDate,
    String? avatarUrl,
    double? attendanceRate,
    int? chaqmoqScore,
    int? rank,
  }) {
    return StudentModel(
      id: id ?? this.id,
      fullName: fullName ?? this.fullName,
      phone: phone ?? this.phone,
      email: email ?? this.email,
      groupName: groupName ?? this.groupName,
      groupId: groupId ?? this.groupId,
      balance: balance ?? this.balance,
      status: status ?? this.status,
      isActive: isActive ?? this.isActive,
      registrationDate: registrationDate ?? this.registrationDate,
      avatarUrl: avatarUrl ?? this.avatarUrl,
      attendanceRate: attendanceRate ?? this.attendanceRate,
      chaqmoqScore: chaqmoqScore ?? this.chaqmoqScore,
      rank: rank ?? this.rank,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'full_name': fullName,
    'phone': phone,
    'email': email,
    'group_name': groupName,
    'group_id': groupId,
    'balance': balance,
    'status': status,
    'is_active': isActive,
    'registration_date': registrationDate?.toIso8601String(),
    'avatar_url': avatarUrl,
    'attendance_rate': attendanceRate,
    'chaqmoq_score': chaqmoqScore,
    'rank': rank,
  };
}

class TeacherModel {
  const TeacherModel({
    required this.id,
    required this.fullName,
    this.phone = '',
    this.email = '',
    this.groupsCount = 0,
    this.studentsCount = 0,
    this.expectedIncome = 0,
    this.attendanceRate = 0,
    this.groupNames = const <String>[],
    this.avatarUrl = '',
  });

  final int id;
  final String fullName;
  final String phone;
  final String email;
  final int groupsCount;
  final int studentsCount;
  final int expectedIncome;
  final double attendanceRate;
  final List<String> groupNames;
  final String avatarUrl;

  factory TeacherModel.fromJson(Map<String, dynamic> json) {
    return TeacherModel(
      id: jsonInt(json['id']),
      fullName: jsonString(json['full_name']).isNotEmpty
          ? jsonString(json['full_name'])
          : jsonString(json['name']),
      phone: jsonString(json['phone']),
      email: jsonString(json['email']),
      groupsCount: jsonInt(json['groups_count']),
      studentsCount: jsonInt(json['students_count']),
      expectedIncome: jsonInt(json['expected_income']),
      attendanceRate: jsonDouble(json['attendance_rate']),
      groupNames: jsonStringList(json['group_names']),
      avatarUrl: jsonString(json['avatar_url']),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'full_name': fullName,
    'phone': phone,
    'email': email,
    'groups_count': groupsCount,
    'students_count': studentsCount,
    'expected_income': expectedIncome,
    'attendance_rate': attendanceRate,
    'group_names': groupNames,
    'avatar_url': avatarUrl,
  };
}

class GroupModel {
  const GroupModel({
    required this.id,
    required this.name,
    this.teacherId = 0,
    this.teacherName = '',
    this.studentCount = 0,
    this.capacity = 0,
    this.schedule = '',
    this.category = '',
    this.monthlyPrice = 0,
    this.attendanceRate = 0,
  });

  final int id;
  final String name;
  final int teacherId;
  final String teacherName;
  final int studentCount;
  final int capacity;
  final String schedule;
  final String category;
  final int monthlyPrice;
  final double attendanceRate;

  double get fillRate {
    if (capacity <= 0) {
      return 0;
    }
    return studentCount / capacity;
  }

  factory GroupModel.fromJson(Map<String, dynamic> json) {
    return GroupModel(
      id: jsonInt(json['id']),
      name: jsonString(json['name']).isNotEmpty
          ? jsonString(json['name'])
          : jsonString(json['nom']),
      teacherId: jsonInt(json['teacher_id']),
      teacherName: jsonString(json['teacher_name']).isNotEmpty
          ? jsonString(json['teacher_name'])
          : jsonString(json['teacher']),
      studentCount: jsonInt(json['student_count'] ?? json['enrolled']),
      capacity: jsonInt(json['capacity'] ?? json['limit'] ?? 24),
      schedule: jsonString(json['schedule']),
      category: jsonString(json['category']),
      monthlyPrice: jsonInt(json['monthly_price']),
      attendanceRate: jsonDouble(json['attendance_rate'] ?? json['att_rate']),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'teacher_id': teacherId,
    'teacher_name': teacherName,
    'student_count': studentCount,
    'capacity': capacity,
    'schedule': schedule,
    'category': category,
    'monthly_price': monthlyPrice,
    'attendance_rate': attendanceRate,
  };
}

class AttendanceStudentModel {
  const AttendanceStudentModel({
    required this.studentId,
    required this.enrollmentId,
    required this.fullName,
    this.balance = 0,
    this.status = 'none',
  });

  final int studentId;
  final int enrollmentId;
  final String fullName;
  final int balance;
  final String status;

  AttendanceStudentModel copyWith({
    int? studentId,
    int? enrollmentId,
    String? fullName,
    int? balance,
    String? status,
  }) {
    return AttendanceStudentModel(
      studentId: studentId ?? this.studentId,
      enrollmentId: enrollmentId ?? this.enrollmentId,
      fullName: fullName ?? this.fullName,
      balance: balance ?? this.balance,
      status: status ?? this.status,
    );
  }

  factory AttendanceStudentModel.fromJson(Map<String, dynamic> json) {
    return AttendanceStudentModel(
      studentId: jsonInt(json['student_id'] ?? json['id']),
      enrollmentId: jsonInt(json['enrollment_id'] ?? json['enr_id']),
      fullName: jsonString(json['full_name']).isNotEmpty
          ? jsonString(json['full_name'])
          : jsonString(json['student_name']).isNotEmpty
          ? jsonString(json['student_name'])
          : jsonString(json['name']),
      balance: jsonInt(json['balance']),
      status: jsonString(json['status']).isEmpty
          ? 'none'
          : jsonString(json['status']),
    );
  }

  Map<String, dynamic> toJson() => {
    'student_id': studentId,
    'enrollment_id': enrollmentId,
    'full_name': fullName,
    'balance': balance,
    'status': status,
  };
}

class AttendanceSheetModel {
  const AttendanceSheetModel({
    required this.groupId,
    required this.groupName,
    required this.date,
    required this.readOnly,
    required this.items,
  });

  final int groupId;
  final String groupName;
  final DateTime date;
  final bool readOnly;
  final List<AttendanceStudentModel> items;

  factory AttendanceSheetModel.fromJson(Map<String, dynamic> json) {
    return AttendanceSheetModel(
      groupId: jsonInt(json['group_id']),
      groupName: jsonString(json['group_name']),
      date: jsonDate(json['date']) ?? DateTime.now(),
      readOnly: jsonBool(json['read_only']),
      items: jsonMapList(
        json['items'],
      ).map(AttendanceStudentModel.fromJson).toList(),
    );
  }

  Map<String, dynamic> toJson() => {
    'group_id': groupId,
    'group_name': groupName,
    'date': date.toIso8601String(),
    'read_only': readOnly,
    'items': items.map((item) => item.toJson()).toList(),
  };
}

class PaymentModel {
  const PaymentModel({
    required this.id,
    required this.studentName,
    required this.amount,
    required this.date,
    this.studentId = 0,
    this.groupId = 0,
    this.groupName = '',
    this.method = '',
    this.note = '',
    this.isDebt = false,
  });

  final int id;
  final int studentId;
  final int groupId;
  final String studentName;
  final String groupName;
  final int amount;
  final DateTime date;
  final String method;
  final String note;
  final bool isDebt;

  factory PaymentModel.fromJson(Map<String, dynamic> json) {
    return PaymentModel(
      id: jsonInt(json['id']),
      studentId: jsonInt(json['student_id']),
      groupId: jsonInt(json['group_id']),
      studentName: jsonString(json['student_name']).isNotEmpty
          ? jsonString(json['student_name'])
          : jsonString(json['full_name']),
      groupName: jsonString(json['group_name']),
      amount: jsonInt(json['amount'] ?? json['summa'] ?? json['debt']),
      date:
          jsonDate(json['date'] ?? json['paid_date'] ?? json['raw_date']) ??
          DateTime.now(),
      method: jsonString(json['method'] ?? json['payment_type']),
      note: jsonString(json['note']),
      isDebt:
          jsonBool(json['is_debt']) ||
          jsonString(json['status']).toLowerCase() == 'debt',
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'student_id': studentId,
    'group_id': groupId,
    'student_name': studentName,
    'group_name': groupName,
    'amount': amount,
    'date': date.toIso8601String(),
    'method': method,
    'note': note,
    'is_debt': isDebt,
  };
}

class PaymentSummaryModel {
  const PaymentSummaryModel({
    required this.totalReceived,
    required this.openDebt,
    required this.thisMonth,
  });

  final int totalReceived;
  final int openDebt;
  final int thisMonth;

  factory PaymentSummaryModel.fromJson(Map<String, dynamic> json) {
    return PaymentSummaryModel(
      totalReceived: jsonInt(json['total_received']),
      openDebt: jsonInt(json['open_debt']),
      thisMonth: jsonInt(json['this_month']),
    );
  }

  Map<String, dynamic> toJson() => {
    'total_received': totalReceived,
    'open_debt': openDebt,
    'this_month': thisMonth,
  };
}

class NotificationModel {
  const NotificationModel({
    required this.id,
    required this.title,
    required this.body,
    required this.createdAt,
    this.type = '',
    this.kind = '',
    this.amount,
    this.signedAmount,
    this.reason = '',
    this.isRead = false,
    this.target = '',
    this.senderName = '',
    this.recipientName = '',
  });

  final int id;
  final String title;
  final String body;
  final DateTime createdAt;
  final String type;
  final String kind;
  final int? amount;
  final int? signedAmount;
  final String reason;
  final bool isRead;
  final String target;
  final String senderName;
  final String recipientName;

  factory NotificationModel.fromJson(Map<String, dynamic> json) {
    return NotificationModel(
      id: jsonInt(json['id']),
      title: cleanHtmlText(json['title']),
      body: cleanHtmlText(json['body']).isNotEmpty
          ? cleanHtmlText(json['body'])
          : cleanHtmlText(json['message']),
      createdAt: jsonDate(json['created_at']) ?? DateTime.now(),
      type: jsonString(json['type']),
      kind: jsonString(json['kind']),
      amount: json['amount'] is num ? (json['amount'] as num).toInt() : null,
      signedAmount: json['signed_amount'] is num
          ? (json['signed_amount'] as num).toInt()
          : null,
      reason: cleanHtmlText(json['reason']),
      isRead: jsonBool(json['is_read']),
      target: jsonString(json['target']),
      senderName: cleanHtmlText(json['sender_name']),
      recipientName: cleanHtmlText(json['recipient_name']),
    );
  }

  NotificationModel copyWith({bool? isRead}) {
    return NotificationModel(
      id: id,
      title: title,
      body: body,
      createdAt: createdAt,
      type: type,
      kind: kind,
      amount: amount,
      signedAmount: signedAmount,
      reason: reason,
      isRead: isRead ?? this.isRead,
      target: target,
      senderName: senderName,
      recipientName: recipientName,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'title': title,
    'body': body,
    'created_at': createdAt.toIso8601String(),
    'type': type,
    'is_read': isRead,
    'target': target,
    'sender_name': senderName,
    'recipient_name': recipientName,
  };
}

class ChaqmoqEntryModel {
  const ChaqmoqEntryModel({
    required this.id,
    required this.points,
    required this.ruleName,
    required this.createdAt,
    this.groupName = '',
    this.giverName = '',
  });

  final int id;
  final int points;
  final String ruleName;
  final String groupName;
  final String giverName;
  final DateTime createdAt;

  factory ChaqmoqEntryModel.fromJson(Map<String, dynamic> json) {
    return ChaqmoqEntryModel(
      id: jsonInt(json['id']),
      points: jsonInt(json['points']),
      ruleName: jsonString(json['rule_name']),
      groupName: jsonString(json['group_name']),
      giverName: jsonString(json['giver_name']),
      createdAt: jsonDate(json['created_at']) ?? DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'points': points,
    'rule_name': ruleName,
    'group_name': groupName,
    'giver_name': giverName,
    'created_at': createdAt.toIso8601String(),
  };
}

class StudentDetailModel {
  const StudentDetailModel({
    required this.student,
    required this.payments,
    required this.attendance,
    required this.chaqmoqHistory,
    required this.badges,
  });

  final StudentModel student;
  final List<PaymentModel> payments;
  final List<DateTime> attendance;
  final List<ChaqmoqEntryModel> chaqmoqHistory;
  final List<String> badges;

  factory StudentDetailModel.fromJson(Map<String, dynamic> json) {
    return StudentDetailModel(
      student: StudentModel.fromJson(jsonMap(json['student'])),
      payments: jsonMapList(
        json['payments'],
      ).map(PaymentModel.fromJson).toList(),
      attendance: jsonMapList(
        json['attendance'],
      ).map((item) => jsonDate(item['date'])).whereType<DateTime>().toList(),
      chaqmoqHistory: jsonMapList(
        json['chaqmoq_history'],
      ).map(ChaqmoqEntryModel.fromJson).toList(),
      badges: jsonStringList(json['badges']),
    );
  }

  Map<String, dynamic> toJson() => {
    'student': student.toJson(),
    'payments': payments.map((item) => item.toJson()).toList(),
    'attendance': attendance
        .map((item) => {'date': item.toIso8601String()})
        .toList(),
    'chaqmoq_history': chaqmoqHistory.map((item) => item.toJson()).toList(),
    'badges': badges,
  };
}
