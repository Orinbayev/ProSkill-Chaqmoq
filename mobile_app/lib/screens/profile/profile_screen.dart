import 'package:chaqmoq_mobile/core/design/ds_colors.dart';
import 'package:chaqmoq_mobile/core/design/ds_components.dart';
import 'package:chaqmoq_mobile/core/design/ds_typography.dart';
import 'package:chaqmoq_mobile/models/parent_models.dart';
import 'package:chaqmoq_mobile/providers/parent_dashboard_provider.dart';
import 'package:chaqmoq_mobile/screens/parent/add_child_screen.dart';
import 'package:chaqmoq_mobile/screens/profile/ideal_profile_screen.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/parent_dashboard_service.dart';
import 'package:chaqmoq_mobile/widgets/adaptive_avatar.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

/// Ota-ona profili — ideal profil + farzandlar bo‘limi.
class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key, this.showBottomNav = true});

  final bool showBottomNav;

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  List<ParentChildModel> _children = const [];
  bool _loadingChildren = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadChildren());
  }

  Future<void> _loadChildren() async {
    setState(() => _loadingChildren = true);
    try {
      final profile = await context.read<ParentDashboardService>().fetchProfile();
      if (!mounted) return;
      setState(() {
        _children = profile.children;
        _loadingChildren = false;
      });
    } on ApiException {
      if (mounted) setState(() => _loadingChildren = false);
    } catch (_) {
      if (mounted) setState(() => _loadingChildren = false);
    }
  }

  Future<void> _addChild() async {
    final created = await Navigator.of(context).push<ParentChildModel>(
      MaterialPageRoute(builder: (_) => const AddChildScreen()),
    );
    if (created == null || !mounted) return;
    await context.read<ParentDashboardProvider>().selectChild(created.id);
    await _loadChildren();
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Farzand muvaffaqiyatli qo‘shildi')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return IdealProfileScreen(
      title: 'Profil',
      extraSections: [
        _ChildrenSection(
          children: _children,
          loading: _loadingChildren,
          onAdd: _addChild,
          onRefresh: _loadChildren,
        ),
      ],
    );
  }
}

class _ChildrenSection extends StatelessWidget {
  const _ChildrenSection({
    required this.children,
    required this.loading,
    required this.onAdd,
    required this.onRefresh,
  });

  final List<ParentChildModel> children;
  final bool loading;
  final VoidCallback onAdd;
  final Future<void> Function() onRefresh;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Text(
              'FARZANDLAR',
              style: DsType.micro(ds.textMuted).copyWith(letterSpacing: 1.2),
            ),
            const Spacer(),
            TextButton.icon(
              onPressed: onAdd,
              icon: Icon(Icons.add_rounded, size: 18, color: ds.primary),
              label: Text('Qo‘shish', style: DsType.small(ds.primary)),
            ),
          ],
        ),
        const SizedBox(height: 8),
        DsCard(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: loading
              ? const Padding(
                  padding: EdgeInsets.all(20),
                  child: Center(child: CircularProgressIndicator(strokeWidth: 2.4)),
                )
              : children.isEmpty
                  ? Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        children: [
                          Icon(Icons.child_care_rounded,
                              size: 36, color: ds.textFaint),
                          const SizedBox(height: 8),
                          Text(
                            'Hali farzand bog‘lanmagan',
                            style: DsType.bodyStrong(ds.textPrimary),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            'Farzandingizni qo‘shib, davomat va to‘lovlarni kuzating',
                            textAlign: TextAlign.center,
                            style: DsType.small(ds.textMuted),
                          ),
                          const SizedBox(height: 12),
                          DsButton(
                            label: 'Farzand qo‘shish',
                            height: 44,
                            onPressed: onAdd,
                          ),
                        ],
                      ),
                    )
                  : Column(
                      children: [
                        for (var i = 0; i < children.length; i++) ...[
                          if (i > 0) Divider(height: 1, color: ds.border),
                          ListTile(
                            contentPadding: const EdgeInsets.symmetric(
                              horizontal: 16,
                              vertical: 4,
                            ),
                            leading: AdaptiveAvatar(
                              name: children[i].fullName,
                              imageUrl: children[i].avatarUrl,
                              size: 42,
                            ),
                            title: Text(
                              children[i].fullName,
                              style: DsType.bodyStrong(ds.textPrimary),
                            ),
                            subtitle: Text(
                              children[i].groupName.isNotEmpty
                                  ? children[i].groupName
                                  : 'Guruh belgilanmagan',
                              style: DsType.small(ds.textMuted),
                            ),
                            trailing: Icon(
                              Icons.chevron_right_rounded,
                              color: ds.textFaint,
                            ),
                            onTap: () async {
                              await context
                                  .read<ParentDashboardProvider>()
                                  .selectChild(children[i].id);
                              if (context.mounted) {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  SnackBar(
                                    content: Text(
                                      '${children[i].fullName} tanlandi',
                                    ),
                                  ),
                                );
                              }
                            },
                          ),
                        ],
                      ],
                    ),
        ),
      ],
    );
  }
}
