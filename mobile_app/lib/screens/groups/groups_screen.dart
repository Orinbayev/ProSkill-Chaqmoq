import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/providers/groups_provider.dart';
import 'package:chaqmoq_mobile/widgets/app_input_field.dart';
import 'package:chaqmoq_mobile/widgets/app_list_item_card.dart';
import 'package:chaqmoq_mobile/widgets/app_page_header.dart';
import 'package:chaqmoq_mobile/widgets/empty_state.dart';
import 'package:chaqmoq_mobile/widgets/loading_state.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class GroupsScreen extends StatefulWidget {
  const GroupsScreen({super.key});

  @override
  State<GroupsScreen> createState() => _GroupsScreenState();
}

class _GroupsScreenState extends State<GroupsScreen> {
  final _searchController = TextEditingController();
  bool _queuedLoad = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_queuedLoad) {
      return;
    }
    _queuedLoad = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      context.read<GroupsProvider>().ensureLoaded();
    });
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<GroupsProvider>();
    final query = _searchController.text.trim().toLowerCase();
    final groups = provider.items.where((group) {
      if (query.isEmpty) {
        return true;
      }
      return group.name.toLowerCase().contains(query) ||
          group.category.toLowerCase().contains(query) ||
          group.teacherName.toLowerCase().contains(query);
    }).toList();

    if (provider.isLoading && provider.items.isEmpty) {
      return const LoadingState(title: 'Guruhlar yuklanmoqda...');
    }

    if (provider.errorMessage != null && provider.items.isEmpty) {
      return EmptyState(
        icon: Icons.groups_rounded,
        title: 'Guruhlar bo\'limi ochilmadi',
        message: provider.errorMessage!,
        actionLabel: 'Qayta urinish',
        onAction: () => context.read<GroupsProvider>().load(),
      );
    }

    return RefreshIndicator(
      onRefresh: () => context.read<GroupsProvider>().load(),
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const AppPageHeader(
            title: 'Guruhlar ro\'yxati',
            subtitle:
                'Sig\'im, narx, dars yuklamasi va ustoz birikmasini kuzating.',
          ),
          const SizedBox(height: 14),
          AppInputField(
            controller: _searchController,
            label: 'Qidiruv',
            hint: 'Guruh, yo\'nalish yoki ustoz bo\'yicha qidiring',
            prefixIcon: Icons.search_rounded,
            onChanged: (_) => setState(() {}),
            suffixIcon: query.isEmpty
                ? null
                : IconButton(
                    onPressed: () {
                      _searchController.clear();
                      setState(() {});
                    },
                    icon: const Icon(Icons.close_rounded),
                  ),
          ),
          const SizedBox(height: 14),
          if (groups.isEmpty)
            const EmptyState(
              icon: Icons.groups_2_rounded,
              title: 'Guruhlar topilmadi',
              message: 'Boshqa so\'rov kiriting yoki ma\'lumotlarni yangilang.',
            )
          else
            for (final group in groups) ...[
              AppListItemCard(
                title: group.name,
                subtitle: group.category,
                trailing: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      AppFormatters.formatMoney(group.monthlyPrice),
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    Text(
                      '${group.monthlyLessons} ta dars/oy',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
                tags: [
                  Chip(label: Text(group.isClosed ? 'Yopilgan' : 'Faol')),
                  _MetaPill(
                    icon: Icons.badge_rounded,
                    label: group.teacherName.isEmpty
                        ? 'Biriktirilmagan'
                        : group.teacherName,
                  ),
                  _MetaPill(
                    icon: Icons.people_alt_rounded,
                    label: '${group.studentCount ?? 0} o\'quvchi',
                  ),
                  _MetaPill(
                    icon: Icons.fact_check_rounded,
                    label:
                        '${group.todayAttendanceCount ?? 0} ta bugungi davomat',
                  ),
                  _MetaPill(
                    icon: Icons.percent_rounded,
                    label: '${group.teacherSharePercent}% ustoz ulushi',
                  ),
                ],
              ),
              if (group != groups.last) const SizedBox(height: 14),
            ],
        ],
      ),
    );
  }
}

class _MetaPill extends StatelessWidget {
  const _MetaPill({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: const Color(0xFFE2E8F0)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 18),
          const SizedBox(width: 8),
          Text(label, style: Theme.of(context).textTheme.bodySmall),
        ],
      ),
    );
  }
}
