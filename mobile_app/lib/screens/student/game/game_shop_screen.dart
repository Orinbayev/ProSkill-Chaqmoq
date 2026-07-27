import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/models/game_models.dart';
import 'package:chaqmoq_mobile/providers/game_provider.dart';
import 'package:chaqmoq_mobile/screens/student/game/widgets/game_scaffold.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/widgets/app_state_widgets.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

/// O'yin do'koni — narxlar **chaqmoqda** (o'yin valyutasi).
///
/// Diqqat: bu ChaqmoqApp'ning asosiy do'koni emas. O'yin chaqmog'i markaz
/// balansidan butunlay alohida yuritiladi.
class GameShopScreen extends StatefulWidget {
  const GameShopScreen({super.key});

  @override
  State<GameShopScreen> createState() => _GameShopScreenState();
}

class _GameShopScreenState extends State<GameShopScreen> {
  int? _sotibOlinmoqda;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);

    return GameScaffold(
      sarlavha: 'O‘yin do‘koni',
      yuklash: () => context.read<GameProvider>().dokonYukla(),
      qurilish: (context) {
        final provider = context.watch<GameProvider>();
        final mahsulotlar = provider.mahsulotlar;

        if (mahsulotlar.isEmpty) {
          return ListView(
            padding: const EdgeInsets.symmetric(vertical: 60),
            children: [
              AppEmptyState(
                icon: Icons.storefront_outlined,
                title: 'Do‘kon bo‘sh',
                subtitle: 'Mahsulotlar qo‘shilgach shu yerda ko‘rinadi.',
                dark: tokens.isDark,
              ),
            ],
          );
        }

        return ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              decoration: BoxDecoration(
                color: tokens.tonedSurface(tokens.warning),
                borderRadius: BorderRadius.circular(18),
              ),
              child: Row(
                children: [
                  Icon(Icons.bolt_rounded, color: tokens.warning, size: 22),
                  const SizedBox(width: 10),
                  Text(
                    'Balans: ${_chaqmoqMatni(provider.profil.chaqmoq)} chaqmoq',
                    style: GoogleFonts.inter(
                      fontSize: 14,
                      fontWeight: FontWeight.w800,
                      color: tokens.text,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 14),
            for (final mahsulot in mahsulotlar)
              _mahsulotKartasi(context, tokens, provider, mahsulot),
          ],
        );
      },
    );
  }

  Widget _mahsulotKartasi(
    BuildContext context,
    StudentTokens tokens,
    GameProvider provider,
    GameMahsulot mahsulot,
  ) {
    final yetarli = provider.profil.chaqmoq >= mahsulot.narxChaqmoq;
    final band = _sotibOlinmoqda == mahsulot.id;
    final ochiq = mahsulot.mavjud && yetarli && _sotibOlinmoqda == null;

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
            width: 46,
            height: 46,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: tokens.tonedSurface(tokens.primary),
              borderRadius: BorderRadius.circular(14),
            ),
            child: mahsulot.rasm != null
                ? ClipRRect(
                    borderRadius: BorderRadius.circular(14),
                    child: Image.network(
                      mahsulot.rasm!,
                      width: 46,
                      height: 46,
                      fit: BoxFit.cover,
                      errorBuilder: (_, _, _) =>
                          Icon(mahsulot.ikonka, color: tokens.primary),
                    ),
                  )
                : Icon(mahsulot.ikonka, color: tokens.primary),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  mahsulot.nom,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 14,
                    fontWeight: FontWeight.w800,
                    color: tokens.text,
                  ),
                ),
                if (mahsulot.izoh.isNotEmpty)
                  Text(
                    mahsulot.izoh,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: GoogleFonts.inter(
                      fontSize: 11.5,
                      fontWeight: FontWeight.w500,
                      color: tokens.textMuted,
                      height: 1.3,
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          FilledButton(
            onPressed: ochiq ? () => _sotibOl(context, provider, mahsulot) : null,
            style: FilledButton.styleFrom(
              backgroundColor: tokens.primary,
              foregroundColor: tokens.onPrimary,
              disabledBackgroundColor: tokens.border,
              disabledForegroundColor: tokens.textDim,
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
            child: band
                ? const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Text(
                    !mahsulot.mavjud
                        ? 'Tugadi'
                        : '${_chaqmoqMatni(mahsulot.narxChaqmoq)} ⚡',
                    style: GoogleFonts.inter(
                      fontSize: 12.5,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
          ),
        ],
      ),
    );
  }

  Future<void> _sotibOl(
    BuildContext context,
    GameProvider provider,
    GameMahsulot mahsulot,
  ) async {
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _sotibOlinmoqda = mahsulot.id);
    try {
      final xabar = await provider.sotibOl(mahsulot);
      messenger.showSnackBar(SnackBar(content: Text(xabar)));
    } on ApiException catch (error) {
      messenger.showSnackBar(SnackBar(content: Text(error.message)));
    } catch (error) {
      messenger.showSnackBar(SnackBar(content: Text('$error')));
    } finally {
      if (mounted) setState(() => _sotibOlinmoqda = null);
    }
  }

  static String _chaqmoqMatni(double qiymat) {
    return qiymat == qiymat.roundToDouble()
        ? qiymat.toStringAsFixed(0)
        : qiymat.toStringAsFixed(1);
  }
}
