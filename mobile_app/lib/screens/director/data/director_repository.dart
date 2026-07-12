// Director ma'lumot manbasi — real (mobil API) va mock implementatsiyalari.
import 'package:dio/dio.dart';
import 'package:image_picker/image_picker.dart';

import '../../../core/design/ds_components.dart' show DsStatus;
import '../../../models/app_models.dart';
import '../../../services/api_client.dart';
import 'director_data.dart';

/// Paginatsiyali o'quvchilar sahifasi.
typedef DirectorStudentsPage = ({List<DirectorDebtor> items, int page, bool hasNext});

abstract class DirectorRepository {
  /// Dashboard + Hisobot + qarzdorlar (bitta so'rovda).
  Future<DirectorData> loadOverview();

  /// O'quvchilar ro'yxati + qidiruv (paginatsiyali).
  Future<DirectorStudentsPage> loadStudents(String query, {int page});

  /// Bitta o'quvchi tafsiloti.
  Future<DirectorStudentDetail> loadStudentDetail(int id);

  /// Bildirishnomalar (paginatsiyali).
  Future<List<DirectorNotification>> loadNotifications({int page});

  /// Oy kesimi bo'yicha hisobot (month = "YYYY-MM", bo'sh = joriy oy).
  Future<DirectorReport> loadReport(String month);

  /// Markazdagi guruhlar (o'quvchini qo'shish uchun).
  Future<List<AvailableGroup>> loadGroups(String query);

  /// O'quvchini guruhga qo'shish.
  Future<void> addStudentToGroup(int studentId, int groupId, {int? price});

  /// O'quvchini guruhdan chiqarish.
  Future<void> removeStudentFromGroup(int studentId, int groupId);

  /// Guruh (enrollment) kurs narxini o'zgartirish.
  Future<void> setStudentPrice(int studentId, int enrollmentId, int price);

  /// To'lov qabul qilish (real). Yangi qarzни qaytaradi (bo'lsa).
  Future<int?> payStudent(int studentId, int enrollmentId, int amount, String method, {String month});

  /// Profil (ism/familya/telefon) yangilash.
  Future<UserModel> updateProfile({String? ism, String? familya, String? phone});

  /// Profil rasmini yuklash.
  Future<UserModel> uploadAvatar(XFile image);

  /// Profil rasmini o'chirish.
  Future<UserModel> removeAvatar();

  /// Parolni o'zgartirish.
  Future<void> changePassword({required String current, required String newPass, required String confirm});
}

const List<String> _uzMonths = [
  '', 'Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun',
  'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr',
];

/// "2026-07" → "Iyul".
String _monthLabel(String ym) {
  final parts = ym.split('-');
  if (parts.length >= 2) {
    final m = int.tryParse(parts[1]) ?? 0;
    if (m >= 1 && m <= 12) return _uzMonths[m];
  }
  return ym;
}

/// Haqiqiy backend: `/api/mobile/director/home/` (Bearer token).
class ApiDirectorRepository implements DirectorRepository {
  ApiDirectorRepository(this._api, {this.centerName = '', this.directorName = ''});

  final ApiClient _api;
  final String centerName;
  final String directorName;

  static const List<DsStatus> _tones = [DsStatus.info, DsStatus.success, DsStatus.warning, DsStatus.danger];

