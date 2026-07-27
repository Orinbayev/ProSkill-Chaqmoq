import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/models/game_models.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:google_fonts/google_fonts.dart';

/// O'yin yakuni — duel ham, yakka o'yin ham shu ekranga tushadi.
class GameResultScreen extends StatelessWidget {
  const GameResultScreen({
    super.key,
    required this.natija,
    this.qaytaOynash,
  });

  final GameNatija natija;
  final VoidCallback? qaytaOynash;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final (sarlavha, rang, ikonka) = _bosh(tokens);

    return PopScope(
      canPop: true,
      child: Scaffold(
        backgroundColor: tokens.bg,
        body: SafeArea(
          child: Column(
            children: [
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(20, 32, 20, 20),
                  child: Column(
                    children: [
                      Container(
                        width: 92,
                        height: 92,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          color: tokens.tonedSurface(rang),
                          shape: BoxShape.circle,
                        ),
                        child: Icon(ikonka, size: 46, color: rang),
                      )
                          .animate()
                          .scale(
                            begin: const Offset(0.6, 0.6),
                            end: const Offset(1, 1),
                            duration: 380.ms,
                            curve: Curves.easeOutBack,
                          )
                          .fadeIn(),
                      const SizedBox(height: 18),
                      Text(
                        sarlavha,
                        style: GoogleFonts.inter(
                          fontSize: 26,
                          fontWeight: FontWeight.w900,
                          color: tokens.text,
                          letterSpacing: -0.7,
                        ),
                      ),
                      const SizedBox(height: 5),
                      Text(
                        natija.oyinNomi,
                        style: GoogleFonts.inter(
                          fontSize: 13.5,
                          fontWeight: FontWeight.w600,
                          color: tokens.textMuted,
                        ),
                      ),
                      const SizedBox(height: 26),

                      if (natija.duel)
                        _duelHisobi(tokens)
                      else
                        _yakkaHisob(tokens),

                      if (natija.kutilmoqda) ...[
                        const SizedBox(height: 14),
                        _kutishBelgisi(tokens),
                      ],
                      const SizedBox(height: 22),
                      _mukofot(tokens),
                      if (natija.olinganChaqmoq < 0) ...[
                        const SizedBox(height: 12),
                        _jarimaIzohi(tokens),
                      ],
                      const SizedBox(height: 16),
                      _holat(tokens),
                    ],
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
                child: Column(
                  children: [
                    if (qaytaOynash != null) ...[
                      SizedBox(
                        width: double.infinity,
                        child: FilledButton.icon(
                          onPressed: natija.jon > 0 ? qaytaOynash : null,
                          icon: const Icon(Icons.replay_rounded, size: 19),
                          label: Text(
                            natija.jon > 0 ? 'Yana o‘ynash' : 'Jon tugadi',
                            style: GoogleFonts.inter(fontWeight: FontWeight.w800),
                          ),
                          style: FilledButton.styleFrom(
                            backgroundColor: tokens.primary,
                            foregroundColor: tokens.onPrimary,
                            padding: const EdgeInsets.symmetric(vertical: 15),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(16),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(height: 10),
                    ],
                    SizedBox(
                      width: double.infinity,
                      child: TextButton(
                        onPressed: () => Navigator.of(context).pop(),
                        style: TextButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 14),
                        ),
                        child: Text(
                          'O‘yinlarga qaytish',
                          style: GoogleFonts.inter(
                            fontWeight: FontWeight.w700,
                            color: tokens.textMuted,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  (String, Color, IconData) _bosh(StudentTokens tokens) {
    if (natija.kutilmoqda) {
      return ('Tugatdingiz!', tokens.info, Icons.hourglass_top_rounded);
    }
    if (natija.duelNatija != null) {
      return switch (natija.duelNatija) {
        'galaba' => ('G‘alaba!', tokens.success, Icons.emoji_events_rounded),
        'maglubiyat' => ('Mag‘lubiyat', tokens.danger, Icons.sentiment_dissatisfied_rounded),
        _ => ('Durrang', tokens.warning, Icons.handshake_rounded),
      };
    }
    if (natija.aniqlik >= 100) {
      return ('Mukammal!', tokens.success, Icons.workspace_premium_rounded);
    }
    if (natija.aniqlik >= 75) {
      return ('Zo‘r natija!', tokens.success, Icons.stars_rounded);
    }
    if (natija.aniqlik >= 50) {
      return ('Yaxshi!', tokens.primary, Icons.thumb_up_rounded);
    }
    if (natija.aniqlik >= 30) {
      return ('Mashq kerak', tokens.warning, Icons.school_rounded);
    }
    return ('Juda past', tokens.danger, Icons.warning_amber_rounded);
  }

  Widget _duelHisobi(StudentTokens tokens) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        _hisobUstuni(tokens, 'Siz', natija.ball, tokens.primary),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Text(
            '—',
            style: GoogleFonts.inter(
              fontSize: 22,
              fontWeight: FontWeight.w800,
              color: tokens.textDim,
            ),
          ),
        ),
        _hisobUstuni(
          tokens,
          natija.raqibNomi ?? 'Raqib',
          natija.raqibBall,
          tokens.textMuted,
        ),
      ],
    );
  }

  Widget _hisobUstuni(StudentTokens tokens, String ism, int ball, Color rang) {
    return Column(
      children: [
        Text(
          '$ball',
          style: GoogleFonts.inter(
            fontSize: 44,
            fontWeight: FontWeight.w900,
            color: rang,
            letterSpacing: -1.5,
          ),
        ),
        SizedBox(
          width: 96,
          child: Text(
            ism,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            textAlign: TextAlign.center,
            style: GoogleFonts.inter(
              fontSize: 12.5,
              fontWeight: FontWeight.w600,
              color: tokens.textMuted,
            ),
          ),
        ),
      ],
    );
  }

  Widget _yakkaHisob(StudentTokens tokens) {
    return Column(
      children: [
        Text(
          '${natija.togriJavoblar}/${natija.jamiSavol}',
          style: GoogleFonts.inter(
            fontSize: 44,
            fontWeight: FontWeight.w900,
            color: tokens.text,
            letterSpacing: -1.5,
          ),
        ),
        Text(
          'to‘g‘ri javob · ${natija.aniqlik}% aniqlik',
          style: GoogleFonts.inter(
            fontSize: 12.5,
            fontWeight: FontWeight.w600,
            color: tokens.textMuted,
          ),
        ),
      ],
    );
  }

  /// PvP'da raqib hali o'ynayapti — chaqmoq berilgan, g'olib keyin ma'lum.
  Widget _kutishBelgisi(StudentTokens tokens) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: tokens.tonedSurface(tokens.info),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.schedule_rounded, size: 16, color: tokens.info),
          const SizedBox(width: 8),
          Flexible(
            child: Text(
              'Raqibingiz hali o‘ynayapti — g‘olib keyinroq ma’lum bo‘ladi. '
              'Chaqmoq allaqachon hisobingizda.',
              style: GoogleFonts.inter(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: tokens.info,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// 30% dan past natija uchun jarima izohi.
  Widget _jarimaIzohi(StudentTokens tokens) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Icon(Icons.info_outline_rounded, size: 14, color: tokens.danger),
        const SizedBox(width: 6),
        Flexible(
          child: Text(
            '30% dan past natija uchun 1 chaqmoq jarima olindi',
            style: GoogleFonts.inter(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: tokens.danger,
            ),
          ),
        ),
      ],
    );
  }

  Widget _mukofot(StudentTokens tokens) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
      decoration: BoxDecoration(
        color: tokens.cardBg,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: tokens.border),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
          _mukofotUstuni(
            tokens,
            '+${natija.olinganXp}',
            'XP',
            Icons.trending_up_rounded,
            tokens.info,
          ),
          Container(width: 1, height: 34, color: tokens.border),
          _mukofotUstuni(
            tokens,
            natija.olinganChaqmoq < 0
                ? _chaqmoqMatni(natija.olinganChaqmoq)
                : '+${_chaqmoqMatni(natija.olinganChaqmoq)}',
            'chaqmoq',
            Icons.bolt_rounded,
            natija.olinganChaqmoq < 0 ? tokens.danger : tokens.warning,
          ),
        ],
      ),
    );
  }

  Widget _mukofotUstuni(
    StudentTokens tokens,
    String qiymat,
    String belgi,
    IconData ikonka,
    Color rang,
  ) {
    return Column(
      children: [
        Icon(ikonka, size: 19, color: rang),
        const SizedBox(height: 5),
        Text(
          qiymat,
          style: GoogleFonts.inter(
            fontSize: 20,
            fontWeight: FontWeight.w900,
            color: tokens.text,
            letterSpacing: -0.5,
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

  Widget _holat(StudentTokens tokens) {
    return Wrap(
      alignment: WrapAlignment.center,
      spacing: 8,
      runSpacing: 8,
      children: [
        _pill(tokens, Icons.favorite_rounded, '${natija.jon}/${natija.maxJon}', tokens.danger),
        _pill(tokens, Icons.local_fire_department_rounded, '${natija.streakKun} kun', tokens.warning),
        _pill(tokens, Icons.bolt_rounded, _chaqmoqMatni(natija.chaqmoq), tokens.primary),
      ],
    );
  }

  Widget _pill(StudentTokens tokens, IconData ikonka, String matn, Color rang) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
      decoration: BoxDecoration(
        color: tokens.tonedSurface(rang),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(ikonka, size: 14, color: rang),
          const SizedBox(width: 5),
          Text(
            matn,
            style: GoogleFonts.inter(
              fontSize: 12,
              fontWeight: FontWeight.w800,
              color: rang,
            ),
          ),
        ],
      ),
    );
  }

  static String _chaqmoqMatni(double qiymat) {
    return qiymat == qiymat.roundToDouble()
        ? qiymat.toStringAsFixed(0)
        : qiymat.toStringAsFixed(1);
  }
}
