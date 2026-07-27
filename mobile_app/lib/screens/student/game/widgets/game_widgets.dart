import 'dart:math' as math;

import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/models/game_models.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// O'yin bo'limining umumiy qurilish bloklari.
///
/// Ranglar `StudentTokens` dan olinadi — o'yin o'quvchi panelining bir qismi,
/// alohida ilova emas, shuning uchun light/dark rejim ham avtomatik ishlaydi.

// ═══════════════════════════════════════════════════════════════
// TAYMER
// ═══════════════════════════════════════════════════════════════

/// Aylanma taymer. Vaqt tugashiga yaqinlashganda qizaradi.
class GameTimerRing extends StatelessWidget {
  const GameTimerRing({
    super.key,
    required this.qolgan,
    required this.jami,
    this.olcham = 74,
  });

  final Duration qolgan;
  final Duration jami;
  final double olcham;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final jamiMs = jami.inMilliseconds;
    final ulush = jamiMs <= 0
        ? 0.0
        : (qolgan.inMilliseconds / jamiMs).clamp(0.0, 1.0);

    final rang = ulush > 0.5
        ? tokens.success
        : ulush > 0.25
        ? tokens.warning
        : tokens.danger;

    final soniya = (qolgan.inMilliseconds / 1000).ceil().clamp(0, 999);

    return SizedBox(
      width: olcham,
      height: olcham,
      child: Stack(
        alignment: Alignment.center,
        children: [
          SizedBox.expand(
            child: TweenAnimationBuilder<double>(
              tween: Tween(begin: ulush, end: ulush),
              duration: const Duration(milliseconds: 120),
              builder: (context, qiymat, _) => CircularProgressIndicator(
                value: qiymat,
                strokeWidth: 5,
                strokeCap: StrokeCap.round,
                backgroundColor: tokens.border,
                valueColor: AlwaysStoppedAnimation(rang),
              ),
            ),
          ),
          Text(
            '$soniya',
            style: GoogleFonts.inter(
              fontSize: olcham * 0.34,
              fontWeight: FontWeight.w800,
              color: rang,
              letterSpacing: -0.5,
            ),
          ),
        ],
      ),
    );
  }
}

/// Chiziqli taymer — umumiy vaqt bilan yuradigan o'yinlar (Sprint) uchun.
class GameTimerBar extends StatelessWidget {
  const GameTimerBar({super.key, required this.qolgan, required this.jami});

  final Duration qolgan;
  final Duration jami;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final jamiMs = jami.inMilliseconds;
    final ulush = jamiMs <= 0
        ? 0.0
        : (qolgan.inMilliseconds / jamiMs).clamp(0.0, 1.0);
    final rang = ulush > 0.4
        ? tokens.primary
        : ulush > 0.2
        ? tokens.warning
        : tokens.danger;

    return Row(
      children: [
        Icon(Icons.timer_outlined, size: 16, color: rang),
        const SizedBox(width: 8),
        Expanded(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              value: ulush,
              minHeight: 8,
              backgroundColor: tokens.border,
              valueColor: AlwaysStoppedAnimation(rang),
            ),
          ),
        ),
        const SizedBox(width: 10),
        Text(
          '${(qolgan.inMilliseconds / 1000).ceil().clamp(0, 999)}s',
          style: GoogleFonts.inter(
            fontSize: 13,
            fontWeight: FontWeight.w800,
            color: rang,
          ),
        ),
      ],
    );
  }
}

// ═══════════════════════════════════════════════════════════════
// JAVOB VARIANTI
// ═══════════════════════════════════════════════════════════════

enum GameJavobHolati { odatiy, tanlangan, togri, xato }

class GameAnswerCard extends StatelessWidget {
  const GameAnswerCard({
    super.key,
    required this.matn,
    required this.holat,
    this.onTap,
  });

  final String matn;
  final GameJavobHolati holat;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);

    final (Color fon, Color chegara, Color matnRangi, IconData? belgi) =
        switch (holat) {
          GameJavobHolati.togri => (
            tokens.tonedSurface(tokens.success),
            tokens.success,
            tokens.success,
            Icons.check_circle_rounded,
          ),
          GameJavobHolati.xato => (
            tokens.tonedSurface(tokens.danger),
            tokens.danger,
            tokens.danger,
            Icons.cancel_rounded,
          ),
          GameJavobHolati.tanlangan => (
            tokens.tonedSurface(tokens.primary),
            tokens.primary,
            tokens.text,
            null,
          ),
          GameJavobHolati.odatiy => (
            tokens.cardBg,
            tokens.border,
            tokens.text,
            null,
          ),
        };

    return AnimatedContainer(
      duration: const Duration(milliseconds: 180),
      curve: Curves.easeOut,
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: fon,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: chegara,
          width: holat == GameJavobHolati.odatiy ? 1 : 1.6,
        ),
      ),
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(16),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 15),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    matn,
                    style: GoogleFonts.inter(
                      fontSize: 15,
                      fontWeight: FontWeight.w700,
                      color: matnRangi,
                    ),
                  ),
                ),
                if (belgi != null) Icon(belgi, size: 20, color: matnRangi),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════
