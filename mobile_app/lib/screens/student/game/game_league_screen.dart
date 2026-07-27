import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/models/game_models.dart';
import 'package:chaqmoq_mobile/providers/game_provider.dart';
import 'package:chaqmoq_mobile/screens/student/game/widgets/game_scaffold.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

/// O'yin reytingi — markaz bo'yicha va umumiy.
class GameLeagueScreen extends StatefulWidget {
  const GameLeagueScreen({super.key, this.ichkiTab = false});

  /// Tab sifatida ochilganda orqaga tugmasi kerak emas.
  final bool ichkiTab;

  @override
  State<GameLeagueScreen> createState() => _GameLeagueScreenState();
}

class _GameLeagueScreenState extends State<GameLeagueScreen> {
  String _doira = 'markaz';

  Future<void> _yukla() => context.read<GameProvider>().ligaYukla(doira: _doira);

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);

    return GameScaffold(
      sarlavha: 'Reyting',
      orqagaTugma: !widget.ichkiTab,
      yuklash: _yukla,
      qurilish: (context) {
        final liga = context.watch<GameProvider>().liga;
        if (liga == null) return const SizedBox.shrink();

        return ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
          children: [
            if (liga.markazBor) ...[
              _doiraTanlagich(tokens),
              const SizedBox(height: 14),
            ],
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              decoration: BoxDecoration(
                color: tokens.tonedSurface(tokens.primary),
                borderRadius: BorderRadius.circular(18),
              ),
              child: Row(
                children: [
                  Icon(Icons.emoji_events_rounded, color: tokens.primary, size: 22),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'Sizning o‘rningiz: ${liga.meningOrinim}',
                      style: GoogleFonts.inter(
                        fontSize: 14,
                        fontWeight: FontWeight.w800,
                        color: tokens.text,
                      ),
                    ),
                  ),
                  Text(
                    _ligaNomi(liga.liga),
                    style: GoogleFonts.inter(
                      fontSize: 12.5,
                      fontWeight: FontWeight.w800,
                      color: tokens.primary,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 14),
            for (final qator in liga.qatorlar) _qator(tokens, qator),
          ],
        );
      },
    );
  }

  Widget _doiraTanlagich(StudentTokens tokens) {
    return Row(
      children: [
        for (final (kalit, nom) in const [
          ('markaz', 'Markazim'),
          ('umumiy', 'Barcha markazlar'),
        ])
          Expanded(
            child: Padding(
              padding: EdgeInsets.only(right: kalit == 'markaz' ? 8 : 0),
              child: Material(
                color: _doira == kalit
                    ? tokens.tonedSurface(tokens.primary)
                    : tokens.cardBg,
                borderRadius: BorderRadius.circular(14),
                child: InkWell(
                  borderRadius: BorderRadius.circular(14),
                  onTap: () {
                    if (_doira == kalit) return;
                    setState(() => _doira = kalit);
                    _yukla();
                  },
                  child: Container(
                    padding: const EdgeInsets.symmetric(vertical: 11),
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(
                        color: _doira == kalit ? tokens.primary : tokens.border,
                      ),
                    ),
                    child: Text(
                      nom,
                      style: GoogleFonts.inter(
                        fontSize: 12.5,
                        fontWeight: FontWeight.w800,
                        color: _doira == kalit ? tokens.primary : tokens.textMuted,
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }

  Widget _qator(StudentTokens tokens, GameLigaQatori qator) {
    final medal = switch (qator.orin) {
      1 => '🥇',
      2 => '🥈',
      3 => '🥉',
      _ => null,
    };

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
      decoration: BoxDecoration(
        color: qator.men ? tokens.tonedSurface(tokens.primary) : tokens.cardBg,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: qator.men ? tokens.primary : tokens.border,
        ),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 30,
            child: medal != null
                ? Text(medal, style: const TextStyle(fontSize: 18))
                : Text(
                    '${qator.orin}',
                    style: GoogleFonts.inter(
                      fontSize: 13,
                      fontWeight: FontWeight.w800,
                      color: tokens.textDim,
                    ),
                  ),
          ),
          CircleAvatar(
            radius: 16,
            backgroundColor: tokens.surfaceElevated,
            backgroundImage:
                qator.avatar != null ? NetworkImage(qator.avatar!) : null,
            child: qator.avatar != null
                ? null
                : Text(
                    qator.ism.isNotEmpty
                        ? qator.ism.characters.first.toUpperCase()
                        : '?',
                    style: GoogleFonts.inter(
                      fontSize: 12,
                      fontWeight: FontWeight.w800,
                      color: tokens.textMuted,
                    ),
                  ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              qator.men ? '${qator.ism} (siz)' : qator.ism,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: GoogleFonts.inter(
                fontSize: 13.5,
                fontWeight: qator.men ? FontWeight.w900 : FontWeight.w700,
                color: tokens.text,
              ),
            ),
          ),
          Text(
            '${qator.haftaXp} XP',
            style: GoogleFonts.inter(
              fontSize: 12.5,
              fontWeight: FontWeight.w800,
              color: tokens.primary,
            ),
          ),
        ],
      ),
    );
  }

  static String _ligaNomi(String liga) => switch (liga) {
    'olmos' => 'Olmos',
    'oltin' => 'Oltin',
    'kumush' => 'Kumush',
    _ => 'Bronza',
  };
}
