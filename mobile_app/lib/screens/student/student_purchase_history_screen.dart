import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/screens/student/widgets/student_atmospheric_backdrop.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

class StudentPurchaseHistoryScreen extends StatefulWidget {
  const StudentPurchaseHistoryScreen({super.key});

  @override
  State<StudentPurchaseHistoryScreen> createState() => _StudentPurchaseHistoryScreenState();
}

class _StudentPurchaseHistoryScreenState extends State<StudentPurchaseHistoryScreen> {
  bool _loading = true;
  String? _error;
  List<PurchaseRequestModel> _items = const <PurchaseRequestModel>[];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final items = await context.read<StoreService>().fetchMyRequests();
      if (!mounted) return;
      setState(() {
        _items = items;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Xaridlar tarixi yuklanmadi';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Scaffold(
      backgroundColor: tokens.bg,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        foregroundColor: tokens.text,
        title: Text(
          'Xaridlar tarixi',
          style: GoogleFonts.inter(
            fontSize: 16,
            fontWeight: FontWeight.w800,
            color: tokens.text,
          ),
        ),
      ),
      body: Stack(
        children: [
          const StudentAtmosphericBackdrop(),
          SafeArea(
            top: false,
            child: RefreshIndicator(
              color: tokens.primary,
              onRefresh: _load,
              child: _body(tokens),
            ),
          ),
        ],
      ),
    );
  }

  Widget _body(StudentTokens tokens) {
    if (_loading && _items.isEmpty) {
      return Center(
        child: CircularProgressIndicator(color: tokens.primary, strokeWidth: 2.4),
      );
    }
    if (_error != null && _items.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.error_outline_rounded, color: tokens.danger, size: 36),
              const SizedBox(height: 8),
              Text(
                _error!,
                textAlign: TextAlign.center,
                style: GoogleFonts.inter(color: tokens.text, fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 12),
              FilledButton.tonal(
                onPressed: _load,
                child: const Text('Qayta urinish'),
              ),
            ],
          ),
        ),
      );
    }
    if (_items.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.shopping_bag_outlined, color: tokens.textMuted, size: 38),
              const SizedBox(height: 10),
              Text(
                'Hozircha xaridlar yo‘q',
                style: GoogleFonts.inter(
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                  color: tokens.text,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                "Do‘kondan mahsulot tanlab so‘rov yuborganingizdan keyin bu yerda ko‘rinadi.",
                textAlign: TextAlign.center,
                style: GoogleFonts.inter(
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                  color: tokens.textMuted,
                ),
              ),
            ],
          ),
        ),
      );
    }
    return ListView.separated(
      physics: const AlwaysScrollableScrollPhysics(parent: BouncingScrollPhysics()),
      padding: const EdgeInsets.fromLTRB(18, 8, 18, 24),
      itemBuilder: (context, index) => _Row(item: _items[index]),
      separatorBuilder: (_, _) => const SizedBox(height: 8),
      itemCount: _items.length,
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.item});

  final PurchaseRequestModel item;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final palette = _statusPalette(tokens, item.status);
    final dateLabel = DateFormat('d MMM yyyy · HH:mm', 'uz').format(item.createdAt);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: tokens.glass,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: tokens.border),
      ),
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: tokens.tonedSurface(palette.color),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(palette.icon, color: palette.color, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        item.productName.isEmpty ? '—' : item.productName,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: GoogleFonts.inter(
                          fontSize: 13.5,
                          fontWeight: FontWeight.w800,
                          color: tokens.text,
                        ),
                      ),
                    ),
                    if (item.qty > 1)
                      Padding(
                        padding: const EdgeInsets.only(left: 6),
                        child: Text(
                          '×${item.qty}',
                          style: GoogleFonts.inter(
                            fontSize: 12,
                            fontWeight: FontWeight.w800,
                            color: tokens.textMuted,
                          ),
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  dateLabel,
                  style: GoogleFonts.inter(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: tokens.textMuted,
                  ),
                ),
                if (item.managerName.isNotEmpty) ...[
                  const SizedBox(height: 2),
                  Text(
                    'Tasdiqlovchi: ${item.managerName}',
                    style: GoogleFonts.inter(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: tokens.textMuted,
                    ),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(
              color: tokens.tonedSurface(palette.color),
              borderRadius: BorderRadius.circular(100),
              border: Border.all(color: palette.color.withValues(alpha: 0.45)),
            ),
            child: Text(
              palette.label,
              style: GoogleFonts.inter(
                fontSize: 10.5,
                fontWeight: FontWeight.w800,
                color: palette.color,
                letterSpacing: 0.3,
              ),
            ),
          ),
        ],
      ),
    );
  }

  ({Color color, IconData icon, String label}) _statusPalette(StudentTokens t, PurchaseStatus s) {
    switch (s) {
      case PurchaseStatus.approved:
        return (color: t.success, icon: Icons.check_circle_outline_rounded, label: 'Tasdiqlandi');
      case PurchaseStatus.rejected:
        return (color: t.danger, icon: Icons.cancel_outlined, label: 'Rad etildi');
      case PurchaseStatus.pending:
        return (color: t.warning, icon: Icons.schedule_rounded, label: 'Kutilmoqda');
      case PurchaseStatus.unknown:
        return (color: t.textMuted, icon: Icons.help_outline_rounded, label: '—');
    }
  }
}
