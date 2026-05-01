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
    required this.debtStatus,
    required this.averageScore,
    required this.currentLevel,
    required this.maxLevel,
    required this.monthlyChange,
    this.nextPaymentDate,
  });

  final int attendancePercent;
  final int debtAmount;
  final String debtStatus;
  final int averageScore;
  final double currentLevel;
  final double maxLevel;
  final double monthlyChange;
  final DateTime? nextPaymentDate;

  factory ParentStatsModel.fromJson(Map<String, dynamic> json) {
    return ParentStatsModel(
      attendancePercent: jsonInt(json['attendance_percent']),
      debtAmount: jsonInt(json['debt_amount']),
      debtStatus: jsonString(json['debt_status']),
      averageScore: jsonInt(json['average_score']),
      currentLevel: jsonDouble(json['current_level']),
      maxLevel: jsonDouble(json['max_level'] ?? 5),
      monthlyChange: jsonDouble(json['monthly_change']),
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
    this.groups = const <ParentAttendanceGroupOption>[],
  });

  final ParentChildModel child;
  final ParentAttendanceSummaryModel summary;
  final List<ParentAttendanceItemModel> items;
  final List<ParentAttendanceGroupOption> groups;

  factory ParentAttendanceModel.fromJson(Map<String, dynamic> json) {
    // Backend top-level "attendance" block doesn't have all summary fields;
    // we merge the per-month attendance fields into the summary if present.
    final summaryMap = Map<String, dynamic>.from(jsonMap(json['summary']));
    final attendanceMap = jsonMap(json['attendance']);
    if (attendanceMap.isNotEmpty) {
      summaryMap.addAll(attendanceMap);
    }
    return ParentAttendanceModel(
      child: ParentChildModel.fromJson(jsonMap(json['child'])),
      summary: ParentAttendanceSummaryModel.fromJson(summaryMap),
      items: jsonMapList(
        json['items'],
      ).map(ParentAttendanceItemModel.fromJson).toList(),
      groups: jsonMapList(json['groups'])
          .map(ParentAttendanceGroupOption.fromJson)
          .toList(),
    );
  }
}

class ParentAttendanceGroupOption {
  const ParentAttendanceGroupOption({required this.id, required this.name});

  final int id;
  final String name;

  factory ParentAttendanceGroupOption.fromJson(Map<String, dynamic> json) {
    return ParentAttendanceGroupOption(
      id: jsonInt(json['id']),
      name: jsonString(json['name']),
    );
  }
}

class ParentAttendanceSummaryModel {
  const ParentAttendanceSummaryModel({
    required this.totalLessons,
    required this.presentLessons,
    required this.attendanceRate,
    required this.recentAttendanceRate,
    required this.attendedLessons,
    required this.missedLessons,
    required this.attendancePercent,
    required this.month,
  });

  final int totalLessons;
  final int presentLessons;
  final double attendanceRate;
  final double recentAttendanceRate;
  final int attendedLessons;
  final int missedLessons;
  final int attendancePercent;
  final String month;

  factory ParentAttendanceSummaryModel.fromJson(Map<String, dynamic> json) {
    final attendedRaw = json['attended_lessons'] ?? json['present_lessons'];
    final percentRaw = json['attendance_percent'] ?? json['attendance_rate'];
    return ParentAttendanceSummaryModel(
      totalLessons: jsonInt(json['total_lessons']),
      presentLessons: jsonInt(json['present_lessons'] ?? json['attended_lessons']),
      attendanceRate: jsonDouble(json['attendance_rate']),
      recentAttendanceRate: jsonDouble(json['recent_attendance_rate']),
      attendedLessons: jsonInt(attendedRaw),
      missedLessons: jsonInt(json['missed_lessons']),
      attendancePercent: jsonInt(percentRaw),
      month: jsonString(json['month']),
    );
  }
}

class ParentPaymentSummaryModel {
  const ParentPaymentSummaryModel({
    required this.totalPlan,
    required this.totalBalance,
    required this.paidTotal,
    required this.debtAmount,
    this.pendingAmount = 0,
    this.nextPaymentDate,
  });

  final int totalPlan;
  final int totalBalance;
  final int paidTotal;
  final int debtAmount;
  final int pendingAmount;
  final DateTime? nextPaymentDate;

