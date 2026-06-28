import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/app_preferences_provider.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/teacher_provider.dart';
import 'package:chaqmoq_mobile/services/teacher_service.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

class TeacherProfileScreen extends StatelessWidget {
  const TeacherProfileScreen({super.key, this.onGoTab});

  final ValueChanged<int>? onGoTab;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final auth = context.watch<AuthProvider>();
    final user = auth.user;
    final prefs = context.watch<AppPreferencesProvider>();

    if (user == null) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    return Scaffold(
      backgroundColor: isDark ? const Color(0xFF0B1220) : const Color(0xFFF5F7FB),
      body: CustomScrollView(
        slivers: [
          _buildSliverHeader(context, user, isDark, prefs),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 80),
            sliver: SliverList(
              delegate: SliverChildListDelegate([
                const SizedBox(height: 20),
                _Section(title: "Profil", isDark: isDark, children: [
                  _Tile(
                    icon: Icons.edit_rounded,
                    label: "Ismni tahrirlash",
                    value: "${user.firstName} ${user.lastName}".trim(),
                    isDark: isDark,
                    onTap: () => _openEditName(context),
                  ),
                  _Tile(
                    icon: Icons.phone_rounded,
                    label: "Telefon",
                    value: user.phone.isNotEmpty ? user.phone : "—",
                    isDark: isDark,
                    onTap: () => _openEditName(context),
                  ),
                  _Tile(
                    icon: Icons.email_rounded,
                    label: "Email",
                    value: user.email.isNotEmpty ? user.email : "—",
                    isDark: isDark,
                  ),
                ]),
                const SizedBox(height: 12),
                _Section(title: "Sozlamalar", isDark: isDark, children: [
                  _ThemeTile(isDark: isDark, prefs: prefs),
                  _Tile(
                    icon: Icons.lock_rounded,
                    label: "Parolni o'zgartirish",
                    isDark: isDark,
                    onTap: () => _openChangePassword(context),
                  ),
                ]),
                const SizedBox(height: 12),
                _Section(title: "Markaz", isDark: isDark, children: [
                  _Tile(
                    icon: Icons.business_rounded,
                    label: "O'quv markazi",
                    value: user.center?.name ?? "—",
                    isDark: isDark,
                  ),
                  _Tile(
                    icon: Icons.badge_rounded,
                    label: "Lavozim",
                    value: _roleLabel(user.role),
                    isDark: isDark,
                  ),
                ]),
                const SizedBox(height: 20),
                _LogoutButton(isDark: isDark),
                const SizedBox(height: 32),
              ]),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSliverHeader(BuildContext context, UserModel user, bool isDark, AppPreferencesProvider prefs) {
    return SliverAppBar(
      backgroundColor: isDark ? const Color(0xFF0B1220) : const Color(0xFFF5F7FB),
      expandedHeight: 200,
      pinned: true,
      elevation: 0,
      flexibleSpace: FlexibleSpaceBar(
        background: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: isDark
                  ? [const Color(0xFF1E1B4B), const Color(0xFF0B1220)]
                  : [const Color(0xFFEEF2FF), const Color(0xFFF5F7FB)],
            ),
          ),
          child: SafeArea(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                _AvatarWidget(user: user),
                const SizedBox(height: 10),
                Text(
                  user.fullName.isNotEmpty ? user.fullName : "O'qituvchi",
                  style: TextStyle(
                      color: isDark ? Colors.white : const Color(0xFF0F172A),
                      fontSize: 18, fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 4),
                Text(
                  _roleLabel(user.role),
                  style: TextStyle(color: isDark ? Colors.white54 : Colors.black45, fontSize: 12),
                ),
              ],
            ),
          ),
        ),
      ),
      title: Text("Profil",
          style: TextStyle(
              color: isDark ? Colors.white : const Color(0xFF0F172A),
              fontWeight: FontWeight.w800, fontSize: 16)),
    );
  }

  void _openEditName(BuildContext context) {
    final auth = context.read<AuthProvider>();
    final service = context.read<TeacherProvider>().service;
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => MultiProvider(
        providers: [
          Provider.value(value: auth),
          Provider.value(value: service),
        ],
        child: _EditNameSheet(user: auth.user!),
      ),
    );
  }

  void _openChangePassword(BuildContext context) {
    final service = context.read<TeacherProvider>().service;
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => Provider.value(value: service, child: const _ChangePasswordSheet()),
    );
  }

  static String _roleLabel(String role) {
    switch (role) {
      case 'teacher': return "O'qituvchi";
      case 'director': return "Direktor";
      case 'manager': return "Menejer";
      default: return role;
    }
  }
}

