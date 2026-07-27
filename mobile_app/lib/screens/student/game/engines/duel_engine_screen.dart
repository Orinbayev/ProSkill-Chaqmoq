import 'dart:async';

import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/models/game_models.dart';
import 'package:chaqmoq_mobile/providers/game_provider.dart';
import 'package:chaqmoq_mobile/screens/student/game/widgets/game_widgets.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

/// Duel motori — raqib bilan yonma-yon poyga.
///
/// Raqibning javoblari serverda duel boshlanishida hisoblab qo'yilgan, lekin
/// ilovaga faqat shu savolgacha yig'ilgan bali beriladi. Shu sababli hisob
/// bosqichma-bosqich ochiladi va poyga hissi saqlanadi.
class DuelEngineScreen extends StatefulWidget {
  const DuelEngineScreen({
    super.key,
    required this.oyin,
    required this.boshlanish,
  });

  final GameOyin oyin;
  final GameBoshlanish boshlanish;

  @override
  State<DuelEngineScreen> createState() => _DuelEngineScreenState();
}

class _DuelEngineScreenState extends State<DuelEngineScreen> {
  static const _javobKutish = Duration(milliseconds: 1500);

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

  int _ball = 0;
  int _raqibBall = 0;
  final List<bool> _javoblar = [];
  final List<bool> _raqibJavoblari = [];

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
        _ball = natija.ball;
        _raqibBall = natija.raqibJami;
        _javoblar.add(natija.togri);
        _raqibJavoblari.add(natija.raqibTogri);
        _yuborilmoqda = false;
      });

      await Future<void>.delayed(_javobKutish);
      if (!mounted) return;

      if (_indeks + 1 >= _jamiSavol) {
        await _yakunla();
      } else {
        setState(() => _indeks++);
        _savolniBoshla();
      }
    } catch (error) {
      if (!mounted) return;
      setState(() => _yuborilmoqda = false);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$error')));
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
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$error')));
    }
  }

  Future<void> _chiqishSorovi() async {
    if (_javobBerilgan || _yuborilmoqda || _yakunlanmoqda) return;

    _taymer?.cancel();
    final pauzaBoshi = DateTime.now();

    final chiq = await gameChiqishSorovi(context, jonKetadi: widget.oyin.jonNarxi > 0);
    if (!mounted) return;

    if (chiq) {
      await _yakunla();
    } else {
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
              Align(
                alignment: Alignment.centerLeft,
                child: IconButton(
                  onPressed: _chiqishSorovi,
                  icon: Icon(Icons.close_rounded, color: tokens.textMuted),
                  tooltip: 'Dueldan chiqish',
                ),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: _hisob(tokens),
              ),
              const SizedBox(height: 14),
              _progress(tokens),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
                  child: Column(
                    children: [
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

  Widget _hisob(StudentTokens tokens) {
    final profil = context.watch<GameProvider>().profil;

    return Row(
      children: [
        Expanded(
          child: _oyinchi(
            tokens,
            ism: profil.ism,
            avatar: profil.avatar,
            ball: _ball,
            javoblar: _javoblar,
            meniki: true,
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: tokens.surfaceElevated,
              borderRadius: BorderRadius.circular(999),
            ),
            child: Text(
              'VS',
              style: GoogleFonts.inter(
                fontSize: 12,
                fontWeight: FontWeight.w900,
                color: tokens.textDim,
              ),
            ),
          ),
        ),
        Expanded(
          child: _oyinchi(
            tokens,
            ism: widget.boshlanish.raqibNomi ?? 'Raqib',
            avatar: widget.boshlanish.raqibAvatar,
            ball: _raqibBall,
            javoblar: _raqibJavoblari,
            meniki: false,
          ),
        ),
      ],
    );
  }

  Widget _oyinchi(
    StudentTokens tokens, {
    required String ism,
    required String? avatar,
    required int ball,
    required List<bool> javoblar,
    required bool meniki,
  }) {
    final avatarWidget = Container(
      padding: const EdgeInsets.all(2),
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: meniki ? tokens.primary : tokens.border,
      ),
      child: CircleAvatar(
        radius: 19,
        backgroundColor: tokens.surfaceElevated,
        backgroundImage: avatar != null ? NetworkImage(avatar) : null,
        child: avatar != null
            ? null
            : Text(
                ism.isNotEmpty ? ism.characters.first.toUpperCase() : '?',
                style: GoogleFonts.inter(
                  fontSize: 14,
                  fontWeight: FontWeight.w800,
                  color: tokens.textMuted,
                ),
              ),
      ),
    );

    final matn = Column(
      crossAxisAlignment:
          meniki ? CrossAxisAlignment.start : CrossAxisAlignment.end,
      children: [
        Text(
          ism,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: GoogleFonts.inter(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: tokens.textMuted,
          ),
        ),
        Text(
          '$ball',
          style: GoogleFonts.inter(
            fontSize: 24,
            fontWeight: FontWeight.w900,
            color: tokens.text,
            letterSpacing: -0.8,
          ),
        ).animate(key: ValueKey('$meniki-$ball')).scaleXY(
          begin: 1.25,
          end: 1,
          duration: 260.ms,
          curve: Curves.easeOut,
        ),
      ],
    );

    return Column(
      crossAxisAlignment:
          meniki ? CrossAxisAlignment.start : CrossAxisAlignment.end,
      children: [
        Row(
          mainAxisAlignment:
              meniki ? MainAxisAlignment.start : MainAxisAlignment.end,
          children: meniki
              ? [avatarWidget, const SizedBox(width: 8), Flexible(child: matn)]
              : [Flexible(child: matn), const SizedBox(width: 8), avatarWidget],
        ),
        const SizedBox(height: 6),
        GameJavobNuqtalari(
          javoblar: javoblar,
          jami: _jamiSavol,
          chapga: meniki,
        ),
      ],
    );
  }

  Widget _progress(StudentTokens tokens) {
    return Text(
      '${_indeks + 1} / $_jamiSavol',
      style: GoogleFonts.inter(
        fontSize: 12,
        fontWeight: FontWeight.w700,
        color: tokens.textDim,
      ),
    );
  }
}
