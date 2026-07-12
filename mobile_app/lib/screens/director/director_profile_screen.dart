import 'dart:io';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../../core/config/app_config.dart';
import '../../core/design/ds_colors.dart';
import '../../core/design/ds_components.dart';
import '../../core/design/ds_tokens.dart';
import '../../core/design/ds_typography.dart';
import '../../providers/auth_provider.dart';
import 'data/director_provider.dart';

class DirectorProfileScreen extends StatefulWidget {
  const DirectorProfileScreen({super.key});
  @override
  State<DirectorProfileScreen> createState() => _DirectorProfileScreenState();
}

class _DirectorProfileScreenState extends State<DirectorProfileScreen> {
  late final TextEditingController _ism;
  late final TextEditingController _familya;
  late final TextEditingController _phone;
  bool _saving = false;
  bool _uploadingAvatar = false;
  File? _localAvatar;

  @override
  void initState() {
    super.initState();
    final u = context.read<AuthProvider>().user;
    _ism = TextEditingController(text: u?.firstName ?? '');
    _familya = TextEditingController(text: u?.lastName ?? '');
    _phone = TextEditingController(text: u?.phone ?? '');
  }

  @override
  void dispose() {
    _ism.dispose();
    _familya.dispose();
    _phone.dispose();
    super.dispose();
  }

  void _toast(String m) {
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      final updated = await context.read<DirectorProvider>().updateProfile(
            ism: _ism.text.trim(),
            familya: _familya.text.trim(),
            phone: _phone.text.trim(),
          );
      if (!mounted) return;
      context.read<AuthProvider>().updateUser(updated);
      _toast('Profil yangilandi ✅');
    } catch (_) {
      _toast('Xatolik — saqlanmadi');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _pickAvatar() async {
    final picked = await ImagePicker().pickImage(source: ImageSource.gallery, maxWidth: 900, imageQuality: 85);
    if (picked == null || !mounted) return;
    setState(() {
      _localAvatar = File(picked.path);
      _uploadingAvatar = true;
    });
    try {
      final updated = await context.read<DirectorProvider>().uploadAvatar(picked);
      if (!mounted) return;
      context.read<AuthProvider>().updateUser(updated);
      _toast('Rasm yangilandi ✅');
    } catch (_) {
      _toast('Rasmни yuklab bo\'lmadi');
    } finally {
      if (mounted) setState(() => _uploadingAvatar = false);
    }
  }

  Future<void> _changePassword() async {
    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => ChangeNotifierProvider<DirectorProvider>.value(
        value: context.read<DirectorProvider>(),
        child: const _ChangePasswordSheet(),
      ),
    );
  }

  String _avatarUrl(String raw) {
    if (raw.isEmpty) return '';
    if (raw.startsWith('http')) return raw;
    return '${AppConfig.baseUrl}$raw';
  }

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    final user = context.watch<AuthProvider>().user;
    final url = _avatarUrl(user?.avatarUrl ?? '');