// ─── Avatar widget ────────────────────────────────────────────────────────────
class _AvatarWidget extends StatefulWidget {
  const _AvatarWidget({required this.user});

  final UserModel user;

  @override
  State<_AvatarWidget> createState() => _AvatarWidgetState();
}

class _AvatarWidgetState extends State<_AvatarWidget> {
  bool _uploading = false;

  Future<void> _pick() async {
    final picker = ImagePicker();
    final img = await picker.pickImage(source: ImageSource.gallery, imageQuality: 85);
    if (img == null || !mounted) return;
    setState(() => _uploading = true);
    try {
      final service = context.read<TeacherProvider>().service;
      final updated = await service.uploadAvatar(img);
      if (mounted) context.read<AuthProvider>().updateUser(updated);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("Xato: $e"), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final url = widget.user.avatarUrl;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return GestureDetector(
      onTap: _pick,
      child: Stack(alignment: Alignment.bottomRight, children: [
        Container(
          width: 80, height: 80,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: url.isEmpty
                ? const LinearGradient(colors: [Color(0xFF818CF8), Color(0xFF6366F1)])
                : null,
            color: url.isNotEmpty ? null : null,
            border: Border.all(
              color: const Color(0xFF6366F1).withValues(alpha: 0.4),
              width: 2.5,
            ),
          ),
          child: ClipOval(
            child: _uploading
                ? const Center(child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2.5))
                : url.isNotEmpty
                    ? Image.network(url, fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => _AvatarInitials(name: widget.user.fullName))
                    : _AvatarInitials(name: widget.user.fullName),
          ),
        ),
        Container(
          width: 26, height: 26,
          decoration: BoxDecoration(
            color: const Color(0xFF6366F1),
            shape: BoxShape.circle,
            border: Border.all(color: isDark ? const Color(0xFF0B1220) : Colors.white, width: 2),
          ),
          child: const Icon(Icons.camera_alt_rounded, size: 13, color: Colors.white),
        ),
      ]),
    );
  }
}

class _AvatarInitials extends StatelessWidget {
  const _AvatarInitials({required this.name});

  final String name;

  String _initials(String n) {
    final p = n.trim().split(RegExp(r'\s+')).where((e) => e.isNotEmpty).toList();
    if (p.isEmpty) return '?';
    return p.take(2).map((e) => e[0].toUpperCase()).join();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      color: const Color(0xFF6366F1),
      child: Center(
        child: Text(_initials(name),
            style: const TextStyle(color: Colors.white, fontSize: 28, fontWeight: FontWeight.w800)),
      ),
    );
  }
}

// ─── Section ─────────────────────────────────────────────────────────────────
class _Section extends StatelessWidget {
  const _Section({required this.title, required this.children, required this.isDark});

  final String title;
  final List<Widget> children;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Padding(
        padding: const EdgeInsets.only(left: 4, bottom: 8),
        child: Text(title.toUpperCase(),
            style: TextStyle(
                color: isDark ? Colors.white38 : Colors.black38,
                fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 1)),
      ),
      Container(
        decoration: BoxDecoration(
          color: isDark ? const Color(0xFF162436) : Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
              color: isDark ? Colors.white.withValues(alpha: 0.06) : Colors.black.withValues(alpha: 0.05)),
        ),
        child: Column(
          children: children.indexed.map((e) {
            final idx = e.$1;
            final child = e.$2;
            return Column(children: [
              child,
              if (idx < children.length - 1)
                Divider(height: 1, indent: 52,
                    color: isDark ? Colors.white.withValues(alpha: 0.06) : Colors.black.withValues(alpha: 0.05)),
            ]);
          }).toList(),
        ),
      ),
    ]);
  }
}

// ─── Tile ─────────────────────────────────────────────────────────────────────
class _Tile extends StatelessWidget {
  const _Tile({
    required this.icon,
    required this.label,
    required this.isDark,
    this.value,
    this.onTap,
  });

