// Director roli uchun namuna (mock) ma'lumotlar.
// Backend ulanmagan — barcha qiymatlar dizayn hujjatidan olingan namunalar.
import '../../core/design/ds_components.dart';

class DirectorProfile {
  const DirectorProfile({required this.centerName, required this.fullName});
  final String centerName;
  final String fullName;
}

class DebtorMonth {
  const DebtorMonth({
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

class Debtor {
  const Debtor({
    required this.name,
    required this.group,
    required this.phone,
    required this.totalDebt,
    required this.status,
    required this.tone,
    this.months = const [],
  });
  final String name;
  final String group;
  final String phone;
  final int totalDebt;
  final DsStatus status;
  final DsStatus tone; // avatar rangi
  final List<DebtorMonth> months;

  String get statusLabel => switch (status) {
        DsStatus.danger => 'Qarzdor',
        DsStatus.warning => 'Qisman',
        _ => 'To\'landi',
      };
}

class PaymentEntry {
  const PaymentEntry({
    required this.name,
    required this.group,
    required this.amount,
    required this.method,
    required this.time,
    required this.tone,
  });
  final String name;
  final String group;
  final int amount;
  final String method; // 'naqd' | 'karta'
  final String time;
  final DsStatus tone;
}

abstract final class DirectorMock {
  static const profile = DirectorProfile(
    centerName: 'Everest Academy',
    fullName: 'Dilnoza Karimova',
  );

  // ── Dashboard KPI ──
  static const int todayIncome = 3250000;
  static const int monthIncome = 42800000;
  static const int totalDebt = 6150000;
  static const int activeStudents = 480;

  /// Oxirgi 12 oy daromadi (mln so'm nuqtalari).
  static const List<double> revenue12 = [
    22, 24, 26, 29, 31, 33, 35, 37, 38, 40, 41.5, 42.8,
  ];
  static const List<String> revenueMonths = [
    'Avg', 'Sen', 'Okt', 'Noy', 'Dek', 'Yan', 'Fev', 'Mar', 'Apr', 'May', 'Iyun', 'Iyul',
  ];

  // ── Qarzdorlar ──
  static const int debtorsCount = 27;

  static const List<Debtor> debtors = [
    Debtor(
      name: 'Shohida Egamberdiyeva',
      group: 'IELTS G-1',
      phone: '+998 90 123 45 67',
      totalDebt: 900000,
      status: DsStatus.danger,
      tone: DsStatus.danger,
      months: [
        DebtorMonth(month: 'Iyul', monthly: 450000, paid: 0, debt: 450000),
        DebtorMonth(month: 'Iyun', monthly: 450000, paid: 0, debt: 450000),
        DebtorMonth(month: 'May', monthly: 450000, paid: 450000, debt: 0),
      ],
    ),
    Debtor(
      name: 'Bekzod To\'rayev',
      group: 'FRONTEND N-2',
      phone: '+998 97 700 21 08',
      totalDebt: 200000,
      status: DsStatus.warning,
      tone: DsStatus.warning,
      months: [
        DebtorMonth(month: 'Iyul', monthly: 450000, paid: 250000, debt: 200000),
        DebtorMonth(month: 'Iyun', monthly: 450000, paid: 450000, debt: 0),
      ],
    ),
    Debtor(
      name: 'Nilufar Rahimova',
      group: 'BEGINNER 1',
      phone: '+998 91 402 77 15',
      totalDebt: 450000,
      status: DsStatus.danger,
      tone: DsStatus.info,
      months: [
        DebtorMonth(month: 'Iyul', monthly: 450000, paid: 0, debt: 450000),
      ],
    ),
  ];

  // ── To'lovlar (bugungi) ──
  static const List<PaymentEntry> todayPayments = [
    PaymentEntry(name: 'Madina Yusupova', group: 'IELTS G-1', amount: 450000, method: 'karta', time: '12:40', tone: DsStatus.info),
    PaymentEntry(name: 'Sardor Aliyev', group: 'FRONTEND N-2', amount: 400000, method: 'naqd', time: '11:05', tone: DsStatus.success),
    PaymentEntry(name: 'Bekzod To\'rayev', group: 'FRONTEND N-2', amount: 250000, method: 'naqd', time: '09:32', tone: DsStatus.warning),
  ];

  // ── O'quvchilar (qisqa ro'yxat) ──
  static const List<Debtor> students = [
    Debtor(name: 'Madina Yusupova', group: 'IELTS G-1', phone: '+998 90 111 22 33', totalDebt: 0, status: DsStatus.success, tone: DsStatus.info),
    Debtor(name: 'Sardor Aliyev', group: 'FRONTEND N-2', phone: '+998 93 444 55 66', totalDebt: 0, status: DsStatus.success, tone: DsStatus.success),
    Debtor(name: 'Shohida Egamberdiyeva', group: 'IELTS G-1', phone: '+998 90 123 45 67', totalDebt: 900000, status: DsStatus.danger, tone: DsStatus.danger),
    Debtor(name: 'Nilufar Rahimova', group: 'BEGINNER 1', phone: '+998 91 402 77 15', totalDebt: 450000, status: DsStatus.danger, tone: DsStatus.info),
    Debtor(name: 'Jasur Karimov', group: 'IELTS G-1', phone: '+998 94 777 88 99', totalDebt: 0, status: DsStatus.success, tone: DsStatus.warning),
  ];

  // ── Hisobot (Moliya) ──
  static const int reportNetProfit = 24600000;
  static const int reportIncome = 42800000;
  static const int reportExpense = 18200000;

  /// Oxirgi 6 oy: (daromad, xarajat) mln.
  static const List<(double, double)> incomeVsExpense = [
    (31, 14), (33, 15), (35, 16), (37, 17), (40, 17.5), (42.8, 18.2),
  ];
  static const List<String> report6Months = ['Fev', 'Mar', 'Apr', 'May', 'Iyun', 'Iyul'];

  static const List<(String, int)> expenseBreakdown = [
    ('O\'qituvchi maoshlari', 11800000),
    ('Ijara', 3600000),
    ('Boshqa xarajat', 2800000),
  ];
}
