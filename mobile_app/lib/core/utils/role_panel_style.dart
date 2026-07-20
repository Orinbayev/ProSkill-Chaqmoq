import 'package:chaqmoq_mobile/core/design/ds_colors.dart';
import 'package:flutter/material.dart';

class RolePanelStyle {
  const RolePanelStyle({
    required this.panelLabel,
    required this.headline,
    required this.subtitle,
    required this.icon,
    required this.accent,
    required this.accentSoft,
    required this.background,
    required this.heroGradient,
  });

  final String panelLabel;
  final String headline;
  final String subtitle;
  final IconData icon;
  final Color accent;
  final Color accentSoft;
  final Color background;
  final LinearGradient heroGradient;
}

/// Barcha rollar bir xil Sky/Slate dizayn; faqat matn/ikon rolga mos.
class RolePanelStyles {
  const RolePanelStyles._();

  static const LinearGradient _heroLight = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: <Color>[DsPalette.sky50, DsPalette.white],
  );

  static const LinearGradient _heroDark = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: <Color>[Color(0xFF13233A), DsPalette.slate800],
  );

  static RolePanelStyle of(String role, {bool isDark = false}) {
    final normalized = role.trim().toLowerCase();
    final accent = DsPalette.sky500;
    final accentSoft = isDark ? const Color(0xFF11324B) : DsPalette.sky100;
    final background = isDark ? DsPalette.slate900 : const Color(0xFFEDF1F5);
    final hero = isDark ? _heroDark : _heroLight;

    switch (normalized) {
      case 'parent':
        return RolePanelStyle(
          panelLabel: 'Ota-ona paneli',
          headline: 'Farzandingiz jarayonlari nazorat ostida',
          subtitle: 'Davomat, progress va to‘lovlarni bir joydan boshqaring.',
          icon: Icons.family_restroom_rounded,
          accent: accent,
          accentSoft: accentSoft,
          background: background,
          heroGradient: hero,
        );
      case 'student':
        return RolePanelStyle(
          panelLabel: 'O‘quvchi paneli',
          headline: 'Natijalar va intizomni bir markazdan kuzating',
          subtitle: 'Reyting, qarzdorlik va bildirishnomalar doim qo‘l ostida.',
          icon: Icons.school_rounded,
          accent: accent,
          accentSoft: accentSoft,
          background: background,
          heroGradient: hero,
        );
      case 'teacher':
        return RolePanelStyle(
          panelLabel: 'Ustoz paneli',
          headline: 'Guruhlar va kundalik nazorat bir joyda',
          subtitle:
              'Dars jarayoni, guruhlar va xabarlar bo‘yicha tezkor boshqaruv.',
          icon: Icons.co_present_rounded,
          accent: accent,
          accentSoft: accentSoft,
          background: background,
          heroGradient: hero,
        );
      case 'manager':
        return RolePanelStyle(
          panelLabel: 'Menejer paneli',
          headline: 'Operatsion jarayonlar bir ko‘rishda',
          subtitle: 'O‘quvchilar, guruhlar va faoliyat oqimini boshqaring.',
          icon: Icons.manage_accounts_rounded,
          accent: DsPalette.sky600,
          accentSoft: accentSoft,
          background: background,
          heroGradient: hero,
        );
      case 'director':
      case 'superadmin':
      case 'superuser':
        return RolePanelStyle(
          panelLabel: 'Boshqaruv paneli',
          headline: 'Asosiy ko‘rsatkichlar va jarayonlar nazoratda',
          subtitle:
              'CRM statistikasi, o‘quvchilar va markaz oqimini boshqaring.',
          icon: Icons.insights_rounded,
          accent: accent,
          accentSoft: accentSoft,
          background: background,
          heroGradient: hero,
        );
      default:
        return RolePanelStyle(
          panelLabel: 'Mobil panel',
          headline: 'Shaxsiy ish maydoni',
          subtitle: 'Asosiy ma’lumotlar va tezkor amallar shu yerda.',
          icon: Icons.phone_iphone_rounded,
          accent: accent,
          accentSoft: accentSoft,
          background: background,
          heroGradient: hero,
        );
    }
  }
}
