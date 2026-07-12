import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/design/ds_colors.dart';
import '../../core/design/ds_components.dart';
import '../../core/design/ds_format.dart';
import '../../core/design/ds_tokens.dart';
import '../../core/design/ds_typography.dart';
import 'data/director_data.dart';
import 'data/director_provider.dart';
import 'widgets/director_states.dart';

class DirectorStudentDetailScreen extends StatefulWidget {
  const DirectorStudentDetailScreen({super.key, required this.studentId, required this.name});
  final int studentId;
  final String name;

  @override
  State<DirectorStudentDetailScreen> createState() => _DirectorStudentDetailScreenState();
}

class _DirectorStudentDetailScreenState extends State<DirectorStudentDetailScreen> {
  late Future<DirectorStudentDetail> _future;

  @override
  void initState() {
    super.initState();
    _future = context.read<DirectorProvider>().loadStudentDetail(widget.studentId);
  }

  void _reload() {
    setState(() => _future = context.read<DirectorProvider>().loadStudentDetail(widget.studentId));
  }

  void _toast(String msg) {
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  // Guruh qatorini bosганда — narx / chiqarish
  Future<void> _groupActions(DirectorStudentDetail d, StudentGroup g) async {
    final ds = context.ds;
    final action = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: ds.card,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(DsRadius.xl))),
      builder: (_) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 8),
            Container(width: 40, height: 4, decoration: BoxDecoration(color: ds.border, borderRadius: DsRadius.all(DsRadius.pill))),
            const SizedBox(height: 8),
            Padding(
              padding: const EdgeInsets.all(DsSpace.x4),
              child: Text(g.group, style: DsType.h3(ds.textPrimary)),
            ),
            ListTile(
              leading: Icon(Icons.edit_rounded, color: ds.primary),
              title: Text('Kurs narxini o\'zgartirish', style: DsType.body(ds.textPrimary)),
              onTap: () => Navigator.pop(context, 'price'),
            ),
            ListTile(
              leading: Icon(Icons.logout_rounded, color: ds.danger),
              title: Text('Guruhdan chiqarish', style: DsType.body(ds.danger)),
              onTap: () => Navigator.pop(context, 'remove'),
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
    if (!mounted) return;
    if (action == 'price') {
      await _editPrice(g);
    } else if (action == 'remove') {
      await _removeGroup(g);
    }
  }

  Future<void> _editPrice(StudentGroup g) async {
    final controller = TextEditingController(text: g.monthlyPrice > 0 ? '${g.monthlyPrice}' : '');
    final ds = context.ds;
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: ds.card,
        title: Text('Kurs narxi — ${g.group}', style: DsType.h3(ds.textPrimary)),
        content: TextField(
          controller: controller,
          keyboardType: TextInputType.number,
          autofocus: true,
          style: DsType.h2(ds.textPrimary),
          decoration: const InputDecoration(suffixText: 'so\'m', hintText: '450000'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Bekor')),
          TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('Saqlash')),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    final price = int.tryParse(controller.text.replaceAll(RegExp(r'[^0-9]'), ''));
    if (price == null) {
      _toast('Narx noto\'g\'ri');
      return;
    }
    try {
      await context.read<DirectorProvider>().setStudentPrice(widget.studentId, g.enrollmentId, price);
      _toast('Narx yangilandi');
      _reload();
    } catch (_) {
      _toast('Xatolik — narx saqlanmadi');
    }
  }

  Future<void> _removeGroup(StudentGroup g) async {
    final ds = context.ds;
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: ds.card,
        title: Text('Guruhdan chiqarish', style: DsType.h3(ds.textPrimary)),
        content: Text('«${g.group}» guruhidан chiqarilsinmi? Qarz joriy oygacha hisoblanadi.', style: DsType.body(ds.textSecondary)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Bekor')),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text('Chiqarish', style: TextStyle(color: ds.danger)),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    try {
      await context.read<DirectorProvider>().removeStudentFromGroup(widget.studentId, g.groupId);
      _toast('Guruhdan chiqarildi');
      _reload();
    } catch (_) {
      _toast('Xatolik — chiqarilmadi');
    }
  }

  Future<void> _addGroup(DirectorStudentDetail d) async {
    final provider = context.read<DirectorProvider>();
    final existing = d.groups.map((g) => g.groupId).toSet();
    final selected = await showModalBottomSheet<AvailableGroup>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _GroupPickerSheet(provider: provider, excludeIds: existing),
    );
    if (selected == null || !mounted) return;
    // Narxни so'raymiz (guruh narxи bilan oldindan to'ldiriladi)
    final controller = TextEditingController(text: selected.price > 0 ? '${selected.price}' : '');
    final ds = context.ds;
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: ds.card,
        title: Text('${selected.name} — kurs narxi', style: DsType.h3(ds.textPrimary)),
        content: TextField(
          controller: controller,
          keyboardType: TextInputType.number,
          autofocus: true,
          style: DsType.h2(ds.textPrimary),
          decoration: const InputDecoration(suffixText: 'so\'m'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Bekor')),
          TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('Qo\'shish')),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    final price = int.tryParse(controller.text.replaceAll(RegExp(r'[^0-9]'), ''));
    try {
      await provider.addStudentToGroup(widget.studentId, selected.id, price: price);
      _toast('${selected.name} guruhiga qo\'shildi');
      _reload();
    } catch (_) {
      _toast('Xatolik — qo\'shilmadi (allaqachon a\'zomi?)');
    }
  }

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Scaffold(
      backgroundColor: ds.bg,
      appBar: AppBar(title: Text(widget.name)),
      body: FutureBuilder<DirectorStudentDetail>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const DirectorLoading();
          }
          if (snapshot.hasError || !snapshot.hasData) {
            return DirectorErrorView(
              onRetry: () => setState(() => _future = context.read<DirectorProvider>().loadStudentDetail(widget.studentId)),
            );
          }
          final d = snapshot.data!;
          return ListView(
            padding: const EdgeInsets.fromLTRB(DsSpace.screen, DsSpace.x5, DsSpace.screen, DsSpace.x8),
            children: [
              // Profil karta
              DsCard(
                child: Row(
                  children: [
                    DsAvatar(d.name, size: 56, tone: d.totalDebt > 0 ? DsStatus.danger : DsStatus.info),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(d.name, style: DsType.h3(ds.textPrimary)),
                          const SizedBox(height: 2),
                          Text([d.group, d.phone].where((e) => e.isNotEmpty).join(' · '), style: DsType.small(ds.textMuted)),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              // Qarz holati
              DsCard(
                padding: const EdgeInsets.all(DsSpace.x4),
                child: Row(
                  children: [
                    Container(
                      width: 34,
                      height: 34,
                      decoration: BoxDecoration(
                        color: d.totalDebt > 0 ? ds.dangerBg : ds.successBg,
                        borderRadius: DsRadius.all(DsRadius.sm),
                      ),
                      child: Icon(
                        d.totalDebt > 0 ? Icons.account_balance_wallet_rounded : Icons.check_circle_rounded,
                        size: 18,
                        color: d.totalDebt > 0 ? ds.dangerFg : ds.successFg,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          d.totalDebt > 0 ? dsSom(-d.totalDebt) : 'Qarzi yo\'q',
                          style: DsType.h3(d.totalDebt > 0 ? ds.danger : ds.success),
                        ),
                        Text('Joriy qarzdorlik', style: DsType.small(ds.textMuted)),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: DsSpace.section),
              // Guruhlar (kurs narxi bilan) — bosib narx/chiqarish
              DsSectionHeader('Guruhlar', actionLabel: '${d.groups.length} ta'),
              const SizedBox(height: 8),
              if (d.groups.isNotEmpty)
                DsCard(
                  padding: const EdgeInsets.symmetric(horizontal: DsSpace.x5, vertical: DsSpace.x2),
                  child: Column(
                    children: [
                      for (final (i, g) in d.groups.indexed) ...[
                        if (i > 0) Container(height: 1, color: ds.border),
                        DsListRow(
                          onTap: () => _groupActions(d, g),
                          leading: Container(
                            width: 34,
                            height: 34,
                            decoration: BoxDecoration(color: ds.primarySoft, borderRadius: DsRadius.all(DsRadius.sm)),
                            child: Icon(Icons.groups_rounded, size: 18, color: ds.primarySoftFg),
                          ),
                          title: g.group,
                          subtitle: 'O\'qituvchi ulushi: ${g.teacherPercent}%',
                          trailing: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Column(
                                crossAxisAlignment: CrossAxisAlignment.end,
                                children: [
                                  Text(dsSom(g.monthlyPrice), style: DsType.bodyStrong(ds.textPrimary)),
                                  Text('oylik narx', style: DsType.small(ds.textFaint)),
                                ],
                              ),
                              const SizedBox(width: 6),
                              Icon(Icons.more_vert_rounded, size: 18, color: ds.textFaint),
                            ],
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              const SizedBox(height: 12),
              DsButton(
                label: 'Guruhga qo\'shish',
                icon: Icons.add,
                variant: DsButtonVariant.outline,
                onPressed: () => _addGroup(d),
              ),
              const SizedBox(height: DsSpace.section),
              DsSectionHeader('So\'nggi to\'lovlar'),
              const SizedBox(height: 8),
              if (d.payments.isEmpty)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 24),
                  child: Center(child: Text('To\'lovlar tarixi yo\'q', style: DsType.caption(ds.textMuted))),
                )
              else
                DsCard(
                  padding: const EdgeInsets.symmetric(horizontal: DsSpace.x5, vertical: DsSpace.x2),
                  child: Column(
                    children: [
                      for (final (i, p) in d.payments.indexed) ...[
                        if (i > 0) Container(height: 1, color: ds.border),
                        DsListRow(
                          leading: Container(
                            width: 34,
                            height: 34,
                            decoration: BoxDecoration(color: ds.successBg, borderRadius: DsRadius.all(DsRadius.sm)),
                            child: Icon(Icons.payments_rounded, size: 18, color: ds.successFg),
                          ),
                          title: p.time.isNotEmpty ? p.time : 'To\'lov',
                          subtitle: p.subtitle,
                          trailing: Text(dsSom(p.amount, sign: true), style: DsType.bodyStrong(ds.success)),
                        ),
                      ],
                    ],
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}

/// Guruh tanlash bottom-sheet (qidiruv bilan).
class _GroupPickerSheet extends StatefulWidget {
  const _GroupPickerSheet({required this.provider, required this.excludeIds});
  final DirectorProvider provider;
  final Set<int> excludeIds;

  @override
  State<_GroupPickerSheet> createState() => _GroupPickerSheetState();
}

class _GroupPickerSheetState extends State<_GroupPickerSheet> {
  late Future<List<AvailableGroup>> _future = widget.provider.loadGroups('');
  Timer? _debounce;

  @override
  void dispose() {
    _debounce?.cancel();
    super.dispose();
  }

  void _search(String q) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), () {
      if (mounted) setState(() => _future = widget.provider.loadGroups(q));
    });
  }

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        constraints: BoxConstraints(maxHeight: MediaQuery.of(context).size.height * 0.72),
        decoration: BoxDecoration(
          color: ds.card,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(DsRadius.xl)),
        ),
        padding: const EdgeInsets.fromLTRB(DsSpace.x5, DsSpace.x3, DsSpace.x5, DsSpace.x5),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(width: 40, height: 4, decoration: BoxDecoration(color: ds.border, borderRadius: DsRadius.all(DsRadius.pill))),
            ),
            const SizedBox(height: 14),
            Text('Guruhga qo\'shish', style: DsType.h3(ds.textPrimary)),
            const SizedBox(height: 12),
            DsTextField(hint: 'Guruh qidirish...', prefixIcon: Icons.search, onChanged: _search),
            const SizedBox(height: 12),
            Flexible(
              child: FutureBuilder<List<AvailableGroup>>(
                future: _future,
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return Padding(
                      padding: const EdgeInsets.all(24),
                      child: Center(child: CircularProgressIndicator(strokeWidth: 2.4, valueColor: AlwaysStoppedAnimation(ds.primary))),
                    );
                  }
                  final groups = (snapshot.data ?? const []).where((g) => !widget.excludeIds.contains(g.id)).toList();
                  if (groups.isEmpty) {
                    return Padding(
                      padding: const EdgeInsets.all(24),
                      child: Center(child: Text('Guruh topilmadi', style: DsType.caption(ds.textMuted))),
                    );
                  }
                  return ListView.separated(
                    shrinkWrap: true,
                    itemCount: groups.length,
                    separatorBuilder: (_, __) => Container(height: 1, color: ds.border),
                    itemBuilder: (_, i) {
                      final g = groups[i];
                      return DsListRow(
                        onTap: () => Navigator.pop(context, g),
                        leading: Container(
                          width: 34,
                          height: 34,
                          decoration: BoxDecoration(color: ds.primarySoft, borderRadius: DsRadius.all(DsRadius.sm)),
                          child: Icon(Icons.groups_rounded, size: 18, color: ds.primarySoftFg),
                        ),
                        title: g.name,
                        subtitle: 'O\'qituvchi ulushi: ${g.teacherPercent}%',
                        trailing: Text(dsSom(g.price), style: DsType.bodyStrong(ds.textPrimary)),
                      );
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
