import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/game_provider.dart';
import 'package:chaqmoq_mobile/screens/student/game/game_launcher.dart';
import 'package:chaqmoq_mobile/screens/student/game/game_league_screen.dart';
import 'package:chaqmoq_mobile/screens/student/game/game_news_screen.dart';
import 'package:chaqmoq_mobile/screens/student/game/game_shop_screen.dart';
import 'package:chaqmoq_mobile/screens/student/game/game_feedback_screen.dart';
import 'package:chaqmoq_mobile/screens/student/game/game_history_screen.dart';
import 'package:chaqmoq_mobile/screens/student/game/game_tariff_screen.dart';
import 'package:chaqmoq_mobile/screens/student/game/widgets/game_widgets.dart';
import 'package:chaqmoq_mobile/widgets/app_state_widgets.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

/// O'quvchi panelidagi «O'yin» bo'limi.
///
/// O'yinlar ro'yxati **serverdan** keladi (admin panelidagi katalog), shuning
/// uchun bu ekranda birorta o'yin nomi qattiq yozilmagan.
class GameHubScreen extends StatefulWidget {
  const GameHubScreen({super.key});

  @override
  State<GameHubScreen> createState() => _GameHubScreenState();
}

class _GameHubScreenState extends State<GameHubScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      context.read<GameProvider>().load();
    });
  }

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final provider = context.watch<GameProvider>();

    return Scaffold(
      backgroundColor: tokens.bg,
      body: SafeArea(
        bottom: false,
        child: switch (provider.state) {
          ViewState.loading || ViewState.idle when provider.oyinlar.isEmpty =>
            AppLoadingState(dark: tokens.isDark),
          ViewState.error when provider.oyinlar.isEmpty => AppErrorState(
            title: 'O‘yinlar yuklanmadi',
            message: provider.errorMessage ?? 'Qayta urinib ko‘ring',
            dark: tokens.isDark,
            onRetry: () => provider.refresh(),
          ),
          _ => RefreshIndicator(
            color: tokens.primary,
            onRefresh: provider.refresh,
            child: _tarkib(context, tokens, provider),
          ),
        },
      ),
    );
  }

  Widget _tarkib(
    BuildContext context,
    StudentTokens tokens,
    GameProvider provider,
  ) {
    final oyinlar = provider.oyinlar;

    return CustomScrollView(
      physics: const AlwaysScrollableScrollPhysics(),
      slivers: [
        SliverToBoxAdapter(child: _boshKarta(context, tokens, provider)),
        SliverToBoxAdapter(child: _tezYollar(context, tokens)),
        SliverToBoxAdapter(child: _pastkiYollar(context, tokens)),
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 22, 20, 12),
            child: Row(
              children: [
                Text(
                  'O‘yinlar',
                  style: GoogleFonts.inter(
                    fontSize: 17,
                    fontWeight: FontWeight.w900,
                    color: tokens.text,
                    letterSpacing: -0.3,
                  ),
                ),
                const SizedBox(width: 8),
                if (oyinlar.isNotEmpty)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: tokens.tonedSurface(tokens.primary),
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: Text(
                      '${oyinlar.length}',
                      style: GoogleFonts.inter(
                        fontSize: 11.5,
                        fontWeight: FontWeight.w800,
                        color: tokens.primary,
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
        if (oyinlar.isEmpty)
          SliverFillRemaining(
            hasScrollBody: false,
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 32),
              child: AppEmptyState(
                icon: Icons.sports_esports_outlined,
                title: 'Hozircha o‘yin yo‘q',
                subtitle:
                    'O‘quv markazingiz o‘yinlarni qo‘shgach, ular shu yerda '
                    'paydo bo‘ladi.',
                dark: tokens.isDark,
                ctaLabel: 'Yangilash',
                onCta: () => provider.refresh(),
              ),
            ),
          )
        else
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 28),
            sliver: SliverGrid(
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
                childAspectRatio: 0.92,
              ),
              delegate: SliverChildBuilderDelegate((context, i) {
                final oyin = oyinlar[i];
                return GameOyinKartasi(
                  oyin: oyin,
                  qollabQuvvatlanadi: gameMotorQollabQuvvatlanadi(oyin.motor),
                  onTap: () => gameOyinOchish(context, oyin),
                ).animate().fadeIn(
                  duration: 260.ms,
                  delay: Duration(milliseconds: 40 * i),
                ).slideY(begin: 0.08, end: 0, curve: Curves.easeOut);
              }, childCount: oyinlar.length),
            ),
          ),
      ],
    );
  }

  Widget _boshKarta(
    BuildContext context,
    StudentTokens tokens,
    GameProvider provider,
  ) {
    final profil = provider.profil;

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(24),
        gradient: tokens.heroGradient,
        border: Border.all(color: tokens.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              CircleAvatar(
                radius: 24,
                backgroundColor: tokens.tonedSurface(tokens.primary),
                backgroundImage:
                    profil.avatar != null ? NetworkImage(profil.avatar!) : null,
                child: profil.avatar != null
                    ? null
                    : Icon(Icons.person_rounded, color: tokens.primary),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      profil.ism,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: GoogleFonts.inter(
                        fontSize: 16.5,
                        fontWeight: FontWeight.w900,
                        color: tokens.text,
                        letterSpacing: -0.3,
                      ),
                    ),
                    Text(
                      '${profil.ligaNomi} liga · ${provider.orin}-o‘rin',
                      style: GoogleFonts.inter(
                        fontSize: 12.5,
                        fontWeight: FontWeight.w600,
                        color: tokens.textMuted,
                      ),
                    ),
                  ],
                ),
              ),
              if (profil.pro)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
                  decoration: BoxDecoration(
                    color: tokens.tonedSurface(tokens.warning),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    'PRO',
                    style: GoogleFonts.inter(
                      fontSize: 10.5,
                      fontWeight: FontWeight.w900,
                      color: tokens.warning,
                      letterSpacing: 0.5,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _KorsatkichUstuni(
                  qiymat: '${profil.xp}',
                  belgi: 'XP',
                  ikonka: Icons.trending_up_rounded,
                  rang: tokens.info,
                ),
              ),
              Container(width: 1, height: 30, color: tokens.border),
              Expanded(
                child: _KorsatkichUstuni(
                  qiymat: _chaqmoqMatni(profil.chaqmoq),
                  belgi: 'chaqmoq',
                  ikonka: Icons.bolt_rounded,
                  rang: tokens.warning,
                ),
              ),
              Container(width: 1, height: 30, color: tokens.border),
              Expanded(
                child: _KorsatkichUstuni(
                  qiymat: '${profil.streakKun}',
                  belgi: 'kun ketma-ket',
                  ikonka: Icons.local_fire_department_rounded,
                  rang: tokens.danger,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              GameJonlar(jon: profil.jon, maxJon: profil.maxJon),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  profil.jon > 0
                      ? '${profil.jon} ta jon qoldi'
                      : _jonMatni(profil.keyingiJonSoniya),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: profil.jon > 0 ? tokens.textMuted : tokens.warning,
                  ),
                ),
              ),
              // Jon tugaganda tezlashtirish yo'lini ko'rsatamiz.
              if (profil.jon <= 0 && !profil.pro)
                TextButton(
                  onPressed: () => _och(context, const GameTariffScreen()),
                  style: TextButton.styleFrom(
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                    minimumSize: Size.zero,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                  child: Text(
                    'Tezlashtirish',
                    style: GoogleFonts.inter(
                      fontSize: 12,
                      fontWeight: FontWeight.w800,
                      color: tokens.primary,
                    ),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _tezYollar(BuildContext context, StudentTokens tokens) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 0),
      child: Row(
        children: [
          _TezYol(
            ikonka: Icons.leaderboard_rounded,
            matn: 'Reyting',
            rang: tokens.primary,
            onTap: () => _och(context, const GameLeagueScreen()),
          ),
          const SizedBox(width: 10),
          _TezYol(
            ikonka: Icons.storefront_rounded,
            matn: 'Do‘kon',
            rang: tokens.success,
            onTap: () => _och(context, const GameShopScreen()),
          ),
          const SizedBox(width: 10),
          _TezYol(
            ikonka: Icons.history_rounded,
            matn: 'Tarix',
            rang: tokens.info,
            onTap: () => _och(context, const GameHistoryScreen()),
          ),
          const SizedBox(width: 10),
          _TezYol(
            ikonka: Icons.campaign_rounded,
            matn: 'Yangilik',
            rang: tokens.warning,
            onTap: () => _och(context, const GameNewsScreen()),
          ),
        ],
      ),
    );
  }

  Widget _pastkiYollar(BuildContext context, StudentTokens tokens) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
      child: Row(
        children: [
          _TezYol(
            ikonka: Icons.rocket_launch_rounded,
            matn: 'Tariflar',
            rang: tokens.secondary,
            onTap: () => _och(context, const GameTariffScreen()),
          ),
          const SizedBox(width: 10),
          _TezYol(
            ikonka: Icons.support_agent_rounded,
            matn: 'Taklif',
            rang: tokens.danger,
            onTap: () => _och(context, const GameFeedbackScreen()),
          ),
        ],
      ),
    );
  }

  void _och(BuildContext context, Widget ekran) {
    Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => ekran));
  }

  static String _jonMatni(int soniya) {
    if (soniya <= 0) return 'Jonlar tez orada tiklanadi';
    final soat = soniya ~/ 3600;
    final daqiqa = (soniya % 3600) ~/ 60;
    if (soat > 0) return 'Keyingi jon: $soat soat $daqiqa daqiqadan keyin';
    return 'Keyingi jon: $daqiqa daqiqadan keyin';
  }

  static String _chaqmoqMatni(double qiymat) {
    return qiymat == qiymat.roundToDouble()
        ? qiymat.toStringAsFixed(0)
        : qiymat.toStringAsFixed(1);
  }
}

