import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/providers/game_provider.dart';
import 'package:chaqmoq_mobile/screens/gameonly/game_only_profile_screen.dart';
import 'package:chaqmoq_mobile/screens/student/game/game_hub_screen.dart';
import 'package:chaqmoq_mobile/screens/student/game/game_league_screen.dart';
import 'package:chaqmoq_mobile/widgets/app_student_bottom_nav.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

/// Markazsiz o'yinchi paneli.
///
/// O'quvchi paneliga o'xshaydi, lekin faqat uchta bo'lim bor: **O'yin**,
/// **Reyting** va **Profil**. Davomat, to'lov va qarzdorlik bunday
/// foydalanuvchiga umuman tegishli emas.
class GameOnlyShell extends StatefulWidget {
  const GameOnlyShell({super.key});

  @override
  State<GameOnlyShell> createState() => _GameOnlyShellState();
}

class _GameOnlyShellState extends State<GameOnlyShell> {
  int _currentIndex = 0;

  static const _gameTabIndex = 0;

  final List<Widget> _screens = const [
    GameHubScreen(),
    GameLeagueScreen(ichkiTab: true),
    GameOnlyProfileScreen(),
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      context.read<GameProvider>().load();
    });
  }

  void _setTab(int index) {
    if (_currentIndex == index) return;
    setState(() => _currentIndex = index);

    if (index == _gameTabIndex) {
      // Provider build fazasida xabar bermasin — kadrdan keyin yangilaymiz.
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        context.read<GameProvider>().refresh();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);

    return Scaffold(
      backgroundColor: tokens.bg,
      body: IndexedStack(index: _currentIndex, children: _screens),
      bottomNavigationBar: AppStudentBottomNav(
        activeIndex: _currentIndex,
        onChanged: _setTab,
        items: [
          AppStudentBottomNavItem(
            label: 'O‘yin',
            icon: Icons.sports_esports_outlined,
            activeIcon: Icons.sports_esports_rounded,
          ),
          AppStudentBottomNavItem(
            label: 'Reyting',
            icon: Icons.leaderboard_outlined,
            activeIcon: Icons.leaderboard_rounded,
          ),
          AppStudentBottomNavItem(
            label: 'Profil',
            icon: Icons.person_outline_rounded,
            activeIcon: Icons.person_rounded,
          ),
        ],
      ),
    );
  }
}
