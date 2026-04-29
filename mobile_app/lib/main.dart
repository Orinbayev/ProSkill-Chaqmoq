import 'package:chaqmoq_mobile/core/theme/app_theme.dart';
import 'package:chaqmoq_mobile/providers/attendance_provider.dart';
import 'package:chaqmoq_mobile/providers/app_preferences_provider.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/dashboard_provider.dart';
import 'package:chaqmoq_mobile/providers/groups_provider.dart';
import 'package:chaqmoq_mobile/providers/notifications_provider.dart';
import 'package:chaqmoq_mobile/providers/parent_dashboard_provider.dart';
import 'package:chaqmoq_mobile/providers/payments_provider.dart';
import 'package:chaqmoq_mobile/providers/students_provider.dart';
import 'package:chaqmoq_mobile/providers/teachers_provider.dart';
import 'package:chaqmoq_mobile/repositories/auth_repository.dart';
import 'package:chaqmoq_mobile/screens/auth/login_screen.dart';
import 'package:chaqmoq_mobile/screens/shell/app_shell.dart';
import 'package:chaqmoq_mobile/screens/parent/parent_app_shell.dart';
import 'package:chaqmoq_mobile/screens/student/student_app_shell.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:chaqmoq_mobile/services/login_service.dart';
import 'package:chaqmoq_mobile/services/parent_dashboard_service.dart';
import 'package:chaqmoq_mobile/services/storage_service.dart';
import 'package:flutter/material.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:provider/provider.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initializeDateFormatting('uz', null);
  await initializeDateFormatting('uz_UZ', null);

  final storageService = StorageService();
  final apiClient = ApiClient(storageService: storageService);

  final loginService = LoginService(apiClient: apiClient);
  final authRepository = AuthRepository(
    apiClient: apiClient,
    loginService: loginService,
    storageService: storageService,
  );
  final dashboardService = DashboardService(apiClient);
  final studentsService = StudentsService(apiClient);
  final teachersService = TeachersService(apiClient);
  final groupsService = GroupsService(apiClient);
  final attendanceService = AttendanceService(apiClient);
  final paymentsService = PaymentsService(apiClient);
  final notificationsService = NotificationsService(apiClient);
  final parentDashboardService = ParentDashboardService(apiClient);

  final authProvider = AuthProvider(authRepository: authRepository);
  apiClient.setUnauthorizedHandler(authProvider.handleUnauthorized);

  runApp(
    ChaqmoqApp(
      storageService: storageService,
      authProvider: authProvider,
      dashboardService: dashboardService,
      studentsService: studentsService,
      teachersService: teachersService,
      groupsService: groupsService,
      attendanceService: attendanceService,
      paymentsService: paymentsService,
      notificationsService: notificationsService,
      parentDashboardService: parentDashboardService,
    ),
  );
}

class ChaqmoqApp extends StatelessWidget {
  const ChaqmoqApp({
    super.key,
    required this.authProvider,
    required this.storageService,
    required this.dashboardService,
    required this.studentsService,
    required this.teachersService,
    required this.groupsService,
    required this.attendanceService,
    required this.paymentsService,
    required this.notificationsService,
    required this.parentDashboardService,
  });

  final AuthProvider authProvider;
  final StorageService storageService;
  final DashboardService dashboardService;
  final StudentsService studentsService;
  final TeachersService teachersService;
  final GroupsService groupsService;
  final AttendanceService attendanceService;
  final PaymentsService paymentsService;
  final NotificationsService notificationsService;
  final ParentDashboardService parentDashboardService;

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        Provider<ParentDashboardService>.value(value: parentDashboardService),
        ChangeNotifierProvider<AuthProvider>.value(value: authProvider),
        ChangeNotifierProvider(
          create: (_) =>
              AppPreferencesProvider(storageService: storageService)..load(),
        ),
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
          create: (_) =>
              AttendanceProvider(attendanceService: attendanceService),
        ),
        ChangeNotifierProvider(
          create: (_) => PaymentsProvider(paymentsService: paymentsService),
        ),
        ChangeNotifierProvider(
          create: (_) =>
              NotificationsProvider(notificationsService: notificationsService),
        ),
        ChangeNotifierProvider(
          create: (_) =>
              ParentDashboardProvider(service: parentDashboardService),
        ),
      ],
      child: Consumer<AppPreferencesProvider>(
        builder: (context, preferences, _) {
          return MaterialApp(
            title: 'ChaqmoqApp Mobile',
            debugShowCheckedModeBanner: false,
            theme: AppTheme.darkTheme,
            darkTheme: AppTheme.darkTheme,
            themeMode: preferences.themeMode,
            home: const AuthGate(),
          );
        },
      ),
    );
  }
}

class AuthGate extends StatefulWidget {
  const AuthGate({super.key});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        context.read<AuthProvider>().restoreSession();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    if (auth.isInitializing) {
      return const Scaffold(
        backgroundColor: Color(0xFFF7FBFF),
        body: Center(child: CircularProgressIndicator()),
      );
    }
    if (!auth.isAuthenticated) {
      return const LoginScreen();
    }

    final role = auth.user?.role.trim().toLowerCase();
    if (role == 'parent') {
      return const ParentAppShell();
    }
    if (role == 'student') {
      return const StudentAppShell();
    }
    return const AppShell();
  }
}
