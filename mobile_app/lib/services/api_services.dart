import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';

class _BaseService {
  const _BaseService(this.apiClient);

  final ApiClient apiClient;

  Future<Map<String, dynamic>> getFirst(
    List<String> paths, {
    Map<String, dynamic>? queryParameters,
  }) async {
    Object? lastError;
    for (final path in paths) {
      try {
        return await apiClient.get(path, queryParameters: queryParameters);
      } catch (error) {
        lastError = error;
      }
    }

    if (lastError is ApiException) {
      throw lastError;
    }
    throw ApiException('So\'rov bajarilmadi');
  }

  Future<Map<String, dynamic>> postFirst(
    List<String> paths, {
    Object? data,
    Map<String, dynamic>? queryParameters,
  }) async {
    Object? lastError;
    for (final path in paths) {
      try {
        return await apiClient.post(
          path,
          data: data,
          queryParameters: queryParameters,
        );
      } catch (error) {
        lastError = error;
      }
    }

    if (lastError is ApiException) {
      throw lastError;
    }
    throw ApiException('So\'rov bajarilmadi');
  }
}

class DashboardService extends _BaseService {
  const DashboardService(super.apiClient);

  Future<DashboardData> fetchDashboard(UserModel user) async {
    final role = user.role.toLowerCase();
    if (role == 'teacher') {
      return _fetchTeacherDashboard();
    }
    if (role == 'student') {
      return _fetchStudentDashboard();
    }
    if (role == 'parent') {
      return _fetchParentDashboard();
    }
    return _fetchDirectorDashboard();
  }

  Future<DashboardData> _fetchDirectorDashboard() async {
    final payload = await getFirst(const [
      '/api/boshqaruv/',
      '/api/dashboards/overview/',
      '/api/mobile/home/',
    ]);
    final kpis = jsonMap(payload['kpis']);
    final charts = jsonMap(payload['charts']);
    final labels = charts['monthly_labels'] is List
        ? List<dynamic>.from(charts['monthly_labels'] as List)
        : List<dynamic>.from(charts['m_labels'] as List? ?? const []);
    final values = charts['monthly_turnover'] is List
        ? List<dynamic>.from(charts['monthly_turnover'] as List)
        : List<dynamic>.from(charts['m_rev'] as List? ?? const []);

    final trend = <ChartPointModel>[];
    for (
      var index = 0;
      index < labels.length && index < values.length;
      index++
    ) {
      trend.add(
        ChartPointModel(
          label: jsonString(labels[index]),
          value: jsonDouble(values[index]),
        ),
      );
    }

    final metrics = <DashboardMetric>[
      DashboardMetric(
        id: 'revenue',
        title: 'Tushum',
        value: jsonInt(
          kpis['revenue'] ??
              kpis['total_pay'] ??
              jsonMap(payload['summary'])['today_payments'],
        ).toString(),
        subtitle: 'Joriy davr',
        trend: jsonDouble(
          jsonMap(kpis['changes'])['revenue'] ??
              jsonMap(kpis['changes'])['total_pay'],
        ),
        colorKey: 'teal',
      ),
      DashboardMetric(
        id: 'students',
        title: 'O\'quvchilar',
        value: jsonInt(
          kpis['active_students'] ??
              kpis['active_count'] ??
              kpis['total_students'],
        ).toString(),
        subtitle: 'Faol kontingent',
        trend: jsonDouble(
          jsonMap(kpis['changes'])['students'] ??
              jsonMap(kpis['changes'])['new_students'],
        ),
        colorKey: 'violet',
      ),
      DashboardMetric(
        id: 'attendance',
        title: 'Davomat',
        value: jsonInt(
          kpis['avg_attendance'] ?? kpis['avg_att_rate'],
        ).toString(),
        subtitle: 'O\'rtacha foiz',
        trend: jsonDouble(
          jsonMap(kpis['changes'])['avg_attendance'] ??
              jsonMap(kpis['changes'])['avg_att_rate'],
        ),
        colorKey: 'green',
      ),
      DashboardMetric(
        id: 'debt',
        title: 'Qarz',
        value: jsonInt(kpis['total_debt']).toString(),
        subtitle: 'Ochiq qoldiq',
        trend: jsonDouble(jsonMap(kpis['changes'])['total_debt']),
        colorKey: 'red',
      ),
    ];

    return DashboardData(
      metrics: metrics,
      revenueTrend: trend.take(7).toList(),
      children: const <ChildSummaryModel>[],
      unreadCount: jsonInt(payload['unread_notifications']),
    );
  }

