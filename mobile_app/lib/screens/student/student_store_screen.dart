import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/chaqmoq_history_provider.dart';
import 'package:chaqmoq_mobile/screens/student/student_purchase_history_screen.dart';
import 'package:chaqmoq_mobile/screens/student/widgets/student_atmospheric_backdrop.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

class StudentStoreScreen extends StatefulWidget {
  const StudentStoreScreen({super.key});

  @override
  State<StudentStoreScreen> createState() => _StudentStoreScreenState();
}

class _StudentStoreScreenState extends State<StudentStoreScreen> {
  bool _loading = true;
  String? _error;
  List<StoreProductModel> _products = const <StoreProductModel>[];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      context.read<ChaqmoqHistoryProvider>().load();
    });
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final products = await context.read<StoreService>().fetchProducts();
      if (!mounted) return;
      setState(() {
        _products = products;
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
        _error = "Do‘kon yuklanmadi";
        _loading = false;
      });
    }
  }

  Future<void> _refresh() async {
    await Future.wait<void>([
      _load(),
      context.read<ChaqmoqHistoryProvider>().refresh(),
    ]);
  }

  void _openHistory() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => const StudentPurchaseHistoryScreen(),
      ),
    );
  }

  Future<void> _openPurchaseSheet(StoreProductModel product, int balance) async {
    final ok = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) => _PurchaseSheet(product: product, balance: balance),
    );
    if (ok == true && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text('Xarid so‘rovi yuborildi. Manager tasdiqlashini kuting.'),
          duration: const Duration(seconds: 3),
        ),
      );
      await context.read<ChaqmoqHistoryProvider>().refresh();
    }
  }

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final balance = context.watch<ChaqmoqHistoryProvider>().balance;
    return Scaffold(
      backgroundColor: tokens.bg,
      body: Stack(
        children: [
          const StudentAtmosphericBackdrop(),
          SafeArea(
            child: RefreshIndicator(
              color: tokens.primary,
              onRefresh: _refresh,
              child: _body(tokens, balance),
            ),
          ),
        ],
      ),
    );
  }

  Widget _body(StudentTokens tokens, int balance) {
    return CustomScrollView(
      physics: const AlwaysScrollableScrollPhysics(parent: BouncingScrollPhysics()),
      slivers: [
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(18, 8, 18, 0),
          sliver: SliverToBoxAdapter(
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    "Do‘kon",
                    style: GoogleFonts.inter(
                      fontSize: 19,
                      fontWeight: FontWeight.w800,
                      color: tokens.text,
                      letterSpacing: -0.2,
                    ),
                  ),
                ),
                _IconBtn(icon: Icons.history_rounded, onTap: _openHistory),
              ],
            ),
          ),
        ),
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(18, 12, 18, 0),
          sliver: SliverToBoxAdapter(child: _BalanceHero(balance: balance)),
        ),
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(18, 14, 18, 0),
          sliver: SliverToBoxAdapter(
            child: Text(
              'MAHSULOTLAR',
              style: GoogleFonts.inter(
                fontSize: 11,
                fontWeight: FontWeight.w800,
                color: tokens.textMuted,
                letterSpacing: 1.6,
              ),
            ),
          ),
        ),
        if (_loading && _products.isEmpty)
          SliverFillRemaining(
            hasScrollBody: false,
            child: Center(
              child: CircularProgressIndicator(color: tokens.primary, strokeWidth: 2.4),
            ),
          )
        else if (_error != null && _products.isEmpty)
          SliverFillRemaining(
            hasScrollBody: false,
            child: _ErrorBox(message: _error!, onRetry: _load),
          )
        else if (_products.isEmpty)
          SliverFillRemaining(
            hasScrollBody: false,
            child: Center(
              child: Text(
                "Hozircha do‘konda mahsulot yo‘q",
                style: GoogleFonts.inter(
                  color: tokens.textMuted,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          )
        else
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(14, 8, 14, 24),
            sliver: SliverGrid(
              gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
                maxCrossAxisExtent: 220,
                crossAxisSpacing: 10,
                mainAxisSpacing: 10,
                childAspectRatio: 0.66,
              ),
              delegate: SliverChildBuilderDelegate(
                (context, index) {
                  final p = _products[index];
                  return _ProductCard(
                    product: p,
                    balance: balance,
                    onTap: () => _openPurchaseSheet(p, balance),
                  );
                },
                childCount: _products.length,
              ),
            ),
          ),
      ],
    );
  }
}

class _BalanceHero extends StatelessWidget {
  const _BalanceHero({required this.balance});

