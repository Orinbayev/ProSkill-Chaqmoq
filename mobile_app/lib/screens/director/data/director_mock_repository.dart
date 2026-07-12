// Dizayn preview uchun mock repository (backendsiz).
import 'package:image_picker/image_picker.dart';

import '../../../core/design/ds_components.dart' show DsStatus;
import '../../../models/app_models.dart';
import '../director_mock.dart';
import 'director_data.dart';
import 'director_repository.dart';

class MockDirectorRepository implements DirectorRepository {
  const MockDirectorRepository();

  @override
  Future<DirectorData> loadOverview() async {
    await Future<void>.delayed(const Duration(milliseconds: 400)); // yuklanish holatini ko'rsatish uchun
    return DirectorData(
      centerName: DirectorMock.profile.centerName,
      directorName: DirectorMock.profile.fullName,
      periodRevenue: DirectorMock.monthIncome,
      revenueChange: 12,
      activeStudents: DirectorMock.activeStudents,
      studentsChange: 0,
      avgAttendance: 91,
      totalDebt: DirectorMock.totalDebt,
      totalDebtors: DirectorMock.debtorsCount,
      netProfit: DirectorMock.reportNetProfit,
      expenses: DirectorMock.reportExpense,
      teacherSalary: DirectorMock.expenseBreakdown.first.$2,
      revenueTrend: [
        for (var i = 0; i < DirectorMock.revenue12.length; i++)
          DirectorChartPoint(DirectorMock.revenueMonths[i], DirectorMock.revenue12[i]),
      ],
      incomeVsExpense: [
        for (var i = 0; i < DirectorMock.incomeVsExpense.length; i++)
          DirectorMonthPair(
            DirectorMock.report6Months[i],
            DirectorMock.incomeVsExpense[i].$1,
            DirectorMock.incomeVsExpense[i].$2,
          ),
      ],
      recentPayments: [
        for (final p in DirectorMock.todayPayments)
          DirectorPayment(
            name: p.name,
            subtitle: '${p.method == 'naqd' ? 'Naqd' : 'Karta'} · ${p.time}',
            amount: p.amount,
            time: p.time,
            tone: p.tone,
          ),
      ],
      debtors: [
        for (final d in DirectorMock.debtors)
          DirectorDebtor(
            id: DirectorMock.debtors.indexOf(d),
            name: d.name,
            group: d.group,
            phone: d.phone,
            totalDebt: d.totalDebt,
            tone: d.tone,
            months: [
              for (final m in d.months)
                DirectorDebtorMonth(month: m.month, monthly: m.monthly, paid: m.paid, debt: m.debt),
            ],
          ),
      ],
      teacherSalaries: const [
        ('Aziz Tursunov', 6200000),
        ('Kamola Sattorova', 5600000),
      ],
      expensesList: const [
        ('Ijara — iyul', 3600000),
        ('Kommunal to\'lovlar', 1400000),
        ('Reklama', 1400000),
      ],
      paymentMethods: const ['NAQD', 'KARTA', 'CLICK', 'PAYME'],
    );
  }

  @override
  Future<DirectorStudentsPage> loadStudents(String query, {int page = 1}) async {
    await Future<void>.delayed(const Duration(milliseconds: 250));
    final all = [
      for (final d in DirectorMock.debtors)
        DirectorDebtor(id: DirectorMock.debtors.indexOf(d), name: d.name, group: d.group, phone: d.phone, totalDebt: d.totalDebt, tone: d.tone),
      for (final s in DirectorMock.students.where((s) => s.totalDebt == 0))
        DirectorDebtor(id: 100 + DirectorMock.students.indexOf(s), name: s.name, group: s.group, phone: s.phone, totalDebt: 0, tone: s.tone),
    ];
    final q = query.trim().toLowerCase();
    final filtered = q.isEmpty
        ? all
        : all.where((s) => s.name.toLowerCase().contains(q) || s.group.toLowerCase().contains(q)).toList();
    return (items: filtered, page: page, hasNext: false);
  }

  @override
  Future<DirectorReport> loadReport(String month) async {
    await Future<void>.delayed(const Duration(milliseconds: 300));
    final label = month.isEmpty ? 'Joriy oy' : month;
    return DirectorReport(
      month: month,
      monthLabel: label,
      revenue: DirectorMock.reportIncome,
      netProfit: DirectorMock.reportNetProfit,
      expenses: DirectorMock.reportExpense,
      teacherSalary: DirectorMock.expenseBreakdown.first.$2,
      teacherSalaries: const [('Aziz Tursunov', 6200000), ('Kamola Sattorova', 5600000)],
      expensesList: const [('Ijara', 3600000), ('Kommunal', 1400000), ('Reklama', 1400000)],
      incomeVsExpense: [
        for (var i = 0; i < DirectorMock.incomeVsExpense.length; i++)
          DirectorMonthPair(DirectorMock.report6Months[i], DirectorMock.incomeVsExpense[i].$1, DirectorMock.incomeVsExpense[i].$2),
      ],
      payments: [
        for (final p in DirectorMock.todayPayments)
          DirectorPayment(name: p.name, subtitle: '${p.method == 'naqd' ? 'Naqd' : 'Karta'}', amount: p.amount, time: p.time, tone: p.tone),
      ],
    );
  }

