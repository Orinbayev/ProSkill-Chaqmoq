import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/design/ds_colors.dart';
import '../../../core/design/ds_components.dart';
import '../../../core/design/ds_format.dart';
import '../../../core/design/ds_tokens.dart';
import '../../../core/design/ds_typography.dart';
import '../data/director_data.dart';
import '../data/director_provider.dart';

/// To'lov kiritish bottom-sheet — real saqlash. Muvaffaqiyatда `true` qaytaradi.
Future<bool?> showDirectorPaymentSheet(
  BuildContext context,
  DirectorDebtor debtor, {
  List<String> methods = const [],
}) {
  // Modal sheet Navigator overlay'да ochiladi — DirectorProvider'ni unga
  // qayta uzatamiz (aks holda "Provider topilmadi" xatosi bo'ladi).
  final provider = context.read<DirectorProvider>();
  return showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => ChangeNotifierProvider<DirectorProvider>.value(
      value: provider,
      child: _PaymentSheet(debtor: debtor, methods: methods),
    ),
  );
}

class _PaymentSheet extends StatefulWidget {
  const _PaymentSheet({required this.debtor, this.methods = const []});
  final DirectorDebtor debtor;
  final List<String> methods;

  @override
  State<_PaymentSheet> createState() => _PaymentSheetState();
}

class _PaymentSheetState extends State<_PaymentSheet> {
  late final DirectorProvider _provider = context.read<DirectorProvider>();
  late Future<DirectorStudentDetail> _detailFuture;

  int _group = 0;
  int _method = 0;
  bool _saving = false;
  late final TextEditingController _amount =
      TextEditingController(text: widget.debtor.totalDebt > 0 ? dsSom(widget.debtor.totalDebt) : '');

  @override
  void initState() {
    super.initState();
    _detailFuture = _provider.loadStudentDetail(widget.debtor.id);
  }

  @override
  void dispose() {
    _amount.dispose();
    super.dispose();
  }

  List<String> get _methods {
    final list = widget.methods.where((m) => m.trim().isNotEmpty).toList();
    return list.isNotEmpty ? list : const ['Naqd', 'Karta'];
  }

  Future<void> _save(List<StudentGroup> groups) async {
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    if (groups.isEmpty) return;
    final amount = int.tryParse(_amount.text.replaceAll(RegExp(r'[^0-9]'), ''));
    if (amount == null || amount <= 0) {
      messenger.showSnackBar(const SnackBar(content: Text('To\'lov summasini kiriting')));
      return;
    }
    setState(() => _saving = true);
    try {
      await _provider.payStudent(
        widget.debtor.id,
        groups[_group.clamp(0, groups.length - 1)].enrollmentId,
        amount,
        _methods[_method],
      );
      navigator.pop(true);
      messenger.showSnackBar(
        SnackBar(content: Text('${widget.debtor.name} — ${dsSom(amount)} so\'m to\'lov saqlandi ✅')),
      );
    } catch (_) {
      if (mounted) setState(() => _saving = false);
      messenger.showSnackBar(const SnackBar(content: Text('Xatolik — to\'lov saqlanmadi')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    final bottomInset = MediaQuery.of(context).viewInsets.bottom;
    return Padding(
      padding: EdgeInsets.only(bottom: bottomInset),
      child: Container(
        decoration: BoxDecoration(
          color: ds.card,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(DsRadius.xl)),
          boxShadow: DsShadow.raised(ds.isDark),
        ),
        padding: const EdgeInsets.fromLTRB(DsSpace.x5, DsSpace.x3, DsSpace.x5, DsSpace.x5),
        child: FutureBuilder<DirectorStudentDetail>(
          future: _detailFuture,
          builder: (context, snapshot) {
            final groups = snapshot.data?.groups ?? const <StudentGroup>[];
            return Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Center(
                  child: Container(
                    width: 40,
                    height: 4,
                    decoration: BoxDecoration(color: ds.border, borderRadius: DsRadius.all(DsRadius.pill)),
                  ),
                ),
                const SizedBox(height: 16),
                Text('To\'lov kiritish', style: DsType.h3(ds.textPrimary)),
                const SizedBox(height: 14),
                Row(children: [
                  DsAvatar(widget.debtor.name, size: 40, tone: widget.debtor.tone),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(widget.debtor.name, style: DsType.bodyStrong(ds.textPrimary)),
                        if (widget.debtor.totalDebt > 0)
                          Text('Qarz: ${dsSom(widget.debtor.totalDebt)} so\'m', style: DsType.small(ds.danger)),
                      ],
                    ),
                  ),
                ]),
                const SizedBox(height: 16),
                if (snapshot.connectionState == ConnectionState.waiting)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 24),
                    child: Center(child: CircularProgressIndicator(strokeWidth: 2.4, valueColor: AlwaysStoppedAnimation(ds.primary))),
                  )
                else if (groups.isEmpty)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 20),
                    child: Center(child: Text('O\'quvchi guruhга biriktirilmagan — to\'lov yozib bo\'lmaydi', style: DsType.caption(ds.textMuted))),
                  )
                else ...[
                  // Guruh tanlash (bir nechta bo'lsa)
                  if (groups.length > 1) ...[
                    Text('Qaysi guruh uchun', style: DsType.small(ds.textMuted).copyWith(fontWeight: FontWeight.w600)),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        for (final (i, g) in groups.indexed)
                          DsChip(label: g.group, selected: _group == i, onTap: () => setState(() => _group = i)),
                      ],
                    ),
                    const SizedBox(height: 16),
                  ],
                  DsTextField(label: 'Summa', controller: _amount, suffixText: 'so\'m', big: true, keyboardType: TextInputType.number),
                  const SizedBox(height: 12),
                  Text('To\'lov usuli', style: DsType.small(ds.textMuted).copyWith(fontWeight: FontWeight.w600)),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (final (i, m) in _methods.indexed)
                        _MethodButton(label: m, selected: _method == i, onTap: () => setState(() => _method = i)),
                    ],
                  ),
                  const SizedBox(height: 16),
                  DsButton(
                    label: _saving ? 'Saqlanmoqda...' : 'Saqlash',
                    loading: _saving,
                    onPressed: _saving ? null : () => _save(groups),
                  ),
                  const SizedBox(height: 10),
                  Center(child: Text('Ortiqcha to\'lov avtomatik keyingi oyga o\'tadi', style: DsType.small(ds.textFaint))),
                ],
              ],
            );
          },
        ),
      ),
    );
  }
}

class _MethodButton extends StatelessWidget {
  const _MethodButton({required this.label, required this.selected, required this.onTap});
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Material(
      color: selected ? ds.primarySoft : ds.card,
      borderRadius: DsRadius.all(DsRadius.md),
      child: InkWell(
        onTap: onTap,
        borderRadius: DsRadius.all(DsRadius.md),
        child: Container(
          height: 46,
          alignment: Alignment.center,
          constraints: const BoxConstraints(minWidth: 92),
          padding: const EdgeInsets.symmetric(horizontal: 18),
          decoration: BoxDecoration(
            borderRadius: DsRadius.all(DsRadius.md),
            border: Border.all(color: selected ? ds.primary : ds.border, width: selected ? 1.4 : 1),
          ),
          child: Text(label, style: DsType.bodyStrong(selected ? ds.primarySoftFg : ds.textSecondary)),
        ),
      ),
    );
  }
}