  int get payableTotal =>
      totalPlan > 0
          ? totalPlan
          : (totalBalance > 0 ? totalBalance : paidTotal + debtAmount + pendingAmount);
  int get remaining => debtAmount;
  int get outstandingTotal => debtAmount + pendingAmount;
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
      pendingAmount: jsonInt(json['pending_amount']),
      nextPaymentDate: jsonDate(json['next_payment_date']),
    );
  }
}

class ParentPaymentPlanItemModel {
  const ParentPaymentPlanItemModel({
    required this.id,
    required this.title,
    required this.groupName,
    required this.monthLabel,
    required this.plannedAmount,
    required this.paidAmount,
    required this.remainingAmount,
    required this.status,
    required this.statusLabel,
    this.month,
    this.dueDate,
  });

  final int id;
  final String title;
  final String groupName;
  final String monthLabel;
  final int plannedAmount;
  final int paidAmount;
  final int remainingAmount;
  final String status;
  final String statusLabel;
  final DateTime? month;
  final DateTime? dueDate;

  factory ParentPaymentPlanItemModel.fromJson(Map<String, dynamic> json) {
    return ParentPaymentPlanItemModel(
      id: jsonInt(json['id']),
      title: jsonString(json['title']),
      groupName: jsonString(json['group_name']),
      monthLabel: jsonString(json['month_label']),
      plannedAmount: jsonInt(json['planned_amount']),
      paidAmount: jsonInt(json['paid_amount']),
      remainingAmount: jsonInt(json['remaining_amount']),
      status: jsonString(json['status']),
      statusLabel: jsonString(json['status_label']),
      month: jsonDate(json['month']),
      dueDate: jsonDate(json['due_date']),
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
    required this.planItems,
    required this.history,
    this.paymentGatewayAvailable = false,
    this.centerContactName = '',
    this.centerContactPhone = '',
  });

  final ParentChildModel child;
  final ParentPaymentSummaryModel summary;
  final List<ParentPaymentPlanItemModel> planItems;
  final List<ParentPaymentHistoryModel> history;
  final bool paymentGatewayAvailable;
  final String centerContactName;
  final String centerContactPhone;

  factory ParentPaymentsModel.fromJson(Map<String, dynamic> json) {
    final centerContact = jsonMap(json['center_contact']);
    return ParentPaymentsModel(
      child: ParentChildModel.fromJson(jsonMap(json['child'])),
      summary: ParentPaymentSummaryModel.fromJson(jsonMap(json['summary'])),
      planItems: jsonMapList(
        json['plan_items'],
      ).map(ParentPaymentPlanItemModel.fromJson).toList(),
      history: jsonMapList(
        json['history'],
      ).map(ParentPaymentHistoryModel.fromJson).toList(),
      paymentGatewayAvailable: jsonBool(json['payment_gateway_available']),
      centerContactName: jsonString(centerContact['name']),
      centerContactPhone: jsonString(centerContact['phone']),
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
    this.examPercent = 0,
    this.attendancePercent = 0,
  });

  final int id;
  final String subject;
  final String teacherName;
  final int percent;
  final String status;
  final int examPercent;
  final int attendancePercent;

  factory ParentSubjectProgressModel.fromJson(Map<String, dynamic> json) {
    return ParentSubjectProgressModel(
      id: jsonInt(json['id']),
      subject: jsonString(json['subject']).isNotEmpty
          ? jsonString(json['subject'])
          : jsonString(json['label']),
      teacherName: jsonString(json['teacher_name']),
      percent: jsonInt(json['percent']),
      status: jsonString(json['status']),
      examPercent: jsonInt(json['exam_percent']),
      attendancePercent: jsonInt(json['attendance_percent']),
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
    required this.selectedPeriod,
    required this.selectedPeriodLabel,
    required this.availablePeriods,
    required this.attendancePercent,
    required this.subjectAveragePercent,
    required this.progressChart,
    required this.progressTimeline,
    required this.subjects,
    required this.teacherComments,
    required this.currentLevel,
    required this.maxLevel,
    required this.levelLabel,
    required this.trend,
    required this.monthlyChange,
    required this.breakdown,
    required this.hasBreakdownData,
    required this.hasMinimumData,
    required this.attendanceRate,
    required this.homeworkRate,
    required this.activityScore,
    required this.activeDays,
    required this.totalChaqmoq,
    required this.monthlyAttendance,
    this.latestTeacherComment,
  });

