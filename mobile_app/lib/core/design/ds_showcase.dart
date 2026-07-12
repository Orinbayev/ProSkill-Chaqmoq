import 'package:flutter/material.dart';

import 'ds_colors.dart';
import 'ds_components.dart';
import 'ds_theme.dart';
import 'ds_tokens.dart';
import 'ds_typography.dart';

/// Dizayn tizimi galereyasi — barcha poydevor komponentlari bir joyda.
///
/// Bu ekran ishlab chiqarish ilovasiga kirmaydi; u faqat poydevorni
/// ko'rish/tekshirish uchun (`design_showcase.dart` entrypoint orqali).
class DsShowcaseApp extends StatefulWidget {
  const DsShowcaseApp({super.key});
  @override
  State<DsShowcaseApp> createState() => _DsShowcaseAppState();
}

class _DsShowcaseAppState extends State<DsShowcaseApp> {
  ThemeMode _mode = ThemeMode.light;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Chaqmoq DS',
      theme: DsTheme.light(),
      darkTheme: DsTheme.dark(),
      themeMode: _mode,
      home: DsShowcaseScreen(
        isDark: _mode == ThemeMode.dark,
        onToggleTheme: () => setState(
          () => _mode = _mode == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark,
        ),
      ),
    );
  }
}

class DsShowcaseScreen extends StatefulWidget {
  const DsShowcaseScreen({super.key, required this.isDark, required this.onToggleTheme});
  final bool isDark;
  final VoidCallback onToggleTheme;

  @override
  State<DsShowcaseScreen> createState() => _DsShowcaseScreenState();
}

