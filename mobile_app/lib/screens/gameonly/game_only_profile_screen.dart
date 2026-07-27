import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/providers/app_preferences_provider.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/game_provider.dart';
import 'package:chaqmoq_mobile/screens/student/game/game_feedback_screen.dart';
import 'package:chaqmoq_mobile/screens/student/game/game_history_screen.dart';
import 'package:chaqmoq_mobile/screens/student/game/game_tariff_screen.dart';
import 'package:chaqmoq_mobile/services/game_auth_service.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

/// Markazsiz o'yinchi profili.
///
/// O'quvchi profilidan farqi: bu yerda **to'lov, qarzdorlik, davomat va
/// markaz ma'lumotlari yo'q** — faqat o'yin statistikasi va sozlamalar.
class GameOnlyProfileScreen extends StatelessWidget {
  const GameOnlyProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final auth = context.watch<AuthProvider>();
    final game = context.watch<GameProvider>();
    final user = auth.user;

    return Scaffold(
      backgroundColor: tokens.bg,
      body: SafeArea(
        bottom: false,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
          children: [
            _boshKarta(context, tokens, user?.fullName ?? '', user?.email ?? '', game),
            const SizedBox(height: 18),

            _bolim(tokens, 'O‘YIN'),
            _karta(tokens, [
              _qator(
                context,
                tokens,
                Icons.rocket_launch_rounded,
                'Tariflar',
                'O‘yinni tezlashtirish',
                () => _och(context, const GameTariffScreen()),
              ),
              _qator(
                context,
                tokens,
                Icons.history_rounded,
                'O‘yin tarixi',
                'Natijalaringiz',
                () => _och(context, const GameHistoryScreen()),
              ),
              _qator(
                context,
                tokens,
                Icons.support_agent_rounded,
                'Shikoyat va takliflar',
                'Bizga yozing',
                () => _och(context, const GameFeedbackScreen()),
                oxirgi: true,
              ),
            ]),

            const SizedBox(height: 18),
            _bolim(tokens, 'SOZLAMALAR'),
            _karta(tokens, [
              _mavzuQatori(context, tokens),
            ]),

            const SizedBox(height: 22),
            SizedBox(
              width: double.infinity,
              child: TextButton.icon(
                onPressed: () => _chiqish(context),
                icon: Icon(Icons.logout_rounded, size: 18, color: tokens.danger),
                label: Text(
                  'Chiqish',
                  style: GoogleFonts.inter(
                    fontSize: 14,
                    fontWeight: FontWeight.w800,
                    color: tokens.danger,
                  ),
                ),
                style: TextButton.styleFrom(
                  backgroundColor: tokens.tonedSurface(tokens.danger),
                  padding: const EdgeInsets.symmetric(vertical: 15),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _boshKarta(
    BuildContext context,
    StudentTokens tokens,
    String ism,
    String email,
    GameProvider game,
  ) {
    final profil = game.profil;

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(24),
        gradient: tokens.heroGradient,
        border: Border.all(color: tokens.border),
      ),
      child: Column(
        children: [
          CircleAvatar(
            radius: 34,
            backgroundColor: tokens.tonedSurface(tokens.primary),
            child: Text(
              ism.isNotEmpty ? ism.characters.first.toUpperCase() : '?',
              style: GoogleFonts.inter(
                fontSize: 26,
                fontWeight: FontWeight.w900,
                color: tokens.primary,
              ),
            ),
          ),
          const SizedBox(height: 12),
          Text(
            ism.isNotEmpty ? ism : 'O‘yinchi',
            style: GoogleFonts.inter(
              fontSize: 19,
              fontWeight: FontWeight.w900,
              color: tokens.text,
              letterSpacing: -0.4,
            ),
          ),
          Text(
            email,
            style: GoogleFonts.inter(
              fontSize: 12.5,
              fontWeight: FontWeight.w500,
              color: tokens.textMuted,
            ),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(child: _kpi(tokens, '${profil.xp}', 'XP', tokens.info)),
              Container(width: 1, height: 32, color: tokens.border),
              Expanded(
                child: _kpi(
                  tokens,
                  _chaqmoqMatni(profil.chaqmoq),
                  'chaqmoq',
                  tokens.warning,
                ),
              ),
              Container(width: 1, height: 32, color: tokens.border),
              Expanded(
                child: _kpi(tokens, '${game.orin}', 'o‘rin', tokens.primary),
              ),
            ],
          ),
          if (profil.pro) ...[
            const SizedBox(height: 14),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: tokens.tonedSurface(tokens.warning),
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text(
                '${profil.tarif ?? "PRO"} tarifi faol',
                style: GoogleFonts.inter(
                  fontSize: 11.5,
                  fontWeight: FontWeight.w800,
                  color: tokens.warning,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _kpi(StudentTokens tokens, String qiymat, String belgi, Color rang) {
    return Column(
      children: [
        Text(
          qiymat,
          style: GoogleFonts.inter(
            fontSize: 18,
            fontWeight: FontWeight.w900,
            color: rang,
            letterSpacing: -0.4,
          ),
        ),
        Text(
          belgi,
          style: GoogleFonts.inter(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: tokens.textDim,
          ),
        ),
      ],
    );
  }

  Widget _bolim(StudentTokens tokens, String matn) {
    return Padding(
      padding: const EdgeInsets.only(left: 4, bottom: 8),
      child: Text(
        matn,
        style: GoogleFonts.inter(
          fontSize: 11.5,
          fontWeight: FontWeight.w800,
          color: tokens.textDim,
          letterSpacing: 0.8,
        ),
      ),
    );
  }

  Widget _karta(StudentTokens tokens, List<Widget> bolalar) {
    // `Material` ishlatiladi, `Container` emas: ListTile o'zining fonini va
    // bosish to'lqinini eng yaqin Material ustiga chizadi — rangli Container
    // ularni yashirib qo'yardi.
    return Material(
      color: tokens.cardBg,
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: BorderSide(color: tokens.border),
      ),
      child: Column(children: bolalar),
    );
  }

  Widget _qator(
    BuildContext context,
    StudentTokens tokens,
    IconData ikonka,
    String sarlavha,
    String izoh,
    VoidCallback onTap, {
    bool oxirgi = false,
  }) {
    return Column(
      children: [
        ListTile(
          onTap: onTap,
          leading: Container(
            width: 38,
            height: 38,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: tokens.tonedSurface(tokens.primary),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(ikonka, size: 19, color: tokens.primary),
          ),
          title: Text(
            sarlavha,
            style: GoogleFonts.inter(
              fontSize: 14.5,
              fontWeight: FontWeight.w700,
              color: tokens.text,
            ),
          ),
          subtitle: Text(
            izoh,
            style: GoogleFonts.inter(
              fontSize: 12,
              fontWeight: FontWeight.w500,
              color: tokens.textMuted,
            ),
          ),
          trailing: Icon(
            Icons.chevron_right_rounded,
            color: tokens.textDim,
          ),
        ),
        if (!oxirgi)
          Divider(height: 1, thickness: 1, color: tokens.border, indent: 66),
      ],
    );
  }

  Widget _mavzuQatori(BuildContext context, StudentTokens tokens) {
    final prefs = context.watch<AppPreferencesProvider>();
    final qorongi = Theme.of(context).brightness == Brightness.dark;

    return SwitchListTile(
      value: qorongi,
      onChanged: (yoq) => prefs.setThemePreference(
        yoq ? AppThemePreference.dark : AppThemePreference.light,
      ),
      secondary: Container(
        width: 38,
        height: 38,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: tokens.tonedSurface(tokens.secondary),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Icon(
          qorongi ? Icons.dark_mode_rounded : Icons.light_mode_rounded,
          size: 19,
          color: tokens.secondary,
        ),
      ),
      title: Text(
        'Qorong‘i rejim',
        style: GoogleFonts.inter(
          fontSize: 14.5,
          fontWeight: FontWeight.w700,
          color: tokens.text,
        ),
      ),
      activeThumbColor: tokens.primary,
    );
  }

  void _och(BuildContext context, Widget ekran) {
    Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => ekran));
  }

  Future<void> _chiqish(BuildContext context) async {
    final tokens = StudentTokens.of(context);
    final auth = context.read<AuthProvider>();
    final googleAuth = context.read<GameAuthService>();

    final tasdiq = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: tokens.surfaceElevated,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Text(
          'Chiqish',
          style: GoogleFonts.inter(
            fontSize: 17,
            fontWeight: FontWeight.w900,
            color: tokens.text,
          ),
        ),
        content: Text(
          'Hisobingizdan chiqmoqchimisiz? Chaqmoq va natijalaringiz saqlanadi.',
          style: GoogleFonts.inter(
            fontSize: 13.5,
            fontWeight: FontWeight.w500,
            color: tokens.textMuted,
            height: 1.45,
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: Text(
              'Bekor',
              style: GoogleFonts.inter(
                fontWeight: FontWeight.w700,
                color: tokens.textMuted,
              ),
            ),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(
              'Chiqish',
              style: GoogleFonts.inter(
                fontWeight: FontWeight.w700,
                color: tokens.danger,
              ),
            ),
          ),
        ],
      ),
    );

    if (tasdiq != true) return;
    await googleAuth.chiqish();
    await auth.logout();
  }

  static String _chaqmoqMatni(double qiymat) {
    return qiymat == qiymat.roundToDouble()
        ? qiymat.toStringAsFixed(0)
        : qiymat.toStringAsFixed(1);
  }
}
