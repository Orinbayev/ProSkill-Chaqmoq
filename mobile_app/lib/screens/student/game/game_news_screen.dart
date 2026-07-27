import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/models/game_models.dart';
import 'package:chaqmoq_mobile/providers/game_provider.dart';
import 'package:chaqmoq_mobile/screens/student/game/widgets/game_scaffold.dart';
import 'package:chaqmoq_mobile/widgets/app_state_widgets.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

/// O'yin yangiliklari — admin paneldan kiritiladi.
class GameNewsScreen extends StatelessWidget {
  const GameNewsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);

    return GameScaffold(
      sarlavha: 'Yangiliklar',
      yuklash: () => context.read<GameProvider>().yangiliklarYukla(),
      qurilish: (context) {
        final yangiliklar = context.watch<GameProvider>().yangiliklar;

        if (yangiliklar.isEmpty) {
          return ListView(
            padding: const EdgeInsets.symmetric(vertical: 60),
            children: [
              AppEmptyState(
                icon: Icons.campaign_outlined,
                title: 'Yangilik yo‘q',
                subtitle: 'Yangi e’lonlar shu yerda chiqadi.',
                dark: tokens.isDark,
              ),
            ],
          );
        }

        return ListView.builder(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
          itemCount: yangiliklar.length,
          itemBuilder: (context, i) => _karta(tokens, yangiliklar[i]),
        );
      },
    );
  }

  Widget _karta(StudentTokens tokens, GameYangilik yangilik) {
    final (String belgi, Color rang) = switch (yangilik.tur) {
      'turnir' => ('Turnir', tokens.warning),
      'elon' => ('E’lon', tokens.info),
      'yangilanish' => ('Yangilanish', tokens.success),
      _ => ('Yangilik', tokens.primary),
    };

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: tokens.cardBg,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: yangilik.muhim ? tokens.tonedBorder(rang) : tokens.border,
        ),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (yangilik.rasm != null)
            Image.network(
              yangilik.rasm!,
              height: 140,
              width: double.infinity,
              fit: BoxFit.cover,
              errorBuilder: (_, _, _) => const SizedBox.shrink(),
            ),
          Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 3,
                      ),
                      decoration: BoxDecoration(
                        color: tokens.tonedSurface(rang),
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Text(
                        belgi,
                        style: GoogleFonts.inter(
                          fontSize: 10.5,
                          fontWeight: FontWeight.w800,
                          color: rang,
                        ),
                      ),
                    ),
                    const Spacer(),
                    if (yangilik.sana != null)
                      Text(
                        DateFormat('d-MMMM', 'uz').format(yangilik.sana!),
                        style: GoogleFonts.inter(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: tokens.textDim,
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 10),
                Text(
                  yangilik.sarlavha,
                  style: GoogleFonts.inter(
                    fontSize: 15,
                    fontWeight: FontWeight.w900,
                    color: tokens.text,
                    letterSpacing: -0.2,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  yangilik.matn,
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                    color: tokens.textMuted,
                    height: 1.5,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
