import 'dart:async';

import 'package:chaqmoq_mobile/core/config/app_config.dart';
import 'package:chaqmoq_mobile/core/theme/app_theme.dart';
import 'package:chaqmoq_mobile/providers/attendance_provider.dart';
import 'package:chaqmoq_mobile/providers/app_preferences_provider.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/chaqmoq_history_provider.dart';
import 'package:chaqmoq_mobile/providers/dashboard_provider.dart';
import 'package:chaqmoq_mobile/providers/groups_provider.dart';
import 'package:chaqmoq_mobile/providers/notifications_provider.dart';
import 'package:chaqmoq_mobile/providers/parent_dashboard_provider.dart';
import 'package:chaqmoq_mobile/providers/payments_provider.dart';
import 'package:chaqmoq_mobile/providers/students_provider.dart';
import 'package:chaqmoq_mobile/providers/leads_provider.dart';
import 'package:chaqmoq_mobile/providers/teachers_provider.dart';
import 'package:chaqmoq_mobile/repositories/auth_repository.dart';
import 'package:chaqmoq_mobile/screens/auth/login_screen.dart';
import 'package:chaqmoq_mobile/screens/shell/app_shell.dart';
import 'package:chaqmoq_mobile/screens/director/data/director_provider.dart';
import 'package:chaqmoq_mobile/screens/director/data/director_repository.dart';
import 'package:chaqmoq_mobile/screens/director/director_app_shell.dart';
import 'package:chaqmoq_mobile/screens/parent/parent_app_shell.dart';
import 'package:chaqmoq_mobile/screens/student/student_app_shell.dart';
import 'package:chaqmoq_mobile/screens/teacher/teacher_app_shell.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:chaqmoq_mobile/services/login_service.dart';
import 'package:chaqmoq_mobile/services/leads_service.dart';
import 'package:chaqmoq_mobile/services/teacher_service.dart';
import 'package:chaqmoq_mobile/providers/teacher_provider.dart';
import 'package:chaqmoq_mobile/services/local_notification_service.dart';
import 'package:chaqmoq_mobile/services/parent_dashboard_service.dart';
import 'package:chaqmoq_mobile/services/storage_service.dart';
import 'package:flutter/material.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:provider/provider.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initializeDateFormatting('uz', null);
  await initializeDateFormatting('uz_UZ', null);
  debugPrint(
    '[Chaqmoq App] env=${AppConfig.environmentName} baseUrl=${AppConfig.baseUrl}',
  );

  final storageService = StorageService();
  final apiClient = ApiClient(storageService: storageService);
  unawaited(apiClient.warmup());
  final localNotificationService = LocalNotificationService();
  await localNotificationService.initialize();

  final loginService = LoginService(apiClient: apiClient);
  final authRepository = AuthRepository(
    apiClient: apiClient,
    loginService: loginService,
    storageService: storageService,
  );
  final teacherService = TeacherService(apiClient: apiClient);
  final dashboardService = DashboardService(apiClient);
  final studentsService = StudentsService(apiClient);
  final teachersService = TeachersService(apiClient);
  final groupsService = GroupsService(apiClient);
  final attendanceService = AttendanceService(apiClient);
  final paymentsService = PaymentsService(apiClient);
  final notificationsService = NotificationsService(apiClient);
  final chaqmoqService = ChaqmoqService(apiClient);
  final storeService = StoreService(apiClient);
  final parentDashboardService = ParentDashboardService(apiClient);
  final leadsService = LeadsService(apiClient);

  final authProvider = AuthProvider(authRepository: authRepository);
  apiClient.setUnauthorizedHandler(authProvider.handleUnauthorized);

  runApp(
    ChaqmoqApp(
      apiClient: apiClient,
      storageService: storageService,
      localNotificationService: localNotificationService,
      authProvider: authProvider,
      dashboardService: dashboardService,
      studentsService: studentsService,
      teachersService: teachersService,
      groupsService: groupsService,
      attendanceService: attendanceService,
      paymentsService: paymentsService,
      notificationsService: notificationsService,
      chaqmoqService: chaqmoqService,
      storeService: storeService,
      parentDashboardService: parentDashboardService,
      teacherService: teacherService,
      leadsService: leadsService,
    ),
  );
}