  Future<DashboardData> _fetchTeacherDashboard() async {
    final payload = await getFirst(const [
      '/api/mobile/teacher/home/',
      '/api/mobile/home/',
      '/api/dashboards/teachers/',
    ]);
    final summary = jsonMap(payload['summary']);
    final kpis = jsonMap(payload['kpis']);
    final teacher = jsonMap(payload['teacher']);
    final groups = jsonMapList(payload['groups']);

    final metrics = <DashboardMetric>[
      DashboardMetric(
        id: 'groups',
        title: 'Guruhlar',
        value: jsonInt(summary['groups_count'] ?? groups.length).toString(),
        subtitle: 'Mas\'ul guruhlar',
        trend: 0,
        colorKey: 'violet',
      ),
      DashboardMetric(
        id: 'students',
        title: 'O\'quvchilar',
        value: jsonInt(
          summary['students_count'] ?? kpis['student_count'],
        ).toString(),
        subtitle: teacher['full_name'] == null
            ? 'Joriy yuklama'
            : 'Ustoz yuklamasi',
        trend: 0,
        colorKey: 'teal',
      ),
      DashboardMetric(
        id: 'attendance',
        title: 'Davomat',
        value: jsonInt(
          kpis['ratio'] ?? summary['today_attendance_marked'],
        ).toString(),
        subtitle: 'Bugungi belgilashlar',
        trend: 0,
        colorKey: 'green',
      ),
      DashboardMetric(
        id: 'income',
        title: 'Kutilgan daromad',
        value: jsonInt(
          payload['expected_income'] ?? kpis['avg_rev'],
        ).toString(),
        subtitle: 'Joriy oy',
        trend: jsonDouble(jsonMap(kpis['changes'])['total_rev']),
        colorKey: 'violet',
      ),
    ];

    final attendanceRate = jsonDouble(
      jsonMap(payload['charts'])['attendance'] is List &&
              (jsonMap(payload['charts'])['attendance'] as List).isNotEmpty
          ? (jsonMap(payload['charts'])['attendance'] as List).first
          : 0,
    );

    return DashboardData(
      metrics: metrics,
      revenueTrend: const <ChartPointModel>[],
      children: const <ChildSummaryModel>[],
      unreadCount: jsonInt(payload['unread_notifications']),
      teacherAttendanceRate: attendanceRate,
    );
  }

  Future<DashboardData> _fetchStudentDashboard() async {
    final home = await getFirst(const [
      '/api/mobile/student/home/',
      '/api/mobile/home/',
    ]);
    final studentPayload = jsonMap(home['student']);
    final student = studentPayload.isNotEmpty
        ? studentPayload
        : jsonMap(home['summary']);
    final lightning = await getFirst(const ['/api/mobile/chaqmoq/history/']);
    final metrics = <DashboardMetric>[
      DashboardMetric(
        id: 'score',
        title: 'Chaqmoq balli',
        value: jsonInt(lightning['balance'] ?? student['balance']).toString(),
        subtitle: 'Joriy holat',
        trend: 0,
        colorKey: 'violet',
      ),
      DashboardMetric(
        id: 'debt',
        title: 'Qarz',
        value: jsonInt(student['debt']).toString(),
        subtitle: 'Ochiq to\'lov',
        trend: 0,
        colorKey: 'red',
      ),
      DashboardMetric(
        id: 'attendance',
        title: 'Davomat',
        value: jsonInt(
          jsonMap(student['attendance'])['attendance_rate'],
        ).toString(),
        subtitle: 'So\'nggi ko\'rsatkich',
        trend: 0,
        colorKey: 'green',
      ),
    ];

    return DashboardData(
      metrics: metrics,
      revenueTrend: const <ChartPointModel>[],
      children: const <ChildSummaryModel>[],
      unreadCount: jsonInt(home['unread_notifications']),
      studentScore: jsonInt(lightning['balance'] ?? student['balance']),
      studentRank: jsonMapList(lightning['items']).length,
    );
  }