  final ParentChildModel child;
  final int overallPercent;
  final String selectedPeriod;
  final String selectedPeriodLabel;
  final List<ParentProgressPeriodModel> availablePeriods;
  final int attendancePercent;
  final int subjectAveragePercent;
  final List<ParentProgressSeries> progressChart;
  final ProgressTimelineModel progressTimeline;
  final List<ParentSubjectProgressModel> subjects;
  final List<ParentTeacherCommentModel> teacherComments;
  final ParentTeacherCommentModel? latestTeacherComment;
  final double currentLevel;
  final double maxLevel;
  final String levelLabel;
  final String trend;
  final double monthlyChange;
  final List<ProgressBreakdownItem> breakdown;
  final bool hasBreakdownData;
  final bool hasMinimumData;
  final double attendanceRate;
  final double homeworkRate;
  final double activityScore;
  final int activeDays;
  final int totalChaqmoq;
  final ParentAttendanceSummaryModel monthlyAttendance;

  factory ParentProgressModel.fromJson(Map<String, dynamic> json) {
    final commentPayload = jsonMap(json['latest_teacher_comment']);
    return ParentProgressModel(
      child: ParentChildModel.fromJson(jsonMap(json['child'])),
      overallPercent: jsonInt(json['overall_percent']),
      selectedPeriod: jsonString(json['selected_period']),
      selectedPeriodLabel: jsonString(json['selected_period_label']),
      availablePeriods: jsonMapList(
        json['available_periods'],
      ).map(ParentProgressPeriodModel.fromJson).toList(),
      attendancePercent: jsonInt(json['attendance_percent']),
      subjectAveragePercent: jsonInt(json['subject_average_percent']),
      progressChart: jsonMapList(
        json['progress_chart'],
      ).map(ParentProgressSeries.fromJson).toList(),
      progressTimeline:
          ProgressTimelineModel.fromJson(jsonMap(json['progress_timeline'])),
      subjects: jsonMapList(
        json['subjects'],
      ).map(ParentSubjectProgressModel.fromJson).toList(),
      teacherComments: jsonMapList(
        json['teacher_comments'],
      ).map(ParentTeacherCommentModel.fromJson).toList(),
      latestTeacherComment: commentPayload.isEmpty
          ? null
          : ParentTeacherCommentModel.fromJson(commentPayload),
      currentLevel: jsonDouble(json['current_level']),
      maxLevel: jsonDouble(json['max_level'] ?? 5),
      levelLabel: jsonString(json['label']),
      trend: jsonString(json['trend']),
      monthlyChange: jsonDouble(json['monthly_change']),
      breakdown: jsonMapList(
        json['breakdown'],
      ).map(ProgressBreakdownItem.fromJson).toList(),
      hasBreakdownData: jsonBool(json['has_breakdown_data']),
      hasMinimumData: jsonBool(json['has_min_data']),
      attendanceRate: jsonDouble(json['attendance_rate']),
      homeworkRate: jsonDouble(json['homework_rate']),
      activityScore: jsonDouble(json['activity_score']),
      activeDays: jsonInt(json['active_days']),
      totalChaqmoq: jsonInt(json['total_chaqmoq']),
      monthlyAttendance: ParentAttendanceSummaryModel.fromJson(
        jsonMap(json['attendance']),
      ),
    );
  }
}

class ProgressBreakdownItem {
  const ProgressBreakdownItem({
    required this.label,
    required this.title,
    required this.value,
    required this.score,
    required this.maxScore,
  });

  final String label;
  final String title;
  final String value;
  final double score;
  final double maxScore;

  bool get hasValue {
    final v = value.trim();
    if (v.isEmpty) return false;
    if (v.startsWith('Ma’lumot')) return false; // "Ma'lumot yetarli emas"
    return true;
  }

