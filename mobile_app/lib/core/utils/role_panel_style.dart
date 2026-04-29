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

class RolePanelStyles {
  const RolePanelStyles._();

  static RolePanelStyle of(String role) {
    final normalized = role.trim().toLowerCase();
    switch (normalized) {
      case 'parent':
        return const RolePanelStyle(
          panelLabel: 'Ota-ona paneli',
          headline: 'Farzandingiz jarayonlari nazorat ostida',
          subtitle: 'Davomat, progress va to‘lovlarni bir joydan boshqaring.',
          icon: Icons.family_restroom_rounded,
          accent: Color(0xFF2563EB),
          accentSoft: Color(0xFFE8F1FF),
          background: Color(0xFFF7FBFF),
          heroGradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: <Color>[Color(0xFFEEF5FF), Color(0xFFFFFFFF)],
          ),
        );
      case 'student':
        return const RolePanelStyle(
          panelLabel: 'O‘quvchi paneli',
          headline: 'Natijalar va intizomni bir markazdan kuzating',
          subtitle: 'Reyting, qarzdorlik va bildirishnomalar doim qo‘l ostida.',
          icon: Icons.school_rounded,
          accent: Color(0xFF0F766E),
          accentSoft: Color(0xFFE6F8F4),
          background: Color(0xFF07131F),
          heroGradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: <Color>[Color(0xFF102235), Color(0xFF0B3C4A)],
          ),
        );
      case 'teacher':
        return const RolePanelStyle(
          panelLabel: 'Ustoz paneli',
          headline: 'Guruhlar va kundalik nazorat bir joyda',
          subtitle:
              'Dars jarayoni, guruhlar va xabarlar bo‘yicha tezkor boshqaruv.',
          icon: Icons.co_present_rounded,
          accent: Color(0xFF0F766E),
          accentSoft: Color(0xFFE6F7F1),
          background: Color(0xFF08131A),
          heroGradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: <Color>[Color(0xFF0D1F2A), Color(0xFF143C32)],
          ),
        );
      case 'manager':
        return const RolePanelStyle(
          panelLabel: 'Menejer paneli',
          headline: 'Operatsion jarayonlar bir ko‘rishda',
          subtitle: 'O‘quvchilar, guruhlar va faoliyat oqimini boshqaring.',
          icon: Icons.manage_accounts_rounded,
          accent: Color(0xFF0F766E),
          accentSoft: Color(0xFFE8FAF6),
          background: Color(0xFF07131F),
          heroGradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: <Color>[Color(0xFF102235), Color(0xFF0E3A3E)],
          ),
        );
      case 'director':
      case 'superadmin':
      case 'superuser':
        return const RolePanelStyle(
          panelLabel: 'Boshqaruv paneli',
          headline: 'Asosiy ko‘rsatkichlar va jarayonlar nazoratda',
          subtitle:
              'CRM statistikasi, o‘quvchilar va markaz oqimini boshqaring.',
          icon: Icons.insights_rounded,
          accent: Color(0xFF2563EB),
          accentSoft: Color(0xFFEAF2FF),
          background: Color(0xFF07131F),
          heroGradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: <Color>[Color(0xFF102235), Color(0xFF1C2D4B)],
          ),
        );
      default:
        return const RolePanelStyle(
          panelLabel: 'Mobil panel',
          headline: 'Shaxsiy ish maydoni',
          subtitle: 'Asosiy ma’lumotlar va tezkor amallar shu yerda.',
          icon: Icons.phone_iphone_rounded,
          accent: Color(0xFF2563EB),
          accentSoft: Color(0xFFEAF2FF),
          background: Color(0xFF07131F),
          heroGradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: <Color>[Color(0xFF102235), Color(0xFF1C2D4B)],
          ),
        );
    }
  }
}
