import 'dart:math' as math;

import 'package:chaqmoq_mobile/core/theme/app_foundation.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/dashboard_provider.dart';
import 'package:chaqmoq_mobile/widgets/chaqmoq_card.dart';
import 'package:chaqmoq_mobile/widgets/empty_state.dart';
import 'package:chaqmoq_mobile/widgets/loading_state.dart';
import 'package:chaqmoq_mobile/widgets/metric_card.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  bool _queuedInitialLoad = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_queuedInitialLoad) {
      return;
    }
    _queuedInitialLoad = true;
    final user = context.read<AuthProvider>().user;
    if (user != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) {
          return;
        }
        context.read<DashboardProvider>().loadForUser(user);
      });
    }
  }

  Map<String, dynamic> _asMap(dynamic value) {
    return value is Map<String, dynamic> ? value : jsonMap(value);
  }

  List<Map<String, dynamic>> _asMapList(dynamic value) {
    return jsonMapList(value);
  }

  List<num> _asNumList(dynamic value) {
    if (value is! List) {
      return const <num>[];
    }
    return value
        .map((item) => item is num ? item : num.tryParse('$item') ?? 0)
        .toList();
  }

  String _prettyKey(String key) {
    const labels = {
      'revenue': 'Daromad',
      'income': 'Daromad',
      'net_profit': 'Sof foyda',
      'profit': 'Foyda',
      'open_debt': 'Ochiq qarz',
      'debt': 'Qarz',
      'active_students': 'Faol o\'quvchilar',
      'students_count': 'O\'quvchilar soni',
      'groups_count': 'Guruhlar soni',
      'teachers_count': 'O\'qituvchilar soni',
      'attendance_rate': 'Davomat',
      'lead_conversion': 'Lid konversiyasi',
      'balance': 'Balans',
      'children_count': 'Farzandlar soni',
      'present_lessons': 'Qatnashgan darslar',
      'recent_present_lessons': 'Yaqin davr qatnashuv',
      'total_lessons': 'Jami darslar',
      'recent_total_lessons': 'Yaqin davr darslari',
      'recent_attendance_rate': 'So\'nggi davomat',
      'groups': 'Guruhlar',
      'students': 'O\'quvchilar',
      'teachers': 'O\'qituvchilar',
      'payments': 'To\'lovlar',
      'certificates': 'Sertifikatlar',
      'unread_notifications': 'O\'qilmagan xabarlar',
      'today_payments': 'Bugungi to\'lovlar',
      'total': 'Jami',
      'active': 'Faol',
      'inactive': 'Nofaol',
      'new_count': 'Yangi o\'quvchilar',
      'debtors_count': 'Qarzdorlar',
    };
    if (labels.containsKey(key)) {
      return labels[key]!;
    }
    return key
        .replaceAll('_', ' ')
        .split(' ')
        .where((part) => part.isNotEmpty)
        .map((part) => '${part[0].toUpperCase()}${part.substring(1)}')
        .join(' ');
  }

  bool _isMoneyKey(String key) {
    final lower = key.toLowerCase();
    return lower.contains('money') ||
        lower.contains('income') ||
        lower.contains('revenue') ||
        lower.contains('profit') ||
        lower.contains('expense') ||
        lower.contains('debt') ||
        lower.contains('payment') ||
        lower.contains('amount') ||
        lower.contains('cost') ||
        lower.contains('cashflow');
  }

  bool _isPercentKey(String key) {
    final lower = key.toLowerCase();
    return lower.contains('rate') ||
        lower.contains('pct') ||
        lower.contains('margin') ||
        lower.contains('fill') ||
        lower.contains('score') ||
        lower.contains('growth') ||
        lower.contains('discipline') ||
        lower.contains('conversion') ||
        lower.contains('risk');
  }

  String _formatValueForKey(String key, dynamic value) {
    if (value is bool) {
      return AppFormatters.yesNo(value);
    }
    if (value is num) {
      if (key == 'pct_signed') {
        return AppFormatters.formatPercent(value, signed: true);
      }
      if (_isMoneyKey(key)) {
        return AppFormatters.formatMoney(value);
      }
      if (_isPercentKey(key)) {
        return AppFormatters.formatPercent(value);
      }
      return AppFormatters.formatNumber(value);
    }
    if (value == null) {
      return '0';
    }
    return '$value';
  }

  IconData _iconForKey(String key) {
    final lower = key.toLowerCase();
    if (lower.contains('student')) {
      return Icons.school_rounded;
    }
    if (lower.contains('teacher')) {
      return Icons.badge_rounded;
    }
    if (lower.contains('payment') ||
        lower.contains('income') ||
        lower.contains('revenue') ||
        lower.contains('debt') ||
        lower.contains('profit')) {
      return Icons.payments_rounded;
    }
    if (lower.contains('group')) {
      return Icons.groups_rounded;
    }
    if (lower.contains('attendance')) {
      return Icons.fact_check_rounded;
    }
    if (lower.contains('lead')) {
      return Icons.insights_rounded;
    }
    return Icons.auto_graph_rounded;
  }

  Color _colorForIndex(int index) {
    const palette = [
      Color(0xFF0EA5E9),
      Color(0xFF14B8A6),
      Color(0xFFF97316),
      Color(0xFF8B5CF6),
      Color(0xFFEF4444),
      Color(0xFF10B981),
    ];
    return palette[index % palette.length];
  }

  List<MapEntry<String, dynamic>> _scalarEntries(Map<String, dynamic> data) {
    return data.entries.where((entry) {
      final value = entry.value;
      return value is num || value is String || value is bool;
    }).toList();
  }

  Widget _buildMetricGrid(Map<String, dynamic> data) {
    final entries = _scalarEntries(data);
    if (entries.isEmpty) {
      return const SizedBox.shrink();
    }

    return GridView.builder(
      itemCount: entries.length,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        crossAxisSpacing: 14,
        mainAxisSpacing: 14,
        childAspectRatio: 1.05,
      ),
      itemBuilder: (context, index) {
        final entry = entries[index];
        return MetricCard(
          label: _prettyKey(entry.key),
          value: _formatValueForKey(entry.key, entry.value),
          icon: _iconForKey(entry.key),
          tint: _colorForIndex(index),
        );
      },
    );
  }

  Widget _buildSectionCard(String title, Map<String, dynamic> data) {
    final entries = _scalarEntries(data);
    if (entries.isEmpty) {
      return const SizedBox.shrink();
    }

    return ChaqmoqCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 14),
          for (final entry in entries) ...[
            Row(
              children: [
                Expanded(child: Text(_prettyKey(entry.key))),
                const SizedBox(width: 12),
                Text(
                  _formatValueForKey(entry.key, entry.value),
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ],
            ),
            if (entry != entries.last) const Divider(height: 24),
          ],
        ],
      ),
    );
  }

  Widget _buildFocusItems(Map<String, dynamic> overview) {
    final items = _asMapList(overview['focus_items']);
    if (items.isEmpty) {
      return const SizedBox.shrink();
    }

    final visible = items.take(4).toList();

    return ChaqmoqCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Bugungi fokus nuqtalari',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 14),
          for (final item in visible) ...[
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: CircleAvatar(
                backgroundColor: const Color(0xFFFEF3C7),
                child: const Icon(Icons.track_changes_rounded),
              ),
              title: Text(jsonString(item['title'])),
              subtitle: Text(jsonString(item['note'])),
              trailing: Text(
                jsonString(item['value']),
                style: Theme.of(
                  context,
                ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w800),
              ),
            ),
            if (item != visible.last) const Divider(height: 8),
          ],
        ],
      ),
    );
  }

  Widget _buildHealthSummary(Map<String, dynamic> health) {
    final normalized = {
      'Kuchli': jsonInt(health['strong']),
      'Barqaror': jsonInt(health['stable']),
      'Xavfli': jsonInt(health['risky']),
      'Zaif': jsonInt(health['weak']),
      'Yopishga yaqin': jsonInt(health['close_candidate']),
    };
    if (normalized.values.every((value) => value == 0)) {
      return const SizedBox.shrink();
    }

    return ChaqmoqCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Guruhlar sog\'lig\'i',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              for (final entry in normalized.entries)
                _InfoChip(label: entry.key, value: '${entry.value} ta'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildFinanceSnapshot(Map<String, dynamic> finance) {
    if (finance.isEmpty) {
      return const SizedBox.shrink();
    }

    return ChaqmoqCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Moliyaviy ko\'rsatkichlar',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 14),
          _buildMetricGrid({
            'income': finance['income'] ?? 0,
            'profit': finance['profit'] ?? 0,
            'open_debt': finance['open_debt'] ?? 0,
            'avg_payment': finance['avg_payment'] ?? 0,
            'profit_margin': finance['profit_margin'] ?? 0,
            'debt_ratio': finance['debt_ratio'] ?? 0,
          }),
        ],
      ),
    );
  }

  String _titleForItem(Map<String, dynamic> item) {
    for (final key in [
      'title',
      'name',
      'full_name',
      'group_name',
      'teacher_name',
      'stage',
      'label',
    ]) {
      final value = item[key];
      if (value != null && '$value'.trim().isNotEmpty) {
        return '$value';
      }
    }
    return 'Yozuv';
  }

  String _subtitleForItem(Map<String, dynamic> item) {
    for (final key in [
      'text',
      'note',
      'message',
      'detail',
      'reason',
      'groups',
      'course',
      'type',
      'status',
      'phone',
    ]) {
      final value = item[key];
      if (value is List && value.isNotEmpty) {
        return value.join(', ');
      }
      if (value != null && '$value'.trim().isNotEmpty) {
        return '$value';
      }
    }
    return '';
  }

  String _trailingForItem(Map<String, dynamic> item) {
    for (final key in [
      'value',
      'amount',
      'debt',
      'revenue',
      'count',
      'status',
      'health_label',
    ]) {
      final value = item[key];
      if (value == null) {
        continue;
      }
      if (value is num) {
        return _formatValueForKey(key, value);
      }
      if (key == 'health_label') {
        return AppFormatters.healthLabel('$value');
      }
      if ('$value'.trim().isNotEmpty) {
        return '$value';
      }
    }
    return '';
  }

  Widget _buildCollectionSection(
    String title,
    List<Map<String, dynamic>> items, {
    int limit = 5,
  }) {
    if (items.isEmpty) {
      return const SizedBox.shrink();
    }

    final visible = items.take(limit).toList();

    return ChaqmoqCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 14),
          for (final item in visible) ...[
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: CircleAvatar(
                backgroundColor: Theme.of(
                  context,
                ).colorScheme.primary.withValues(alpha: 0.12),
                child: Text(
                  _titleForItem(item).characters.first.toUpperCase(),
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              title: Text(_titleForItem(item)),
              subtitle: _subtitleForItem(item).isEmpty
                  ? null
                  : Text(_subtitleForItem(item)),
              trailing: _trailingForItem(item).isEmpty
                  ? null
                  : Text(
                      _trailingForItem(item),
                      style: Theme.of(
                        context,
                      ).textTheme.bodyMedium?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                    ),
            ),
            if (item != visible.last) const Divider(height: 8),
          ],
        ],
      ),
    );
  }

  Widget _buildHero(AppUser user, RoleHomeModel? roleHome) {
    final centerName =
        roleHome?.center?.name ?? user.center?.name ?? 'Chaqmoq markazi';
    final slug = roleHome?.center?.slug ?? user.center?.slug ?? '';
    final role = user.effectiveRole;
    final roleGradient = switch (role) {
      'superadmin' => const LinearGradient(
          colors: [Color(0xFF111827), Color(0xFF1D4ED8), Color(0xFF0EA5E9)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      'director' => const LinearGradient(
          colors: [Color(0xFF0B1220), Color(0xFF0F6CBD), Color(0xFF14B8A6)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      'manager' => const LinearGradient(
          colors: [Color(0xFF172554), Color(0xFF0F766E), Color(0xFF38BDF8)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      'teacher' => const LinearGradient(
          colors: [Color(0xFF0F172A), Color(0xFF7C3AED), Color(0xFF22C55E)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      'student' => const LinearGradient(
          colors: [Color(0xFF0F172A), Color(0xFF2563EB), Color(0xFFF59E0B)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      'parent' => const LinearGradient(
          colors: [Color(0xFF0F172A), Color(0xFF0891B2), Color(0xFF14B8A6)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      _ => AppGradients.brand,
    };
    final roleSubtitle = switch (role) {
      'superadmin' => 'Tizim bo\'yicha markazlar, tariflar va umumiy faollik nazorati',
      'director' => 'Daromad, o\'quvchilar va markaz salomatligini bir oynada kuzating',
      'manager' => 'Kunlik operatsiyalar, jamoa yuklamasi va bajariladigan ishlarni boshqaring',
      'teacher' => 'Biriktirilgan guruhlar, davomat va kutilayotgan tushumni kuzating',
      'student' => 'Darslar, to\'lovlar va shaxsiy o\'quv jarayoningiz shu yerda',
      'parent' => 'Farzandingizning rivoji, to\'lovlari va davomatini kuzating',
      _ => 'Ish maydoningiz bo\'yicha asosiy ko\'rsatkichlar',
    };

    return ChaqmoqCard(
      gradient: roleGradient,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Xush kelibsiz, ${user.ism.isEmpty ? user.fullName : user.ism}',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '$centerName${slug.isEmpty ? '' : ' • $slug'}',
            style: Theme.of(
              context,
            ).textTheme.bodyLarge?.copyWith(color: Colors.white70),
          ),
          const SizedBox(height: 10),
          Text(
            roleSubtitle,
            style: Theme.of(
              context,
            ).textTheme.bodyMedium?.copyWith(color: Colors.white70),
          ),
          const SizedBox(height: 18),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              _HeroPill(
                label: AppFormatters.roleLabel(user.effectiveRole),
                icon: Icons.workspace_premium_rounded,
              ),
              _HeroPill(
                label: '${roleHome?.unreadNotifications ?? 0} ta o\'qilmagan xabar',
                icon: Icons.notifications_active_rounded,
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSuperadmin(DashboardProvider dashboard) {
    final home = dashboard.superadminHome;
    if (home == null) {
      return const SizedBox.shrink();
    }

    return Column(
      children: [
        _buildMetricGrid(home.summary),
        const SizedBox(height: 14),
        ChaqmoqCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Markazlar', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 14),
              for (final center in home.centers) ...[
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: CircleAvatar(
                    backgroundColor: const Color(0xFFE0F2FE),
                    child: Text(
                      center.name.characters.take(1).toString().toUpperCase(),
                    ),
                  ),
                  title: Text(center.name),
                  subtitle: Text('${center.slug} • ${center.plan}'),
                  trailing: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        '${center.studentsCount} o\'quvchi',
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      Text(
                        AppFormatters.formatMoney(center.todayPayments),
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
                if (center != home.centers.last) const Divider(height: 12),
              ],
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildTeacher(DashboardProvider dashboard) {
    final home = dashboard.teacherHome ?? {};
    final groups = _asMapList(home['groups']);

    return Column(
      children: [
        _buildMetricGrid(dashboard.roleHome?.summary ?? {}),
        const SizedBox(height: 14),
        if (_asMap(home['expected_income']).isNotEmpty)
          _buildSectionCard(
            'Kutilayotgan daromad',
            _asMap(home['expected_income']),
          ),
        if (_asMap(home['expected_income']).isNotEmpty)
          const SizedBox(height: 14),
        _buildCollectionSection('Sizga biriktirilgan guruhlar', groups),
      ],
    );
  }

  Widget _buildStudentSummary(Map<String, dynamic> summary) {
    final payments = _asMapList(summary['payments']);
    final groups = _asMapList(summary['groups']);
    final certificates = _asMapList(summary['certificates']);

    return Column(
      children: [
        _buildMetricGrid({
          'balance': summary['balance'] ?? 0,
          'debt': summary['debt'] ?? 0,
          ..._asMap(summary['attendance']),
        }),
        const SizedBox(height: 14),
        _buildCollectionSection('Joriy guruhlar', groups),
        if (payments.isNotEmpty) ...[
          const SizedBox(height: 14),
          _buildCollectionSection('So\'nggi to\'lovlar', payments),
        ],
        if (certificates.isNotEmpty) ...[
          const SizedBox(height: 14),
          _buildCollectionSection('Sertifikatlar', certificates),
        ],
      ],
    );
  }

  Widget _buildParentSummary(Map<String, dynamic> summary) {
    final children = _asMapList(summary['children']);

    return Column(
      children: [
        _buildMetricGrid({
          'children_count': summary['children_count'] ?? children.length,
        }),
        const SizedBox(height: 14),
        for (final child in children) ...[
          ChaqmoqCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  child['full_name']?.toString() ?? 'O\'quvchi',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 12),
                _buildMetricGrid({
                  'balance': child['balance'] ?? 0,
                  'debt': child['debt'] ?? 0,
                }),
              ],
            ),
          ),
          if (child != children.last) const SizedBox(height: 14),
        ],
      ],
    );
  }

  Widget _buildTodayStrip(Map<String, dynamic> executive) {
    final items = _asMapList(executive['today_strip']);
    if (items.isEmpty) {
      return const SizedBox.shrink();
    }

    return GridView.builder(
      itemCount: items.length,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        crossAxisSpacing: 14,
        mainAxisSpacing: 14,
        childAspectRatio: 1.2,
      ),
      itemBuilder: (context, index) {
        final item = items[index];
        final kind = jsonString(item['kind']);
        final value = item['value'];
        final formatted = kind == 'money'
            ? AppFormatters.formatMoney(value is num ? value : jsonDouble(value))
            : value is num
            ? AppFormatters.formatNumber(value)
            : '$value';
        return ChaqmoqCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                jsonString(item['label']),
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const Spacer(),
              Text(
                formatted,
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                jsonString(item['detail']),
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildTrendSignal(Map<String, dynamic> executive) {
    final signal = _asMap(executive['trend_signal']);
    if (signal.isEmpty) {
      return const SizedBox.shrink();
    }
    final chips = _asMapList(signal['chips']);

    return ChaqmoqCard(
      gradient: const LinearGradient(
        colors: [Color(0xFFECFEFF), Color(0xFFF0FDF4)],
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            jsonString(signal['title']),
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            jsonString(signal['text']),
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          if (chips.isNotEmpty) ...[
            const SizedBox(height: 14),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                for (final chip in chips)
                  _InfoChip(
                    label: jsonString(chip['label']),
                    value: _formatValueForKey(
                      jsonString(chip['kind']),
                      chip['value'],
                    ),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildProblemHub(Map<String, dynamic> executive) {
    final items = _asMapList(executive['problem_hub']);
    if (items.isEmpty) {
      return const SizedBox.shrink();
    }

    return ChaqmoqCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'E\'tibor talab qiladigan nuqtalar',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 14),
          for (final item in items) ...[
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: CircleAvatar(
                backgroundColor: const Color(0xFFFEE2E2),
                child: const Icon(
                  Icons.priority_high_rounded,
                  color: Color(0xFFB91C1C),
                ),
              ),
              title: Text(jsonString(item['label'])),
              subtitle: Text(
                '${jsonString(item['detail_prefix'])}: ${_formatValueForKey(jsonString(item['detail_kind']), item['detail'])}',
              ),
              trailing: Text(
                _formatValueForKey(jsonString(item['kind']), item['value']),
                style: Theme.of(
                  context,
                ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
              ),
            ),
            if (item != items.last) const Divider(height: 8),
          ],
        ],
      ),
    );
  }

  Widget _buildPlans(Map<String, dynamic> plans) {
    if (plans.isEmpty) {
      return const SizedBox.shrink();
    }

    return ChaqmoqCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Reja bajarilishi', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 14),
          for (final entry in plans.entries) ...[
            _PlanProgressRow(title: _prettyKey(entry.key), plan: _asMap(entry.value)),
            if (entry.key != plans.keys.last) const SizedBox(height: 14),
          ],
        ],
      ),
    );
  }

  Widget _buildBarsCard({
    required String title,
    required List<String> labels,
    required List<num> values,
    required Color color,
    required String Function(num value) formatter,
  }) {
    if (labels.isEmpty || values.isEmpty) {
      return const SizedBox.shrink();
    }
    final length = math.min(labels.length, values.length);
    final visibleLabels = labels.take(length).toList();
    final visibleValues = values.take(length).toList();
    final maxValue = visibleValues.fold<num>(0, (max, item) => item > max ? item : max);

    return ChaqmoqCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 14),
          for (var i = 0; i < length; i++) ...[
            Row(
              children: [
                SizedBox(width: 56, child: Text(visibleLabels[i])),
                const SizedBox(width: 10),
                Expanded(
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(999),
                    child: LinearProgressIndicator(
                      value: maxValue <= 0 ? 0 : visibleValues[i] / maxValue,
                      minHeight: 10,
                      color: color,
                      backgroundColor: color.withValues(alpha: 0.12),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                SizedBox(
                  width: 96,
                  child: Text(
                    formatter(visibleValues[i]),
                    textAlign: TextAlign.right,
                    style: Theme.of(
                      context,
                    ).textTheme.bodySmall?.copyWith(fontWeight: FontWeight.w800),
                  ),
                ),
              ],
            ),
            if (i != length - 1) const SizedBox(height: 12),
          ],
        ],
      ),
    );
  }

  Widget _buildTopDebtors(Map<String, dynamic> finance) {
    final items = _asMapList(finance['top_debtors']);
    if (items.isEmpty) {
      return const SizedBox.shrink();
    }
    return ChaqmoqCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Eng katta qarzdorlar', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 14),
          for (final item in items.take(6)) ...[
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: CircleAvatar(
                backgroundColor: const Color(0xFFFEF3C7),
                child: Text(
                  jsonString(item['student_name']).characters.first.toUpperCase(),
                ),
              ),
              title: Text(jsonString(item['student_name'])),
              subtitle: Text(
                (item['groups'] as List?)?.join(', ') ?? 'Guruh biriktirilmagan',
              ),
              trailing: Text(
                AppFormatters.formatMoney(jsonDouble(item['debt'])),
                style: Theme.of(
                  context,
                ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w800),
              ),
            ),
            if (item != items.take(6).last) const Divider(height: 8),
          ],
        ],
      ),
    );
  }

  Widget _buildTeacherRanking(Map<String, dynamic> teachers) {
    final items = _asMapList(teachers['ranking']);
    if (items.isEmpty) {
      return const SizedBox.shrink();
    }
    return ChaqmoqCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'O\'qituvchilar reytingi',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 14),
          for (final item in items.take(6)) ...[
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: CircleAvatar(
                backgroundColor: const Color(0xFFDBEAFE),
                child: Text(
                  jsonString(item['teacher_name']).characters.first.toUpperCase(),
                ),
              ),
              title: Text(jsonString(item['teacher_name'])),
              subtitle: Text(
                '${jsonInt(item['students'])} o\'quvchi • ${jsonInt(item['groups'])} guruh',
              ),
              trailing: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    AppFormatters.formatMoney(jsonDouble(item['revenue'])),
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  Text(
                    'Sog\'liq: ${AppFormatters.formatPercent(jsonDouble(item['health_score']))}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
            if (item != items.take(6).last) const Divider(height: 8),
          ],
        ],
      ),
    );
  }

  Widget _buildGroupHighlights(Map<String, dynamic> groups) {
    final top = _asMapList(groups['top_profitable']);
    final weak = _asMapList(groups['least_profitable']);
    final promotions = _asMapList(groups['promotion_candidates']);
    final mostIndebted = _asMap(groups['most_indebted']);

    return Column(
      children: [
        if (promotions.isNotEmpty)
          _buildCollectionSection('O\'sishga tayyor guruhlar', promotions, limit: 3),
        if (promotions.isNotEmpty) const SizedBox(height: 14),
        if (top.isNotEmpty)
          _buildCollectionSection('Eng foydali guruhlar', top, limit: 4),
        if (top.isNotEmpty) const SizedBox(height: 14),
        if (weak.isNotEmpty)
          _buildCollectionSection('Zaif guruhlar', weak, limit: 4),
        if (weak.isNotEmpty && mostIndebted.isNotEmpty) const SizedBox(height: 14),
        if (mostIndebted.isNotEmpty)
          ChaqmoqCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Eng qarzdor guruh',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 12),
                Text(
                  jsonString(mostIndebted['group_name']),
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  'Qarz: ${AppFormatters.formatMoney(jsonDouble(mostIndebted['open_debt']))}',
                ),
                Text(
                  'Faol o\'quvchilar: ${jsonInt(mostIndebted['active_students'])}',
                ),
                Text('Holati: ${AppFormatters.healthLabel(jsonString(mostIndebted['health_label']))}'),
                const SizedBox(height: 8),
                Text(
                  jsonString(mostIndebted['primary_action']),
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }

  Widget _buildRiskStudents(Map<String, dynamic> students) {
    final items = _asMapList(students['risk_students']);
    if (items.isEmpty) {
      return const SizedBox.shrink();
    }
    return ChaqmoqCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Xavfdagi o\'quvchilar',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 14),
          for (final item in items.take(6)) ...[
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: CircleAvatar(
                backgroundColor: const Color(0xFFFEE2E2),
                child: Text(jsonString(item['name']).characters.first.toUpperCase()),
              ),
              title: Text(jsonString(item['name'])),
              subtitle: Text(jsonString(item['reason'])),
              trailing: Text(
                AppFormatters.formatPercent(jsonDouble(item['risk_score'])),
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
            if (item != items.take(6).last) const Divider(height: 8),
          ],
        ],
      ),
    );
  }

  Widget _buildMarketing(Map<String, dynamic> marketing) {
    final funnel = _asMapList(marketing['funnel']);
    final bestSource = marketing['best_source'];
    final worstSource = marketing['worst_source'];
    if (marketing.isEmpty) {
      return const SizedBox.shrink();
    }
    return ChaqmoqCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Marketing voronkasi', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 14),
          _InfoChip(
            label: 'Jami lidlar',
            value: AppFormatters.formatNumber(jsonInt(marketing['total_leads'])),
          ),
          const SizedBox(height: 12),
          _InfoChip(
            label: 'Konversiya',
            value: AppFormatters.formatPercent(
              jsonDouble(marketing['conversion_rate']),
            ),
          ),
          const SizedBox(height: 12),
          _InfoChip(
            label: 'Faol o\'quvchilar',
            value: AppFormatters.formatNumber(
              jsonInt(marketing['active_students']),
            ),
          ),
          if (bestSource != null || worstSource != null) ...[
            const SizedBox(height: 12),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                if (bestSource != null)
                  _InfoChip(label: 'Eng yaxshi manba', value: '$bestSource'),
                if (worstSource != null)
                  _InfoChip(label: 'Sust manba', value: '$worstSource'),
              ],
            ),
          ],
          if (funnel.isNotEmpty) ...[
            const SizedBox(height: 14),
            for (final item in funnel) ...[
              Row(
                children: [
                  Expanded(child: Text(jsonString(item['stage']))),
                  Text(
                    AppFormatters.formatNumber(jsonInt(item['count'])),
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ],
              ),
              if (item != funnel.last) const SizedBox(height: 10),
            ],
          ],
        ],
      ),
    );
  }

  Widget _buildInsights(List<Map<String, dynamic>> insights) {
    if (insights.isEmpty) {
      return const SizedBox.shrink();
    }
    return ChaqmoqCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Tavsiyalar va xulosalar', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 14),
          for (final insight in insights.take(6)) ...[
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: CircleAvatar(
                backgroundColor: const Color(0xFFE0F2FE),
                child: const Icon(Icons.tips_and_updates_rounded),
              ),
              title: Text(jsonString(insight['title'])),
              subtitle: Text(jsonString(insight['text'])),
            ),
            if (insight != insights.take(6).last) const Divider(height: 8),
          ],
        ],
      ),
    );
  }

  Widget _buildDirectorManager(DashboardProvider dashboard) {
    final payload = dashboard.directorDashboard ?? const <String, dynamic>{};
    final overview = _asMap(payload['overview']);
    final executive = _asMap(payload['executive']);
    final finance = _asMap(payload['finance']);
    final students = _asMap(payload['students']);
    final teachers = _asMap(payload['teachers']);
    final groups = _asMap(payload['groups']);
    final charts = _asMap(payload['charts']);
    final marketing = _asMap(payload['marketing']);
    final plans = _asMap(payload['plans']);
    final insights = _asMapList(payload['insights']);
    final summary = _asMap(overview['kpis']);
    final healthSummary = _asMap(overview['health_summary']);
    final labels = (charts['labels'] as List?)?.map((item) => '$item').toList() ?? const <String>[];

    return Column(
      children: [
        _buildMetricGrid(summary),
        const SizedBox(height: 14),
        _buildFocusItems(overview),
        const SizedBox(height: 14),
        _buildTodayStrip(executive),
        const SizedBox(height: 14),
        _buildTrendSignal(executive),
        const SizedBox(height: 14),
        _buildProblemHub(executive),
        const SizedBox(height: 14),
        _buildHealthSummary(healthSummary),
        const SizedBox(height: 14),
        _buildFinanceSnapshot(finance),
        const SizedBox(height: 14),
        _buildPlans(plans),
        const SizedBox(height: 14),
        _buildBarsCard(
          title: 'Tushum dinamikasi',
          labels: labels,
          values: _asNumList(charts['income']),
          color: const Color(0xFF0EA5E9),
          formatter: AppFormatters.formatMoney,
        ),
        const SizedBox(height: 14),
        _buildBarsCard(
          title: 'Xarajat dinamikasi',
          labels: labels,
          values: _asNumList(charts['expenses']),
          color: const Color(0xFFF97316),
          formatter: AppFormatters.formatMoney,
        ),
        const SizedBox(height: 14),
        _buildBarsCard(
          title: 'Yangi o\'quvchilar oqimi',
          labels: labels,
          values: _asNumList(charts['new_students']),
          color: const Color(0xFF10B981),
          formatter: (value) => AppFormatters.formatNumber(value),
        ),
        const SizedBox(height: 14),
        _buildBarsCard(
          title: 'Qarzdorlar soni',
          labels: labels,
          values: _asNumList(charts['debt_students']),
          color: const Color(0xFFEF4444),
          formatter: (value) => AppFormatters.formatNumber(value),
        ),
        const SizedBox(height: 14),
        _buildBarsCard(
          title: 'Sof pul oqimi',
          labels: labels,
          values: _asNumList(charts['cashflow']),
          color: const Color(0xFF14B8A6),
          formatter: AppFormatters.formatMoney,
        ),
        const SizedBox(height: 14),
        _buildBarsCard(
          title: 'Ochiq qarz dinamikasi',
          labels: labels,
          values: _asNumList(charts['debt_series']),
          color: const Color(0xFFF59E0B),
          formatter: AppFormatters.formatMoney,
        ),
        const SizedBox(height: 14),
        _buildTopDebtors(finance),
        const SizedBox(height: 14),
        _buildTeacherRanking(teachers),
        const SizedBox(height: 14),
        _buildGroupHighlights(groups),
        const SizedBox(height: 14),
        _buildRiskStudents(students),
        const SizedBox(height: 14),
        _buildMarketing(marketing),
        const SizedBox(height: 14),
        _buildInsights(insights),
      ],
    );
  }

  Widget _buildManagerBoard(DashboardProvider dashboard) {
    final payload = dashboard.directorDashboard ?? const <String, dynamic>{};
    final overview = _asMap(payload['overview']);
    final executive = _asMap(payload['executive']);
    final students = _asMap(payload['students']);
    final teachers = _asMap(payload['teachers']);
    final groups = _asMap(payload['groups']);
    final marketing = _asMap(payload['marketing']);
    final insights = _asMapList(payload['insights']);

    return Column(
      children: [
        _buildMetricGrid({
          ..._asMap(overview['kpis']),
          'teachers_count': teachers['total_count'] ?? 0,
          'groups_count': groups['total_count'] ?? 0,
        }),
        const SizedBox(height: 14),
        _buildTodayStrip(executive),
        const SizedBox(height: 14),
        _buildProblemHub(executive),
        const SizedBox(height: 14),
        _buildTeacherRanking(teachers),
        const SizedBox(height: 14),
        _buildGroupHighlights(groups),
        const SizedBox(height: 14),
        _buildRiskStudents(students),
        const SizedBox(height: 14),
        _buildMarketing(marketing),
        const SizedBox(height: 14),
        _buildInsights(insights),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final dashboard = context.watch<DashboardProvider>();
    final user = auth.user;

    if (user == null) {
      return const SizedBox.shrink();
    }

    if (dashboard.isLoading && dashboard.roleHome == null) {
      return const LoadingState();
    }

    if (dashboard.errorMessage != null && dashboard.roleHome == null) {
      return EmptyState(
        icon: Icons.cloud_off_rounded,
        title: 'Asosiy panel ochilmadi',
        message: dashboard.errorMessage!,
        actionLabel: 'Qayta urinish',
        onAction: () =>
            context.read<DashboardProvider>().loadForUser(user, force: true),
      );
    }

    final roleHome = dashboard.roleHome;
    final role = user.effectiveRole;

    return RefreshIndicator(
      onRefresh: () =>
          context.read<DashboardProvider>().loadForUser(user, force: true),
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          _buildHero(user, roleHome),
          const SizedBox(height: 16),
          if (dashboard.errorMessage != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(
                dashboard.errorMessage!,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.error,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          switch (role) {
            'superadmin' => _buildSuperadmin(dashboard),
            'director' => _buildDirectorManager(dashboard),
            'manager' => _buildManagerBoard(dashboard),
            'teacher' => _buildTeacher(dashboard),
            'student' => _buildStudentSummary(roleHome?.summary ?? const {}),
            'parent' => _buildParentSummary(roleHome?.summary ?? const {}),
            _ => _buildMetricGrid(roleHome?.summary ?? const {}),
          },
        ],
      ),
    );
  }
}

class _HeroPill extends StatelessWidget {
  const _HeroPill({required this.label, required this.icon});

  final String label;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 18, color: Colors.white),
          const SizedBox(width: 8),
          Text(
            label,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

class _InfoChip extends StatelessWidget {
  const _InfoChip({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFE2E8F0)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            '$label: ',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          Text(
            value,
            style: Theme.of(
              context,
            ).textTheme.bodySmall?.copyWith(fontWeight: FontWeight.w800),
          ),
        ],
      ),
    );
  }
}

class _PlanProgressRow extends StatelessWidget {
  const _PlanProgressRow({required this.title, required this.plan});

  final String title;
  final Map<String, dynamic> plan;

  @override
  Widget build(BuildContext context) {
    final pct = jsonInt(plan['pct']).clamp(0, 100);
    final current = plan['current'];
    final target = plan['target'];
    final isMoney =
        title.toLowerCase().contains('daromad') ||
        title.toLowerCase().contains('moliya');

    String format(dynamic value) {
      final parsed = value is num ? value : num.tryParse('$value') ?? 0;
      return isMoney
          ? AppFormatters.formatMoney(parsed)
          : AppFormatters.formatNumber(parsed);
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                title,
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            Text(
              '$pct%',
              style: Theme.of(
                context,
              ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w800),
            ),
          ],
        ),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(999),
          child: LinearProgressIndicator(
            value: pct / 100,
            minHeight: 10,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          '${format(current)} / ${format(target)}',
          style: Theme.of(context).textTheme.bodySmall,
        ),
      ],
    );
  }
}
