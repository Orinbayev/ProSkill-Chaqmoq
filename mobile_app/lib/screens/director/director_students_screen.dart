import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/design/ds_colors.dart';
import '../../core/design/ds_components.dart';
import '../../core/design/ds_tokens.dart';
import '../../core/design/ds_typography.dart';
import 'data/director_provider.dart';
import 'director_student_detail_screen.dart';
import 'widgets/director_states.dart';

class DirectorStudentsScreen extends StatefulWidget {
  const DirectorStudentsScreen({super.key});
  @override
  State<DirectorStudentsScreen> createState() => _DirectorStudentsScreenState();
}

class _DirectorStudentsScreenState extends State<DirectorStudentsScreen> {
  int _chip = 0; // 0=barchasi, 1=qarzdor, 2=to'langan
  Timer? _debounce;
  final ScrollController _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    _scroll.addListener(_onScroll);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<DirectorProvider>().loadStudents('');
    });
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _scroll.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scroll.position.pixels >= _scroll.position.maxScrollExtent - 300) {
      context.read<DirectorProvider>().loadMoreStudents();
    }
  }

  void _onSearch(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), () {
      if (mounted) context.read<DirectorProvider>().loadStudents(value);
    });
  }

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    final provider = context.watch<DirectorProvider>();
    final all = provider.students;
    final filtered = switch (_chip) {
      1 => all.where((s) => s.totalDebt > 0).toList(),
      2 => all.where((s) => s.totalDebt == 0).toList(),
      _ => all,
    };

    Widget listArea;
    if (provider.studentsState == DirectorLoadState.loading && all.isEmpty) {
      listArea = Padding(
        padding: const EdgeInsets.only(top: 60),
        child: Center(child: CircularProgressIndicator(strokeWidth: 2.6, valueColor: AlwaysStoppedAnimation(ds.primary))),
      );
    } else if (provider.studentsState == DirectorLoadState.error && all.isEmpty) {
      listArea = Padding(
        padding: const EdgeInsets.only(top: 40),
        child: DirectorErrorView(onRetry: () => provider.loadStudents('', force: true)),
      );
    } else if (filtered.isEmpty) {
      listArea = Padding(
        padding: const EdgeInsets.only(top: 60),
        child: Center(child: Text('Mos o\'quvchi topilmadi', style: DsType.caption(ds.textMuted))),
      );
    } else {
      listArea = DsCard(
        padding: const EdgeInsets.symmetric(horizontal: DsSpace.x5, vertical: DsSpace.x2),
        child: Column(
          children: [
            for (final (i, s) in filtered.indexed) ...[
              if (i > 0) Container(height: 1, color: ds.border),
              DsListRow(
                leading: DsAvatar(s.name, tone: s.tone),
                title: s.name,
                subtitle: [s.group, s.phone].where((e) => e.isNotEmpty).join(' · '),
                trailing: s.totalDebt > 0
                    ? DsBadge('Qarzdor', status: DsStatus.danger)
                    : const DsBadge('To\'langan', status: DsStatus.success),
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => ChangeNotifierProvider<DirectorProvider>.value(
                      value: provider,
                      child: DirectorStudentDetailScreen(studentId: s.id, name: s.name),
                    ),
                  ),
                ),
              ),
            ],
          ],
        ),
      );
    }

    return SafeArea(
      bottom: false,
      child: ListView(
        controller: _scroll,
        padding: const EdgeInsets.fromLTRB(DsSpace.screen, DsSpace.x3, DsSpace.screen, DsSpace.x8),
        children: [
          Row(children: [
            Text('O\'quvchilar', style: DsType.h1(ds.textPrimary)),
            const Spacer(),
            if (all.isNotEmpty) DsBadge('${all.length} ta', status: DsStatus.info),
          ]),
          const SizedBox(height: 14),
          DsTextField(hint: 'Ism yoki guruh bo\'yicha qidiruv...', prefixIcon: Icons.search, onChanged: _onSearch),
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final (i, label) in ['Barchasi', 'Qarzdor', 'To\'langan'].indexed)
                DsChip(label: label, selected: _chip == i, onTap: () => setState(() => _chip = i)),
            ],
          ),
          const SizedBox(height: DsSpace.x5),
          listArea,
          // Paginatsiya indikatori (faqat filtr yo'q holatida — chunki loadMore serverdan keladi)
          if (_chip == 0 && all.isNotEmpty) _paginationFooter(context, provider),
        ],
      ),
    );
  }

  Widget _paginationFooter(BuildContext context, DirectorProvider provider) {
    final ds = context.ds;
    if (provider.loadingMoreStudents) {
      return Padding(
        padding: const EdgeInsets.only(top: 18),
        child: Center(
          child: SizedBox(
            width: 22,
            height: 22,
            child: CircularProgressIndicator(strokeWidth: 2.4, valueColor: AlwaysStoppedAnimation(ds.primary)),
          ),
        ),
      );
    }
    if (!provider.studentsHasNext) {
      return Padding(
        padding: const EdgeInsets.only(top: 16),
        child: Center(child: Text('Barcha o\'quvchilar yuklandi', style: DsType.small(ds.textFaint))),
      );
    }
    return const SizedBox(height: 8);
  }
}