// SAVOL KARTASI
// ═══════════════════════════════════════════════════════════════

class GameSavolKartasi extends StatelessWidget {
  const GameSavolKartasi({super.key, required this.savol, this.izoh});

  final GameSavol savol;
  final String? izoh;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);

    return Column(
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
          decoration: BoxDecoration(
            color: tokens.cardBg,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: tokens.border),
          ),
          child: Column(
            children: [
              Text(
                savol.yoriqnoma.toUpperCase(),
                textAlign: TextAlign.center,
                style: GoogleFonts.inter(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  color: tokens.textDim,
                  letterSpacing: 1,
                ),
              ),
              if (savol.rasm != null) ...[
                const SizedBox(height: 14),
                ClipRRect(
                  borderRadius: BorderRadius.circular(14),
                  child: Image.network(
                    savol.rasm!,
                    height: 130,
                    fit: BoxFit.cover,
                    errorBuilder: (_, _, _) => const SizedBox.shrink(),
                  ),
                ),
              ],
              const SizedBox(height: 12),
              Text(
                savol.matn,
                textAlign: TextAlign.center,
                style: GoogleFonts.inter(
                  fontSize: 26,
                  fontWeight: FontWeight.w800,
                  color: tokens.text,
                  letterSpacing: -0.6,
                  height: 1.2,
                ),
              ),
            ],
          ),
        ),
        if (izoh != null && izoh!.isNotEmpty) ...[
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.lightbulb_outline_rounded, size: 16, color: tokens.info),
              const SizedBox(width: 6),
              Flexible(
                child: Text(
                  izoh!,
                  textAlign: TextAlign.center,
                  style: GoogleFonts.inter(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w600,
                    color: tokens.info,
                  ),
                ),
              ),
            ],
          ),
        ],
      ],
    );
  }
}

// ═══════════════════════════════════════════════════════════════
// KO'RSATKICHLAR
// ═══════════════════════════════════════════════════════════════

class GameStatChip extends StatelessWidget {
  const GameStatChip({
    super.key,
    required this.ikonka,
    required this.matn,
    required this.rang,
    this.onTap,
  });

  final IconData ikonka;
  final String matn;
  final Color rang;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);

    return Material(
      color: tokens.tonedSurface(rang),
      borderRadius: BorderRadius.circular(999),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(999),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 7),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(ikonka, size: 15, color: rang),
              const SizedBox(width: 5),
              Text(
                matn,
                style: GoogleFonts.inter(
                  fontSize: 12.5,
                  fontWeight: FontWeight.w800,
                  color: rang,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Javob nuqtalari — kim nechtasini to'g'ri bilgani bir qarashda ko'rinadi.
class GameJavobNuqtalari extends StatelessWidget {
  const GameJavobNuqtalari({
    super.key,
    required this.javoblar,
    required this.jami,
    this.chapga = true,
  });

  final List<bool> javoblar;
  final int jami;
  final bool chapga;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    // Juda uzun o'yinlarda nuqtalar sig'masligi mumkin — cheklaymiz.
    final korinadigan = math.min(jami, 12);

    return Row(
      mainAxisAlignment: chapga ? MainAxisAlignment.start : MainAxisAlignment.end,
      children: List.generate(korinadigan, (i) {
        final berilgan = i < javoblar.length;
        final rang = berilgan
            ? (javoblar[i] ? tokens.success : tokens.danger)
            : tokens.border;

        return AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          width: 7,
          height: 7,
          margin: const EdgeInsets.symmetric(horizontal: 1.5),
          decoration: BoxDecoration(color: rang, shape: BoxShape.circle),
        );
      }),
    );
  }
}

/// Jonlar qatori — to'lgani rangli, sarflangani bo'sh.
class GameJonlar extends StatelessWidget {
  const GameJonlar({super.key, required this.jon, required this.maxJon});

  final int jon;
  final int maxJon;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final korinadigan = math.min(math.max(maxJon, jon), 6);

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        for (var i = 0; i < korinadigan; i++)
          Padding(
            padding: const EdgeInsets.only(right: 3),
            child: Icon(
              i < jon ? Icons.favorite_rounded : Icons.favorite_border_rounded,
              size: 16,
              color: i < jon ? tokens.danger : tokens.textDim,
            ),
          ),
        if (maxJon > korinadigan)
          Text(
            ' +${maxJon - korinadigan}',
            style: GoogleFonts.inter(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: tokens.textMuted,
            ),
          ),
      ],
    );
  }
}

// ═══════════════════════════════════════════════════════════════
// O'YIN KARTASI (katalog)
// ═══════════════════════════════════════════════════════════════

class GameOyinKartasi extends StatelessWidget {
  const GameOyinKartasi({
    super.key,
    required this.oyin,
    required this.qollabQuvvatlanadi,
    required this.onTap,
  });

  final GameOyin oyin;

  /// Ilovada shu motor uchun ekran bormi. Yo'q bo'lsa — "ilovani yangilang".
  final bool qollabQuvvatlanadi;

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final rang = oyin.rang(tokens.primary);
    final ochiq = oyin.ochiq && qollabQuvvatlanadi;