  @override
  Future<DirectorData> loadOverview() async {
    Map<String, dynamic> payload;
    try {
      payload = await _api.get('/api/mobile/director/home/');
    } catch (_) {
      // Yangi endpoint hali serverda bo'lmasligi mumkin (deploy qilinmagan) —
      // mavjud /api/mobile/home/ ga tushamiz (login baribir ishlaydi).
      payload = await _api.get('/api/mobile/home/');
    }

    // To'liq (boshqaruv) payload bo'lmasa — cheklangan summary'dan quramiz.
    if (payload['kpis'] == null && payload['summary'] != null) {
      return _fromSummary(payload);
    }

    final kpis = jsonMap(payload['kpis']);
    final changes = jsonMap(kpis['changes']);
    final charts = jsonMap(payload['charts']);

    final labels = (charts['monthly_labels'] as List?) ?? const [];
    final turnover = (charts['monthly_turnover'] as List?) ?? const [];
    final expensesM = (charts['monthly_expenses'] as List?) ?? const [];

    final trend = <DirectorChartPoint>[];
    final pairs = <DirectorMonthPair>[];
    for (var i = 0; i < labels.length && i < turnover.length; i++) {
      final inc = jsonDouble(turnover[i]) / 1000000;
      final exp = i < expensesM.length ? jsonDouble(expensesM[i]) / 1000000 : 0.0;
      trend.add(DirectorChartPoint(jsonString(labels[i]), inc));
      pairs.add(DirectorMonthPair(jsonString(labels[i]), inc, exp));
    }

    // Alohida to'lovlar ro'yxati (yangi endpoint). Bo'lmasa — recent_activity'ga tushamiz.
    final payments = <DirectorPayment>[];
    final rawPayments = jsonMapList(payload['payments']);
    if (rawPayments.isNotEmpty) {
      for (final item in rawPayments) {
        final method = jsonString(item['method']);
        final time = jsonString(item['time']);
        payments.add(DirectorPayment(
          name: jsonString(item['full_name']),
          subtitle: [
            item['group'] == null ? '' : jsonString(item['group']),
            method == 'naqd' ? 'Naqd' : (method == 'karta' ? 'Karta' : ''),
          ].where((e) => e.isNotEmpty).join(' · '),
          amount: jsonInt(item['amount']),
          time: time,
          tone: DsStatus.success,
        ));
      }
    } else {
      for (final item in jsonMapList(payload['recent_activity'])) {
        if (jsonString(item['type']) != 'payment') continue;
        final ts = jsonDate(item['timestamp']);
        payments.add(DirectorPayment(
          name: jsonString(item['title']).replaceAll(' to\'lov qildi', ''),
          subtitle: jsonString(item['subtitle']),
          amount: jsonInt(item['amount']),
          time: ts == null ? '' : _hhmm(ts),
          tone: DsStatus.success,
        ));
      }
    }

    final teacherSalaries = <(String, int)>[
      for (final item in jsonMapList(payload['teacher_salaries']))
        (jsonString(item['full_name']), jsonInt(item['amount'])),
    ];
    final expensesList = <(String, int)>[
      for (final item in jsonMapList(payload['expenses']))
        (jsonString(item['title']), jsonInt(item['amount'])),
    ];

    final debtors = <DirectorDebtor>[];
    var t = 0;
    for (final item in jsonMapList(payload['debtors'])) {
      final months = <DirectorDebtorMonth>[];
      for (final m in jsonMapList(item['months'])) {
        final debt = jsonInt(m['debt']);
        months.add(DirectorDebtorMonth(
          month: _monthLabel(jsonString(m['month'])),
          monthly: jsonInt(m['monthly'] ?? m['fee'] ?? debt),
          paid: jsonInt(m['paid']),
          debt: debt,
        ));
      }
      debtors.add(DirectorDebtor(
        id: jsonInt(item['id']),
        name: jsonString(item['full_name']),
        group: jsonString(item['group']),
        phone: jsonString(item['phone']),
        totalDebt: jsonInt(item['total_debt']),
        months: months,
        tone: _tones[t++ % _tones.length],
      ));
    }

    return DirectorData(
      centerName: centerName.isNotEmpty ? centerName : jsonString(payload['center_name']),
      directorName: directorName.isNotEmpty ? directorName : jsonString(payload['director_name']),
      periodRevenue: jsonInt(kpis['revenue']),
      revenueChange: jsonDouble(changes['revenue']),
      activeStudents: jsonInt(kpis['active_students'] ?? kpis['total_students']),
      studentsChange: jsonDouble(changes['active_students'] ?? changes['students']),
      avgAttendance: jsonInt(kpis['avg_attendance']),
      totalDebt: jsonInt(kpis['total_debt']),
      totalDebtors: jsonInt(kpis['total_debtors']),
      netProfit: jsonInt(kpis['net_profit']),
      expenses: jsonInt(kpis['expenses']),
      teacherSalary: jsonInt(kpis['teacher_salary_total']),
      revenueTrend: trend.length > 12 ? trend.sublist(trend.length - 12) : trend,
      incomeVsExpense: pairs.length > 6 ? pairs.sublist(pairs.length - 6) : pairs,
      recentPayments: payments.take(25).toList(),
      debtors: debtors,
      teacherSalaries: teacherSalaries,
      expensesList: expensesList,
      paymentMethods: [
        for (final m in (payload['payment_methods'] as List? ?? const [])) jsonString(m),
      ],
    );
  }