  @override
  Future<List<AvailableGroup>> loadGroups(String query) async {
    await Future<void>.delayed(const Duration(milliseconds: 200));
    const all = [
      AvailableGroup(id: 1, name: 'IELTS G-1', price: 450000, teacherPercent: 40),
      AvailableGroup(id: 2, name: 'SPEAKING CLUB', price: 300000, teacherPercent: 45),
      AvailableGroup(id: 3, name: 'BEGINNER 1', price: 350000, teacherPercent: 40),
      AvailableGroup(id: 4, name: 'FRONTEND N-2', price: 600000, teacherPercent: 50),
    ];
    if (query.trim().isEmpty) return all;
    final q = query.trim().toLowerCase();
    return all.where((g) => g.name.toLowerCase().contains(q)).toList();
  }

  @override
  Future<void> addStudentToGroup(int studentId, int groupId, {int? price}) async {
    await Future<void>.delayed(const Duration(milliseconds: 200));
  }

  @override
  Future<void> removeStudentFromGroup(int studentId, int groupId) async {
    await Future<void>.delayed(const Duration(milliseconds: 200));
  }

  @override
  Future<void> setStudentPrice(int studentId, int enrollmentId, int price) async {
    await Future<void>.delayed(const Duration(milliseconds: 200));
  }

  @override
  Future<int?> payStudent(int studentId, int enrollmentId, int amount, String method, {String month = ''}) async {
    await Future<void>.delayed(const Duration(milliseconds: 250));
    return null;
  }

  static const _mockUser = UserModel(id: 0, fullName: 'Dilnoza Karimova', role: 'director', center: null);

  @override
  Future<UserModel> updateProfile({String? ism, String? familya, String? phone}) async {
    await Future<void>.delayed(const Duration(milliseconds: 200));
    return _mockUser;
  }

  @override
  Future<UserModel> uploadAvatar(XFile image) async {
    await Future<void>.delayed(const Duration(milliseconds: 200));
    return _mockUser;
  }

  @override
  Future<UserModel> removeAvatar() async {
    await Future<void>.delayed(const Duration(milliseconds: 200));
    return _mockUser;
  }

  @override
  Future<void> changePassword({required String current, required String newPass, required String confirm}) async {
    await Future<void>.delayed(const Duration(milliseconds: 200));
  }

  @override
  Future<List<DirectorNotification>> loadNotifications({int page = 1}) async {
    await Future<void>.delayed(const Duration(milliseconds: 200));
    if (page > 1) return const [];
    return const [
      DirectorNotification(id: 1, title: 'Yangi to\'lov', message: 'Madina Yusupova 450 000 so\'m to\'lov qildi.', isRead: false, createdAt: '2026-07-10T12:40:00'),
      DirectorNotification(id: 2, title: 'Qarzdorlik ogohlantirishi', message: 'Shohida Egamberdiyeva 2 oydan beri qarzdor.', isRead: false, createdAt: '2026-07-10T09:15:00'),
      DirectorNotification(id: 3, title: 'Yangi o\'quvchi', message: 'IELTS G-1 guruhiga yangi o\'quvchi qo\'shildi.', isRead: true, createdAt: '2026-07-09T18:00:00'),
    ];
  }

  @override
  Future<DirectorStudentDetail> loadStudentDetail(int id) async {
    await Future<void>.delayed(const Duration(milliseconds: 200));
    final d = DirectorMock.debtors.first;
    return DirectorStudentDetail(
      id: id,
      name: d.name,
      group: d.group,
      phone: d.phone,
      totalDebt: d.totalDebt,
      groups: [
        StudentGroup(enrollmentId: 1, groupId: 1, group: d.group, monthlyPrice: 450000, teacherPercent: 40),
        const StudentGroup(enrollmentId: 2, groupId: 2, group: 'SPEAKING CLUB', monthlyPrice: 300000, teacherPercent: 45),
      ],
      payments: const [
        DirectorPayment(name: '', subtitle: 'Naqd', amount: 450000, time: '2026-05-02', tone: DsStatus.success),
      ],
    );
  }
}
