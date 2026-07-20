import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Gradient avatar with initials, matching primitives.jsx `Avatar`.
class AppAvatar extends StatelessWidget {
  const AppAvatar({
    super.key,
    required this.name,
    this.size = 40,
    this.color = AppAvatarColor.blue,
    this.imageUrl,
  });

  final String name;
  final double size;
  final AppAvatarColor color;
  final String? imageUrl;

  @override
  Widget build(BuildContext context) {
    final palette = _palette(color);
    final initials = _initials(name);

    if ((imageUrl ?? '').trim().isNotEmpty) {
      return ClipOval(
        child: SizedBox(
          width: size,
          height: size,
          child: CachedNetworkImage(
            imageUrl: imageUrl!.trim(),
            fit: BoxFit.cover,
            placeholder: (_, _) => _placeholder(palette, initials),
            errorWidget: (_, _, _) => _placeholder(palette, initials),
          ),
        ),
      );
    }

    return _placeholder(palette, initials);
  }

  Widget _placeholder(_AvatarPalette palette, String initials) {
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [palette.start, palette.end],
        ),
        shape: BoxShape.circle,
        boxShadow: const [
          BoxShadow(
            color: Color(0x14000000),
            blurRadius: 6,
            offset: Offset(0, 2),
          ),
        ],
      ),
      child: Text(
        initials,
        style: GoogleFonts.inter(
          fontSize: size * 0.36,
          height: 1,
          fontWeight: FontWeight.w800,
          color: palette.fg,
          letterSpacing: -0.2,
        ),
      ),
    );
  }

  static String _initials(String name) {
    final parts = name
        .trim()
        .split(RegExp(r'\s+'))
        .where((part) => part.isNotEmpty)
        .toList();
    if (parts.isEmpty) return 'HR';
    return parts.take(2).map((part) => part[0].toUpperCase()).join();
  }

  static _AvatarPalette _palette(AppAvatarColor color) {
    switch (color) {
      case AppAvatarColor.blue:
        return const _AvatarPalette(
          start: Color(0xFF3B82F6),
          end: Color(0xFF60A5FA),
          fg: Colors.white,
        );
      case AppAvatarColor.teal:
        return const _AvatarPalette(
          start: Color(0xFF0EA5E9),
          end: Color(0xFF38BDF8),
          fg: Color(0xFF0A1F1A),
        );
      case AppAvatarColor.violet:
        return const _AvatarPalette(
          start: Color(0xFF0EA5E9),
          end: Color(0xFF38BDF8),
          fg: Colors.white,
        );
      case AppAvatarColor.amber:
        return const _AvatarPalette(
          start: Color(0xFFF59E0B),
          end: Color(0xFFFBBF24),
          fg: Color(0xFF3F2A06),
        );
      case AppAvatarColor.rose:
        return const _AvatarPalette(
          start: Color(0xFFF43F5E),
          end: Color(0xFFFB7185),
          fg: Colors.white,
        );
      case AppAvatarColor.slate:
        return const _AvatarPalette(
          start: Color(0xFF475569),
          end: Color(0xFF64748B),
          fg: Colors.white,
        );
    }
  }
}

enum AppAvatarColor { blue, teal, violet, amber, rose, slate }

class _AvatarPalette {
  const _AvatarPalette({
    required this.start,
    required this.end,
    required this.fg,
  });
  final Color start;
  final Color end;
  final Color fg;
}