  @override
  Future<DirectorStudentsPage> loadStudents(String query, {int page = 1}) async {
    final params = <String, dynamic>{'page': '$page', 'per_page': '20'};
    if (query.trim().isNotEmpty) params['q'] = query.trim();
    final payload = await _api.get('/api/mobile/director/students/', queryParameters: params);
    final items = <DirectorDebtor>[];
    var t = (page - 1) * 20;
    for (final item in jsonMapList(payload['students'])) {
      final balance = jsonInt(item['balance']);
      items.add(DirectorDebtor(
        id: jsonInt(item['id']),
        name: jsonString(item['full_name']),
        group: jsonString(item['group']),
        phone: jsonString(item['phone']),
        totalDebt: balance < 0 ? -balance : 0,
        tone: _tones[t++ % _tones.length],
      ));
    }
    final pagination = jsonMap(payload['pagination']);
    return (items: items, page: page, hasNext: pagination['has_next'] == true);
  }

  @override
  Future<List<DirectorNotification>> loadNotifications({int page = 1}) async {
    final payload = await _api.get('/api/mobile/notifications/', queryParameters: {'page': '$page'});
    return [
      for (final item in jsonMapList(payload['items']))
        DirectorNotification(
          id: jsonInt(item['id']),
          title: jsonString(item['title']),
          message: jsonString(item['message']),
          isRead: item['is_read'] == true,
          createdAt: jsonString(item['created_at']),
          kind: jsonString(item['kind']),
        ),
    ];
  }

  @override
  Future<DirectorStudentDetail> loadStudentDetail(int id) async {
    final payload = await _api.get('/api/mobile/director/students/$id/');
    return DirectorStudentDetail(
      id: jsonInt(payload['id']),
      name: jsonString(payload['full_name']),
      group: jsonString(payload['group']),
      phone: jsonString(payload['phone']),
      totalDebt: jsonInt(payload['total_debt']),
      groups: [
        for (final e in jsonMapList(payload['enrollments']))
          StudentGroup(
            enrollmentId: jsonInt(e['enrollment_id']),
            groupId: jsonInt(e['group_id']),
            group: jsonString(e['group']),
            monthlyPrice: jsonInt(e['monthly_price']),
            teacherPercent: jsonInt(e['teacher_percent']),
          ),
      ],
      payments: [
        for (final p in jsonMapList(payload['payments']))
          DirectorPayment(
            name: '',
            subtitle: jsonString(p['method']) == 'naqd' ? 'Naqd' : 'Karta',
            amount: jsonInt(p['amount']),
            time: jsonString(p['date']),
            tone: DsStatus.success,
          ),
      ],
    );
  }

  /// `/api/mobile/home/` cheklangan javobidan (revenue/qarz/grafik yo'q).
  DirectorData _fromSummary(Map<String, dynamic> payload) {
    final summary = jsonMap(payload['summary']);
    final center = jsonMap(payload['center']);
    return DirectorData(
      centerName: centerName.isNotEmpty ? centerName : jsonString(center['name']),
      directorName: directorName,
      periodRevenue: jsonInt(summary['today_payments']),
      revenueChange: 0,
      activeStudents: jsonInt(summary['active_students']),
      studentsChange: 0,
      avgAttendance: 0,
      totalDebt: 0,
      totalDebtors: 0,
      netProfit: 0,
      expenses: 0,
      teacherSalary: 0,
      revenueTrend: const [],
      incomeVsExpense: const [],
      recentPayments: const [],
      debtors: const [],
    );
  }