  Future<DashboardData> _fetchParentDashboard() async {
    final payload = await getFirst(const [
      '/api/mobile/parent/home/',
      '/api/mobile/home/',
    ]);
    final directChildren = jsonMapList(payload['children']);
    final children =
        (directChildren.isNotEmpty
                ? directChildren
                : jsonMapList(jsonMap(payload['summary'])['children']))
            .map(ChildSummaryModel.fromJson)
            .toList();
    return DashboardData(
      metrics: <DashboardMetric>[
        DashboardMetric(
          id: 'children',
          title: 'Farzandlar',
          value: children.length.toString(),
          subtitle: 'Biriktirilgan profillar',
          trend: 0,
          colorKey: 'violet',
        ),
      ],
      revenueTrend: const <ChartPointModel>[],
      children: children,
      unreadCount: jsonInt(payload['unread_notifications']),
    );
  }
}

class StudentsService extends _BaseService {
  const StudentsService(super.apiClient);

  Future<List<StudentModel>> fetchStudents({String? query}) async {
    final payload = await getFirst(const [
      '/chaqmoq/api/students/',
      '/api/students/',
    ], queryParameters: query == null || query.isEmpty ? null : {'q': query});

    final studentsPayload = jsonMapList(payload['students']);
    final rawItems = studentsPayload.isNotEmpty
        ? studentsPayload
        : jsonMapList(payload['items']);
    return rawItems.map((item) => StudentModel.fromJson(item)).toList();
  }

  Future<StudentDetailModel> fetchStudentDetail(StudentModel student) async {
    final paymentsPayload = await getFirst([
      '/talim/tolovlar/tarix/${student.id}/',
      '/api/students/${student.id}/payments/',
    ]);

    Map<String, dynamic> chaqmoqPayload = <String, dynamic>{};
    try {
      chaqmoqPayload = await getFirst(
        ['/api/mobile/chaqmoq/history/'],
        queryParameters: {'student_id': '${student.id}'},
      );
    } catch (_) {}

    Map<String, dynamic> debtPayload = <String, dynamic>{};
    try {
      debtPayload = await getFirst(
        ['/api/mobile/student/debt/'],
        queryParameters: {'student_id': '${student.id}'},
      );
    } catch (_) {}

    final badges = <String>[
      if (jsonInt(chaqmoqPayload['balance']) >= 100) 'Top faollik',
      if (jsonInt(debtPayload['total_debt']) == 0) 'To\'lov intizomi',
      if (student.attendanceRate >= 85) 'Davomat yetakchisi',
    ];

    return StudentDetailModel(
      student: student.copyWith(
        balance: jsonInt(chaqmoqPayload['balance']) == 0
            ? student.balance
            : jsonInt(chaqmoqPayload['balance']),
      ),
      payments: jsonMapList(
        paymentsPayload['payments'],
      ).map(PaymentModel.fromJson).toList(),
      attendance: const <DateTime>[],
      chaqmoqHistory: jsonMapList(
        chaqmoqPayload['items'],
      ).map(ChaqmoqEntryModel.fromJson).toList(),
      badges: badges,
    );
  }
}

class TeachersService extends _BaseService {
  const TeachersService(super.apiClient);

  Future<List<TeacherModel>> fetchTeachers() async {
    final payload = await getFirst(const [
      '/api/dashboards/teachers/',
      '/api/teachers/',
    ]);
    final teachersPayload = jsonMapList(payload['teachers']);
    final rawItems = teachersPayload.isNotEmpty
        ? teachersPayload
        : jsonMapList(payload['items']);
    return rawItems.map(TeacherModel.fromJson).toList();
  }

