import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/design/ds_bottom_nav.dart';
import '../../core/design/ds_colors.dart';
import '../../core/design/ds_theme.dart';
import '../../screens/profile/ideal_profile_screen.dart';
import 'data/director_provider.dart';
import 'director_dashboard_screen.dart';
import 'director_notifications_screen.dart';
import 'director_payments_screen.dart';
import 'director_report_screen.dart';
import 'director_students_screen.dart';
import 'widgets/director_states.dart';

class DirectorAppShell extends StatefulWidget {
  const DirectorAppShell({super.key, this.isDark = false, this.onToggleTheme});

  /// Panelning yorug'/qorong'i rejimi (host ilova boshqaradi).
  final bool isDark;
  final VoidCallback? onToggleTheme;

  @override
  State<DirectorAppShell> createState() => _DirectorAppShellState();
}

class _DirectorAppShellState extends State<DirectorAppShell> {
  int _index = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<DirectorProvider>().load();
    });
  }

  void _openNotifications(BuildContext context, DirectorProvider provider) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ChangeNotifierProvider<DirectorProvider>.value(
          value: provider,
          child: const DirectorNotificationsScreen(),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Theme(
      data: widget.isDark ? DsTheme.dark() : DsTheme.light(),
      child: Builder(builder: _buildScaffold),
    );
  }

  Widget _buildScaffold(BuildContext context) {
    final ds = context.ds;
    final provider = context.watch<DirectorProvider>();
    final data = provider.data;

    Widget body;
    if (provider.state == DirectorLoadState.error && data == null) {
      body = DirectorErrorView(onRetry: () => provider.load(force: true));
    } else if (data == null) {
      body = const DirectorLoading();
    } else {
      body = IndexedStack(
        index: _index,
        children: [
          DirectorDashboardScreen(
            data: data,
            onRefresh: provider.refresh,
            onProfileTap: () => setState(() => _index = 4),
            onBellTap: () => _openNotifications(context, provider),
          ),
          DirectorPaymentsScreen(data: data),
          const DirectorStudentsScreen(),
          DirectorReportScreen(data: data),
          // "Profil" tab — ichki sahifasiz, hamma narsa shu yerda.
          const IdealProfileScreen(
            showAppBar: false,
            title: 'Profil',
          ),
        ],
      );
    }

    return Scaffold(
      backgroundColor: ds.bg,
      body: body,
      bottomNavigationBar: DsBottomNav(
        currentIndex: _index,
        onTap: (i) => setState(() => _index = i),
        items: const [
          DsNavItem(icon: Icons.home_rounded, label: 'Bosh sahifa'),
          DsNavItem(icon: Icons.credit_card_rounded, label: "To'lovlar"),
          DsNavItem(icon: Icons.people_alt_rounded, label: "O'quvchilar"),
          DsNavItem(icon: Icons.bar_chart_rounded, label: 'Hisobot'),
          DsNavItem(icon: Icons.person_rounded, label: 'Profil'),
        ],
      ),
    );
  }
}
