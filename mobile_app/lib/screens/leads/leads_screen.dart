import 'package:chaqmoq_mobile/core/theme/panel_tokens.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/lead_models.dart';
import 'package:chaqmoq_mobile/providers/leads_provider.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

class LeadsScreen extends StatefulWidget {
  const LeadsScreen({super.key});

  @override
  State<LeadsScreen> createState() => _LeadsScreenState();
}

class _LeadsScreenState extends State<LeadsScreen> {
  final _searchCtrl = TextEditingController();
  String _query = '';

  static const _statuses = [
    ('', 'Barchasi'),
    ('new', 'Yangi'),
    ('contacted', "Bog'lanildi"),
    ('trial', 'Sinov'),
    ('confirmed', 'Tasdiqlandi'),
    ('converted', "O'quvchi"),
    ('canceled', 'Bekor'),
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) context.read<LeadsProvider>().load(force: true);
    });
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  void _search(String q) {
    setState(() => _query = q);
    context.read<LeadsProvider>().load(q: q, force: true);
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final p = context.watch<LeadsProvider>();
    final bg = PanelTokens.bg(isDark);
    final navBg = isDark ? const Color(0xFF0F1B2A) : Colors.white;

    return Scaffold(
      backgroundColor: bg,
      body: NestedScrollView(
        headerSliverBuilder: (_, __) => [
          SliverAppBar(
            backgroundColor: navBg,
            surfaceTintColor: Colors.transparent,
            floating: true,
            snap: true,
            pinned: false,
            title: Text(
              'Leadlar',
              style: TextStyle(
                color: isDark ? Colors.white : const Color(0xFF0F172A),
                fontWeight: FontWeight.w800,
                fontSize: 20,
              ),
            ),
            actions: [
              if (p.state != ViewState.loading)
                IconButton(
                  icon: Icon(Icons.refresh_rounded,
                      color: isDark ? Colors.white70 : Colors.black54),
                  onPressed: () => p.load(q: _query, force: true),
                ),
            ],
            bottom: PreferredSize(
              preferredSize: const Size.fromHeight(108),
              child: Column(children: [
                // Search bar
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                  child: TextField(
                    controller: _searchCtrl,
                    onChanged: _search,
                    style: TextStyle(
                        color: isDark ? Colors.white : const Color(0xFF0F172A)),
                    decoration: InputDecoration(
                      hintText: 'Ism, familya yoki telefon...',
                      hintStyle: TextStyle(
                          color: isDark ? Colors.white38 : Colors.black38,
                          fontSize: 14),
                      prefixIcon: Icon(Icons.search_rounded,
                          color: isDark ? Colors.white38 : Colors.black38,
                          size: 20),
                      suffixIcon: _query.isNotEmpty
                          ? IconButton(
                              icon: Icon(Icons.close_rounded,
                                  color:
                                      isDark ? Colors.white54 : Colors.black45,
                                  size: 18),
                              onPressed: () {
                                _searchCtrl.clear();
                                _search('');
                              },
                            )
                          : null,
                      filled: true,
                      fillColor: isDark
                          ? Colors.white.withValues(alpha: 0.06)
                          : Colors.black.withValues(alpha: 0.05),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                        borderSide: BorderSide.none,
                      ),
                      contentPadding:
                          const EdgeInsets.symmetric(vertical: 10),
                    ),
                  ),
                ),
                // Status filter chips
                SizedBox(
                  height: 40,
                  child: ListView.separated(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                    itemCount: _statuses.length,
                    separatorBuilder: (_, __) => const SizedBox(width: 6),
                    itemBuilder: (_, i) {
                      final (code, label) = _statuses[i];
                      final selected = p.statusFilter == code;
                      final color = _statusColor(code);
                      return GestureDetector(
                        onTap: () => p.setStatusFilter(code),
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 180),
                          padding: const EdgeInsets.symmetric(
                              horizontal: 14, vertical: 5),
                          decoration: BoxDecoration(
                            color: selected
                                ? color
                                : (isDark
                                    ? Colors.white.withValues(alpha: 0.07)
                                    : Colors.black.withValues(alpha: 0.05)),
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: Text(
                            label,
                            style: TextStyle(
                              color: selected
                                  ? Colors.white
                                  : (isDark ? Colors.white60 : Colors.black54),
                              fontWeight: selected
                                  ? FontWeight.w700
                                  : FontWeight.w500,
                              fontSize: 12,
                            ),
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ]),
            ),
          ),
        ],
        body: () {
          if (p.state == ViewState.loading) {
            return const Center(
              child: CircularProgressIndicator(color: Color(0xFF0EA5E9)),
            );
          }
          if (p.state == ViewState.error) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(mainAxisSize: MainAxisSize.min, children: [
                  const Icon(Icons.error_outline,
                      color: Color(0xFFEF4444), size: 44),
                  const SizedBox(height: 12),
                  Text(p.error,
                      textAlign: TextAlign.center,
                      style: TextStyle(
                          color: isDark ? Colors.white60 : Colors.black54,
                          fontSize: 14)),
                  const SizedBox(height: 20),
                  ElevatedButton.icon(
                    onPressed: () => p.load(force: true),
                    icon: const Icon(Icons.refresh_rounded, size: 16),
                    label: const Text('Qayta urinish'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF0EA5E9),
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12)),
                    ),
                  ),
                ]),
              ),
            );
          }
          if (p.leads.isEmpty) {
            return Center(
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.person_search_rounded,
                    size: 56,
                    color: isDark ? Colors.white24 : Colors.black26),
                const SizedBox(height: 14),
                Text(
                  _query.isNotEmpty
                      ? 'Qidiruv bo\'yicha natija yo\'q'
                      : 'Leadlar topilmadi',
                  style: TextStyle(
                    color: isDark ? Colors.white38 : Colors.black38,
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                if (_query.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text(
                    '"$_query" bo\'yicha hech narsa topilmadi',
                    style: TextStyle(
                        color: isDark ? Colors.white24 : Colors.black26,
                        fontSize: 13),
                  ),
                ],
              ]),
            );
          }

          return RefreshIndicator(
            color: const Color(0xFF0EA5E9),
            onRefresh: () => p.load(q: _query, force: true),
            child: ListView.separated(
              padding: const EdgeInsets.fromLTRB(12, 8, 12, 80),
              itemCount: p.leads.length,
              separatorBuilder: (_, __) => const SizedBox(height: 6),
              itemBuilder: (_, i) => _LeadCard(
                lead: p.leads[i],
                isDark: isDark,
              ),
            ),
          );
        }(),
      ),
    );
  }

  static Color _statusColor(String code) {
    return switch (code) {
      'new' => const Color(0xFF0EA5E9),
      'contacted' => const Color(0xFF3B82F6),
      'trial' => const Color(0xFFF59E0B),
      'confirmed' => const Color(0xFF10B981),
      'converted' => const Color(0xFF059669),
      'canceled' => const Color(0xFFEF4444),
      _ => const Color(0xFF6B7280),
    };
  }
}

