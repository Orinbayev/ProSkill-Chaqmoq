import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/models/game_models.dart';
import 'package:chaqmoq_mobile/providers/game_provider.dart';
import 'package:chaqmoq_mobile/screens/student/game/widgets/game_scaffold.dart';
import 'package:chaqmoq_mobile/widgets/app_state_widgets.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

/// O'yin tarixi — duel va yakka o'yinlar bitta ro'yxatda, sana bo'yicha.
class GameHistoryScreen extends StatelessWidget {
  const GameHistoryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);

    return GameScaffold(
      sarlavha: 'O‘yin tarixi',
      yuklash: () => context.read<GameProvider>().tarixYukla(),
      qurilish: (context) {
        final tarix = context.watch<GameProvider>().tarix;

        if (tarix.isEmpty) {
          return ListView(
            padding: const EdgeInsets.symmetric(vertical: 60),
            children: [
              AppEmptyState(
                icon: Icons.history_rounded,
                title: 'Hali o‘yin o‘ynamagansiz',
                subtitle: 'Birinchi o‘yiningizdan keyin natijalar shu yerda chiqadi.',
                dark: tokens.isDark,
              ),
            ],
          );
        }

        return ListView.builder(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
          itemCount: tarix.length,
          itemBuilder: (context, i) => _qator(tokens, tarix[i]),
        );
      },
    );
  }

  Widget _qator(StudentTokens tokens, GameTarix element) {
    final rang = rangdanColor(element.rangHex, tokens.primary);

    final (String natijaMatni, Color natijaRangi) = element.duel
        ? switch (element.natija) {
            'galaba' => ('G‘alaba', tokens.success),
            'maglubiyat' => ('Mag‘lubiyat', tokens.danger),
            _ => ('Durrang', tokens.warning),
          }
        : (
            '${element.togriJavoblar}/${element.jamiSavol}',
            element.jamiSavol > 0 &&
                    element.togriJavoblar / element.jamiSavol >= 0.8
                ? tokens.success
                : tokens.textMuted,
          );

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: tokens.cardBg,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: tokens.border),
      ),
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: tokens.tonedSurface(rang),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Text(element.ikonka, style: const TextStyle(fontSize: 19)),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  element.duel ? '${element.nom} bilan duel' : element.nom,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w800,
                    color: tokens.text,
                  ),
                ),
                const SizedBox(height: 2),
                Row(
                  children: [
                    Text(
                      natijaMatni,
                      style: GoogleFonts.inter(
                        fontSize: 11.5,
                        fontWeight: FontWeight.w800,
                        color: natijaRangi,
                      ),
                    ),
                    if (element.duel) ...[
                      Text(
                        ' · ${element.ball}:${element.raqibBall}',
                        style: GoogleFonts.inter(
                          fontSize: 11.5,
                          fontWeight: FontWeight.w600,
                          color: tokens.textMuted,
                        ),
                      ),
                    ],
                    if (element.sana != null)
                      Text(
                        ' · ${DateFormat('d-MMM, HH:mm', 'uz').format(element.sana!)}',
                        style: GoogleFonts.inter(
                          fontSize: 11.5,
                          fontWeight: FontWeight.w500,
                          color: tokens.textDim,
                        ),
                      ),
                  ],
                ),
              ],
            ),
          ),
          Text(
            '+${_chaqmoqMatni(element.olinganChaqmoq)} ⚡',
            style: GoogleFonts.inter(
              fontSize: 12.5,
              fontWeight: FontWeight.w800,
              color: tokens.warning,
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