  final IconData icon;
  final String label;
  final String? value;
  final bool isDark;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 2),
      leading: Container(
        width: 34, height: 34,
        decoration: BoxDecoration(
          color: const Color(0xFF6366F1).withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(9),
        ),
        child: Icon(icon, size: 17, color: const Color(0xFF818CF8)),
      ),
      title: Text(label,
          style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A),
              fontWeight: FontWeight.w600, fontSize: 14)),
      subtitle: value != null
          ? Text(value!, style: TextStyle(color: isDark ? Colors.white38 : Colors.black38, fontSize: 12))
          : null,
      trailing: onTap != null
          ? Icon(Icons.chevron_right_rounded, color: isDark ? Colors.white24 : Colors.black26, size: 20)
          : null,
      onTap: onTap,
    );
  }
}

// ─── Theme tile ──────────────────────────────────────────────────────────────
class _ThemeTile extends StatelessWidget {
  const _ThemeTile({required this.isDark, required this.prefs});

  final bool isDark;
  final AppPreferencesProvider prefs;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 2),
      leading: Container(
        width: 34, height: 34,
        decoration: BoxDecoration(
          color: const Color(0xFF6366F1).withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(9),
        ),
        child: Icon(isDark ? Icons.dark_mode_rounded : Icons.light_mode_rounded,
            size: 17, color: const Color(0xFF818CF8)),
      ),
      title: Text("Ko'rinish",
          style: TextStyle(color: isDark ? Colors.white : const Color(0xFF0F172A),
              fontWeight: FontWeight.w600, fontSize: 14)),
      subtitle: Text(prefs.themeLabel,
          style: TextStyle(color: isDark ? Colors.white38 : Colors.black38, fontSize: 12)),
      trailing: Row(mainAxisSize: MainAxisSize.min, children: [
        _ThemeBtn(
          icon: Icons.light_mode_rounded,
          active: prefs.themePreference == AppThemePreference.light,
          onTap: () => prefs.setThemePreference(AppThemePreference.light),
        ),
        const SizedBox(width: 4),
        _ThemeBtn(
          icon: Icons.dark_mode_rounded,
          active: prefs.themePreference == AppThemePreference.dark,
          onTap: () => prefs.setThemePreference(AppThemePreference.dark),
        ),
        const SizedBox(width: 4),
        _ThemeBtn(
          icon: Icons.phone_android_rounded,
          active: prefs.themePreference == AppThemePreference.system,
          onTap: () => prefs.setThemePreference(AppThemePreference.system),
        ),
      ]),
    );
  }
}

class _ThemeBtn extends StatelessWidget {
  const _ThemeBtn({required this.icon, required this.active, required this.onTap});

  final IconData icon;
  final bool active;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () {
        HapticFeedback.selectionClick();
        onTap();
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        width: 32, height: 32,
        decoration: BoxDecoration(
          color: active ? const Color(0xFF6366F1) : Colors.transparent,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: active ? const Color(0xFF6366F1) : Colors.grey.withValues(alpha: 0.3),
          ),
        ),
        child: Icon(icon, size: 16, color: active ? Colors.white : Colors.grey),
      ),
    );
  }
}

// ─── Logout ──────────────────────────────────────────────────────────────────
class _LogoutButton extends StatelessWidget {
  const _LogoutButton({required this.isDark});

  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: OutlinedButton.icon(
        onPressed: () => _confirm(context),
        icon: const Icon(Icons.logout_rounded, size: 17),
        label: const Text("Chiqish", style: TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
        style: OutlinedButton.styleFrom(
          foregroundColor: const Color(0xFFEF4444),
          side: const BorderSide(color: Color(0xFFEF4444), width: 1.5),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          padding: const EdgeInsets.symmetric(vertical: 14),
        ),
      ),
    );
  }

  void _confirm(BuildContext context) {
    showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text("Chiqish"),
        content: const Text("Dasturdan chiqishni istaysizmi?"),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text("Bekor")),
          TextButton(
            onPressed: () {
              Navigator.pop(ctx);
              context.read<AuthProvider>().logout();
            },
            child: const Text("Chiqish", style: TextStyle(color: Color(0xFFEF4444))),
          ),
        ],
      ),
    );
  }
}

// ─── Edit name bottom sheet ───────────────────────────────────────────────────
class _EditNameSheet extends StatefulWidget {
  const _EditNameSheet({required this.user});

