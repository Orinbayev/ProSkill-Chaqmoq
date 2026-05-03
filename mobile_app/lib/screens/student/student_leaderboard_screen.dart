import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
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
  ChaqmoqLeaderboardData _data = ChaqmoqLeaderboardData.empty();
  bool _loading = true;
  String? _error;
  String _query = '';

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
      final service = context.read<DashboardService>();
      final data = await service.fetchChaqmoqLeaderboard();
      if (!mounted) return;
      setState(() {
        _data = data;
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

  List<ChaqmoqLeaderboardEntry> get _filtered {
    if (_query.trim().isEmpty) return _data.items;
    final q = _query.trim().toLowerCase();
    return _data.items
        .where((e) => e.fullName.toLowerCase().contains(q))
        .toList();
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
              onRefresh: _load,
              child: _body(tokens),
            ),
          ),
        ],
      ),
    );
  }

  Widget _body(StudentTokens tokens) {
    return CustomScrollView(
      physics: const AlwaysScrollableScrollPhysics(parent: BouncingScrollPhysics()),
      slivers: [
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(18, 8, 18, 0),
          sliver: SliverToBoxAdapter(child: _Header(data: _data)),
        ),
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(18, 12, 18, 8),
          sliver: SliverToBoxAdapter(
            child: TextField(
              onChanged: (v) => setState(() => _query = v),
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
            ),
          ),
        ),
        if (_loading)
          SliverFillRemaining(
            hasScrollBody: false,
            child: Center(
              child: CircularProgressIndicator(color: tokens.primary, strokeWidth: 2.4),
            ),
          )
        else if (_error != null)
          SliverFillRemaining(
            hasScrollBody: false,
            child: _ErrorBox(message: _error!, onRetry: _load),
          )
        else if (_filtered.isEmpty)
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
        else
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(18, 0, 18, 24),
            sliver: SliverList(
              delegate: SliverChildBuilderDelegate(
                (context, index) {
                  final entry = _filtered[index];
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: _LeaderRow(entry: entry),
                  );
                },
                childCount: _filtered.length,
              ),
            ),
          ),
      ],
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
                      ? 'Sizning o‘rningiz: ${data.meRank} / ${data.total}'
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
                      'Ballingiz: ${Formatters.number(data.meBalance)}',
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
  const _LeaderRow({required this.entry});

  final ChaqmoqLeaderboardEntry entry;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final isMe = entry.isMe;
    final rankBg = entry.rank == 1
        ? const Color(0xFFFFD24A)
        : entry.rank == 2
            ? const Color(0xFFC0C7D2)
            : entry.rank == 3
                ? const Color(0xFFE0A26B)
                : tokens.tonedSurface(tokens.primary);
    final rankFg = entry.rank <= 3 ? Colors.white : tokens.primary;
    return Container(
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
              color: rankBg,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(
              '${entry.rank}',
              style: GoogleFonts.inter(
                fontSize: 14,
                fontWeight: FontWeight.w800,
                color: rankFg,
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
        ],
      ),
    );
  }
}
