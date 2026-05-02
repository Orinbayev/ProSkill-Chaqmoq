import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';

/// Modal bottom sheet that lets a student pick a payment method for an
/// outstanding tuition balance.
///
/// Backend integration: the existing `/api/mobile/payments/` endpoint
/// returns plan items (per-month debt) but no payment-link API exists yet.
/// So each method shows clear instructions and a "Aloqa" button to copy the
/// administrator's phone to the clipboard. When a payment-link API arrives,
/// wire `_PayMethod.click` and `_PayMethod.payme` to launch the URL.
class StudentPaymentActionSheet extends StatelessWidget {
  const StudentPaymentActionSheet({
    super.key,
    required this.summary,
    required this.debtItems,
    required this.center,
  });

  final PaymentSummaryModel summary;
  final List<PaymentModel> debtItems;
  final CenterModel? center;

  static Future<void> show(
    BuildContext context, {
    required PaymentSummaryModel summary,
    required List<PaymentModel> debtItems,
    required CenterModel? center,
  }) {
    return showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (_) => StudentPaymentActionSheet(
        summary: summary,
        debtItems: debtItems,
        center: center,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return SafeArea(
      top: false,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxHeight: MediaQuery.of(context).size.height * 0.92,
        ),
        child: Container(
          margin: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 20),
          decoration: BoxDecoration(
            color: tokens.isDark ? tokens.surfaceElevated : tokens.surface,
            borderRadius: BorderRadius.circular(22),
            border: Border.all(color: tokens.border),
            boxShadow: [
              BoxShadow(color: tokens.shadow, blurRadius: 28, offset: const Offset(0, 8)),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 36,
                  height: 4,
                  decoration: BoxDecoration(
                    color: tokens.textDim,
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
              ),
              const SizedBox(height: 14),
              Row(
                children: [
                  Container(
                    width: 40,
                    height: 40,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      gradient: tokens.primaryGradient,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(Icons.payments_rounded, color: tokens.onPrimary, size: 22),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          "To‘lov qilish",
                          style: GoogleFonts.inter(
                            fontSize: 16,
                            fontWeight: FontWeight.w800,
                            color: tokens.text,
                          ),
                        ),
                        Text(
                          summary.openDebt > 0
                              ? "Jami qarz: ${Formatters.currency(summary.openDebt)}"
                              : "Hozir to‘lov talab etilmaydi",
                          style: GoogleFonts.inter(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: summary.openDebt > 0 ? tokens.warning : tokens.success,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Flexible(
                child: SingleChildScrollView(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (debtItems.isNotEmpty) ...[
                        Text(
                          'QARZ TAFSILOTI',
                          style: GoogleFonts.inter(
                            fontSize: 10.5,
                            fontWeight: FontWeight.w800,
                            color: tokens.textMuted,
                            letterSpacing: 1.4,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Container(
                          decoration: BoxDecoration(
                            color: tokens.glass,
                            borderRadius: BorderRadius.circular(14),
                            border: Border.all(color: tokens.border),
                          ),
                          child: Column(
                            children: [
                              for (var i = 0; i < debtItems.length; i++) ...[
                                _DebtRow(item: debtItems[i]),
                                if (i < debtItems.length - 1)
                                  Container(height: 1, color: tokens.border),
                              ],
                            ],
                          ),
                        ),
                        const SizedBox(height: 16),
                      ],
                      Text(
                        "TO‘LOV USULINI TANLANG",
                        style: GoogleFonts.inter(
                          fontSize: 10.5,
                          fontWeight: FontWeight.w800,
                          color: tokens.textMuted,
                          letterSpacing: 1.4,
                        ),
                      ),
                      const SizedBox(height: 8),
                      _MethodTile(
                        icon: Icons.flash_on_rounded,
                        title: 'Click',
                        subtitle: 'Tezkor onlayn to‘lov',
                        accent: const Color(0xFF1259C3),
                        onTap: () => _showInstructions(
                          context,
                          method: 'Click',
                          steps: const [
                            "Click ilovasini oching",
                            "“Maxsus xizmatlar” bo‘limidan ChaqmoqApp / o‘quv markazini tanlang",
                            "Karta yoki balansdan to‘lovni tasdiqlang",
                            "Chek nusxasini ma’murga yuboring",
                          ],
                        ),
                      ),
                      const SizedBox(height: 8),
                      _MethodTile(
                        icon: Icons.payment_rounded,
                        title: 'Payme',
                        subtitle: 'Onlayn karta orqali',
                        accent: const Color(0xFF00BFA5),
                        onTap: () => _showInstructions(
                          context,
                          method: 'Payme',
                          steps: const [
                            "Payme ilovasidan ChaqmoqApp / markaz xizmatini tanlang",
                            "O‘quvchi ID-ni kiriting va summani tasdiqlang",
                            "To‘lov chekini ma’muriyatga yuboring",
                          ],
                        ),
                      ),
                      const SizedBox(height: 8),
                      _MethodTile(
                        icon: Icons.credit_card_rounded,
                        title: 'Bank kartasi (P2P)',
                        subtitle: 'Markaz kartasiga o‘tkazma',
                        accent: const Color(0xFF6C63FF),
                        onTap: () => _showInstructions(
                          context,
                          method: 'Bank kartasi',
                          steps: [
                            "Markaz ma’muriyati bilan bog‘lanib karta raqamini oling",
                            "Mobil bank ilovasidan o‘tkazmani amalga oshiring",
                            "Chek skrinini ma’murga yuboring",
                            if ((center?.phone ?? '').isNotEmpty)
                              "Markaz aloqa: ${center!.phone}",
                          ],
                          phone: center?.phone,
                        ),
                      ),
                      const SizedBox(height: 8),
                      _MethodTile(
                        icon: Icons.payments_outlined,
                        title: "Naqd o‘qituvchiga",
                        subtitle: 'Markazda yoki darsda',
                        accent: const Color(0xFF2ED573),
                        onTap: () => _showInstructions(
                          context,
                          method: 'Naqd to‘lov',
                          steps: const [
                            "Markazga keling yoki o‘qituvchiga naqd toping",
                            "To‘lov amalga oshirilgach, ma’muriyat tizimga kiritadi",
                            "Bir necha daqiqada qarz miqdori yangilanadi",
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 14),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton(
                  onPressed: () => Navigator.of(context).pop(),
                  style: OutlinedButton.styleFrom(
                    side: BorderSide(color: tokens.border),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    foregroundColor: tokens.text,
                  ),
                  child: Text(
                    'Yopish',
                    style: GoogleFonts.inter(fontSize: 13, fontWeight: FontWeight.w700),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showInstructions(
    BuildContext context, {
    required String method,
    required List<String> steps,
    String? phone,
  }) {
    showDialog<void>(
      context: context,
      builder: (dialogCtx) {
        final tokens = StudentTokens.of(dialogCtx);
        return AlertDialog(
          backgroundColor: tokens.isDark ? tokens.surfaceElevated : tokens.surface,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(18),
            side: BorderSide(color: tokens.border),
          ),
          title: Text(
            method,
            style: GoogleFonts.inter(
              fontSize: 16,
              fontWeight: FontWeight.w800,
              color: tokens.text,
            ),
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              for (var i = 0; i < steps.length; i++)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        width: 22,
                        height: 22,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          color: tokens.tonedSurface(tokens.primary),
                          shape: BoxShape.circle,
                        ),
                        child: Text(
                          '${i + 1}',
                          style: GoogleFonts.inter(
                            fontSize: 11,
                            fontWeight: FontWeight.w800,
                            color: tokens.primary,
                          ),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          steps[i],
                          style: GoogleFonts.inter(
                            fontSize: 12.5,
                            fontWeight: FontWeight.w600,
                            color: tokens.text,
                            height: 1.4,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
          actions: [
            if (phone != null && phone.isNotEmpty)
              TextButton.icon(
                onPressed: () {
                  Clipboard.setData(ClipboardData(text: phone));
                  Navigator.of(dialogCtx).pop();
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Telefon nusxalandi: $phone')),
                  );
                },
                icon: Icon(Icons.copy_rounded, size: 16, color: tokens.primary),
                label: Text(
                  'Telefon nusxalash',
                  style: GoogleFonts.inter(color: tokens.primary, fontWeight: FontWeight.w700),
                ),
              ),
            TextButton(
              onPressed: () => Navigator.of(dialogCtx).pop(),
              child: Text(
                'Tushundim',
                style: GoogleFonts.inter(color: tokens.primary, fontWeight: FontWeight.w800),
              ),
            ),
          ],
        );
      },
    );
  }
}

class _DebtRow extends StatelessWidget {
  const _DebtRow({required this.item});

  final PaymentModel item;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Row(
        children: [
          Container(
            width: 32,
            height: 32,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: tokens.tonedSurface(tokens.warning),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(Icons.schedule_rounded, color: tokens.warning, size: 18),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  item.groupName.isEmpty ? 'Oylik to‘lov' : item.groupName,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w800,
                    color: tokens.text,
                  ),
                ),
                Text(
                  Formatters.shortDayMonth(item.date),
                  style: GoogleFonts.inter(
                    fontSize: 10.5,
                    fontWeight: FontWeight.w600,
                    color: tokens.textMuted,
                  ),
                ),
              ],
            ),
          ),
          Text(
            Formatters.currency(item.amount),
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
}

class _MethodTile extends StatelessWidget {
  const _MethodTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.accent,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final Color accent;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: tokens.glass,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: tokens.border),
          ),
          child: Row(
            children: [
              Container(
                width: 40,
                height: 40,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: accent.withValues(alpha: 0.18),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: accent, size: 22),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      title,
                      style: GoogleFonts.inter(
                        fontSize: 13.5,
                        fontWeight: FontWeight.w800,
                        color: tokens.text,
                      ),
                    ),
                    Text(
                      subtitle,
                      style: GoogleFonts.inter(
                        fontSize: 11.5,
                        fontWeight: FontWeight.w600,
                        color: tokens.textMuted,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(Icons.chevron_right_rounded, color: tokens.textDim, size: 20),
            ],
          ),
        ),
      ),
    );
  }
}
