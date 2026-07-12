import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/design/ds_bottom_nav.dart';
import '../../core/design/ds_colors.dart';
import '../../core/design/ds_components.dart';
import '../../core/design/ds_theme.dart';
import '../../core/design/ds_tokens.dart';
import '../../core/design/ds_typography.dart';
import '../../providers/auth_provider.dart';
import 'data/director_provider.dart';
import 'director_dashboard_screen.dart';
import 'director_notifications_screen.dart';
import 'director_payments_screen.dart';
import 'director_profile_screen.dart';
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
    // Panelni yagona dizayn tizimi mavzusiga o'raymiz — host ilova mavzusidan qat'i nazar.
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
          _MoreScreen(isDark: widget.isDark, onToggleTheme: widget.onToggleTheme),
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
          DsNavItem(icon: Icons.credit_card_rounded, label: 'To\'lovlar'),
          DsNavItem(icon: Icons.people_alt_rounded, label: 'O\'quvchilar'),
          DsNavItem(icon: Icons.bar_chart_rounded, label: 'Hisobot'),
          DsNavItem(icon: Icons.more_horiz_rounded, label: 'Yana'),
        ],
      ),
    );
  }
}

class _MoreScreen extends StatelessWidget {
  const _MoreScreen({required this.isDark, this.onToggleTheme});
  final bool isDark;
  final VoidCallback? onToggleTheme;

  Future<void> _logout(BuildContext context) async {
    final ds = context.ds;
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: ds.card,
        title: Text('Chiqish', style: DsType.h3(ds.textPrimary)),
        content: Text('Hisobingizdan chiqmoqchimisiz?', style: DsType.body(ds.textSecondary)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Bekor')),
          TextButton(onPressed: () => Navigator.pop(context, true), child: Text('Chiqish', style: TextStyle(color: ds.danger))),
        ],
      ),
    );
    if (ok == true && context.mounted) {
      await context.read<AuthProvider>().logout();
    }
  }

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    final provider = context.watch<DirectorProvider>();
    final data = provider.data;
    final user = context.watch<AuthProvider>().user;
    final name = user?.fullName ?? data?.directorName ?? 'Direktor';

    Widget tile(IconData icon, String title, {Widget? trailing, VoidCallback? onTap}) => DsListRow(
          leading: Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(color: ds.primarySoft, borderRadius: DsRadius.all(DsRadius.sm)),
            child: Icon(icon, size: 20, color: ds.primarySoftFg),
          ),
          title: title,
          trailing: trailing ?? Icon(Icons.chevron_right, color: ds.textFaint),
          onTap: onTap,
        );

    void openProfile() => Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => ChangeNotifierProvider<DirectorProvider>.value(
              value: provider,
              child: const DirectorProfileScreen(),
            ),
          ),
        );

    return SafeArea(
      bottom: false,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(DsSpace.screen, DsSpace.x3, DsSpace.screen, DsSpace.x8),
        children: [
          Text('Yana', style: DsType.h1(ds.textPrimary)),
          const SizedBox(height: DsSpace.x5),
          // Profil header — bosib tahrirlash
          DsCard(
            onTap: openProfile,
            child: Row(
              children: [
                DsAvatar(name, size: 52),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(name, style: DsType.h3(ds.textPrimary)),
                      const SizedBox(height: 2),
                      Text('${data?.centerName ?? 'Markaz'} · Direktor', style: DsType.small(ds.textMuted)),
                    ],
                  ),
                ),
                Icon(Icons.chevron_right, color: ds.textFaint),
              ],
            ),
          ),
          const SizedBox(height: DsSpace.section),
          DsCard(
            padding: const EdgeInsets.symmetric(horizontal: DsSpace.x5, vertical: DsSpace.x1),
            child: Column(children: [
              tile(Icons.person_rounded, 'Profilни tahrirlash', onTap: openProfile),
              if (onToggleTheme != null) ...[
                Container(height: 1, color: ds.border),
                tile(
                  isDark ? Icons.light_mode_rounded : Icons.dark_mode_rounded,
                  isDark ? 'Yorug\' rejim' : 'Qorong\'i rejim',
                  trailing: Switch(value: isDark, activeThumbColor: ds.primary, onChanged: (_) => onToggleTheme!.call()),
                  onTap: onToggleTheme,
                ),
              ],
            ]),
          ),
          const SizedBox(height: DsSpace.section),
          DsButton(label: 'Chiqish', icon: Icons.logout_rounded, variant: DsButtonVariant.danger, onPressed: () => _logout(context)),
          const SizedBox(height: 20),
          Center(child: Text('ChaqmoqApp · Director paneli', style: DsType.small(ds.textFaint))),
        ],
      ),
    );
  }
}