class _LeadCard extends StatelessWidget {
  const _LeadCard({required this.lead, required this.isDark});

  final LeadModel lead;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    final statusColor = _statusColor(lead.status);
    final cardBg = isDark ? const Color(0xFF162436) : Colors.white;
    final border =
        isDark ? Colors.white.withValues(alpha: 0.06) : Colors.black.withValues(alpha: 0.05);

    return Container(
      decoration: BoxDecoration(
        color: cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: border),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            // Avatar
            CircleAvatar(
              radius: 22,
              backgroundColor: statusColor.withValues(alpha: 0.15),
              child: Text(
                _initials(lead.fullName),
                style: TextStyle(
                  color: statusColor,
                  fontWeight: FontWeight.w800,
                  fontSize: 14,
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      lead.fullName,
                      style: TextStyle(
                        color: isDark ? Colors.white : const Color(0xFF0F172A),
                        fontWeight: FontWeight.w800,
                        fontSize: 15,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Row(children: [
                      Icon(Icons.phone_rounded,
                          size: 12,
                          color: isDark ? Colors.white38 : Colors.black38),
                      const SizedBox(width: 4),
                      Text(
                        lead.phone,
                        style: TextStyle(
                          color: isDark ? Colors.white54 : Colors.black54,
                          fontSize: 12,
                        ),
                      ),
                    ]),
                  ]),
            ),
            // Status chip
            Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(
                color: statusColor.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                lead.statusLabel.isEmpty ? lead.status : lead.statusLabel,
                style: TextStyle(
                  color: statusColor,
                  fontWeight: FontWeight.w700,
                  fontSize: 11,
                ),
              ),
            ),
          ]),

          if (lead.source.isNotEmpty || lead.nextFollowUpDate != null) ...[
            const SizedBox(height: 10),
            Divider(
              color: isDark
                  ? Colors.white.withValues(alpha: 0.06)
                  : Colors.black.withValues(alpha: 0.05),
              height: 1,
            ),
            const SizedBox(height: 10),
            Row(children: [
              if (lead.source.isNotEmpty) ...[
                Icon(Icons.campaign_rounded,
                    size: 13,
                    color: isDark ? Colors.white38 : Colors.black38),
                const SizedBox(width: 4),
                Text(
                  lead.source,
                  style: TextStyle(
                      color: isDark ? Colors.white54 : Colors.black54,
                      fontSize: 12),
                ),
                const SizedBox(width: 12),
              ],
              if (lead.nextFollowUpDate != null) ...[
                Icon(Icons.event_rounded,
                    size: 13,
                    color: _isOverdue(lead.nextFollowUpDate!)
                        ? const Color(0xFFEF4444)
                        : const Color(0xFFF59E0B)),
                const SizedBox(width: 4),
                Text(
                  _formatDate(lead.nextFollowUpDate!),
                  style: TextStyle(
                    color: _isOverdue(lead.nextFollowUpDate!)
                        ? const Color(0xFFEF4444)
                        : const Color(0xFFF59E0B),
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
              const Spacer(),
              // Call button
              GestureDetector(
                onTap: () => _call(lead.phone),
                child: Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: const Color(0xFF10B981).withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.call_rounded,
                            size: 14, color: Color(0xFF10B981)),
                        SizedBox(width: 4),
                        Text('Qo\'ng\'iroq',
                            style: TextStyle(
                              color: Color(0xFF10B981),
                              fontWeight: FontWeight.w700,
                              fontSize: 11,
                            )),
                      ]),
                ),
              ),
            ]),
          ],
        ]),
      ),
    );
  }

  static Color _statusColor(String code) {
    return switch (code) {
      'new' => const Color(0xFF0EA5E9),
      'contacted' => const Color(0xFF3B82F6),
      'trial' => const Color(0xFFF59E0B),
      'confirmed' => const Color(0xFF10B981),
      'converted' => const Color(0xFF059669),
      'canceled' => const Color(0xFFEF4444),
      _ => const Color(0xFF6B7280),
    };
  }

  static bool _isOverdue(DateTime d) => d.isBefore(DateTime.now());

  static String _formatDate(DateTime d) {
    return '${d.day.toString().padLeft(2, '0')}.${d.month.toString().padLeft(2, '0')}.${d.year}';
  }

  static String _initials(String n) {
    final p = n.trim().split(RegExp(r'\s+')).where((e) => e.isNotEmpty).toList();
    if (p.isEmpty) return '?';
    return p.take(2).map((e) => e[0].toUpperCase()).join();
  }

  static Future<void> _call(String phone) async {
    final uri = Uri(scheme: 'tel', path: phone);
    if (await canLaunchUrl(uri)) await launchUrl(uri);
  }
}