class _DsShowcaseScreenState extends State<DsShowcaseScreen> {
  int _chip = 0;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 460),
          child: CustomScrollView(
            slivers: [
              SliverAppBar(
                pinned: true,
                backgroundColor: ds.surface,
                surfaceTintColor: Colors.transparent,
                title: Row(
                  children: [
                    Container(
                      width: 34,
                      height: 34,
                      decoration: BoxDecoration(
                        gradient: LinearGradient(colors: ds.primaryGradient),
                        borderRadius: DsRadius.all(DsRadius.sm),
                      ),
                      child: const Icon(Icons.bolt, color: Colors.white, size: 20),
                    ),
                    const SizedBox(width: 10),
                    Text('Chaqmoq — Dizayn tizimi', style: DsType.bodyStrong(ds.textPrimary)),
                  ],
                ),
                actions: [
                  IconButton(
                    onPressed: widget.onToggleTheme,
                    icon: Icon(widget.isDark ? Icons.light_mode_outlined : Icons.dark_mode_outlined,
                        color: ds.textSecondary),
                  ),
                ],
              ),
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(DsSpace.screen, 8, DsSpace.screen, 40),
                sliver: SliverList.list(children: [
                  _group('Ranglar', _colors(ds)),
                  _group('Tipografiya', _typography(ds)),
                  _group('Tugmalar', _buttons()),
                  _group('Status badge', _badges()),
                  _group('Filter chip', _chips()),
                  _group('Input', _inputs()),
                  _group('KPI tile', _kpis()),
                  _group('Ro\'yxat kartasi', _listCard(ds)),
                  _group('To\'lov bottom-sheet', _paymentSheet(ds)),
                ]),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ── layout yordamchi ──
  Widget _group(String title, Widget child) => Padding(
        padding: const EdgeInsets.only(bottom: DsSpace.section),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.only(bottom: 12, top: 8),
              child: Row(children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(color: context.ds.textPrimary, borderRadius: DsRadius.all(4)),
                  child: Text(title.substring(0, 2).toUpperCase(),
                      style: DsType.micro(context.ds.bg)),
                ),
                const SizedBox(width: 8),
                Text(title, style: DsType.h3(context.ds.textPrimary)),
              ]),
            ),
            child,
          ],
        ),
      );

  Widget _swatchRow(List<Color> colors) => ClipRRect(
        borderRadius: DsRadius.all(DsRadius.sm),
        child: Row(children: [for (final c in colors) Expanded(child: Container(height: 40, color: c))]),
      );

  Widget _colors(DsColors ds) => DsCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Primary — Sky', style: DsType.small(ds.textMuted).copyWith(fontWeight: FontWeight.w600)),
          const SizedBox(height: 6),
          _swatchRow(const [
            DsPalette.sky50, DsPalette.sky100, DsPalette.sky200, DsPalette.sky300, DsPalette.sky400,
            DsPalette.sky500, DsPalette.sky600, DsPalette.sky700, DsPalette.sky800, DsPalette.sky900,
          ]),
          const SizedBox(height: 14),
          Text('Neutral — Slate', style: DsType.small(ds.textMuted).copyWith(fontWeight: FontWeight.w600)),
          const SizedBox(height: 6),
          _swatchRow(const [
            DsPalette.slate50, DsPalette.slate100, DsPalette.slate200, DsPalette.slate300, DsPalette.slate400,
            DsPalette.slate500, DsPalette.slate600, DsPalette.slate700, DsPalette.slate800, DsPalette.slate900,
          ]),
          const SizedBox(height: 14),
          Text('Semantik', style: DsType.small(ds.textMuted).copyWith(fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          Wrap(spacing: 8, runSpacing: 8, children: const [
            DsBadge('success', status: DsStatus.success),
            DsBadge('warning', status: DsStatus.warning),
            DsBadge('danger', status: DsStatus.danger),
            DsBadge('info', status: DsStatus.info),
            DsBadge('neutral', status: DsStatus.neutral),
          ]),
        ]),
      );

  Widget _typography(DsColors ds) => DsCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Display 28', style: DsType.display(ds.textPrimary)),
          Text('H1 — 24 bold', style: DsType.h1(ds.textPrimary)),
          Text('H2 — 20 semibold', style: DsType.h2(ds.textPrimary)),
          Text('H3 — 18 semibold', style: DsType.h3(ds.textPrimary)),
          const SizedBox(height: 4),
          Text('Body 15 — O\'quvchilar ro\'yxati va izohlar shu o\'lchamda.', style: DsType.body(ds.textSecondary)),
          Text('Caption 13 — yordamchi matn', style: DsType.caption(ds.textMuted)),
          Text('Small 12 — meta', style: DsType.small(ds.textFaint)),
          const SizedBox(height: 8),
          Text('2 450 000 so\'m', style: DsType.money(ds.textPrimary)),
        ]),
      );

  Widget _buttons() => Column(children: const [
        DsButton(label: 'To\'lov kiritish', onPressed: _noop, icon: Icons.add),
        SizedBox(height: 10),
        DsButton(label: 'Secondary', onPressed: _noop, variant: DsButtonVariant.secondary),
        SizedBox(height: 10),
        DsButton(label: 'Outline', onPressed: _noop, variant: DsButtonVariant.outline),
        SizedBox(height: 10),
        Row(children: [
          Expanded(child: DsButton(label: 'Ghost', onPressed: _noop, variant: DsButtonVariant.ghost)),
          SizedBox(width: 10),
          Expanded(child: DsButton(label: 'Danger', onPressed: _noop, variant: DsButtonVariant.danger)),
        ]),
      ]);

  Widget _badges() => Wrap(spacing: 8, runSpacing: 8, children: const [
        DsBadge('Faol', status: DsStatus.success),
        DsBadge('To\'landi', status: DsStatus.success),
        DsBadge('3 kun', status: DsStatus.warning),
        DsBadge('Qarzdor', status: DsStatus.danger),
        DsBadge('Bloklangan', status: DsStatus.neutral),
        DsBadge('Yangi', status: DsStatus.info),
      ]);

  Widget _chips() => Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [
          for (final (i, label) in ['Barchasi', 'Faol', 'Tugaydigan', 'Bloklangan'].indexed)
            DsChip(label: label, selected: _chip == i, onTap: () => setState(() => _chip = i)),
        ],
      );

  Widget _inputs() => const Column(children: [
        DsTextField(label: 'To\'lov summasi', hint: '450 000', suffixText: 'so\'m', big: true),
        SizedBox(height: 12),
        DsTextField(hint: 'Qidiruv...', prefixIcon: Icons.search),
      ]);

  Widget _kpis() => const Row(children: [
        Expanded(child: DsKpiTile(icon: Icons.apartment, value: '128', label: 'Jami markazlar', tone: DsStatus.info)),
        SizedBox(width: 12),
        Expanded(child: DsKpiTile(icon: Icons.bolt, value: '112', label: 'Faol', tone: DsStatus.success, delta: '4')),
      ]);

  Widget _listCard(DsColors ds) => DsCard(
        padding: const EdgeInsets.symmetric(horizontal: DsSpace.x5, vertical: DsSpace.x2),
        child: Column(children: [
          DsListRow(
            leading: const DsAvatar('Everest Academy', tone: DsStatus.info),
            title: 'Everest Academy',
            subtitle: 'Biznes tarif · oxirgi to\'lov 05.06.2026',
            trailing: const DsBadge('3 kun', status: DsStatus.warning),
          ),
          DsHairline(),
          DsListRow(
            leading: const DsAvatar('Najot Talim', tone: DsStatus.success),
            title: 'Najot Ta\'lim Yunusobod',
            subtitle: 'Premium tarif · oxirgi to\'lov 28.06.2026',
            trailing: const DsBadge('Faol', status: DsStatus.success),
          ),
          DsHairline(),
          DsListRow(
            leading: const DsAvatar('Smart English', tone: DsStatus.warning),
            title: 'Smart English Sergeli',
            subtitle: 'Start tarif · oxirgi to\'lov 12.06.2026',
            trailing: Icon(Icons.chevron_right, color: ds.textFaint),
          ),
        ]),
      );

  Widget _paymentSheet(DsColors ds) => Container(
        decoration: BoxDecoration(
          color: ds.card,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(DsRadius.xl)),
          boxShadow: DsShadow.raised(ds.isDark),
        ),
        padding: const EdgeInsets.all(DsSpace.x5),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Center(
            child: Container(
              width: 40, height: 4,
              decoration: BoxDecoration(color: ds.border, borderRadius: DsRadius.all(DsRadius.pill)),
            ),
          ),
          const SizedBox(height: 16),
          Text('To\'lov kiritish', style: DsType.h3(ds.textPrimary)),
          const SizedBox(height: 4),
          Text('Shohida Egamberdiyeva · IELTS G-1', style: DsType.small(ds.textMuted)),
          const SizedBox(height: 16),
          const DsTextField(label: 'Summa', hint: '450 000', suffixText: 'so\'m', big: true),
          const SizedBox(height: 12),
          Row(children: const [
            Expanded(child: DsButton(label: 'Naqd', onPressed: _noop, variant: DsButtonVariant.secondary)),
            SizedBox(width: 10),
            Expanded(child: DsButton(label: 'Karta', onPressed: _noop, variant: DsButtonVariant.outline)),
          ]),
          const SizedBox(height: 12),
          const DsButton(label: 'Saqlash — 450 000 so\'m', onPressed: _noop),
        ]),
      );
}

void _noop() {}