  Future<TeacherModel> fetchTeacherDetail(TeacherModel teacher) async {
    final payload = await getFirst(
      const ['/api/mobile/teacher/home/'],
      queryParameters: {'teacher_id': '${teacher.id}'},
    );
    final groups = jsonMapList(payload['groups']);
    return TeacherModel(
      id: teacher.id,
      fullName: jsonString(jsonMap(payload['teacher'])['full_name']).isNotEmpty
          ? jsonString(jsonMap(payload['teacher'])['full_name'])
          : teacher.fullName,
      phone: teacher.phone,
      email: teacher.email,
      groupsCount: groups.length,
      studentsCount: groups.fold<int>(
        0,
        (previousValue, element) =>
            previousValue + jsonInt(element['student_count']),
      ),
      expectedIncome: jsonInt(payload['expected_income']),
      attendanceRate: teacher.attendanceRate,
      groupNames: groups.map((group) => jsonString(group['name'])).toList(),
      avatarUrl: teacher.avatarUrl,
    );
  }
}

class GroupsService extends _BaseService {
  const GroupsService(super.apiClient);

  Future<List<GroupModel>> fetchGroups(String role) async {
    if (role == 'teacher') {
      final payload = await getFirst(const ['/api/mobile/teacher/home/']);
      return jsonMapList(payload['groups']).map(GroupModel.fromJson).toList();
    }

    final payload = await getFirst(const [
      '/api/dashboards/groups/',
      '/api/groups/',
    ]);
    final groupsPayload = jsonMapList(payload['groups']);
    final rawItems = groupsPayload.isNotEmpty
        ? groupsPayload
        : jsonMapList(payload['items']);
    return rawItems.map(GroupModel.fromJson).toList();
  }

  Future<List<StudentModel>> fetchGroupStudents(int groupId) async {
    final payload = await getFirst(
      ['/chaqmoq/api/students/', '/api/groups/$groupId/students/'],
      queryParameters: {'group': '$groupId'},
    );
    final studentsPayload = jsonMapList(payload['students']);
    final items = studentsPayload.isNotEmpty
        ? studentsPayload
        : jsonMapList(payload['items']);
    return items.map(StudentModel.fromJson).toList();
  }
}

class AttendanceService extends _BaseService {
  const AttendanceService(super.apiClient);

  Future<AttendanceSheetModel> fetchAttendanceSheet({
    required int groupId,
    required String groupName,
    required DateTime date,
  }) async {
    final payload = await getFirst(
      ['/chaqmoq/api/students/', '/api/groups/$groupId/students/'],
      queryParameters: {'group': '$groupId'},
    );

    final studentsPayload = jsonMapList(payload['students']);
    final students =
        (studentsPayload.isNotEmpty
                ? studentsPayload
                : jsonMapList(payload['items']))
            .map(
              (item) => AttendanceStudentModel(
                studentId: jsonInt(item['id']),
                enrollmentId: jsonInt(item['enrollment_id'] ?? item['id']),
                fullName: jsonString(item['full_name']).isNotEmpty
                    ? jsonString(item['full_name'])
                    : jsonString(item['name']),
                balance: jsonInt(item['balance']),
                status: 'none',
              ),
            )
            .toList();

    return AttendanceSheetModel(
      groupId: groupId,
      groupName: groupName,
      date: date,
      readOnly: !_isSameDay(date, DateTime.now()),
      items: students,
    );
  }

  bool _isSameDay(DateTime left, DateTime right) {
    return left.year == right.year &&
        left.month == right.month &&
        left.day == right.day;
  }

