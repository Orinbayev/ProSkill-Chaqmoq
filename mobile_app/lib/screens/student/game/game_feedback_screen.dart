import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/models/game_models.dart';
import 'package:chaqmoq_mobile/providers/game_provider.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

/// Shikoyat va takliflar — o'quvchi to'g'ridan-to'g'ri adminга yozadi.
class GameFeedbackScreen extends StatefulWidget {
  const GameFeedbackScreen({super.key});

  @override
  State<GameFeedbackScreen> createState() => _GameFeedbackScreenState();
}

class _GameFeedbackScreenState extends State<GameFeedbackScreen> {
  static const _turlar = [
    ('taklif', 'Taklif', Icons.lightbulb_outline_rounded),
    ('shikoyat', 'Shikoyat', Icons.report_gmailerrorred_rounded),
    ('xato', 'Xatolik', Icons.bug_report_outlined),
  ];

  final _matnCtrl = TextEditingController();
  String _tanlanganTur = 'taklif';
  List<GameMurojaat> _murojaatlar = const [];
  bool _yuklanmoqda = true;
  bool _yuborilmoqda = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _yukla());
  }

  @override
  void dispose() {
    _matnCtrl.dispose();
    super.dispose();
  }

  Future<void> _yukla() async {
    try {
      final royxat = await context.read<GameProvider>().murojaatlar();
      if (!mounted) return;
      setState(() {
        _murojaatlar = royxat;
        _yuklanmoqda = false;
      });
    } catch (_) {
      if (mounted) setState(() => _yuklanmoqda = false);
    }
  }

  Future<void> _yubor() async {
    final matn = _matnCtrl.text.trim();
    final messenger = ScaffoldMessenger.of(context);

    if (matn.length < 5) {
      messenger.showSnackBar(
        const SnackBar(content: Text('Xabar juda qisqa')),
      );
      return;
    }

    setState(() => _yuborilmoqda = true);
    try {
      final xabar = await context.read<GameProvider>().murojaatYubor(
        tur: _tanlanganTur,
        matn: matn,
      );
      _matnCtrl.clear();
      messenger.showSnackBar(SnackBar(content: Text(xabar)));
      await _yukla();
    } on ApiException catch (error) {
      messenger.showSnackBar(SnackBar(content: Text(error.message)));
    } catch (error) {
      messenger.showSnackBar(SnackBar(content: Text('$error')));
    } finally {
      if (mounted) setState(() => _yuborilmoqda = false);
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
          'Shikoyat va takliflar',
          style: GoogleFonts.inter(
            fontSize: 17,
            fontWeight: FontWeight.w900,
            color: tokens.text,
            letterSpacing: -0.3,
          ),
        ),
      ),
      body: ListView(
        padding: EdgeInsets.fromLTRB(
          16,
          8,
          16,
          24 + MediaQuery.viewInsetsOf(context).bottom,
        ),
        children: [
          _yozishBloki(tokens),
          const SizedBox(height: 22),
          if (!_yuklanmoqda && _murojaatlar.isNotEmpty) ...[
            Text(
              'Yuborilganlar',
              style: GoogleFonts.inter(
                fontSize: 15,
                fontWeight: FontWeight.w900,
                color: tokens.text,
              ),
            ),
            const SizedBox(height: 10),
            for (final murojaat in _murojaatlar) _murojaatKartasi(tokens, murojaat),
          ],
        ],
      ),
    );
  }

  Widget _yozishBloki(StudentTokens tokens) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: tokens.cardBg,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: tokens.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Nima haqida yozmoqchisiz?',
            style: GoogleFonts.inter(
              fontSize: 14,
              fontWeight: FontWeight.w800,
              color: tokens.text,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              for (final (kalit, nom, ikonka) in _turlar)
                Expanded(
                  child: Padding(
                    padding: EdgeInsets.only(right: kalit == 'xato' ? 0 : 8),
                    child: _turTugmasi(tokens, kalit, nom, ikonka),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 14),
          TextField(
            controller: _matnCtrl,
            maxLines: 5,
            maxLength: 1000,
            style: GoogleFonts.inter(fontSize: 14, color: tokens.text),
            decoration: InputDecoration(
              hintText: 'Fikringizni yozing…',
              hintStyle: GoogleFonts.inter(color: tokens.textDim, fontSize: 14),
              filled: true,
              fillColor: tokens.surfaceElevated,
              counterStyle: GoogleFonts.inter(fontSize: 11, color: tokens.textDim),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(14),
                borderSide: BorderSide(color: tokens.border),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(14),
                borderSide: BorderSide(color: tokens.border),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(14),
                borderSide: BorderSide(color: tokens.primary, width: 1.6),
              ),
            ),
          ),
          const SizedBox(height: 6),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: _yuborilmoqda ? null : _yubor,
              icon: _yuborilmoqda
                  ? const SizedBox(
                      width: 15,
                      height: 15,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.send_rounded, size: 18),
              label: Text(
                _yuborilmoqda ? 'Yuborilmoqda…' : 'Yuborish',
                style: GoogleFonts.inter(fontWeight: FontWeight.w800),
              ),
              style: FilledButton.styleFrom(
                backgroundColor: tokens.primary,
                foregroundColor: tokens.onPrimary,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _turTugmasi(
    StudentTokens tokens,
    String kalit,
    String nom,
    IconData ikonka,
  ) {
    final tanlangan = _tanlanganTur == kalit;
    return Material(
      color: tanlangan ? tokens.tonedSurface(tokens.primary) : tokens.surfaceElevated,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () => setState(() => _tanlanganTur = kalit),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 11),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: tanlangan ? tokens.primary : tokens.border,
            ),
          ),
          child: Column(
            children: [
              Icon(
                ikonka,
                size: 18,
                color: tanlangan ? tokens.primary : tokens.textMuted,
              ),
              const SizedBox(height: 4),
              Text(
                nom,
                style: GoogleFonts.inter(
                  fontSize: 11.5,
                  fontWeight: FontWeight.w700,
                  color: tanlangan ? tokens.primary : tokens.textMuted,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _murojaatKartasi(StudentTokens tokens, GameMurojaat murojaat) {
    final (Color rang, String belgi) = switch (murojaat.holat) {
      'hal' => (tokens.success, 'Hal qilindi'),
      'korildi' => (tokens.info, 'Ko‘rib chiqilmoqda'),
      _ => (tokens.textMuted, 'Yangi'),
    };

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: tokens.cardBg,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: tokens.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
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
              Text(
                murojaat.turNomi,
                style: GoogleFonts.inter(
                  fontSize: 11.5,
                  fontWeight: FontWeight.w600,
                  color: tokens.textDim,
                ),
              ),
              if (murojaat.sana != null) ...[
                Text(
                  ' · ${DateFormat('d-MMM', 'uz').format(murojaat.sana!)}',
                  style: GoogleFonts.inter(
                    fontSize: 11.5,
                    fontWeight: FontWeight.w500,
                    color: tokens.textDim,
                  ),
                ),
              ],
            ],
          ),
          const SizedBox(height: 8),
          Text(
            murojaat.matn,
            style: GoogleFonts.inter(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: tokens.text,
              height: 1.45,
            ),
          ),
          if (murojaat.javobBor) ...[
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(11),
              decoration: BoxDecoration(
                color: tokens.tonedSurface(tokens.success),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.reply_rounded, size: 15, color: tokens.success),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      murojaat.javob,
                      style: GoogleFonts.inter(
                        fontSize: 12.5,
                        fontWeight: FontWeight.w600,
                        color: tokens.success,
                        height: 1.4,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}