  final int balance;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: tokens.heroGradient,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: tokens.primary.withValues(alpha: 0.28)),
      ),
      child: Row(
        children: [
          Container(
            width: 56,
            height: 56,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: tokens.violetTealGradient,
            ),
            child: const Icon(Icons.bolt_rounded, color: Colors.white, size: 28),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'SIZNING CHAQMOQLARINGIZ',
                  style: GoogleFonts.inter(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    color: tokens.textMuted,
                    letterSpacing: 1.6,
                  ),
                ),
                const SizedBox(height: 4),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    Text(
                      Formatters.number(balance),
                      style: GoogleFonts.inter(
                        fontSize: 26,
                        fontWeight: FontWeight.w800,
                        color: tokens.text,
                        letterSpacing: -0.4,
                      ),
                    ),
                    const SizedBox(width: 6),
                    Icon(Icons.bolt_rounded, color: tokens.primary, size: 20),
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  "Do‘kondan mahsulot tanlang va so‘rov yuboring",
                  style: GoogleFonts.inter(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: tokens.textMuted,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ProductCard extends StatelessWidget {
  const _ProductCard({
    required this.product,
    required this.balance,
    required this.onTap,
  });

  final StoreProductModel product;
  final int balance;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final canAfford = balance >= product.priceChaqmoq;
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          decoration: BoxDecoration(
            color: tokens.glass,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: tokens.border),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Expanded(
                child: ClipRRect(
                  borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
                  child: _ProductImage(url: product.imageUrl),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(10, 8, 10, 10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      product.name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: GoogleFonts.inter(
                        fontSize: 13,
                        fontWeight: FontWeight.w800,
                        color: tokens.text,
                        height: 1.15,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: [
                        Flexible(
                          child: Text(
                            Formatters.number(product.priceChaqmoq),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: GoogleFonts.inter(
                              fontSize: 14,
                              fontWeight: FontWeight.w800,
                              color: canAfford ? tokens.primary : tokens.textMuted,
                              letterSpacing: -0.3,
                            ),
                          ),
                        ),
                        const SizedBox(width: 3),
                        Icon(
                          Icons.bolt_rounded,
                          color: canAfford ? tokens.primary : tokens.textMuted,
                          size: 14,
                        ),
                        const Spacer(),
                        if (product.soldCount > 0)
                          Text(
                            '${product.soldCount}',
                            style: GoogleFonts.inter(
                              fontSize: 10.5,
                              fontWeight: FontWeight.w700,
                              color: tokens.textMuted,
                            ),
                          ),
                      ],
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
}

class _ProductImage extends StatelessWidget {
  const _ProductImage({required this.url});

  final String url;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    if (url.isEmpty) {
      return Container(
        color: tokens.glassStrong,
        alignment: Alignment.center,
        child: Icon(Icons.shopping_bag_outlined, color: tokens.textMuted, size: 36),
      );
    }
    return Image.network(
      url,
      fit: BoxFit.cover,
      errorBuilder: (_, _, _) => Container(
        color: tokens.glassStrong,
        alignment: Alignment.center,
        child: Icon(Icons.broken_image_outlined, color: tokens.textMuted, size: 32),
      ),
      loadingBuilder: (context, child, progress) {
        if (progress == null) return child;
        return Container(
          color: tokens.glassStrong,
          alignment: Alignment.center,
          child: SizedBox(
            width: 22,
            height: 22,
            child: CircularProgressIndicator(strokeWidth: 2.2, color: tokens.primary),
          ),
        );
      },
    );
  }
}

class _PurchaseSheet extends StatefulWidget {
  const _PurchaseSheet({required this.product, required this.balance});

  final StoreProductModel product;
  final int balance;

  @override
  State<_PurchaseSheet> createState() => _PurchaseSheetState();
}

class _PurchaseSheetState extends State<_PurchaseSheet> {
  int _qty = 1;
  bool _submitting = false;
  String? _error;

  int get _maxQty {
    if (widget.product.priceChaqmoq <= 0) return 99;
    final affordable = widget.balance ~/ widget.product.priceChaqmoq;
    return affordable.clamp(1, 99);
  }

  int get _totalCost => widget.product.priceChaqmoq * _qty;
  bool get _canAfford => widget.balance >= _totalCost;

  Future<void> _submit() async {
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await context.read<StoreService>().createPurchaseRequest(
            productId: widget.product.id,
            qty: _qty,
          );
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _submitting = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = "So‘rov yuborilmadi";
        _submitting = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final p = widget.product;
    return SafeArea(
      top: false,
      child: Container(
        margin: const EdgeInsets.fromLTRB(12, 0, 12, 12),
        padding: const EdgeInsets.fromLTRB(20, 14, 20, 20),
        decoration: BoxDecoration(
          color: tokens.isDark ? tokens.surfaceElevated : tokens.surface,
          borderRadius: BorderRadius.circular(22),
          border: Border.all(color: tokens.border),
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
                ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: SizedBox(
                    width: 76,
                    height: 76,
                    child: _ProductImage(url: p.imageUrl),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        p.name,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: GoogleFonts.inter(
                          fontSize: 15,
                          fontWeight: FontWeight.w800,
                          color: tokens.text,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Row(
                        children: [
                          Text(
                            Formatters.number(p.priceChaqmoq),
                            style: GoogleFonts.inter(
                              fontSize: 15,
                              fontWeight: FontWeight.w800,
                              color: tokens.primary,
                            ),
                          ),
                          const SizedBox(width: 3),
                          Icon(Icons.bolt_rounded, color: tokens.primary, size: 14),
                          const SizedBox(width: 6),
                          Text(
                            "/ dona",
                            style: GoogleFonts.inter(
                              fontSize: 11.5,
                              fontWeight: FontWeight.w600,
                              color: tokens.textMuted,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
            if (p.description.isNotEmpty) ...[
              const SizedBox(height: 12),
              Text(
                p.description,
                style: GoogleFonts.inter(
                  fontSize: 12.5,
                  fontWeight: FontWeight.w500,
                  color: tokens.textMuted,
                  height: 1.4,
                ),
              ),
            ],
            const SizedBox(height: 16),
            Container(height: 1, color: tokens.border),
            const SizedBox(height: 14),
            Row(
              children: [
                Text(
                  'Soni',
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: tokens.text,
                  ),
                ),
                const Spacer(),
                _QtyButton(
                  icon: Icons.remove_rounded,
                  enabled: _qty > 1 && !_submitting,
                  onTap: () => setState(() => _qty--),
                ),
                Container(
                  width: 44,
                  alignment: Alignment.center,
                  child: Text(
                    '$_qty',
                    style: GoogleFonts.inter(
                      fontSize: 16,
                      fontWeight: FontWeight.w800,
                      color: tokens.text,
                    ),
                  ),
                ),
                _QtyButton(
                  icon: Icons.add_rounded,
                  enabled: _qty < _maxQty && !_submitting,
                  onTap: () => setState(() => _qty++),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Text(
                  'Jami narx',
                  style: GoogleFonts.inter(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w600,
                    color: tokens.textMuted,
                  ),
                ),
                const Spacer(),
                Text(
                  Formatters.number(_totalCost),
                  style: GoogleFonts.inter(
                    fontSize: 17,
                    fontWeight: FontWeight.w800,
                    color: _canAfford ? tokens.text : tokens.danger,
                    letterSpacing: -0.3,
                  ),
                ),
                const SizedBox(width: 4),
                Icon(
                  Icons.bolt_rounded,
                  color: _canAfford ? tokens.primary : tokens.danger,
                  size: 16,
                ),
              ],
            ),
            const SizedBox(height: 4),
            Row(
              children: [
                Text(
                  'Sizning balansingiz',
                  style: GoogleFonts.inter(
                    fontSize: 11.5,
                    fontWeight: FontWeight.w600,
                    color: tokens.textMuted,
                  ),
                ),
                const Spacer(),
                Text(
                  Formatters.number(widget.balance),
                  style: GoogleFonts.inter(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w700,
                    color: tokens.textMuted,
                  ),
                ),
                const SizedBox(width: 3),
                Icon(Icons.bolt_rounded, color: tokens.primary, size: 13),
              ],
            ),
            if (!_canAfford) ...[
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                decoration: BoxDecoration(
                  color: tokens.tonedSurface(tokens.danger),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: tokens.danger.withValues(alpha: 0.4)),
                ),
                child: Row(
                  children: [
                    Icon(Icons.info_outline_rounded, size: 16, color: tokens.danger),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Chaqmoqlaringiz yetarli emas',
                        style: GoogleFonts.inter(
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          color: tokens.danger,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
            if (_error != null) ...[
              const SizedBox(height: 10),
              Text(
                _error!,
                style: GoogleFonts.inter(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  color: tokens.danger,
                ),
              ),
            ],
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: _submitting ? null : () => Navigator.of(context).pop(),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: tokens.text,
                      side: BorderSide(color: tokens.border),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                    child: const Text('Bekor qilish'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  flex: 2,
                  child: FilledButton(
                    onPressed: (_canAfford && !_submitting) ? _submit : null,
                    style: FilledButton.styleFrom(
                      backgroundColor: tokens.primary,
                      foregroundColor: tokens.onPrimary,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                    child: _submitting
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2.2, color: Colors.white),
                          )
                        : Text(
                            "Sotib olish",
                            style: GoogleFonts.inter(fontSize: 13, fontWeight: FontWeight.w800),
                          ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _QtyButton extends StatelessWidget {
  const _QtyButton({required this.icon, required this.enabled, required this.onTap});

  final IconData icon;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Opacity(
      opacity: enabled ? 1 : 0.4,
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(10),
        child: InkWell(
          onTap: enabled ? onTap : null,
          borderRadius: BorderRadius.circular(10),
          child: Container(
            width: 32,
            height: 32,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: tokens.glass,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: tokens.border),
            ),
            child: Icon(icon, size: 16, color: tokens.text),
          ),
        ),
      ),
    );
  }
}

class _IconBtn extends StatelessWidget {
  const _IconBtn({required this.icon, required this.onTap});

  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          width: 38,
          height: 38,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: tokens.glass,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: tokens.border),
          ),
          child: Icon(icon, size: 18, color: tokens.text),
        ),
      ),
    );
  }
}

class _ErrorBox extends StatelessWidget {
  const _ErrorBox({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline_rounded, color: tokens.danger, size: 36),
            const SizedBox(height: 8),
            Text(
              message,
              textAlign: TextAlign.center,
              style: GoogleFonts.inter(color: tokens.text, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 12),
            FilledButton.tonal(
              onPressed: onRetry,
              child: const Text('Qayta urinish'),
            ),
          ],
        ),
      ),
    );
  }
}