  final UserModel user;

  @override
  State<_EditNameSheet> createState() => _EditNameSheetState();
}

class _EditNameSheetState extends State<_EditNameSheet> {
  late final _ismCtrl = TextEditingController(text: widget.user.firstName);
  late final _familyaCtrl = TextEditingController(text: widget.user.lastName);
  late final _phoneCtrl = TextEditingController(text: widget.user.phone);
  bool _saving = false;
  String? _error;

  @override
  void dispose() {
    _ismCtrl.dispose();
    _familyaCtrl.dispose();
    _phoneCtrl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final ism = _ismCtrl.text.trim();
    final familya = _familyaCtrl.text.trim();
    if (ism.isEmpty) {
      setState(() => _error = "Ism kiritilmadi");
      return;
    }
    setState(() { _saving = true; _error = null; });
    try {
      final service = context.read<TeacherService>();
      final updated = await service.updateProfile(
        ism: ism,
        familya: familya,
        phone: _phoneCtrl.text.trim().isNotEmpty ? _phoneCtrl.text.trim() : null,
      );
      if (mounted) {
        context.read<AuthProvider>().updateUser(updated);
        Navigator.pop(context);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Profil yangilandi"), backgroundColor: Color(0xFF10B981)),
        );
      }
    } catch (e) {
      setState(() { _saving = false; _error = e.toString(); });
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bg = isDark ? const Color(0xFF0F1B2A) : Colors.white;
    return Container(
      padding: EdgeInsets.fromLTRB(20, 20, 20, MediaQuery.of(context).viewInsets.bottom + 24),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Text("Profilni tahrirlash",
              style: TextStyle(color: isDark ? Colors.white : Colors.black87,
                  fontWeight: FontWeight.w800, fontSize: 16)),
          const Spacer(),
          IconButton(
            icon: Icon(Icons.close_rounded, color: isDark ? Colors.white38 : Colors.black38),
            onPressed: () => Navigator.pop(context),
          ),
        ]),
        const SizedBox(height: 16),
        _Field(ctrl: _ismCtrl, label: "Ism", icon: Icons.person_rounded, isDark: isDark),
        const SizedBox(height: 10),
        _Field(ctrl: _familyaCtrl, label: "Familya", icon: Icons.person_outline_rounded, isDark: isDark),
        const SizedBox(height: 10),
        _Field(ctrl: _phoneCtrl, label: "Telefon", icon: Icons.phone_rounded, isDark: isDark, keyboard: TextInputType.phone),
        if (_error != null) ...[
          const SizedBox(height: 8),
          Text(_error!, style: const TextStyle(color: Color(0xFFEF4444), fontSize: 12)),
        ],
        const SizedBox(height: 16),
        SizedBox(
          width: double.infinity,
          child: ElevatedButton(
            onPressed: _saving ? null : _save,
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF6366F1),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              padding: const EdgeInsets.symmetric(vertical: 14),
            ),
            child: _saving
                ? const SizedBox(height: 18, width: 18,
                    child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2.5))
                : const Text("Saqlash", style: TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
          ),
        ),
      ]),
    );
  }
}

class _Field extends StatelessWidget {
  const _Field({required this.ctrl, required this.label, required this.icon, required this.isDark, this.keyboard});

  final TextEditingController ctrl;
  final String label;
  final IconData icon;
  final bool isDark;
  final TextInputType? keyboard;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: ctrl,
      keyboardType: keyboard,
      style: TextStyle(color: isDark ? Colors.white : Colors.black87),
      decoration: InputDecoration(
        labelText: label,
        prefixIcon: Icon(icon, size: 18, color: const Color(0xFF818CF8)),
        labelStyle: TextStyle(color: isDark ? Colors.white54 : Colors.black45),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: isDark ? Colors.white.withValues(alpha: 0.15) : Colors.black.withValues(alpha: 0.15)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xFF6366F1)),
        ),
        filled: true,
        fillColor: isDark ? const Color(0xFF162436) : const Color(0xFFF8F9FB),
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      ),
    );
  }
}

// ─── Change password bottom sheet ────────────────────────────────────────────
class _ChangePasswordSheet extends StatefulWidget {
  const _ChangePasswordSheet();

  @override
  State<_ChangePasswordSheet> createState() => _ChangePasswordSheetState();
}

