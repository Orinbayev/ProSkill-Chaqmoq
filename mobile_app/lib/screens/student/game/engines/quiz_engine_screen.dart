import 'dart:async';

import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/models/game_models.dart';
import 'package:chaqmoq_mobile/providers/game_provider.dart';
import 'package:chaqmoq_mobile/screens/student/game/widgets/game_widgets.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

/// Viktorina motori — savolma-savol, har biriga alohida taymer.
///
/// Shu ekran **«Omon qol»** motorini ham yuritadi: farqi faqat sozlamadagi
/// `ruxsat_xato` — belgilangan xatodan keyin o'yin darhol tugaydi. Ikkalasi
/// bitta ekran, chunki mexanika bir xil, faqat tugash sharti boshqacha.
class QuizEngineScreen extends StatefulWidget {
  const QuizEngineScreen({
    super.key,
    required this.oyin,
    required this.boshlanish,
  });

  final GameOyin oyin;
  final GameBoshlanish boshlanish;

  @override
  State<QuizEngineScreen> createState() => _QuizEngineScreenState();
}

class _QuizEngineScreenState extends State<QuizEngineScreen> {
  static const _javobKutish = Duration(milliseconds: 1400);

  late final int _ruxsatXato = widget.oyin.sozlamaInt('ruxsat_xato', 0);
  late final Duration _savolVaqti = Duration(
    seconds: widget.boshlanish.savolSoniya > 0 ? widget.boshlanish.savolSoniya : 10,
  );

  int _indeks = 0;
  Duration _qolgan = Duration.zero;
  Timer? _taymer;
  DateTime _savolBoshlandi = DateTime.now();

  String? _tanlangan;
  GameJavobNatijasi? _natija;
  bool _yuborilmoqda = false;
  bool _yakunlanmoqda = false;

  final List<bool> _javoblar = [];
  int _xatolar = 0;

  bool get _omonQol => _ruxsatXato > 0;
  bool get _javobBerilgan => _natija != null;
  GameSavol get _savol => widget.boshlanish.savollar[_indeks];
  int get _jamiSavol => widget.boshlanish.savollar.length;

  @override
  void initState() {
    super.initState();
    _savolniBoshla();
  }

  @override
  void dispose() {
    _taymer?.cancel();
    super.dispose();
  }

  void _savolniBoshla() {
    _taymer?.cancel();
    setState(() {
      _qolgan = _savolVaqti;
      _tanlangan = null;
      _natija = null;
      _savolBoshlandi = DateTime.now();
    });
    _taymerniIshgaTushir();
  }

  void _taymerniIshgaTushir() {
    _taymer?.cancel();
    _taymer = Timer.periodic(const Duration(milliseconds: 100), (t) {
      final qolgan = _savolVaqti - DateTime.now().difference(_savolBoshlandi);
      if (qolgan <= Duration.zero) {
        t.cancel();
        // Vaqt tugadi — bo'sh javob noto'g'ri hisoblanadi.
        _javobYubor('');
        return;
      }
      if (mounted) setState(() => _qolgan = qolgan);
    });
  }

  Future<void> _javobYubor(String tanlangan) async {
    if (_javobBerilgan || _yuborilmoqda || _yakunlanmoqda) return;

    _taymer?.cancel();
    final sarflangan = DateTime.now().difference(_savolBoshlandi).inMilliseconds;

    setState(() {
      _tanlangan = tanlangan;
      _yuborilmoqda = true;
    });

    try {
      final natija = await context.read<GameProvider>().javobYubor(
        oyin: widget.boshlanish,
        tartib: _savol.tartib,
        tanlangan: tanlangan,
        sarflanganMs: sarflangan.clamp(0, _savolVaqti.inMilliseconds),
      );

      if (!mounted) return;
      setState(() {
        _natija = natija;
        _javoblar.add(natija.togri);
        if (!natija.togri) _xatolar++;
        _yuborilmoqda = false;
      });

      await Future<void>.delayed(_javobKutish);
      if (!mounted) return;

      final jonTugadi = _omonQol && _xatolar >= _ruxsatXato;
      if (jonTugadi || _indeks + 1 >= _jamiSavol) {
        await _yakunla();
      } else {
        setState(() => _indeks++);
        _savolniBoshla();
      }
    } catch (error) {
      if (!mounted) return;
      setState(() => _yuborilmoqda = false);
      _xatoKorsat(error);
      // Javob yozilmadi — taymerni davom ettiramiz, o'quvchi qayta urinsin.
      _savolBoshlandi = DateTime.now();
      _taymerniIshgaTushir();
    }
  }

