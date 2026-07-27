import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/models/game_models.dart';
import 'package:chaqmoq_mobile/providers/game_provider.dart';
import 'package:chaqmoq_mobile/screens/student/game/engines/duel_engine_screen.dart';
import 'package:chaqmoq_mobile/screens/student/game/engines/match_engine_screen.dart';
import 'package:chaqmoq_mobile/screens/student/game/engines/memory_engine_screen.dart';
import 'package:chaqmoq_mobile/screens/student/game/engines/quiz_engine_screen.dart';
import 'package:chaqmoq_mobile/screens/student/game/engines/sprint_engine_screen.dart';
import 'package:chaqmoq_mobile/screens/student/game/game_matchmaking_screen.dart';
import 'package:chaqmoq_mobile/screens/student/game/game_result_screen.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

/// Motor registri — motor kaliti → o'sha mexanikaning ekrani.
///
/// Admin panelda yangi **o'yin** qo'shilsa bu yerga hech narsa qo'shish shart
/// emas: o'yin katalogdan keladi va mos motor ekranida ochiladi. Bu yerga
/// qo'shish faqat yangi **mexanika** yozilganda kerak bo'ladi.
typedef _MotorQuruvchi = Widget Function(GameOyin oyin, GameBoshlanish boshlanish);

final Map<String, _MotorQuruvchi> _motorlar = <String, _MotorQuruvchi>{
  'duel': (oyin, boshlanish) =>
      DuelEngineScreen(oyin: oyin, boshlanish: boshlanish),
  'viktorina': (oyin, boshlanish) =>
      QuizEngineScreen(oyin: oyin, boshlanish: boshlanish),
  // «Omon qol» ham viktorina ekrani — farqi sozlamadagi `ruxsat_xato`da.
  'omon_qol': (oyin, boshlanish) =>
      QuizEngineScreen(oyin: oyin, boshlanish: boshlanish),
  'sprint': (oyin, boshlanish) =>
      SprintEngineScreen(oyin: oyin, boshlanish: boshlanish),
  'xotira': (oyin, boshlanish) =>
      MemoryEngineScreen(oyin: oyin, boshlanish: boshlanish),
  'juftlash': (oyin, boshlanish) =>
      MatchEngineScreen(oyin: oyin, boshlanish: boshlanish),
};

bool gameMotorQollabQuvvatlanadi(String motor) => _motorlar.containsKey(motor);

// ═══════════════════════════════════════════════════════════════
// O'YIN OLDI OYNASI
// ═══════════════════════════════════════════════════════════════

