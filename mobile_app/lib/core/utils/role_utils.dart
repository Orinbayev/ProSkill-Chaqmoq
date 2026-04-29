import 'package:chaqmoq_mobile/core/theme/app_colors.dart';
import 'package:flutter/material.dart';

class RoleUtils {
  const RoleUtils._();

  static String normalize(String role) {
    if (role == 'superadmin') {
      return 'superuser';
    }
    return role.trim().toLowerCase();
  }

  static String roleLabel(String role) {
    return switch (normalize(role)) {
      'superuser' => 'Superadmin',
      'director' => 'Direktor',
      'manager' => 'Menejer',
      'teacher' => 'Ustoz',
      'student' => 'O\'quvchi',
      'parent' => 'Ota-ona',
      _ => 'Foydalanuvchi',
    };
  }

  static String panelLabel(String role) {
    return switch (normalize(role)) {
      'student' => 'O‘quvchi paneli',
      'parent' => 'Ota-ona paneli',
      'teacher' => 'Ustoz paneli',
      'manager' => 'Menejer paneli',
      'director' || 'superuser' => 'Boshqaruv paneli',
      _ => 'Mobil panel',
    };
  }

  static IconData roleIcon(String role) {
    return switch (normalize(role)) {
      'superuser' => Icons.admin_panel_settings_rounded,
      'director' => Icons.monitor_heart_rounded,
      'manager' => Icons.manage_accounts_rounded,
      'teacher' => Icons.school_rounded,
      'student' => Icons.bolt_rounded,
      'parent' => Icons.family_restroom_rounded,
      _ => Icons.person_rounded,
    };
  }

  static Color roleColor(String role) {
    return switch (normalize(role)) {
      'superuser' => const Color(0xFFD97706),
      'director' => const Color(0xFF2563EB),
      'manager' => const Color(0xFF0F766E),
      'teacher' => const Color(0xFF1A936F),
      'student' => const Color(0xFF0F766E),
      'parent' => const Color(0xFF2563EB),
      _ => AppColors.textMuted,
    };
  }

  static bool isDirectorScope(String role) {
    final normalized = normalize(role);
    return normalized == 'director' ||
        normalized == 'manager' ||
        normalized == 'superuser';
  }
}
