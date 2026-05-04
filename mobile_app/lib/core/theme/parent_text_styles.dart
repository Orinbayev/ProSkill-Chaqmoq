import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Parent typography — Inter, weights 400–800, sizes 10–32px.
/// Ranglar mavzuga moslashish uchun olib tashlangan — har bir Text widget
/// kerakli ParentColors.text/textSoft rangini berishi kerak.
class ParentTextStyles {
  const ParentTextStyles._();

  static TextStyle get hero => GoogleFonts.inter(
    fontSize: 26,
    height: 1.1,
    fontWeight: FontWeight.w800,
    letterSpacing: -0.4,
  );

  static TextStyle get headline => GoogleFonts.inter(
    fontSize: 22,
    height: 1.15,
    fontWeight: FontWeight.w800,
    letterSpacing: -0.3,
  );

  static TextStyle get title => GoogleFonts.inter(
    fontSize: 19,
    height: 1.18,
    fontWeight: FontWeight.w800,
    letterSpacing: -0.2,
  );

  static TextStyle get titleSm => GoogleFonts.inter(
    fontSize: 16,
    height: 1.18,
    fontWeight: FontWeight.w800,
    letterSpacing: -0.2,
  );

  static TextStyle get body => GoogleFonts.inter(
    fontSize: 13.5,
    height: 1.4,
    fontWeight: FontWeight.w500,
  );

  static TextStyle get bodySoft => GoogleFonts.inter(
    fontSize: 13,
    height: 1.45,
    fontWeight: FontWeight.w500,
  );

  static TextStyle get bodyMuted => GoogleFonts.inter(
    fontSize: 12.5,
    height: 1.4,
    fontWeight: FontWeight.w500,
  );

  static TextStyle get bodySm => GoogleFonts.inter(
    fontSize: 11.5,
    height: 1.4,
    fontWeight: FontWeight.w600,
  );

  static TextStyle get label => GoogleFonts.inter(
    fontSize: 11,
    height: 1.2,
    fontWeight: FontWeight.w700,
    letterSpacing: 0.12,
  );

  static TextStyle get sectionTitle => GoogleFonts.inter(
    fontSize: 14,
    height: 1.2,
    fontWeight: FontWeight.w800,
    letterSpacing: -0.1,
  );

  static TextStyle get value => GoogleFonts.inter(
    fontSize: 18,
    height: 1.1,
    fontWeight: FontWeight.w800,
    letterSpacing: -0.4,
  );

  static TextStyle get valueLg => GoogleFonts.inter(
    fontSize: 30,
    height: 1.05,
    fontWeight: FontWeight.w800,
    letterSpacing: -0.6,
  );
}

/// Student typography (white-on-dark variants).
class StudentTextStyles {
  const StudentTextStyles._();

  static TextStyle get hero => GoogleFonts.inter(
    fontSize: 22,
    height: 1.1,
    fontWeight: FontWeight.w800,
    color: const Color(0xFFF1F2F6),
    letterSpacing: -0.3,
  );

  static TextStyle get title => GoogleFonts.inter(
    fontSize: 19,
    height: 1.18,
    fontWeight: FontWeight.w800,
    color: const Color(0xFFF1F2F6),
    letterSpacing: -0.2,
  );

  static TextStyle get sectionTitle => GoogleFonts.inter(
    fontSize: 13,
    height: 1.2,
    fontWeight: FontWeight.w800,
    color: const Color(0xFFF1F2F6),
  );

  static TextStyle get body => GoogleFonts.inter(
    fontSize: 13,
    height: 1.4,
    fontWeight: FontWeight.w500,
    color: const Color(0xFFF1F2F6),
  );

  static TextStyle get bodyMuted => GoogleFonts.inter(
    fontSize: 12,
    height: 1.4,
    fontWeight: FontWeight.w500,
    color: const Color(0xFF8892A4),
  );

  static TextStyle get label => GoogleFonts.inter(
    fontSize: 11,
    height: 1.2,
    fontWeight: FontWeight.w700,
    color: const Color(0xFF8892A4),
    letterSpacing: 0.14,
  );

  static TextStyle get value => GoogleFonts.inter(
    fontSize: 19,
    height: 1.1,
    fontWeight: FontWeight.w800,
    color: const Color(0xFFF1F2F6),
    letterSpacing: -0.4,
  );

  static TextStyle get valueLg => GoogleFonts.inter(
    fontSize: 28,
    height: 1.05,
    fontWeight: FontWeight.w800,
    color: const Color(0xFFF1F2F6),
    letterSpacing: -0.6,
  );
}
