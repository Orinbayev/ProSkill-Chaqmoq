import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/models/game_models.dart';
import 'package:chaqmoq_mobile/providers/game_provider.dart';
import 'package:chaqmoq_mobile/screens/student/game/widgets/game_confirm.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

/// Tariflar — o'yinni tezlashtirish.
///
/// Bepul rejada 3 jon har 8 soatda tiklanadi va o'ynalgan o'yin 24 soatga
/// yopiladi. Tarif ikkala kutishni ham qisqartiradi (va chaqmoq bonusi beradi).
class GameTariffScreen extends StatefulWidget {
  const GameTariffScreen({super.key});

  @override
  State<GameTariffScreen> createState() => _GameTariffScreenState();
}

class _GameTariffScreenState extends State<GameTariffScreen> {
  GameTariflar? _malumot;
  bool _yuklanmoqda = true;
  String? _xato;
  int? _sotibOlinmoqda;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _yukla());
  }

  Future<void> _yukla() async {
    try {
      final malumot = await context.read<GameProvider>().tariflar();
      if (!mounted) return;
      setState(() {
        _malumot = malumot;
        _yuklanmoqda = false;
        _xato = null;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _yuklanmoqda = false;
        _xato = error is ApiException ? error.message : 'Tariflar yuklanmadi';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);

    return Scaffold(
      backgroundColor: tokens.bg,
      appBar: AppBar(
        backgroundColor: tokens.bg,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
        iconTheme: IconThemeData(color: tokens.text),
        title: Text(
          'Tariflar',
          style: GoogleFonts.inter(
            fontSize: 17,
            fontWeight: FontWeight.w900,
            color: tokens.text,
            letterSpacing: -0.3,
          ),
        ),
      ),
      body: _tarkib(tokens),
    );
  }

  Widget _tarkib(StudentTokens tokens) {
    if (_yuklanmoqda) {
      return Center(child: CircularProgressIndicator(color: tokens.primary));
    }
    if (_xato != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(28),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                _xato!,
                textAlign: TextAlign.center,
                style: GoogleFonts.inter(color: tokens.textMuted),
              ),
              const SizedBox(height: 14),
              TextButton(
                onPressed: () {
                  setState(() => _yuklanmoqda = true);
                  _yukla();
                },
                child: const Text('Qayta urinish'),
              ),
            ],
          ),
        ),
      );
    }

    final malumot = _malumot!;
    return RefreshIndicator(
      color: tokens.primary,
      onRefresh: _yukla,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 28),
        children: [
          _joriyReja(tokens, malumot),
          if (malumot.kutayotganSorov != null) ...[
            const SizedBox(height: 12),
            _kutayotganSorov(tokens, malumot.kutayotganSorov!),
          ],
          const SizedBox(height: 20),
          Text(
            'Tezlashtirish',
            style: GoogleFonts.inter(
              fontSize: 16,
              fontWeight: FontWeight.w900,
              color: tokens.text,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'Tarif jonlarni tezroq tiklaydi va o‘ynalgan o‘yinni ertaroq ochadi.',
            style: GoogleFonts.inter(
              fontSize: 12.5,
              fontWeight: FontWeight.w500,
              color: tokens.textMuted,
              height: 1.45,
            ),
          ),
          const SizedBox(height: 14),
          for (final tarif in malumot.tariflar)
            _tarifKartasi(tokens, tarif, malumot),
        ],
      ),
    );
  }

  Widget _joriyReja(StudentTokens tokens, GameTariflar malumot) {
    final reja = malumot.joriy;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        gradient: tokens.heroGradient,
        border: Border.all(color: tokens.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                malumot.proMi
                    ? Icons.workspace_premium_rounded
                    : Icons.person_outline_rounded,
                size: 19,
                color: malumot.proMi ? tokens.warning : tokens.textMuted,
              ),
              const SizedBox(width: 8),
              Text(
                malumot.joriyTarif ?? 'Bepul reja',
                style: GoogleFonts.inter(
                  fontSize: 16,
                  fontWeight: FontWeight.w900,
                  color: tokens.text,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _qator(tokens, Icons.favorite_rounded,
              '${reja.jonSoni} ta jon har ${reja.jonSoat} soatda'),
          _qator(tokens, Icons.lock_clock_rounded,
              'O‘ynalgan o‘yin ${reja.oyinQulfSoat} soatda ochiladi'),
          if (reja.chaqmoqBonusFoiz > 0)
            _qator(tokens, Icons.bolt_rounded,
                'Har o‘yindan +${reja.chaqmoqBonusFoiz}% chaqmoq'),
          if (malumot.tugaydi != null)
            _qator(tokens, Icons.event_rounded,
                'Amal qiladi: ${malumot.tugaydi!.day}.${malumot.tugaydi!.month}.${malumot.tugaydi!.year}'),
        ],
      ),
    );
  }

  Widget _kutayotganSorov(StudentTokens tokens, String tarif) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: tokens.tonedSurface(tokens.warning),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          Icon(Icons.hourglass_top_rounded, size: 17, color: tokens.warning),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              '«$tarif» uchun to‘lov kutilmoqda. To‘lov tasdiqlangach '
              'tarif avtomatik yoqiladi.',
              style: GoogleFonts.inter(
                fontSize: 12.5,
                fontWeight: FontWeight.w600,
                color: tokens.warning,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _qator(StudentTokens tokens, IconData ikonka, String matn) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          Icon(ikonka, size: 15, color: tokens.textMuted),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              matn,
              style: GoogleFonts.inter(
                fontSize: 12.5,
                fontWeight: FontWeight.w600,
                color: tokens.textMuted,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _tarifKartasi(
    StudentTokens tokens,
    GameTarif tarif,
    GameTariflar malumot,
  ) {
    final bepul = malumot.bepul;
    final band = _sotibOlinmoqda == tarif.id;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: tokens.cardBg,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: tarif.joriy ? tokens.primary : tokens.border,
          width: tarif.joriy ? 1.6 : 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      tarif.nom,
                      style: GoogleFonts.inter(
                        fontSize: 17,
                        fontWeight: FontWeight.w900,
                        color: tokens.text,
                        letterSpacing: -0.3,
                      ),
                    ),
                    Text(
                      '${tarif.kun} kun · haftasiga ~${_som(tarif.haftalikNarx)}',
                      style: GoogleFonts.inter(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: tokens.textDim,
                      ),
                    ),
                  ],
                ),
              ),
              Text(
                _som(tarif.narxSom),
                style: GoogleFonts.inter(
                  fontSize: 17,
                  fontWeight: FontWeight.w900,
                  color: tokens.primary,
                  letterSpacing: -0.4,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _foyda(
            tokens,
            Icons.favorite_rounded,
            '${tarif.jonSoni} jon har ${tarif.jonSoat} soatda',
            '${bepul.jonSoni} jon / ${bepul.jonSoat} soat',
          ),
          _foyda(
            tokens,
            Icons.lock_clock_rounded,
            'O‘yin ${tarif.oyinQulfSoat} soatda ochiladi',
            '${bepul.oyinQulfSoat} soat',
          ),
          if (tarif.chaqmoqBonusFoiz > 0)
            _foyda(
              tokens,
              Icons.bolt_rounded,
              '+${tarif.chaqmoqBonusFoiz}% chaqmoq',
              'bonussiz',
            ),
          const SizedBox(height: 14),
          if (tarif.joriy)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 12),
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: tokens.tonedSurface(tokens.success),
                borderRadius: BorderRadius.circular(14),
              ),
              child: Text(
                'Joriy tarifingiz',
                style: GoogleFonts.inter(
                  fontSize: 13,
                  fontWeight: FontWeight.w800,
                  color: tokens.success,
                ),
              ),
            )
          else
            Row(
              children: [
                Expanded(
                  child: FilledButton(
                    onPressed: band ? null : () => _sotibOl(tarif, 'click'),
                    style: FilledButton.styleFrom(
                      backgroundColor: tokens.primary,
                      foregroundColor: tokens.onPrimary,
                      padding: const EdgeInsets.symmetric(vertical: 13),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14),
                      ),
                    ),
                    child: band
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : Text(
                            'Click orqali',
                            style: GoogleFonts.inter(
                              fontSize: 13.5,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton(
                    onPressed: band ? null : () => _sotibOl(tarif, 'naqd'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: tokens.text,
                      side: BorderSide(color: tokens.border),
                      padding: const EdgeInsets.symmetric(vertical: 13),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14),
                      ),
                    ),
                    child: Text(
                      'Naqd',
                      style: GoogleFonts.inter(
                        fontSize: 13.5,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                ),
              ],
            ),
        ],
      ),
    );
  }

  /// Tarif nima berishini bepul reja bilan yonma-yon ko'rsatadi.
  Widget _foyda(
    StudentTokens tokens,
    IconData ikonka,
    String tarifda,
    String bepulda,
  ) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 7),
      child: Row(
        children: [
          Icon(ikonka, size: 15, color: tokens.success),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              tarifda,
              style: GoogleFonts.inter(
                fontSize: 12.5,
                fontWeight: FontWeight.w700,
                color: tokens.text,
              ),
            ),
          ),
          Text(
            bepulda,
            style: GoogleFonts.inter(
              fontSize: 11.5,
              fontWeight: FontWeight.w500,
              color: tokens.textDim,
              decoration: TextDecoration.lineThrough,
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _sotibOl(GameTarif tarif, String usul) async {
    final usulNomi = usul == 'naqd' ? 'Naqd' : 'Click';

    // Tasodifan bosilib ketmasin — avval aniq so'raymiz.
    final tasdiq = await gameTasdiq(
      context,
      sarlavha: '${tarif.nom} tarifi',
      matn:
          '${_som(tarif.narxSom)} — ${tarif.kun} kunga.\n\n'
          '$usulNomi usulini tanladingiz. Tasdiqlasangiz so‘rov yuboriladi '
          'va to‘lovni kelishish uchun Telegram ochiladi.',
      tasdiqMatni: 'Ha, davom etaman',
      ikonka: Icons.rocket_launch_rounded,
    );
    if (!tasdiq || !mounted) return;

    final messenger = ScaffoldMessenger.of(context);
    setState(() => _sotibOlinmoqda = tarif.id);

    try {
      final natija = await context.read<GameProvider>().tarifSotibOl(
        tarif.id,
        usul: usul,
      );
      if (!mounted) return;

      if (natija.telegramUsername.isNotEmpty) {
        await gameTelegramOch(
          context,
          username: natija.telegramUsername,
          matn: natija.telegramMatn,
        );
      } else {
        messenger.showSnackBar(SnackBar(content: Text(natija.xabar)));
      }
      await _yukla();
    } on ApiException catch (error) {
      messenger.showSnackBar(SnackBar(content: Text(error.message)));
    } catch (error) {
      messenger.showSnackBar(SnackBar(content: Text('$error')));
    } finally {
      if (mounted) setState(() => _sotibOlinmoqda = null);
    }
  }

  static String _som(int qiymat) {
    final matn = qiymat.toString();
    final bulaklar = <String>[];
    for (var i = matn.length; i > 0; i -= 3) {
      bulaklar.insert(0, matn.substring(i - 3 < 0 ? 0 : i - 3, i));
    }
    return '${bulaklar.join(' ')} so‘m';
  }
}
