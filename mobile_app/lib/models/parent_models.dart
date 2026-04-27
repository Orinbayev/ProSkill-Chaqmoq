import 'package:chaqmoq_mobile/models/app_models.dart';

class ParentChildModel {
  const ParentChildModel({
    required this.id,
    required this.fullName,
    this.groupName = '',
    this.className = '',
    this.avatarUrl = '',
    this.childCode = '',
    this.center,
  });

  final int id;
  final String fullName;
  final String groupName;
  final String className;
  final String avatarUrl;
  final String childCode;
  final CenterModel? center;

  factory ParentChildModel.fromJson(Map<String, dynamic> json) {
    return ParentChildModel(
      id: jsonInt(json['id']),
      fullName: jsonString(json['full_name']),
      groupName: jsonString(json['group_name']),
      className: jsonString(json['class_name']),
      avatarUrl: jsonString(json['avatar_url']),
      childCode: jsonString(json['child_code']),
      center: json['center'] == null
          ? null
          : CenterModel.fromJson(jsonMap(json['center'])),
    );
  }
}

class ParentStatsModel {
  const ParentStatsModel({
    required this.attendancePercent,
    required this.debtAmount,
    required this.averageScore,
    this.nextPaymentDate,
  });

  final int attendancePercent;
  final int debtAmount;
  final int averageScore;
  final DateTime? nextPaymentDate;

  factory ParentStatsModel.fromJson(Map<String, dynamic> json) {
    return ParentStatsModel(
      attendancePercent: jsonInt(json['attendance_percent']),
      debtAmount: jsonInt(json['debt_amount']),
      averageScore: jsonInt(json['average_score']),
      nextPaymentDate: jsonDate(json['next_payment_date']),
    );
  }
}

class ParentProgressSeries {
  const ParentProgressSeries({
    required this.label,
    required this.percent,
    required this.points,
    required this.months,
  });

  final String label;
  final int percent;
  final List<double> points;
  final List<String> months;

  factory ParentProgressSeries.fromJson(Map<String, dynamic> json) {
    final rawPoints = json['points'];
    return ParentProgressSeries(
      label: jsonString(json['label']).isNotEmpty
          ? jsonString(json['label'])
          : jsonString(json['subject']),
      percent: jsonInt(json['percent']),
      points: rawPoints is List
          ? rawPoints.map((item) => jsonDouble(item)).toList()
          : const <double>[],
      months: jsonStringList(json['months']),
    );
  }
}

class ParentNotificationModel {
  const ParentNotificationModel({
    required this.id,
    required this.title,
    required this.message,
    required this.type,
    required this.isRead,
    this.createdAt,
  });

  final int id;
  final String title;
  final String message;
  final String type;
  final bool isRead;
  final DateTime? createdAt;

  factory ParentNotificationModel.fromJson(Map<String, dynamic> json) {
    return ParentNotificationModel(
      id: jsonInt(json['id']),
      title: cleanHtmlText(json['title']),
      message: cleanHtmlText(json['message']),
      type: jsonString(json['type']),
      isRead: jsonBool(json['is_read']),
      createdAt: jsonDate(json['created_at']),
    );
  }
}

class ParentAttendanceItemModel {
  const ParentAttendanceItemModel({
    required this.id,
    required this.date,
    required this.groupName,
    required this.status,
    required this.present,
    this.groupId = 0,
    this.teacherName = '',
    this.statusLabel = '',
    this.createdAt,
  });

  final int id;
  final DateTime date;
  final int groupId;
  final String groupName;
  final String teacherName;
  final String status;
  final String statusLabel;
  final bool present;
  final DateTime? createdAt;

  factory ParentAttendanceItemModel.fromJson(Map<String, dynamic> json) {
    return ParentAttendanceItemModel(
      id: jsonInt(json['id']),
      date: jsonDate(json['date']) ?? DateTime.now(),
      groupId: jsonInt(json['group_id']),
      groupName: jsonString(json['group_name']),
      teacherName: jsonString(json['teacher_name']),
      status: jsonString(json['status']),
      statusLabel: jsonString(json['status_label']),
      present:
          jsonBool(json['present']) || jsonString(json['status']) == 'present',
      createdAt: jsonDate(json['created_at']),
    );
  }
}

class ParentAttendanceModel {
  const ParentAttendanceModel({
    required this.child,
    required this.summary,
    required this.items,
  });