    final qulfMatni = !qollabQuvvatlanadi
        ? 'Ilovani yangilang'
        : oyin.qulfMatni;
    // Qulflangan o'yin "yopiq" emas — shunchaki navbati kelmagan, shuning
    // uchun ogohlantirish rangi emas, xotirjam ko'k bilan ko'rsatiladi.
    final qulflangan = qollabQuvvatlanadi && oyin.qulf == 'oyin_qulflangan';

    return Opacity(
      opacity: ochiq ? 1 : 0.62,
      child: Material(
        color: tokens.cardBg,
        borderRadius: BorderRadius.circular(22),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(22),
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(22),
              border: Border.all(
                color: ochiq ? tokens.tonedBorder(rang) : tokens.border,
              ),
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  rang.withValues(alpha: tokens.isDark ? 0.16 : 0.10),
                  Colors.transparent,
                ],
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      width: 42,
                      height: 42,
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        color: tokens.tonedSurface(rang),
                        borderRadius: BorderRadius.circular(14),
                      ),
                      child: Text(
                        oyin.ikonka,
                        style: const TextStyle(fontSize: 21),
                      ),
                    ),
                    const Spacer(),
                    if (oyin.qulf == 'oyin_qulflangan')
                      Icon(Icons.timelapse_rounded, size: 16, color: tokens.info)
                    else if (!ochiq)
                      Icon(Icons.lock_rounded, size: 16, color: tokens.textDim)
                    else if (oyin.faqatPro)
                      Icon(Icons.workspace_premium_rounded,
                          size: 16, color: tokens.warning),
                  ],
                ),
                const SizedBox(height: 12),
                Text(
                  oyin.nom,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                    color: tokens.text,
                    letterSpacing: -0.3,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  oyin.izoh,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                    color: tokens.textMuted,
                    height: 1.35,
                  ),
                ),
                const SizedBox(height: 12),
                if (qulfMatni != null)
                  Row(
                    children: [
                      Icon(
                        qulflangan
                            ? Icons.schedule_rounded
                            : Icons.info_outline_rounded,
                        size: 13,
                        color: qulflangan ? tokens.info : tokens.warning,
                      ),
                      const SizedBox(width: 4),
                      Expanded(
                        child: Text(
                          qulflangan ? '$qulfMatni qoldi' : qulfMatni,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: GoogleFonts.inter(
                            fontSize: 11.5,
                            fontWeight: FontWeight.w700,
                            color: qulflangan ? tokens.info : tokens.warning,
                          ),
                        ),
                      ),
                    ],
                  )
                else
                  Row(
                    children: [
                      _Belgi(
                        ikonka: Icons.help_outline_rounded,
                        matn: '${oyin.savollarSoni}',
                        rang: tokens.textMuted,
                      ),
                      const SizedBox(width: 10),
                      if (oyin.jonNarxi > 0)
                        _Belgi(
                          ikonka: Icons.favorite_rounded,
                          matn: '${oyin.jonNarxi}',
                          rang: tokens.danger,
                        )
                      else
                        _Belgi(
                          ikonka: Icons.all_inclusive_rounded,
                          matn: 'Bepul',
                          rang: tokens.success,
                        ),
                    ],
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Belgi extends StatelessWidget {
  const _Belgi({required this.ikonka, required this.matn, required this.rang});

  final IconData ikonka;
  final String matn;
  final Color rang;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(ikonka, size: 13, color: rang),
        const SizedBox(width: 3),
        Text(
          matn,
          style: GoogleFonts.inter(
            fontSize: 11.5,
            fontWeight: FontWeight.w700,
            color: rang,
          ),
        ),
      ],
    );
  }
}

// ═══════════════════════════════════════════════════════════════
// O'YINDAN CHIQISH TASDIG'I
// ═══════════════════════════════════════════════════════════════

Future<bool> gameChiqishSorovi(BuildContext context, {required bool jonKetadi}) async {
  final tokens = StudentTokens.of(context);

  final javob = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      backgroundColor: tokens.surfaceElevated,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      title: Text(
        'O‘yindan chiqasizmi?',
        style: GoogleFonts.inter(
          fontSize: 17,
          fontWeight: FontWeight.w800,
          color: tokens.text,
        ),
      ),
      content: Text(
        jonKetadi
            ? 'O‘yin yakunlanmagan hisoblanadi va sarflangan jon qaytmaydi.'
            : 'Hozirgi natijangiz saqlanadi.',
        style: GoogleFonts.inter(
          fontSize: 13.5,
          fontWeight: FontWeight.w500,
          color: tokens.textMuted,
          height: 1.45,
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(ctx, false),
          child: Text(
            'Davom etish',
            style: GoogleFonts.inter(
              fontWeight: FontWeight.w700,
              color: tokens.primary,
            ),
          ),
        ),
        TextButton(
          onPressed: () => Navigator.pop(ctx, true),
          child: Text(
            'Chiqish',
            style: GoogleFonts.inter(
              fontWeight: FontWeight.w700,
              color: tokens.danger,
            ),
          ),
        ),
      ],
    ),
  );

  return javob ?? false;
}