  factory ProgressBreakdownItem.fromJson(Map<String, dynamic> json) {
    final rawTitle = jsonString(json['title']);
    final rawLabel = jsonString(json['label']);
    return ProgressBreakdownItem(
      label: rawLabel.isNotEmpty ? rawLabel : rawTitle,
      title: rawTitle.isNotEmpty ? rawTitle : rawLabel,
      value: jsonString(json['value']),
      score: jsonDouble(json['score']),
      maxScore: jsonDouble(json['max_score']),
    );
  }
}

class ProgressTimelineModel {
  const ProgressTimelineModel({
    required this.period,
    required this.startDate,
    required this.endDate,
    required this.totalScore,
    required this.points,
  });

  final String period;
  final String startDate;
  final String endDate;
  final int totalScore;
  final List<ProgressTimelinePoint> points;

  bool get isEmpty => points.every((point) => point.score == 0);

  factory ProgressTimelineModel.fromJson(Map<String, dynamic> json) {
    return ProgressTimelineModel(
      period: jsonString(json['period']),
      startDate: jsonString(json['start_date']),
      endDate: jsonString(json['end_date']),
      totalScore: jsonInt(json['total_score']),
      points: jsonMapList(
        json['timeline'],
      ).map(ProgressTimelinePoint.fromJson).toList(),
    );
  }
}

class ProgressReasonEntry {
  const ProgressReasonEntry({
    required this.text,
    required this.score,
    required this.type,
    this.createdAt = '',
    this.group = '',
    this.teacher = '',
    this.awardedBy = '',
    this.reason = '',
    this.source = '',
  });

  final String text;
  final int score;
  final String type;
  final String createdAt;
  final String group;
  final String teacher;
  final String awardedBy;
  final String reason;
  final String source;

  DateTime? get parsedCreatedAt =>
      createdAt.isEmpty ? null : DateTime.tryParse(createdAt);

  factory ProgressReasonEntry.fromJson(Map<String, dynamic> json) {
    return ProgressReasonEntry(
      text: jsonString(json['text']),
      score: jsonInt(json['score']),
      type: jsonString(json['type']),
      createdAt: jsonString(json['created_at']),
      group: jsonString(json['group']),
      teacher: jsonString(json['teacher']),
      awardedBy: jsonString(json['awarded_by']),
      reason: jsonString(json['reason']),
      source: jsonString(json['source']),
    );
  }
}

class ProgressTimelinePoint {
  const ProgressTimelinePoint({
    required this.date,
    required this.score,
    required this.reasons,
    required this.entries,
  });

  final String date;
  final int score;
  final List<String> reasons;
  final List<ProgressReasonEntry> entries;

  DateTime? get parsedDate => DateTime.tryParse(date);

  factory ProgressTimelinePoint.fromJson(Map<String, dynamic> json) {
    final rawReasons = json['reasons'];
    final reasons = <String>[];
    if (rawReasons is List) {
      for (final item in rawReasons) {
        final value = item?.toString().trim() ?? '';
        if (value.isNotEmpty) {
          reasons.add(value);
        }
      }
    }
    final rawEntries = json['entries'];
    final entries = <ProgressReasonEntry>[];
    if (rawEntries is List) {
      for (final item in rawEntries) {
        if (item is Map) {
          entries.add(ProgressReasonEntry.fromJson(
            Map<String, dynamic>.from(item),
          ));
        }
      }
    }
    // Eski API javobi (faqat string sabablar) bilan moslik uchun fallback.
    if (entries.isEmpty && reasons.isNotEmpty) {
      for (final r in reasons) {
        entries.add(ProgressReasonEntry(text: r, score: 0, type: 'other'));
      }
    }
    return ProgressTimelinePoint(
      date: jsonString(json['date']),
      score: jsonInt(json['score']),
      reasons: reasons,
      entries: entries,
    );
  }
}

class ParentProgressPeriodModel {
  const ParentProgressPeriodModel({
    required this.key,
    required this.label,
  });

  final String key;
  final String label;

