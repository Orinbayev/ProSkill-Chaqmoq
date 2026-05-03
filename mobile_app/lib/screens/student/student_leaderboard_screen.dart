import 'dart:async';

import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/screens/student/student_chaqmoq_detail_screen.dart';
import 'package:chaqmoq_mobile/screens/student/widgets/student_atmospheric_backdrop.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

class StudentLeaderboardScreen extends StatefulWidget {
  const StudentLeaderboardScreen({super.key});

  @override
  State<StudentLeaderboardScreen> createState() => _StudentLeaderboardScreenState();
}

class _StudentLeaderboardScreenState extends State<StudentLeaderboardScreen> {
  static const int _perPage = 10;
  ChaqmoqLeaderboardData _data = ChaqmoqLeaderboardData.empty();
  bool _loading = true;
  String? _error;
  String _query = '';
  int _page = 1;
  Timer? _debounce;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    super.dispose();
  }

  Future<void> _load({int? page, String? query}) async {
    setState(() {
      _loading = true;
      _error = null;
      if (page != null) _page = page;
      if (query != null) _query = query;
    });
    try {
      final service = context.read<DashboardService>();
      final data = await service.fetchChaqmoqLeaderboard(
        page: _page,
        perPage: _perPage,
        query: _query,
      );
      if (!mounted) return;
      setState(() {
        _data = data;
        _page = data.page;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      final message = e.code == 'not_found'
          ? 'Reyting xizmati hali yangilanmoqda. Bir oz keyin urinib ko‘ring.'
          : e.message;
      setState(() {
        _error = message;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Reyting yuklanmadi';
        _loading = false;
      });
    }
  }

  void _onSearchChanged(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), () {
      _load(page: 1, query: value);
    });
  }

  Future<void> _refresh() => _load(page: _page, query: _query);

  void _openDetail(ChaqmoqLeaderboardEntry entry) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => StudentChaqmoqDetailScreen(
          studentId: entry.id,
          fallbackName: entry.fullName,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Scaffold(
      backgroundColor: tokens.bg,
      body: Stack(
        children: [
          const StudentAtmosphericBackdrop(),
          SafeArea(
            child: RefreshIndicator(
              color: tokens.primary,
              onRefresh: _refresh,
              child: _body(tokens),
            ),
          ),
        ],
      ),
    );
  }

  Widget _body(StudentTokens tokens) {
    final isFirstPage = _data.page == 1 && _query.isEmpty;
    final podiumEntries = isFirstPage && _data.items.length >= 3
        ? _data.items.take(3).toList()
        : <ChaqmoqLeaderboardEntry>[];
    final restEntries = isFirstPage && _data.items.length >= 3
        ? _data.items.skip(3).toList()
        : _data.items;

    return CustomScrollView(
      physics: const AlwaysScrollableScrollPhysics(parent: BouncingScrollPhysics()),
      slivers: [
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(18, 8, 18, 0),
          sliver: SliverToBoxAdapter(child: _Header(data: _data)),
        ),
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(18, 12, 18, 8),
          sliver: SliverToBoxAdapter(child: _searchField(tokens)),
        ),
        if (_loading && _data.items.isEmpty)
          SliverFillRemaining(
            hasScrollBody: false,
            child: Center(
              child: CircularProgressIndicator(color: tokens.primary, strokeWidth: 2.4),
            ),
          )
        else if (_error != null && _data.items.isEmpty)
          SliverFillRemaining(
            hasScrollBody: false,
            child: _ErrorBox(message: _error!, onRetry: _refresh),
          )
        else if (_data.items.isEmpty)
          SliverFillRemaining(
            hasScrollBody: false,
            child: Center(
              child: Text(
                _query.isNotEmpty
                    ? 'Bu nomda o‘quvchi topilmadi'
                    : 'Hozircha reyting tayyor emas',
                style: GoogleFonts.inter(
                  color: tokens.textMuted,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          )
        else ...[
          if (podiumEntries.isNotEmpty)
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(18, 4, 18, 14),
              sliver: SliverToBoxAdapter(
                child: _Podium(
                  entries: podiumEntries,
                  onTap: _openDetail,
                ),
              ),
            ),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(18, 0, 18, 8),
            sliver: SliverList(
              delegate: SliverChildBuilderDelegate(
                (context, index) {
                  final entry = restEntries[index];
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: _LeaderRow(
                      entry: entry,
                      onTap: () => _openDetail(entry),
                    ),
                  );
                },
                childCount: restEntries.length,
              ),
            ),
          ),
          if (_data.totalPages > 1)
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(18, 4, 18, 24),
              sliver: SliverToBoxAdapter(
                child: _PageNav(
                  current: _data.page,
                  totalPages: _data.totalPages,
                  loading: _loading,
                  onChange: (p) => _load(page: p, query: _query),
                ),
              ),
            )
          else
            const SliverPadding(padding: EdgeInsets.only(bottom: 24)),
        ],
      ],
    );
  }

  Widget _searchField(StudentTokens tokens) {
    return TextField(
      onChanged: _onSearchChanged,
      style: GoogleFonts.inter(
        fontSize: 13,
        fontWeight: FontWeight.w600,
        color: tokens.text,
      ),
      decoration: InputDecoration(
        hintText: 'Ism bo‘yicha qidirish',
        hintStyle: GoogleFonts.inter(
          fontSize: 13,
          color: tokens.textMuted,
          fontWeight: FontWeight.w500,
        ),
        prefixIcon: Icon(Icons.search_rounded, color: tokens.textMuted),
        filled: true,
        fillColor: tokens.glass,
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: tokens.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: tokens.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: tokens.primary, width: 1.4),
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.data});

  final ChaqmoqLeaderboardData data;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: tokens.heroGradient,
        borderRadius: BorderRadius.circular(22),
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
                  'CHAQMOQ REYTING',
                  style: GoogleFonts.inter(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    color: tokens.textMuted,
                    letterSpacing: 1.6,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  data.meRank > 0
                      ? 'Sizning o‘rningiz: ${data.meRank}'
                      : 'Reyting tayyor emas',
                  style: GoogleFonts.inter(
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                    color: tokens.text,
                  ),
                ),
                const SizedBox(height: 2),
                Row(
                  children: [
                    Text(
                      'Sizning chaqmoqlaringiz: ${Formatters.number(data.meBalance)}',
                      style: GoogleFonts.inter(
                        fontSize: 12.5,
                        fontWeight: FontWeight.w700,
                        color: tokens.textMuted,
                      ),
                    ),
                    const SizedBox(width: 4),
                    Icon(Icons.bolt_rounded, color: tokens.primary, size: 14),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Podium extends StatelessWidget {
  const _Podium({required this.entries, required this.onTap});

  final List<ChaqmoqLeaderboardEntry> entries;
  final ValueChanged<ChaqmoqLeaderboardEntry> onTap;

  @override
  Widget build(BuildContext context) {
    // entries are sorted [1st, 2nd, 3rd]; render in [2nd, 1st, 3rd] order
    // so the podium reads visually like a stadium platform.
    final first = entries[0];
    final second = entries[1];
    final third = entries[2];
    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Expanded(
          child: _PodiumColumn(
            entry: second,
            podiumHeight: 72,
            onTap: () => onTap(second),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _PodiumColumn(
            entry: first,
            podiumHeight: 96,
            onTap: () => onTap(first),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _PodiumColumn(
            entry: third,
            podiumHeight: 56,
            onTap: () => onTap(third),
          ),
        ),
      ],
    );
  }
}

class _PodiumColumn extends StatelessWidget {
  const _PodiumColumn({
    required this.entry,
    required this.podiumHeight,
    required this.onTap,
  });

  final ChaqmoqLeaderboardEntry entry;
  final double podiumHeight;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final colorPair = _palette(entry.rank);
    final medalIcon = entry.rank == 1
        ? Icons.emoji_events_rounded
        : Icons.workspace_premium_rounded;
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 52,
              height: 52,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: LinearGradient(
                  colors: [colorPair.$1, colorPair.$2],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                boxShadow: [
                  BoxShadow(
                    color: colorPair.$1.withValues(alpha: 0.45),
                    blurRadius: 14,
                    offset: const Offset(0, 6),
                  ),
                ],
              ),
              child: Icon(medalIcon, color: Colors.white, size: 26),
            ),
            const SizedBox(height: 6),
            Text(
              _firstName(entry.fullName),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.center,
              style: GoogleFonts.inter(
                fontSize: 12.5,
                fontWeight: FontWeight.w800,
                color: tokens.text,
              ),
            ),
            const SizedBox(height: 2),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.bolt_rounded, color: tokens.primary, size: 12),
                const SizedBox(width: 2),
                Text(
                  Formatters.number(entry.balance),
                  style: GoogleFonts.inter(
                    fontSize: 11.5,
                    fontWeight: FontWeight.w800,
                    color: tokens.text,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Container(
              height: podiumHeight,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    colorPair.$1.withValues(alpha: 0.85),
                    colorPair.$2.withValues(alpha: 0.95),
                  ],
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                ),
                borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
              ),
              child: Text(
                '${entry.rank}',
                style: GoogleFonts.inter(
                  fontSize: 28,
                  fontWeight: FontWeight.w900,
                  color: Colors.white,
                  letterSpacing: -0.6,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  static String _firstName(String name) {
    if (name.trim().isEmpty) return '—';
    final parts = name.trim().split(RegExp(r'\s+'));
    return parts.first;
  }

  static (Color, Color) _palette(int rank) {
    if (rank == 1) {
      return (const Color(0xFFFFC83D), const Color(0xFFEFA02B));
    }
    if (rank == 2) {
      return (const Color(0xFFD4DBE5), const Color(0xFF9BA4B5));
    }
    return (const Color(0xFFE0A26B), const Color(0xFFB97843));
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

class _LeaderRow extends StatelessWidget {
  const _LeaderRow({required this.entry, required this.onTap});

  final ChaqmoqLeaderboardEntry entry;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final isMe = entry.isMe;
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
          decoration: BoxDecoration(
            color: isMe ? tokens.tonedSurface(tokens.primary) : tokens.glass,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: isMe ? tokens.primary.withValues(alpha: 0.6) : tokens.border,
              width: isMe ? 1.4 : 1,
            ),
          ),
          child: Row(
            children: [
              Container(
                width: 38,
                height: 38,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: tokens.tonedSurface(tokens.primary),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  '${entry.rank}',
                  style: GoogleFonts.inter(
                    fontSize: 14,
                    fontWeight: FontWeight.w800,
                    color: tokens.primary,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      entry.fullName,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: GoogleFonts.inter(
                        fontSize: 13.5,
                        fontWeight: isMe ? FontWeight.w800 : FontWeight.w700,
                        color: tokens.text,
                      ),
                    ),
                    if (isMe) ...[
                      const SizedBox(height: 2),
                      Text(
                        'Siz',
                        style: GoogleFonts.inter(
                          fontSize: 10.5,
                          fontWeight: FontWeight.w700,
                          color: tokens.primary,
                          letterSpacing: 0.3,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              Icon(Icons.bolt_rounded, color: tokens.primary, size: 16),
              const SizedBox(width: 4),
              Text(
                Formatters.number(entry.balance),
                style: GoogleFonts.inter(
                  fontSize: 14,
                  fontWeight: FontWeight.w800,
                  color: tokens.text,
                ),
              ),
              const SizedBox(width: 4),
              Icon(Icons.chevron_right_rounded, color: tokens.textMuted, size: 16),
            ],
          ),
        ),
      ),
    );
  }
}

class _PageNav extends StatelessWidget {
  const _PageNav({
    required this.current,
    required this.totalPages,
    required this.loading,
    required this.onChange,
  });

  final int current;
  final int totalPages;
  final bool loading;
  final ValueChanged<int> onChange;

  @override
  Widget build(BuildContext context) {
    final start = (current - 2).clamp(1, totalPages);
    final end = (current + 2).clamp(1, totalPages);
    final pages = [for (var i = start; i <= end; i++) i];
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        _PageBtn(
          icon: Icons.chevron_left_rounded,
          enabled: current > 1 && !loading,
          onTap: () => onChange(current - 1),
        ),
        const SizedBox(width: 6),
        for (final p in pages) ...[
          _PageNumber(
            label: '$p',
            isActive: p == current,
            disabled: loading,
            onTap: () => onChange(p),
          ),
          const SizedBox(width: 4),
        ],
        const SizedBox(width: 2),
        _PageBtn(
          icon: Icons.chevron_right_rounded,
          enabled: current < totalPages && !loading,
          onTap: () => onChange(current + 1),
        ),
      ],
    );
  }
}

class _PageBtn extends StatelessWidget {
  const _PageBtn({required this.icon, required this.enabled, required this.onTap});

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
            child: Icon(icon, size: 18, color: tokens.text),
          ),
        ),
      ),
    );
  }
}

class _PageNumber extends StatelessWidget {
  const _PageNumber({
    required this.label,
    required this.isActive,
    required this.disabled,
    required this.onTap,
  });

  final String label;
  final bool isActive;
  final bool disabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return Opacity(
      opacity: disabled ? 0.6 : 1,
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(10),
        child: InkWell(
          onTap: (isActive || disabled) ? null : onTap,
          borderRadius: BorderRadius.circular(10),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            constraints: const BoxConstraints(minWidth: 32),
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: isActive ? tokens.primary : tokens.glass,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                color: isActive ? Colors.transparent : tokens.border,
              ),
            ),
            child: Text(
              label,
              style: GoogleFonts.inter(
                fontSize: 12.5,
                fontWeight: FontWeight.w800,
                color: isActive ? tokens.onPrimary : tokens.text,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
