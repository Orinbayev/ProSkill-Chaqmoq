import 'package:chaqmoq_mobile/core/theme/app_foundation.dart';
import 'package:chaqmoq_mobile/core/theme/app_theme.dart';
import 'package:chaqmoq_mobile/providers/attendance_provider.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/dashboard_provider.dart';
import 'package:chaqmoq_mobile/providers/groups_provider.dart';
import 'package:chaqmoq_mobile/providers/notifications_provider.dart';
import 'package:chaqmoq_mobile/providers/payments_provider.dart';
import 'package:chaqmoq_mobile/providers/profile_provider.dart';
import 'package:chaqmoq_mobile/providers/students_provider.dart';
import 'package:chaqmoq_mobile/providers/teachers_provider.dart';
import `'package:chaqmoq_mobile/screens/auth/login_screen.dart';
import 'package:chaqmoq_mobile/screens/shell/app_shell.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:chaqmoq_mobile/services/storage_service.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();

  final storageService = SecureStorageService();
  final apiClient = ApiClient(storageService: storageService);

  final authService = AuthService(
    apiClient: apiClient,
    storageService: storageService,
  );
  final dashboardService = DashboardService(apiClient: apiClient);
  final studentService = StudentService(apiClient: apiClient);
  final teacherService = TeacherService(apiClient: apiClient);
  final groupService = GroupService(apiClient: apiClient);
  final attendanceService = AttendanceService(apiClient: apiClient);
  final paymentService = PaymentService(apiClient: apiClient);
  final notificationsService = NotificationsService(apiClient: apiClient);
  final profileService = ProfileService(apiClient: apiClient);

  runApp(
    ChaqmoqMobileApp(
      authService: authService,
      dashboardService: dashboardService,
      studentService: studentService,
      teacherService: teacherService,
      groupService: groupService,
      attendanceService: attendanceService,
      paymentService: paymentService,
      notificationsService: notificationsService,
      profileService: profileService,
    ),
  );
}

class ChaqmoqMobileApp extends StatelessWidget {
  const ChaqmoqMobileApp({
    super.key,
    required this.authService,
    required this.dashboardService,
    required this.studentService,
    required this.teacherService,
    required this.groupService,
    required this.attendanceService,
    required this.paymentService,
    required this.notificationsService,
    required this.profileService,
  });

  final AuthService authService;
  final DashboardService dashboardService;
  final StudentService studentService;
  final TeacherService teacherService;
  final GroupService groupService;
  final AttendanceService attendanceService;
  final PaymentService paymentService;
  final NotificationsService notificationsService;
  final ProfileService profileService;

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(
          create: (_) =>
              AuthProvider(authService: authService)..restoreSession(),
        ),
        ChangeNotifierProvider(
          create: (_) => DashboardProvider(dashboardService: dashboardService),
        ),
        ChangeNotifierProvider(
          create: (_) => StudentsProvider(studentService: studentService),
        ),
        ChangeNotifierProvider(
          create: (_) => TeachersProvider(teacherService: teacherService),
        ),
        ChangeNotifierProvider(
          create: (_) => GroupsProvider(groupService: groupService),
        ),
        ChangeNotifierProvider(
          create: (_) =>
              AttendanceProvider(attendanceService: attendanceService),
        ),
        ChangeNotifierProvider(
          create: (_) => PaymentsProvider(paymentService: paymentService),
        ),
        ChangeNotifierProvider(
          create: (_) =>
              NotificationsProvider(notificationsService: notificationsService),
        ),
        ChangeNotifierProvider(
          create: (_) => ProfileProvider(profileService: profileService),
        ),
      ],
      child: MaterialApp(
        title: 'Chaqmoq Mobil',
        theme: AppTheme.lightTheme,
        themeAnimationCurve: Curves.easeInOutCubic,
        themeAnimationDuration: const Duration(milliseconds: 250),
        debugShowCheckedModeBanner: false,
        home: Consumer<AuthProvider>(
          builder: (context, auth, _) {
            if (auth.isInitializing) {
              return const _SplashGate();
            }

            if (auth.isAuthenticated) {
              return const AppShell();
            }

            return const LoginScreen();
          },
        ),
      ),
    );
  }
}

class _SplashGate extends StatelessWidget {
  const _SplashGate();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: DecoratedBox(
        decoration: const BoxDecoration(gradient: AppGradients.darkHero),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 88,
                height: 88,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(AppRadius.lg),
                  border: Border.all(color: Colors.white24),
                ),
                alignment: Alignment.center,
                child: const Icon(
                  Icons.bolt_rounded,
                  color: Colors.white,
                  size: 46,
                ),
              ),
              const SizedBox(height: 20),
              Text(
                'Chaqmoq Mobil',
                style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Markazingiz ma\'lumotlari ulanmoqda...',
                style: Theme.of(
                  context,
                ).textTheme.bodyMedium?.copyWith(color: Colors.white70),
              ),
              const SizedBox(height: 24),
              const CircularProgressIndicator(color: Colors.white),
            ],
          ),
        ),
      ),
    );
  }
}
