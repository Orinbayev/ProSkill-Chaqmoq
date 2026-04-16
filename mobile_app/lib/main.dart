import 'package:chaqmoq_mobile/core/theme/app_theme.dart';
import 'package:chaqmoq_mobile/providers/attendance_provider.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/dashboard_provider.dart';
import 'package:chaqmoq_mobile/providers/groups_provider.dart';
import 'package:chaqmoq_mobile/providers/notifications_provider.dart';
import 'package:chaqmoq_mobile/providers/payments_provider.dart';
import 'package:chaqmoq_mobile/providers/students_provider.dart';
import 'package:chaqmoq_mobile/providers/teachers_provider.dart';
import 'package:chaqmoq_mobile/screens/splash/splash_screen.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:chaqmoq_mobile/services/storage_service.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();

  final storageService = StorageService();
  final apiClient = ApiClient(storageService: storageService);

  final authService = AuthService(
    apiClient: apiClient,
    storageService: storageService,
  );
  final dashboardService = DashboardService(apiClient);
  final studentsService = StudentsService(apiClient);
  final teachersService = TeachersService(apiClient);
  final groupsService = GroupsService(apiClient);
  final attendanceService = AttendanceService(apiClient);
  final paymentsService = PaymentsService(apiClient);
  final notificationsService = NotificationsService(apiClient);

  final authProvider = AuthProvider(authService: authService);
  apiClient.setUnauthorizedHandler(authProvider.handleUnauthorized);

  runApp(
    ChaqmoqApp(
      authProvider: authProvider,
      dashboardService: dashboardService,
      studentsService: studentsService,
      teachersService: teachersService,
      groupsService: groupsService,
      attendanceService: attendanceService,
      paymentsService: paymentsService,
      notificationsService: notificationsService,
    ),
  );
}

class ChaqmoqApp extends StatelessWidget {
  const ChaqmoqApp({
    super.key,
    required this.authProvider,
    required this.dashboardService,
    required this.studentsService,
    required this.teachersService,
    required this.groupsService,
    required this.attendanceService,
    required this.paymentsService,
    required this.notificationsService,
  });

  final AuthProvider authProvider;
  final DashboardService dashboardService;
  final StudentsService studentsService;
  final TeachersService teachersService;
  final GroupsService groupsService;
  final AttendanceService attendanceService;
  final PaymentsService paymentsService;
  final NotificationsService notificationsService;

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider<AuthProvider>.value(value: authProvider),
        ChangeNotifierProvider(
          create: (_) => DashboardProvider(dashboardService: dashboardService),
        ),
        ChangeNotifierProvider(
          create: (_) => StudentsProvider(studentsService: studentsService),
        ),
        ChangeNotifierProvider(
          create: (_) => TeachersProvider(teachersService: teachersService),
        ),
        ChangeNotifierProvider(
          create: (_) => GroupsProvider(groupsService: groupsService),
        ),
        ChangeNotifierProvider(
          create: (_) => AttendanceProvider(attendanceService: attendanceService),
        ),
        ChangeNotifierProvider(
          create: (_) => PaymentsProvider(paymentsService: paymentsService),
        ),
        ChangeNotifierProvider(
          create: (_) => NotificationsProvider(
            notificationsService: notificationsService,
          ),
        ),
      ],
      child: MaterialApp(
        title: 'ChaqmoqApp Mobile',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.darkTheme,
        home: const SplashScreen(),
      ),
    );
  }
}
