import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

class StudentLeaderboardSheet extends StatefulWidget {
  const StudentLeaderboardSheet({super.key});

  static Future<void> show(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: tokens.bg,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      builder: (_) => const StudentLeaderboardSheet(),
    );
  }

  @override
  State<StudentLeaderboardSheet> createState() => _StudentLeaderboardSheetState();
}

class _StudentLeaderboardSheetState extends State<StudentLeaderboardSheet> {
  ChaqmoqLeaderboardData _data = ChaqmoqLeaderboardData.empty();
  bool _loading = true;
  String? _error;

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
      // 404 — server yangi endpoint hali deploy qilmagan. User-friendly xabar.
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

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.85,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      builder: (context, scroll) {
        return Container(
          decoration: BoxDecoration(
            color: tokens.bg,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(28)),
          ),
          child: Column(
            children: [
              const SizedBox(height: 8),
              Container(
                width: 44,
                height: 4,
                decoration: BoxDecoration(
                  color: tokens.border,
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 14, 20, 8),
                child: Row(
                  children: [
                    Icon(Icons.bolt_rounded, color: tokens.primary, size: 22),
                    const SizedBox(width: 8),
                    Text(
                      'Chaqmoq reytingi',
                      style: GoogleFonts.inter(
                        fontSize: 17,
                        fontWeight: FontWeight.w800,
                        color: tokens.text,
                      ),
                    ),
                    const Spacer(),
                    if (_data.meRank > 0)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        decoration: BoxDecoration(
                          color: tokens.tonedSurface(tokens.primary),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Text(
                          'Siz: ${_data.meRank}-o‘rin',
                          style: GoogleFonts.inter(
                            fontSize: 11.5,
                            fontWeight: FontWeight.w700,
                            color: tokens.primary,
                          ),
                        ),
                      ),
                  ],
                ),
              ),
              Expanded(child: _content(scroll, tokens)),
            ],
          ),
        );
      },
    );
  }

  Widget _content(ScrollController scroll, StudentTokens tokens) {
    if (_loading) {
      return Center(
        child: CircularProgressIndicator(color: tokens.primary, strokeWidth: 2.4),
      );
    }
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline_rounded, color: tokens.danger, size: 36),
            const SizedBox(height: 8),
            Text(
              _error!,
              style: GoogleFonts.inter(color: tokens.text, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 12),
            TextButton(onPressed: _load, child: const Text('Qayta urinish')),
          ],
        ),
      );
    }
    if (_data.items.isEmpty) {
      return Center(
        child: Text(
          'Hozircha reyting tayyor emas',
          style: GoogleFonts.inter(color: tokens.textMuted, fontWeight: FontWeight.w600),
        ),
      );
    }
    return ListView.separated(
      controller: scroll,
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
      itemCount: _data.items.length,
      separatorBuilder: (_, _) => const SizedBox(height: 6),
      itemBuilder: (context, index) {
        final entry = _data.items[index];
        return _LeaderRow(entry: entry);
      },
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
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
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
            width: 34,
            height: 34,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: rankBg,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(
              '${entry.rank}',
              style: GoogleFonts.inter(
                fontSize: 13,
                fontWeight: FontWeight.w800,
                color: rankFg,
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              entry.fullName,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: GoogleFonts.inter(
                fontSize: 13.5,
                fontWeight: isMe ? FontWeight.w800 : FontWeight.w700,
                color: tokens.text,
              ),
            ),
          ),
          Icon(Icons.bolt_rounded, color: tokens.primary, size: 16),
          const SizedBox(width: 4),
          Text(
            Formatters.number(entry.balance),
            style: GoogleFonts.inter(
              fontSize: 13.5,
              fontWeight: FontWeight.w800,
              color: tokens.text,
            ),
          ),
        ],
      ),
    );
  }
}
