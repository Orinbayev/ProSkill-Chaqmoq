import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:url_launcher/url_launcher.dart';

/// Sotib olishdan oldingi tasdiq oynasi.
///
/// Tasodifan bosib yuborish chaqmoqni yoki pulni yo'qotmasligi kerak —
/// shuning uchun har xarid oldidan aniq savol beriladi.
Future<bool> gameTasdiq(
  BuildContext context, {
  required String sarlavha,
  required String matn,
  String tasdiqMatni = 'Ha, olaman',
  String bekorMatni = 'Bekor',
  IconData ikonka = Icons.help_outline_rounded,
  Color? rang,
}) async {
  final tokens = StudentTokens.of(context);
  final asosiy = rang ?? tokens.primary;

  final javob = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      backgroundColor: tokens.surfaceElevated,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
      titlePadding: const EdgeInsets.fromLTRB(22, 22, 22, 0),
      contentPadding: const EdgeInsets.fromLTRB(22, 12, 22, 0),
      title: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: tokens.tonedSurface(asosiy),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(ikonka, size: 20, color: asosiy),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              sarlavha,
              style: GoogleFonts.inter(
                fontSize: 17,
                fontWeight: FontWeight.w900,
                color: tokens.text,
                letterSpacing: -0.3,
              ),
            ),
          ),
        ],
      ),
      content: Text(
        matn,
        style: GoogleFonts.inter(
          fontSize: 13.5,
          fontWeight: FontWeight.w500,
          color: tokens.textMuted,
          height: 1.5,
        ),
      ),
      actionsPadding: const EdgeInsets.fromLTRB(16, 8, 16, 14),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(ctx, false),
          child: Text(
            bekorMatni,
            style: GoogleFonts.inter(
              fontWeight: FontWeight.w700,
              color: tokens.textMuted,
            ),
          ),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(ctx, true),
          style: FilledButton.styleFrom(
            backgroundColor: asosiy,
            foregroundColor: Colors.white,
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 11),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          child: Text(
            tasdiqMatni,
            style: GoogleFonts.inter(fontWeight: FontWeight.w800),
          ),
        ),
      ],
    ),
  );

  return javob ?? false;
}

/// Telegram lichkani ochadi va xabar matnini buferga nusxalaydi.
///
/// Telegram havolasi orqali matn oldindan qo'yib bo'lmaydi (faqat botlarga
/// mumkin), shuning uchun matnni buferga qo'yamiz — foydalanuvchi bitta
/// qo'yish (paste) bilan yuboradi.
Future<bool> gameTelegramOch(
  BuildContext context, {
  required String username,
  required String matn,
}) async {
  final messenger = ScaffoldMessenger.of(context);
  final tozaNom = username.trim().replaceAll('@', '');
  if (tozaNom.isEmpty) return false;

  await Clipboard.setData(ClipboardData(text: matn));

  final manzillar = <Uri>[
    Uri.parse('tg://resolve?domain=$tozaNom'),
    Uri.parse('https://t.me/$tozaNom'),
  ];

  for (final uri in manzillar) {
    try {
      final ochildi = await launchUrl(uri, mode: LaunchMode.externalApplication);
      if (ochildi) {
        messenger.showSnackBar(
          const SnackBar(
            content: Text('Xabar nusxalandi — Telegramda qo‘yib yuboring'),
            duration: Duration(seconds: 4),
          ),
        );
        return true;
      }
    } catch (_) {
      // Keyingi manzilni sinaymiz.
    }
  }

  messenger.showSnackBar(
    SnackBar(content: Text('Telegram ochilmadi. @$tozaNom manziliga yozing.')),
  );
  return false;
}