class _ChangePasswordSheetState extends State<_ChangePasswordSheet> {
  final _oldCtrl = TextEditingController();
  final _newCtrl = TextEditingController();
  final _confirmCtrl = TextEditingController();
  bool _saving = false;
  String? _error;
  bool _showOld = false;
  bool _showNew = false;
  bool _showConfirm = false;

  @override
  void dispose() {
    _oldCtrl.dispose();
    _newCtrl.dispose();
    _confirmCtrl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_newCtrl.text != _confirmCtrl.text) {
      setState(() => _error = "Yangi parollar mos emas");
      return;
    }
    if (_newCtrl.text.length < 6) {
      setState(() => _error = "Parol kamida 6 ta belgidan iborat bo'lsin");
      return;
    }
    setState(() { _saving = true; _error = null; });
    try {
      final service = context.read<TeacherService>();
      await service.changePassword(
        currentPassword: _oldCtrl.text,
        newPassword: _newCtrl.text,
        confirmPassword: _confirmCtrl.text,
      );
      if (mounted) {
        Navigator.pop(context);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Parol muvaffaqiyatli o'zgartirildi"), backgroundColor: Color(0xFF10B981)),
        );
      }
    } catch (e) {
      setState(() { _saving = false; _error = e.toString(); });
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bg = isDark ? const Color(0xFF0F1B2A) : Colors.white;
    return Container(
      padding: EdgeInsets.fromLTRB(20, 20, 20, MediaQuery.of(context).viewInsets.bottom + 24),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Text("Parolni o'zgartirish",
              style: TextStyle(color: isDark ? Colors.white : Colors.black87,
                  fontWeight: FontWeight.w800, fontSize: 16)),
          const Spacer(),
          IconButton(
            icon: Icon(Icons.close_rounded, color: isDark ? Colors.white38 : Colors.black38),
            onPressed: () => Navigator.pop(context),
          ),
        ]),
        const SizedBox(height: 16),
        _PassField(ctrl: _oldCtrl, label: "Hozirgi parol", show: _showOld, isDark: isDark,
            onToggle: () => setState(() => _showOld = !_showOld)),
        const SizedBox(height: 10),
        _PassField(ctrl: _newCtrl, label: "Yangi parol", show: _showNew, isDark: isDark,
            onToggle: () => setState(() => _showNew = !_showNew)),
        const SizedBox(height: 10),
        _PassField(ctrl: _confirmCtrl, label: "Yangi parolni takrorlang", show: _showConfirm, isDark: isDark,
            onToggle: () => setState(() => _showConfirm = !_showConfirm)),
        if (_error != null) ...[
          const SizedBox(height: 8),
          Text(_error!, style: const TextStyle(color: Color(0xFFEF4444), fontSize: 12)),
        ],
        const SizedBox(height: 16),
        SizedBox(
          width: double.infinity,
          child: ElevatedButton(
            onPressed: _saving ? null : _save,
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF6366F1),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              padding: const EdgeInsets.symmetric(vertical: 14),
            ),
            child: _saving
                ? const SizedBox(height: 18, width: 18,
                    child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2.5))
                : const Text("O'zgartirish", style: TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
          ),
        ),
      ]),
    );
  }
}

class _PassField extends StatelessWidget {
  const _PassField({required this.ctrl, required this.label, required this.show, required this.isDark, required this.onToggle});

  final TextEditingController ctrl;
  final String label;
  final bool show;
  final bool isDark;
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: ctrl,
      obscureText: !show,
      style: TextStyle(color: isDark ? Colors.white : Colors.black87),
      decoration: InputDecoration(
        labelText: label,
        prefixIcon: const Icon(Icons.lock_rounded, size: 18, color: Color(0xFF818CF8)),
        suffixIcon: IconButton(
          icon: Icon(show ? Icons.visibility_off_rounded : Icons.visibility_rounded, size: 18, color: Colors.grey),
          onPressed: onToggle,
        ),
        labelStyle: TextStyle(color: isDark ? Colors.white54 : Colors.black45),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: isDark ? Colors.white.withValues(alpha: 0.15) : Colors.black.withValues(alpha: 0.15)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xFF6366F1)),
        ),
        filled: true,
        fillColor: isDark ? const Color(0xFF162436) : const Color(0xFFF8F9FB),
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      ),
    );
  }
}