class _KorsatkichUstuni extends StatelessWidget {
  const _KorsatkichUstuni({
    required this.qiymat,
    required this.belgi,
    required this.ikonka,
    required this.rang,
  });

  final String qiymat;
  final String belgi;
  final IconData ikonka;
  final Color rang;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Column(
      children: [
        Icon(ikonka, size: 17, color: rang),
        const SizedBox(height: 4),
        Text(
          qiymat,
          style: GoogleFonts.inter(
            fontSize: 17,
            fontWeight: FontWeight.w900,
            color: tokens.text,
            letterSpacing: -0.4,
          ),
        ),
        Text(
          belgi,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: GoogleFonts.inter(
            fontSize: 10.5,
            fontWeight: FontWeight.w600,
            color: tokens.textDim,
          ),
        ),
      ],
    );
  }
}

class _TezYol extends StatelessWidget {
  const _TezYol({
    required this.ikonka,
    required this.matn,
    required this.rang,
    required this.onTap,
  });

  final IconData ikonka;
  final String matn;
  final Color rang;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Expanded(
      child: Material(
        color: tokens.cardBg,
        borderRadius: BorderRadius.circular(16),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 12),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: tokens.border),
            ),
            child: Column(
              children: [
                Icon(ikonka, size: 19, color: rang),
                const SizedBox(height: 5),
                Text(
                  matn,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    color: tokens.textMuted,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