    return Scaffold(
      backgroundColor: ds.bg,
      appBar: AppBar(title: const Text('Profil')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(DsSpace.screen, DsSpace.x5, DsSpace.screen, DsSpace.x8),
        children: [
          // Avatar
          Center(
            child: Stack(
              children: [
                Container(
                  width: 104,
                  height: 104,
                  decoration: BoxDecoration(shape: BoxShape.circle, color: ds.primarySoft, border: Border.all(color: ds.border)),
                  clipBehavior: Clip.antiAlias,
                  child: _localAvatar != null
                      ? Image.file(_localAvatar!, fit: BoxFit.cover)
                      : (url.isNotEmpty
                          ? CachedNetworkImage(
                              imageUrl: url,
                              fit: BoxFit.cover,
                              errorWidget: (_, __, ___) => _initials(ds, user?.fullName ?? ''),
                            )
                          : _initials(ds, user?.fullName ?? '')),
                ),
                Positioned(
                  right: 0,
                  bottom: 0,
                  child: GestureDetector(
                    onTap: _uploadingAvatar ? null : _pickAvatar,
                    child: Container(
                      width: 34,
                      height: 34,
                      decoration: BoxDecoration(color: ds.primary, shape: BoxShape.circle, border: Border.all(color: ds.bg, width: 2)),
                      child: _uploadingAvatar
                          ? const Padding(padding: EdgeInsets.all(8), child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                          : const Icon(Icons.camera_alt_rounded, size: 17, color: Colors.white),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 10),
          Center(child: Text(user?.fullName ?? 'Direktor', style: DsType.h2(ds.textPrimary))),
          Center(child: Text('Direktor', style: DsType.small(ds.textMuted))),
          const SizedBox(height: DsSpace.section),
          // Tahrirlash
          DsCard(
            child: Column(
              children: [
                DsTextField(label: 'Ism', controller: _ism, hint: 'Ismingiz'),
                const SizedBox(height: 12),
                DsTextField(label: 'Familya', controller: _familya, hint: 'Familyangiz'),
                const SizedBox(height: 12),
                DsTextField(label: 'Telefon', controller: _phone, hint: '+998 90 123 45 67', keyboardType: TextInputType.phone),
              ],
            ),
          ),
          const SizedBox(height: 12),
          DsButton(label: _saving ? 'Saqlanmoqda...' : 'Saqlash', loading: _saving, onPressed: _saving ? null : _save),
          const SizedBox(height: DsSpace.section),
          DsCard(
            padding: const EdgeInsets.symmetric(horizontal: DsSpace.x5, vertical: DsSpace.x1),
            child: DsListRow(
              onTap: _changePassword,
              leading: Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(color: ds.primarySoft, borderRadius: DsRadius.all(DsRadius.sm)),
                child: Icon(Icons.lock_rounded, size: 20, color: ds.primarySoftFg),
              ),
              title: 'Parolni o\'zgartirish',
              trailing: Icon(Icons.chevron_right, color: ds.textFaint),
            ),
          ),
        ],
      ),
    );
  }

  Widget _initials(DsColors ds, String name) {
    final parts = name.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty).toList();
    final ini = parts.isEmpty
        ? '?'
        : (parts.length == 1 ? parts[0].characters.first : parts[0].characters.first + parts[1].characters.first).toUpperCase();
    return Center(child: Text(ini, style: DsType.display(ds.primarySoftFg)));
  }
}

class _ChangePasswordSheet extends StatefulWidget {
  const _ChangePasswordSheet();
  @override
  State<_ChangePasswordSheet> createState() => _ChangePasswordSheetState();
}

class _ChangePasswordSheetState extends State<_ChangePasswordSheet> {
  final _current = TextEditingController();
  final _new = TextEditingController();
  final _confirm = TextEditingController();
  bool _saving = false;

  @override
  void dispose() {
    _current.dispose();
    _new.dispose();
    _confirm.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_new.text.length < 8) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Yangi parol kamida 8 belgi')));
      return;
    }
    if (_new.text != _confirm.text) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Parollar mos kelmadi')));
      return;
    }
    setState(() => _saving = true);
    try {
      await context.read<DirectorProvider>().changePassword(current: _current.text, newPass: _new.text, confirm: _confirm.text);
      if (!mounted) return;
      Navigator.pop(context);
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Parol yangilandi ✅')));
    } catch (_) {
      if (!mounted) return;
      setState(() => _saving = false);
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Xatolik — joriy parol noto\'g\'ri bo\'lishi mumkin')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        decoration: BoxDecoration(
          color: ds.card,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(DsRadius.xl)),
          boxShadow: DsShadow.raised(ds.isDark),
        ),
        padding: const EdgeInsets.fromLTRB(DsSpace.x5, DsSpace.x3, DsSpace.x5, DsSpace.x5),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(child: Container(width: 40, height: 4, decoration: BoxDecoration(color: ds.border, borderRadius: DsRadius.all(DsRadius.pill)))),
            const SizedBox(height: 16),
            Text('Parolni o\'zgartirish', style: DsType.h3(ds.textPrimary)),
            const SizedBox(height: 16),
            DsTextField(label: 'Joriy parol', controller: _current, obscureText: true),
            const SizedBox(height: 12),
            DsTextField(label: 'Yangi parol', controller: _new, obscureText: true),
            const SizedBox(height: 12),
            DsTextField(label: 'Yangi parolни tasdiqlang', controller: _confirm, obscureText: true),
            const SizedBox(height: 16),
            DsButton(label: _saving ? 'Saqlanmoqda...' : 'Saqlash', loading: _saving, onPressed: _saving ? null : _submit),
          ],
        ),
      ),
    );
  }
}