  final ParentChildModel child;
  final ParentAttendanceSummaryModel summary;
  final List<ParentAttendanceItemModel> items;

  factory ParentAttendanceModel.fromJson(Map<String, dynamic> json) {
    return ParentAttendanceModel(
      child: ParentChildModel.fromJson(jsonMap(json['child'])),
      summary: ParentAttendanceSummaryModel.fromJson(jsonMap(json['summary'])),
      items: jsonMapList(
        json['items'],
      ).map(ParentAttendanceItemModel.fromJson).toList(),
    );
  }
}

class ParentAttendanceSummaryModel {
  const ParentAttendanceSummaryModel({
    required this.totalLessons,
    required this.presentLessons,
    required this.attendanceRate,
    required this.recentAttendanceRate,
  });

  final int totalLessons;
  final int presentLessons;
  final double attendanceRate;
  final double recentAttendanceRate;

  factory ParentAttendanceSummaryModel.fromJson(Map<String, dynamic> json) {
    return ParentAttendanceSummaryModel(
      totalLessons: jsonInt(json['total_lessons']),
      presentLessons: jsonInt(json['present_lessons']),
      attendanceRate: jsonDouble(json['attendance_rate']),
      recentAttendanceRate: jsonDouble(json['recent_attendance_rate']),
    );
  }
}

class ParentPaymentSummaryModel {
  const ParentPaymentSummaryModel({
    required this.totalPlan,
    required this.totalBalance,
    required this.paidTotal,
    required this.debtAmount,
    this.nextPaymentDate,
  });

  final int totalPlan;
  final int totalBalance;
  final int paidTotal;
  final int debtAmount;
  final DateTime? nextPaymentDate;

  int get payableTotal =>
      totalBalance > 0 ? totalBalance : paidTotal + debtAmount;
  int get remaining => debtAmount;
  double get paidRatio {
    final denominator = payableTotal > 0 ? payableTotal : totalPlan;
    if (denominator <= 0) {
      return 0;
    }
    return (paidTotal / denominator).clamp(0, 1).toDouble();
  }

  factory ParentPaymentSummaryModel.fromJson(Map<String, dynamic> json) {
    final paidTotal = jsonInt(json['paid_total'] ?? json['total_received']);
    final debtAmount = jsonInt(json['debt_amount'] ?? json['open_debt']);
    return ParentPaymentSummaryModel(
      totalPlan: jsonInt(json['total_plan']),
      totalBalance: jsonInt(json['total_balance']),
      paidTotal: paidTotal,
      debtAmount: debtAmount,
      nextPaymentDate: jsonDate(json['next_payment_date']),
    );
  }
}

class ParentPaymentHistoryModel {
  const ParentPaymentHistoryModel({
    required this.id,
    required this.title,
    required this.date,
    required this.amount,
    required this.status,
    this.groupName = '',
    this.statusLabel = '',
    this.paymentType = '',
    this.note = '',
  });

  final int id;
  final String title;
  final DateTime date;
  final int amount;
  final String status;
  final String groupName;
  final String statusLabel;
  final String paymentType;
  final String note;

  factory ParentPaymentHistoryModel.fromJson(Map<String, dynamic> json) {
    return ParentPaymentHistoryModel(
      id: jsonInt(json['id']),
      title: jsonString(json['title']).isNotEmpty
          ? jsonString(json['title'])
          : '${jsonString(json['group_name'])} uchun to‘lov',
      date: jsonDate(json['date'] ?? json['paid_date']) ?? DateTime.now(),
      amount: jsonInt(json['amount'] ?? json['summa']),
      status: jsonString(json['status']).isEmpty
          ? 'paid'
          : jsonString(json['status']),
      groupName: jsonString(json['group_name']),
      statusLabel: jsonString(json['status_label']),
      paymentType: jsonString(json['payment_type']),
      note: jsonString(json['note']),
    );
  }
}

class ParentPaymentsModel {
  const ParentPaymentsModel({
    required this.child,
    required this.summary,
    required this.history,
  });

  final ParentChildModel child;
  final ParentPaymentSummaryModel summary;
  final List<ParentPaymentHistoryModel> history;

  factory ParentPaymentsModel.fromJson(Map<String, dynamic> json) {
    return ParentPaymentsModel(
      child: ParentChildModel.fromJson(jsonMap(json['child'])),
      summary: ParentPaymentSummaryModel.fromJson(jsonMap(json['summary'])),
      history: jsonMapList(
        json['history'],
      ).map(ParentPaymentHistoryModel.fromJson).toList(),
    );
  }
}