/// Katalog kartasi bosilganda ochiladi: qoida, narx va "Boshlash".
Future<void> gameOyinOchish(BuildContext context, GameOyin oyin) async {
  final tokens = StudentTokens.of(context);
  final provider = context.read<GameProvider>();
  final qollabQuvvatlanadi = gameMotorQollabQuvvatlanadi(oyin.motor);
  final motorTavsifi = provider.motorTavsifi(oyin.motor);

  final boshlansin = await showModalBottomSheet<bool>(
    context: context,
    backgroundColor: Colors.transparent,
    isScrollControlled: true,
    builder: (ctx) {
      final rang = oyin.rang(tokens.primary);
      return Container(
        decoration: BoxDecoration(
          color: tokens.surfaceElevated,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(26)),
          border: Border.all(color: tokens.border),
        ),
        padding: EdgeInsets.fromLTRB(
          22,
          12,
          22,
          22 + MediaQuery.of(ctx).padding.bottom,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: tokens.border,
                  borderRadius: BorderRadius.circular(999),
                ),
              ),
            ),
            const SizedBox(height: 20),
            Row(
              children: [
                Container(
                  width: 52,
                  height: 52,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: tokens.tonedSurface(rang),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Text(oyin.ikonka, style: const TextStyle(fontSize: 26)),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        oyin.nom,
                        style: GoogleFonts.inter(
                          fontSize: 19,
                          fontWeight: FontWeight.w900,
                          color: tokens.text,
                          letterSpacing: -0.4,
                        ),
                      ),
                      Text(
                        oyin.motorNomi,
                        style: GoogleFonts.inter(
                          fontSize: 12.5,
                          fontWeight: FontWeight.w600,
                          color: tokens.textMuted,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Text(
              qollabQuvvatlanadi
                  ? (oyin.yoriqnoma.isNotEmpty
                        ? oyin.yoriqnoma
                        : (motorTavsifi?.yoriqnoma ?? oyin.izoh))
                  : 'Bu o‘yin ilovaning yangi versiyasini talab qiladi. '
                        'App Store yoki Play Market’dan ChaqmoqApp’ni yangilang.',
              style: GoogleFonts.inter(
                fontSize: 13.5,
                fontWeight: FontWeight.w500,
                color: tokens.textMuted,
                height: 1.5,
              ),
            ),
            const SizedBox(height: 18),
            Row(
              children: [
                _Xususiyat(
                  ikonka: Icons.help_outline_rounded,
                  sarlavha: '${oyin.savollarSoni}',
                  izoh: 'savol',
                ),
                _Xususiyat(
                  ikonka: Icons.timer_outlined,
                  sarlavha: oyin.savolSoniya > 0 ? '${oyin.savolSoniya}s' : '∞',
                  izoh: oyin.savolSoniya > 0 ? 'savolga' : 'taymersiz',
                ),
                _Xususiyat(
                  ikonka: Icons.favorite_rounded,
                  sarlavha: oyin.jonNarxi > 0 ? '${oyin.jonNarxi}' : '0',
                  izoh: 'jon',
                ),
                _Xususiyat(
                  ikonka: Icons.trending_up_rounded,
                  sarlavha: '${oyin.xpMukofot}',
                  izoh: 'XP gacha',
                ),
              ],
            ),
            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: (oyin.ochiq && qollabQuvvatlanadi)
                    ? () => Navigator.pop(ctx, true)
                    : null,
                style: FilledButton.styleFrom(
                  backgroundColor: rang,
                  foregroundColor: Colors.white,
                  disabledBackgroundColor: tokens.border,
                  disabledForegroundColor: tokens.textDim,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
                child: Text(
                  _tugmaMatni(oyin, qollabQuvvatlanadi),
                  style: GoogleFonts.inter(
                    fontSize: 15,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ),
          ],
        ),
      );
    },
  );

  if (boshlansin != true || !context.mounted) return;
  await _oyinniIshgaTushir(context, oyin);
}

String _tugmaMatni(GameOyin oyin, bool qollabQuvvatlanadi) {
  if (!qollabQuvvatlanadi) return 'Ilovani yangilang';
  return switch (oyin.qulf) {
    'pro_kerak' => 'Tarif kerak',
    'jon_yoq' => 'Jonlar tugadi',
    'savol_yetarli_emas' => 'Savollar yetarli emas',
    _ => 'Boshlash',
  };
}

class _Xususiyat extends StatelessWidget {
  const _Xususiyat({
    required this.ikonka,
    required this.sarlavha,
    required this.izoh,
  });

  final IconData ikonka;
  final String sarlavha;
  final String izoh;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Expanded(
      child: Column(
        children: [
          Icon(ikonka, size: 17, color: tokens.textMuted),
          const SizedBox(height: 5),
          Text(
            sarlavha,
            style: GoogleFonts.inter(
              fontSize: 15,
              fontWeight: FontWeight.w900,
              color: tokens.text,
            ),
          ),
          Text(
            izoh,
            style: GoogleFonts.inter(
              fontSize: 10.5,
              fontWeight: FontWeight.w600,
              color: tokens.textDim,
            ),
          ),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════
// ISHGA TUSHIRISH
// ═══════════════════════════════════════════════════════════════

/// O'yinni serverdan boshlaydi, mos motor ekranini ochadi va natijani
/// ko'rsatadi. «Yana o'ynash» shu funksiyani qayta chaqiradi.
Future<void> _oyinniIshgaTushir(BuildContext context, GameOyin oyin) async {
  final provider = context.read<GameProvider>();
  final navigator = Navigator.of(context);
  final messenger = ScaffoldMessenger.of(context);

  final quruvchi = _motorlar[oyin.motor];
  if (quruvchi == null) {
    messenger.showSnackBar(
      const SnackBar(content: Text('Bu o‘yin uchun ilovani yangilash kerak.')),
    );
    return;
  }

  final yuklanmoqdaniYop = _yuklanmoqdaKorsat(context);

  GameBoshlanish boshlanish;
  try {
    boshlanish = await provider.oyinBoshla(oyin);
  } on ApiException catch (error) {
    yuklanmoqdaniYop();
    messenger.showSnackBar(SnackBar(content: Text(error.message)));
    // Jon tugagan bo'lishi mumkin — katalogdagi holatni yangilaymiz.
    await provider.refresh();
    return;
  } catch (error) {
    yuklanmoqdaniYop();
    messenger.showSnackBar(SnackBar(content: Text('$error')));
    return;
  }

  yuklanmoqdaniYop();

  // Duel motorida server avval jonli raqib qidiradi — kutish ekranini ochamiz.
  if (boshlanish.navbatId > 0) {
    final topilgan = await navigator.push<GameBoshlanish>(
      MaterialPageRoute(
        builder: (_) => GameMatchmakingScreen(oyin: oyin, navbat: boshlanish),
      ),
    );
    if (topilgan == null) {
      // O'quvchi kutishni bekor qildi — jon sarflanmagan.
      await provider.refresh();
      return;
    }
    boshlanish = topilgan;
  }

  if (boshlanish.savollar.isEmpty) {
    messenger.showSnackBar(
      const SnackBar(content: Text('Bu o‘yin uchun savollar topilmadi.')),
    );
    return;
  }

  final natija = await navigator.push<GameNatija>(
    MaterialPageRoute(builder: (_) => quruvchi(oyin, boshlanish)),
  );

  if (natija == null) return;
  await provider.natijaniQabulQil(natija);
  if (!context.mounted) return;

  await navigator.push<void>(
    MaterialPageRoute(
      builder: (resultContext) => GameResultScreen(
        natija: natija,
        qaytaOynash: () {
          Navigator.of(resultContext).pop();
          _oyinniIshgaTushir(context, oyin);
        },
      ),
    ),
  );
}

/// Yuklanish oynasini ochadi va uni yopadigan funksiyani qaytaradi.
///
/// `showDialog` marshrutni darhol (sinxron) qo'shadi, shuning uchun qaytgan
/// funksiya xavfsiz: u aynan shu oynani yopadi, tagidagi ekranni emas.
VoidCallback _yuklanmoqdaKorsat(BuildContext context) {
  final tokens = StudentTokens.of(context);
  final navigator = Navigator.of(context, rootNavigator: true);

  showDialog<void>(
    context: context,
    barrierDismissible: false,
    useRootNavigator: true,
    builder: (_) => Center(
      child: Container(
        padding: const EdgeInsets.all(22),
        decoration: BoxDecoration(
          color: tokens.surfaceElevated,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(color: tokens.primary, strokeWidth: 3),
            const SizedBox(height: 14),
            Text(
              'Tayyorlanmoqda…',
              style: GoogleFonts.inter(
                fontSize: 13,
                fontWeight: FontWeight.w700,
                color: tokens.textMuted,
              ),
            ),
          ],
        ),
      ),
    ),
  );

  var yopilgan = false;
  return () {
    if (yopilgan) return;
    yopilgan = true;
    navigator.pop();
  };
}