  Future<void> _yakunla() async {
    if (_yakunlanmoqda) return;
    _yakunlanmoqda = true;
    _taymer?.cancel();

    final navigator = Navigator.of(context);
    try {
      final natija = await context.read<GameProvider>().yakunla(widget.boshlanish);
      if (!mounted) return;
      navigator.pop(natija);
    } catch (error) {
      if (!mounted) return;
      _yakunlanmoqda = false;
      _xatoKorsat(error);
    }
  }

  void _xatoKorsat(Object error) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('$error')),
    );
  }

  Future<void> _chiqishSorovi() async {
    if (_yuborilmoqda || _yakunlanmoqda) return;

    _taymer?.cancel();
    final pauzaBoshi = DateTime.now();

    final chiq = await gameChiqishSorovi(context, jonKetadi: widget.oyin.jonNarxi > 0);
    if (!mounted) return;

    if (chiq) {
      // Chiqishda ham natijani yopamiz — topilgan chaqmoq yo'qolmasin.
      await _yakunla();
    } else if (!_javobBerilgan) {
      _savolBoshlandi = _savolBoshlandi.add(DateTime.now().difference(pauzaBoshi));
      _taymerniIshgaTushir();
    }
  }

  GameJavobHolati _holat(String variant) {
    if (!_javobBerilgan) {
      return _tanlangan == variant
          ? GameJavobHolati.tanlangan
          : GameJavobHolati.odatiy;
    }
    if (variant == _natija!.togriJavob) return GameJavobHolati.togri;
    if (variant == _tanlangan) return GameJavobHolati.xato;
    return GameJavobHolati.odatiy;
  }

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _chiqishSorovi();
      },
      child: Scaffold(
        backgroundColor: tokens.bg,
        body: SafeArea(
          child: Column(
            children: [
              _sarlavha(tokens),
              const SizedBox(height: 6),
              _progress(tokens),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
                  child: Column(
                    children: [
                      if (_savolVaqti > Duration.zero)
                        GameTimerRing(
                          qolgan: _javobBerilgan ? Duration.zero : _qolgan,
                          jami: _savolVaqti,
                        ),
                      const SizedBox(height: 18),
                      GameSavolKartasi(
                        savol: _savol,
                        izoh: _javobBerilgan ? _natija!.izoh : null,
                      ),
                    ],
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 12),
                child: Column(
                  children: [
                    for (final variant in _savol.variantlar)
                      GameAnswerCard(
                        matn: variant,
                        holat: _holat(variant),
                        onTap: () => _javobYubor(variant),
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

  Widget _sarlavha(StudentTokens tokens) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(6, 6, 16, 0),
      child: Row(
        children: [
          IconButton(
            onPressed: _chiqishSorovi,
            icon: Icon(Icons.close_rounded, color: tokens.textMuted),
            tooltip: 'O‘yindan chiqish',
          ),
          Expanded(
            child: Text(
              widget.oyin.nom,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: GoogleFonts.inter(
                fontSize: 15,
                fontWeight: FontWeight.w800,
                color: tokens.text,
              ),
            ),
          ),
          if (_omonQol)
            GameJonlar(
              jon: (_ruxsatXato - _xatolar).clamp(0, _ruxsatXato),
              maxJon: _ruxsatXato,
            )
          else
            GameStatChip(
              ikonka: Icons.check_circle_outline_rounded,
              matn: '${_natija?.togriJavoblar ?? _javoblar.where((e) => e).length}',
              rang: tokens.success,
            ),
        ],
      ),
    );
  }

  Widget _progress(StudentTokens tokens) {
    return Column(
      children: [
        Text(
          _omonQol
              ? 'Savol ${_indeks + 1}'
              : '${_indeks + 1} / $_jamiSavol',
          style: GoogleFonts.inter(
            fontSize: 12,
            fontWeight: FontWeight.w700,
            color: tokens.textDim,
          ),
        ),
        const SizedBox(height: 8),
        GameJavobNuqtalari(javoblar: _javoblar, jami: _jamiSavol),
      ],
    ).animate(key: ValueKey(_indeks)).fadeIn(duration: 220.ms);
  }
}