  factory ParentProgressPeriodModel.fromJson(Map<String, dynamic> json) {
    return ParentProgressPeriodModel(
      key: jsonString(json['key']),
      label: jsonString(json['label']),
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

class ParentReminderSettingsModel {
  const ParentReminderSettingsModel({
    required this.childId,
    required this.centerSlug,
    required this.label,
    required this.scheduledAt,
    this.notificationId,
    this.note = '',
  });

  final int childId;
  final String centerSlug;
  final String label;
  final DateTime scheduledAt;
  final int? notificationId;
  final String note;

  factory ParentReminderSettingsModel.fromJson(Map<String, dynamic> json) {
    return ParentReminderSettingsModel(
      childId: jsonInt(json['child_id']),
      centerSlug: jsonString(json['center_slug']),
      label: jsonString(json['label']),
      scheduledAt: jsonDate(json['scheduled_at']) ?? DateTime.now(),
      notificationId: json['notification_id'] == null
          ? null
          : jsonInt(json['notification_id']),
      note: jsonString(json['note']),
    );
  }

  Map<String, dynamic> toJson() => <String, dynamic>{
    'child_id': childId,
    'center_slug': centerSlug,
    'label': label,
    'scheduled_at': scheduledAt.toIso8601String(),
    'notification_id': notificationId,
    'note': note,
  };

  bool matchesChild({
    required int currentChildId,
    required String currentCenterSlug,
  }) {
    return childId == currentChildId &&
        centerSlug.trim().toLowerCase() ==
            currentCenterSlug.trim().toLowerCase();
  }
}

class ParentChaqmoqMonth {
  const ParentChaqmoqMonth({
    required this.year,
    required this.month,
    required this.earned,
    required this.lost,
    required this.net,
  });

  final int year;
  final int month;
  final int earned;
  final int lost;
  final int net;

  factory ParentChaqmoqMonth.fromJson(Map<String, dynamic> json) {
    return ParentChaqmoqMonth(
      year: jsonInt(json['year']),
      month: jsonInt(json['month']),
      earned: jsonInt(json['earned']),
      lost: jsonInt(json['lost']),
      net: jsonInt(json['net']),
    );
  }
}

class ParentChaqmoqStatsModel {
  const ParentChaqmoqStatsModel({
    required this.balance,
    required this.thisMonthEarned,
    required this.thisMonthLost,
    required this.thisMonthNet,
    required this.monthly,
  });

  final int balance;
  final int thisMonthEarned;
  final int thisMonthLost;
  final int thisMonthNet;
  final List<ParentChaqmoqMonth> monthly;

  static const ParentChaqmoqStatsModel empty = ParentChaqmoqStatsModel(
    balance: 0,
    thisMonthEarned: 0,
    thisMonthLost: 0,
    thisMonthNet: 0,
    monthly: <ParentChaqmoqMonth>[],
  );

  factory ParentChaqmoqStatsModel.fromJson(Map<String, dynamic> json) {
    return ParentChaqmoqStatsModel(
      balance: jsonInt(json['balance']),
      thisMonthEarned: jsonInt(json['this_month_earned']),
      thisMonthLost: jsonInt(json['this_month_lost']),
      thisMonthNet: jsonInt(json['this_month_net']),
      monthly: jsonMapList(
        json['monthly'],
      ).map(ParentChaqmoqMonth.fromJson).toList(),
    );
  }
}

class ParentDashboardModel {
  const ParentDashboardModel({
    required this.parent,
    required this.children,
    required this.selectedChild,
    required this.stats,
    required this.chaqmoq,
    required this.progressChart,
    required this.progressTimeline,
    required this.latestNotifications,
    required this.unreadNotifications,
    this.center,
  });

  final UserModel parent;
  final CenterModel? center;
  final List<ParentChildModel> children;
  final ParentChildModel selectedChild;
  final ParentStatsModel stats;
  final ParentChaqmoqStatsModel chaqmoq;
  final List<ParentProgressSeries> progressChart;
  final ProgressTimelineModel progressTimeline;
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
      chaqmoq: json['chaqmoq'] is Map
          ? ParentChaqmoqStatsModel.fromJson(jsonMap(json['chaqmoq']))
          : ParentChaqmoqStatsModel.empty,
      progressChart: jsonMapList(
        json['progress_chart'],
      ).map(ParentProgressSeries.fromJson).toList(),
      progressTimeline: ProgressTimelineModel.fromJson(
        jsonMap(json['progress_timeline']),
      ),
      latestNotifications: jsonMapList(
        json['latest_notifications'],
      ).map(ParentNotificationModel.fromJson).toList(),
      unreadNotifications: jsonInt(json['unread_notifications']),
    );
  }
}