  @override
  Future<DirectorReport> loadReport(String month) async {
    final payload = await _api.get(
      '/api/mobile/director/report/',
      queryParameters: month.trim().isEmpty ? null : {'month': month.trim()},
    );
    return DirectorReport(
      month: jsonString(payload['month']),
      monthLabel: jsonString(payload['month_label']),
      revenue: jsonInt(payload['revenue']),
      netProfit: jsonInt(payload['net_profit']),
      expenses: jsonInt(payload['expenses']),
      teacherSalary: jsonInt(payload['teacher_salary']),
      teacherSalaries: [
        for (final e in jsonMapList(payload['teacher_salaries'])) (jsonString(e['full_name']), jsonInt(e['amount'])),
      ],
      expensesList: [
        for (final e in jsonMapList(payload['expenses_list'])) (jsonString(e['title']), jsonInt(e['amount'])),
      ],
      incomeVsExpense: [
        for (final p in jsonMapList(payload['income_vs_expense']))
          DirectorMonthPair(jsonString(p['label']), jsonDouble(p['income']) / 1000000, jsonDouble(p['expense']) / 1000000),
      ],
      payments: [
        for (final p in jsonMapList(payload['payments']))
          DirectorPayment(
            name: jsonString(p['full_name']),
            subtitle: [
              jsonString(p['group']),
              jsonString(p['method']) == 'naqd' ? 'Naqd' : 'Karta',
            ].where((e) => e.isNotEmpty).join(' · '),
            amount: jsonInt(p['amount']),
            time: jsonString(p['time']),
            tone: DsStatus.success,
          ),
      ],
    );
  }

  @override
  Future<List<AvailableGroup>> loadGroups(String query) async {
    final payload = await _api.get(
      '/api/mobile/director/groups/',
      queryParameters: query.trim().isEmpty ? null : {'q': query.trim()},
    );
    return [
      for (final g in jsonMapList(payload['groups']))
        AvailableGroup(
          id: jsonInt(g['id']),
          name: jsonString(g['name']),
          price: jsonInt(g['price']),
          teacherPercent: jsonInt(g['teacher_percent']),
        ),
    ];
  }

  @override
  Future<void> addStudentToGroup(int studentId, int groupId, {int? price}) async {
    await _api.post(
      '/api/mobile/director/students/$studentId/add-group/',
      data: {'group_id': groupId, if (price != null) 'price': price},
    );
  }

  @override
  Future<void> removeStudentFromGroup(int studentId, int groupId) async {
    await _api.post(
      '/api/mobile/director/students/$studentId/remove-group/',
      data: {'group_id': groupId},
    );
  }

  @override
  Future<void> setStudentPrice(int studentId, int enrollmentId, int price) async {
    await _api.post(
      '/api/mobile/director/students/$studentId/set-price/',
      data: {'enrollment_id': enrollmentId, 'price': price},
    );
  }

  @override
  Future<int?> payStudent(int studentId, int enrollmentId, int amount, String method, {String month = ''}) async {
    final payload = await _api.post(
      '/api/mobile/director/students/$studentId/pay/',
      data: {
        'enrollment_id': enrollmentId,
        'amount': amount,
        'method': method,
        if (month.isNotEmpty) 'month': month,
      },
    );
    final debt = payload['total_debt'];
    return debt == null ? null : jsonInt(debt);
  }

  @override
  Future<UserModel> updateProfile({String? ism, String? familya, String? phone}) async {
    final data = await _api.patch(
      '/api/mobile/profile/',
      data: {
        if (ism != null) 'ism': ism,
        if (familya != null) 'familya': familya,
        if (phone != null) 'phone': phone,
      },
    );
    return UserModel.fromJson(jsonMap(data['user']));
  }

  @override
  Future<UserModel> uploadAvatar(XFile image) async {
    final data = await _api.post(
      '/api/mobile/profile/avatar/',
      data: FormData.fromMap(<String, dynamic>{
        'avatar': await MultipartFile.fromFile(image.path, filename: image.name),
      }),
    );
    return UserModel.fromJson(jsonMap(data['user']));
  }

  @override
  Future<UserModel> removeAvatar() async {
    final data = await _api.post(
      '/api/mobile/profile/avatar/',
      data: FormData.fromMap(<String, dynamic>{'clear': 'true'}),
    );
    return UserModel.fromJson(jsonMap(data['user']));
  }

  @override
  Future<void> changePassword({required String current, required String newPass, required String confirm}) async {
    await _api.post(
      '/api/mobile/auth/change-password/',
      data: {'current_password': current, 'new_password': newPass, 'confirm_password': confirm},
    );
  }

  static String _hhmm(DateTime dt) {
    final l = dt.toLocal();
    return '${l.hour.toString().padLeft(2, '0')}:${l.minute.toString().padLeft(2, '0')}';
  }
}
