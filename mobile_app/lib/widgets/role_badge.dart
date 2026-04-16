import 'package:chaqmoq_mobile/core/utils/role_utils.dart';
import 'package:chaqmoq_mobile/widgets/stat_chip.dart';
import 'package:flutter/material.dart';

class RoleBadge extends StatelessWidget {
  const RoleBadge({super.key, required this.role});

  final String role;

  @override
  Widget build(BuildContext context) {
    return StatChip(
      label: RoleUtils.roleLabel(role),
      color: RoleUtils.roleColor(role),
      icon: RoleUtils.roleIcon(role),
    );
  }
}