class ChaqmoqApp extends StatelessWidget {
  const ChaqmoqApp({
    super.key,
    required this.apiClient,
    required this.authProvider,
    required this.storageService,
    required this.localNotificationService,
    required this.dashboardService,
    required this.studentsService,
    required this.teachersService,
    required this.groupsService,
    required this.attendanceService,
    required this.paymentsService,
    required this.notificationsService,
    required this.chaqmoqService,
    required this.storeService,
    required this.parentDashboardService,
    required this.teacherService,
    required this.leadsService,
  });

  final ApiClient apiClient;
  final AuthProvider authProvider;
  final StorageService storageService;
  final LocalNotificationService localNotificationService;
  final DashboardService dashboardService;
  final StudentsService studentsService;
  final TeachersService teachersService;
  final GroupsService groupsService;
  final AttendanceService attendanceService;
  final PaymentsService paymentsService;
  final NotificationsService notificationsService;
  final ChaqmoqService chaqmoqService;
  final StoreService storeService;
  final ParentDashboardService parentDashboardService;
  final TeacherService teacherService;
  final LeadsService leadsService;

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        Provider<StorageService>.value(value: storageService),
        Provider<ApiClient>.value(value: apiClient),
        Provider<ParentDashboardService>.value(value: parentDashboardService),
        Provider<DashboardService>.value(value: dashboardService),
        Provider<StoreService>.value(value: storeService),
        Provider<LocalNotificationService>.value(value: localNotificationService),
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
          create: (_) => ChaqmoqHistoryProvider(service: chaqmoqService),
        ),
        ChangeNotifierProvider(
          create: (_) =>
              ParentDashboardProvider(service: parentDashboardService),
        ),
        ChangeNotifierProvider(
          create: (_) => LeadsProvider(service: leadsService),
        ),
        ChangeNotifierProvider(
          create: (_) => TeacherProvider(service: teacherService),
        ),
      ],
      child: Consumer<AppPreferencesProvider>(
        builder: (context, preferences, _) {
          return MaterialApp(
            title: 'ChaqmoqApp Mobile',
            debugShowCheckedModeBanner: false,
            theme: AppTheme.lightTheme,
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

    final Widget child;
    final ValueKey<String> key;

    if (auth.isInitializing) {
      key = const ValueKey('auth-init');
      child = const _AuthInitScreen();
    } else if (!auth.isAuthenticated) {
      key = const ValueKey('auth-login');
      child = const LoginScreen();
    } else if (auth.justAuthenticated) {
      // Briefly show a success splash so the user gets clear feedback that
      // login worked, then the gate fades into the home shell.
      key = const ValueKey('auth-success');
      child = const _AuthSuccessSplash();
    } else {
      final role = auth.user?.role.trim().toLowerCase();
      if (role == 'parent') {
        key = const ValueKey('home-parent');
        child = const ParentAppShell();
      } else if (role == 'student') {
        key = const ValueKey('home-student');
        child = const StudentAppShell();
      } else if (role == 'teacher') {
        key = const ValueKey('home-teacher');
        child = const TeacherAppShell();
      } else if (role == 'director' || role == 'manager') {
        // Manager ham Director panelini ko'radi (kunlik davomat nazorati +
        // ko'rsatkichlar). `/api/mobile/director/home/` manager'ga ham ruxsat beradi.
        key = ValueKey('home-$role');
        final user = auth.user!;
        final apiClient = context.read<ApiClient>();
        final prefs = context.read<AppPreferencesProvider>();
        final isDark = Theme.of(context).brightness == Brightness.dark;
        child = ChangeNotifierProvider<DirectorProvider>(
          create: (_) => DirectorProvider(
            ApiDirectorRepository(
              apiClient,
              centerName: user.center?.name ?? '',
              directorName: user.fullName,
            ),
          ),
          child: DirectorAppShell(
            isDark: isDark,
            onToggleTheme: () => prefs.setThemePreference(
              isDark ? AppThemePreference.light : AppThemePreference.dark,
            ),
          ),
        );
      } else {
        key = const ValueKey('home-manager');
        child = const AppShell();
      }
    }

    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 240),
      switchInCurve: Curves.easeOutCubic,
      switchOutCurve: Curves.easeInCubic,
      transitionBuilder: (Widget c, Animation<double> a) {
        final offset = Tween<Offset>(
          begin: const Offset(0, 0.04),
          end: Offset.zero,
        ).animate(a);
        return FadeTransition(
          opacity: a,
          child: SlideTransition(
            position: offset,
            child: ScaleTransition(
              scale: Tween<double>(begin: 0.985, end: 1.0).animate(a),
              child: c,
            ),
          ),
        );
      },
      child: KeyedSubtree(key: key, child: child),
    );
  }
}