  Future<void> submitAttendance({
    required int groupId,
    required DateTime date,
    required List<AttendanceStudentModel> items,
  }) async {
    final formattedDate = date.toIso8601String().split('T').first;
    for (final item in items) {
      await postFirst(
        ['/talim/guruh/$groupId/attendance_today/', '/api/attendance/mark/'],
        data: <String, dynamic>{
          'enr_id': item.enrollmentId,
          'date': formattedDate,
          'status': item.status,
        },
      );
    }
  }
}

class PaymentsService extends _BaseService {
  const PaymentsService(super.apiClient);

  Future<(PaymentSummaryModel, List<PaymentModel>)> fetchPayments(
    UserModel user,
  ) async {
    if (user.role == 'student') {
      final data = await _studentPayments(user.id);
      return data;
    }

    if (user.role == 'parent') {
      final parentPayload = await getFirst(const ['/api/mobile/parent/home/']);
      final children = jsonMapList(parentPayload['children']);
      final items = <PaymentModel>[];
      var totalReceived = 0;
      var openDebt = 0;
      var thisMonth = 0;
      for (final child in children) {
        final childId = jsonInt(child['id']);
        final data = await _studentPayments(childId);
        totalReceived += data.$1.totalReceived;
        openDebt += data.$1.openDebt;
        thisMonth += data.$1.thisMonth;
        items.addAll(data.$2);
      }
      items.sort((left, right) => right.date.compareTo(left.date));
      return (
        PaymentSummaryModel(
          totalReceived: totalReceived,
          openDebt: openDebt,
          thisMonth: thisMonth,
        ),
        items.take(20).toList(),
      );
    }

    final billingPayload = await getFirst(const ['/api/dashboards/billing/']);
    final kpis = jsonMap(billingPayload['kpis']);
    final studentsPayload = await getFirst(const ['/chaqmoq/api/students/']);
    final students = jsonMapList(studentsPayload['students']).take(10).toList();
    final items = <PaymentModel>[];
    for (final student in students) {
      try {
        final data = await _studentPayments(jsonInt(student['id']));
        items.addAll(data.$2.take(2));
      } catch (_) {}
    }
    items.sort((left, right) => right.date.compareTo(left.date));
    return (
      PaymentSummaryModel(
        totalReceived: jsonInt(kpis['total_pay']),
        openDebt: jsonInt(kpis['total_debt']),
        thisMonth: jsonInt(kpis['total_pay']),
      ),
      items.take(20).toList(),
    );
  }

  Future<(PaymentSummaryModel, List<PaymentModel>)> _studentPayments(
    int studentId,
  ) async {
    final history = await getFirst([
      '/talim/tolovlar/tarix/$studentId/',
      '/api/students/$studentId/payments/',
    ]);
    Map<String, dynamic> debtPayload = <String, dynamic>{};
    try {
      debtPayload = await getFirst(
        const ['/api/mobile/student/debt/'],
        queryParameters: {'student_id': '$studentId'},
      );
    } catch (_) {}

    final payments = jsonMapList(
      history['payments'],
    ).map(PaymentModel.fromJson).toList();
    final thisMonth = jsonInt(history['paid_this_month']);
    final total = payments.fold<int>(0, (sum, item) => sum + item.amount);

    return (
      PaymentSummaryModel(
        totalReceived: total,
        openDebt: jsonInt(debtPayload['total_debt'] ?? history['qoldiq']),
        thisMonth: thisMonth,
      ),
      payments,
    );
  }
}

class NotificationsService extends _BaseService {
  const NotificationsService(super.apiClient);

  Future<(List<NotificationModel>, int)> fetchNotifications() async {
    final payload = await getFirst(const [
      '/api/mobile/notifications/',
      '/api/notifications/',
    ]);
    return (
      jsonMapList(payload['items']).map(NotificationModel.fromJson).toList(),
      jsonInt(payload['unread_count']),
    );
  }

  Future<void> markAllRead() async {
    await postFirst(const ['/api/mobile/notifications/read-all/']);
  }

  Future<void> markRead(int notificationId) async {
    await postFirst([
      '/api/mobile/notifications/$notificationId/read/',
      '/api/mobile/parent/notifications/$notificationId/read/',
    ]);
  }
}
