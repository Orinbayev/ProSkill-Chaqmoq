import 'package:flutter/material.dart';

enum AppSection {
  home,
  students,
  teachers,
  groups,
  attendance,
  payments,
  notifications,
  profile,
}

class SectionItem {
  const SectionItem({
    required this.section,
    required this.label,
    required this.icon,
  });

  final AppSection section;
  final String label;
  final IconData icon;
}

class RoleUtils {
  static List<SectionItem> primarySections(String role) {
    switch (role) {
      case 'superadmin':
        return const [
          SectionItem(
            section: AppSection.home,
            label: 'Asosiy',
            icon: Icons.grid_view_rounded,
          ),
          SectionItem(
            section: AppSection.students,
            label: 'O\'quvchilar',
            icon: Icons.school_rounded,
          ),
          SectionItem(
            section: AppSection.teachers,
            label: 'O\'qituvchilar',
            icon: Icons.badge_rounded,
          ),
          SectionItem(
            section: AppSection.payments,
            label: 'To\'lovlar',
            icon: Icons.payments_rounded,
          ),
        ];
      case 'director':
        return const [
          SectionItem(
            section: AppSection.home,
            label: 'Asosiy',
            icon: Icons.grid_view_rounded,
          ),
          SectionItem(
            section: AppSection.students,
            label: 'O\'quvchilar',
            icon: Icons.school_rounded,
          ),
          SectionItem(
            section: AppSection.attendance,
            label: 'Davomat',
            icon: Icons.fact_check_rounded,
          ),
          SectionItem(
            section: AppSection.payments,
            label: 'To\'lovlar',
            icon: Icons.payments_rounded,
          ),
        ];
      case 'manager':
        return const [
          SectionItem(
            section: AppSection.home,
            label: 'Asosiy',
            icon: Icons.grid_view_rounded,
          ),
          SectionItem(
            section: AppSection.students,
            label: 'O\'quvchilar',
            icon: Icons.school_rounded,
          ),
          SectionItem(
            section: AppSection.groups,
            label: 'Guruhlar',
            icon: Icons.groups_rounded,
          ),
          SectionItem(
            section: AppSection.payments,
            label: 'To\'lovlar',
            icon: Icons.payments_rounded,
          ),
        ];
      case 'teacher':
        return const [
          SectionItem(
            section: AppSection.home,
            label: 'Asosiy',
            icon: Icons.grid_view_rounded,
          ),
          SectionItem(
            section: AppSection.groups,
            label: 'Guruhlar',
            icon: Icons.groups_rounded,
          ),
          SectionItem(
            section: AppSection.attendance,
            label: 'Davomat',
            icon: Icons.fact_check_rounded,
          ),
          SectionItem(
            section: AppSection.notifications,
            label: 'Xabarlar',
            icon: Icons.notifications_active_rounded,
          ),
        ];
      case 'student':
      case 'parent':
        return const [
          SectionItem(
            section: AppSection.home,
            label: 'Asosiy',
            icon: Icons.grid_view_rounded,
          ),
          SectionItem(
            section: AppSection.payments,
            label: 'To\'lovlar',
            icon: Icons.payments_rounded,
          ),
          SectionItem(
            section: AppSection.notifications,
            label: 'Xabarlar',
            icon: Icons.notifications_active_rounded,
          ),
          SectionItem(
            section: AppSection.profile,
            label: 'Profil',
            icon: Icons.person_rounded,
          ),
        ];
      default:
        return const [
          SectionItem(
            section: AppSection.home,
            label: 'Asosiy',
            icon: Icons.grid_view_rounded,
          ),
        ];
    }
  }

  static List<SectionItem> secondarySections(String role) {
    switch (role) {
      case 'superadmin':
        return const [
          SectionItem(
            section: AppSection.groups,
            label: 'Guruhlar',
            icon: Icons.groups_rounded,
          ),
          SectionItem(
            section: AppSection.notifications,
            label: 'Bildirishnomalar',
            icon: Icons.notifications_rounded,
          ),
          SectionItem(
            section: AppSection.profile,
            label: 'Profil',
            icon: Icons.person_rounded,
          ),
        ];
      case 'director':
      case 'manager':
        return const [
          SectionItem(
            section: AppSection.teachers,
            label: 'O\'qituvchilar',
            icon: Icons.badge_rounded,
          ),
          SectionItem(
            section: AppSection.groups,
            label: 'Guruhlar',
            icon: Icons.groups_rounded,
          ),
          SectionItem(
            section: AppSection.notifications,
            label: 'Bildirishnomalar',
            icon: Icons.notifications_rounded,
          ),
          SectionItem(
            section: AppSection.profile,
            label: 'Profil',
            icon: Icons.person_rounded,
          ),
        ];
      case 'teacher':
        return const [
          SectionItem(
            section: AppSection.students,
            label: 'O\'quvchilar',
            icon: Icons.school_rounded,
          ),
          SectionItem(
            section: AppSection.payments,
            label: 'To\'lovlar',
            icon: Icons.payments_rounded,
          ),
          SectionItem(
            section: AppSection.profile,
            label: 'Profil',
            icon: Icons.person_rounded,
          ),
        ];
      case 'student':
      case 'parent':
        return const [
          SectionItem(
            section: AppSection.groups,
            label: 'Guruhlar',
            icon: Icons.groups_rounded,
          ),
        ];
      default:
        return const [];
    }
  }

  static String sectionTitle(AppSection section) {
    switch (section) {
      case AppSection.home:
        return 'Asosiy panel';
      case AppSection.students:
        return 'O\'quvchilar';
      case AppSection.teachers:
        return 'O\'qituvchilar';
      case AppSection.groups:
        return 'Guruhlar';
      case AppSection.attendance:
        return 'Davomat';
      case AppSection.payments:
        return 'To\'lovlar';
      case AppSection.notifications:
        return 'Bildirishnomalar';
      case AppSection.profile:
        return 'Profil';
    }
  }
}