class ParentSubjectProgressModel {
  const ParentSubjectProgressModel({
    required this.id,
    required this.subject,
    required this.teacherName,
    required this.percent,
    required this.status,
  });

  final int id;
  final String subject;
  final String teacherName;
  final int percent;
  final String status;

  factory ParentSubjectProgressModel.fromJson(Map<String, dynamic> json) {
    return ParentSubjectProgressModel(
      id: jsonInt(json['id']),
      subject: jsonString(json['subject']).isNotEmpty
          ? jsonString(json['subject'])
          : jsonString(json['label']),
      teacherName: jsonString(json['teacher_name']),
      percent: jsonInt(json['percent']),
      status: jsonString(json['status']),
    );
  }
}

class ParentTeacherCommentModel {
  const ParentTeacherCommentModel({
    required this.teacherName,
    required this.teacherRole,
    required this.comment,
    this.date,
  });

  final String teacherName;
  final String teacherRole;
  final String comment;
  final DateTime? date;

  factory ParentTeacherCommentModel.fromJson(Map<String, dynamic> json) {
    return ParentTeacherCommentModel(
      teacherName: jsonString(json['teacher_name']),
      teacherRole: jsonString(json['teacher_role']),
      comment: cleanHtmlText(json['comment']),
      date: jsonDate(json['date']),
    );
  }
}

class ParentProgressModel {
  const ParentProgressModel({
    required this.child,
    required this.overallPercent,
    required this.progressChart,
    required this.subjects,
    this.latestTeacherComment,
  });

  final ParentChildModel child;
  final int overallPercent;
  final List<ParentProgressSeries> progressChart;
  final List<ParentSubjectProgressModel> subjects;
  final ParentTeacherCommentModel? latestTeacherComment;

  factory ParentProgressModel.fromJson(Map<String, dynamic> json) {
    final commentPayload = jsonMap(json['latest_teacher_comment']);
    return ParentProgressModel(
      child: ParentChildModel.fromJson(jsonMap(json['child'])),
      overallPercent: jsonInt(json['overall_percent']),
      progressChart: jsonMapList(
        json['progress_chart'],
      ).map(ParentProgressSeries.fromJson).toList(),
      subjects: jsonMapList(
        json['subjects'],
      ).map(ParentSubjectProgressModel.fromJson).toList(),
      latestTeacherComment: commentPayload.isEmpty
          ? null
          : ParentTeacherCommentModel.fromJson(commentPayload),
    );
  }
}

class ParentProfileModel {
  const ParentProfileModel({required this.parent, required this.children});

  final UserModel parent;
  final List<ParentChildModel> children;

  factory ParentProfileModel.fromJson(Map<String, dynamic> json) {
    return ParentProfileModel(
      parent: UserModel.fromJson(jsonMap(json['parent'])),
      children: jsonMapList(
        json['children'],
      ).map(ParentChildModel.fromJson).toList(),
    );
  }
}

class ParentDashboardModel {
  const ParentDashboardModel({
    required this.parent,
    required this.children,
    required this.selectedChild,
    required this.stats,
    required this.progressChart,
    required this.latestNotifications,
    required this.unreadNotifications,
    this.center,
  });

  final UserModel parent;
  final CenterModel? center;
  final List<ParentChildModel> children;
  final ParentChildModel selectedChild;
  final ParentStatsModel stats;
  final List<ParentProgressSeries> progressChart;
  final List<ParentNotificationModel> latestNotifications;
  final int unreadNotifications;

  factory ParentDashboardModel.fromJson(Map<String, dynamic> json) {
    return ParentDashboardModel(
      parent: UserModel.fromJson(jsonMap(json['parent'])),
      center: json['center'] == null
          ? null
          : CenterModel.fromJson(jsonMap(json['center'])),
      children: jsonMapList(
        json['children'],
      ).map(ParentChildModel.fromJson).toList(),
      selectedChild: ParentChildModel.fromJson(jsonMap(json['selected_child'])),
      stats: ParentStatsModel.fromJson(jsonMap(json['stats'])),
      progressChart: jsonMapList(
        json['progress_chart'],
      ).map(ParentProgressSeries.fromJson).toList(),
      latestNotifications: jsonMapList(
        json['latest_notifications'],
      ).map(ParentNotificationModel.fromJson).toList(),
      unreadNotifications: jsonInt(json['unread_notifications']),
    );
  }
}