class _AuthInitScreen extends StatelessWidget {
  const _AuthInitScreen();

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bg = isDark ? const Color(0xFF0F172A) : const Color(0xFFEDF1F5);
    final accent = const Color(0xFF0EA5E9);
    return Scaffold(
      backgroundColor: bg,
      body: Center(
        child: CircularProgressIndicator(color: accent),
      ),
    );
  }
}

/// Tinch, jonli success splash — login muvaffaqiyatli bo'lganda
/// ~900 ms ko'rinadi, keyin home shell'ga fade qiladi.
class _AuthSuccessSplash extends StatefulWidget {
  const _AuthSuccessSplash();

  @override
  State<_AuthSuccessSplash> createState() => _AuthSuccessSplashState();
}

class _AuthSuccessSplashState extends State<_AuthSuccessSplash>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _scale;
  late final Animation<double> _ringFade;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 700),
    );
    _scale = CurvedAnimation(parent: _controller, curve: Curves.easeOutBack);
    _ringFade = CurvedAnimation(parent: _controller, curve: Curves.easeOutCubic);
    _controller.forward();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bg = isDark ? const Color(0xFF0F172A) : const Color(0xFFEDF1F5);
    final accent = const Color(0xFF0EA5E9);

    return Scaffold(
      backgroundColor: bg,
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            AnimatedBuilder(
              animation: _controller,
              builder: (_, __) {
                final scale = 0.6 + (0.4 * _scale.value);
                final ringOpacity = (1.0 - _ringFade.value).clamp(0.0, 1.0);
                final ringScale = 0.6 + (1.4 * _ringFade.value);
                return SizedBox(
                  width: 140,
                  height: 140,
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      // Pulsing ring
                      Opacity(
                        opacity: ringOpacity * 0.6,
                        child: Transform.scale(
                          scale: ringScale,
                          child: Container(
                            width: 110,
                            height: 110,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              border: Border.all(color: accent, width: 3),
                            ),
                          ),
                        ),
                      ),
                      // Solid checkmark badge
                      Transform.scale(
                        scale: scale,
                        child: Container(
                          width: 96,
                          height: 96,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            gradient: LinearGradient(
                              begin: Alignment.topLeft,
                              end: Alignment.bottomRight,
                              colors: [accent, const Color(0xFF38BDF8)],
                            ),
                            boxShadow: [
                              BoxShadow(
                                color: accent.withValues(alpha: 0.35),
                                blurRadius: 30,
                                spreadRadius: 4,
                              ),
                            ],
                          ),
                          child: const Icon(
                            Icons.check_rounded,
                            color: Colors.white,
                            size: 56,
                          ),
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
            const SizedBox(height: 22),
            FadeTransition(
              opacity: _ringFade,
              child: Text(
                'Xush kelibsiz!',
                style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.w800,
                  color: isDark ? Colors.white : const Color(0xFF0F172A),
                  letterSpacing: -0.3,
                ),
              ),
            ),
            const SizedBox(height: 6),
            FadeTransition(
              opacity: _ringFade,
              child: Text(
                'Tizimga muvaffaqiyatli kirdingiz',
                style: TextStyle(
                  fontSize: 13.5,
                  fontWeight: FontWeight.w600,
                  color: isDark
                      ? Colors.white.withValues(alpha: 0.7)
                      : const Color(0xFF64748B),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
