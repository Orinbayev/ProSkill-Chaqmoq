import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/profile_provider.dart';
import 'package:chaqmoq_mobile/widgets/app_button.dart';
import 'package:chaqmoq_mobile/widgets/app_input_field.dart';
import 'package:chaqmoq_mobile/widgets/app_page_header.dart';
import 'package:chaqmoq_mobile/widgets/chaqmoq_card.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final _formKey = GlobalKey<FormState>();
  final _ismController = TextEditingController();
  final _familyaController = TextEditingController();
  final _otchestvoController = TextEditingController();
  final _emailController = TextEditingController();
  final _phoneNumberController = TextEditingController();
  final _telefon1Controller = TextEditingController();
  final _telefon2Controller = TextEditingController();
  int? _boundUserId;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final user = context.read<AuthProvider>().user;
    if (user == null || _boundUserId == user.id) {
      return;
    }
    _boundUserId = user.id;
    _ismController.text = user.ism;
    _familyaController.text = user.familya;
    _otchestvoController.text = user.otchestvo;
    _emailController.text = user.email;
    _phoneNumberController.text = user.phoneNumber;
    _telefon1Controller.text = user.telefon1;
    _telefon2Controller.text = user.telefon2;
  }

  @override
  void dispose() {
    _ismController.dispose();
    _familyaController.dispose();
    _otchestvoController.dispose();
    _emailController.dispose();
    _phoneNumberController.dispose();
    _telefon1Controller.dispose();
    _telefon2Controller.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    final profileProvider = context.read<ProfileProvider>();
    final updatedUser = await profileProvider.save({
      'ism': _ismController.text.trim(),
      'familya': _familyaController.text.trim(),
      'otchestvo': _otchestvoController.text.trim(),
      'email': _emailController.text.trim(),
      'phone_number': _phoneNumberController.text.trim(),
      'telefon1': _telefon1Controller.text.trim(),
      'telefon2': _telefon2Controller.text.trim(),
    });

    if (!mounted || updatedUser == null) {
      if (mounted && profileProvider.errorMessage != null) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(profileProvider.errorMessage!)));
      }
      return;
    }

    context.read<AuthProvider>().replaceUser(updatedUser);
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Profil muvaffaqiyatli yangilandi')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final profileProvider = context.watch<ProfileProvider>();
    final user = auth.user;

    if (user == null) {
      return const SizedBox.shrink();
    }

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        ChaqmoqCard(
          gradient: const LinearGradient(
            colors: [Color(0xFF0F172A), Color(0xFF1D4ED8)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CircleAvatar(
                radius: 28,
                backgroundColor: Colors.white.withValues(alpha: 0.18),
                child: Text(
                  (user.fullName.isEmpty ? 'F' : user.fullName.characters.first)
                      .toUpperCase(),
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    color: Colors.white,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Text(
                user.fullName.isEmpty ? 'Chaqmoq foydalanuvchisi' : user.fullName,
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                '${AppFormatters.roleLabel(user.effectiveRole)} • ${user.center?.name ?? 'ChaqmoqApp'}',
                style: Theme.of(
                  context,
                ).textTheme.bodyLarge?.copyWith(color: Colors.white70),
              ),
            ],
          ),
        ),
        const SizedBox(height: 14),
        const AppPageHeader(
          title: 'Profil',
          subtitle:
              'Shaxsiy ma\'lumotlaringizni yangilang va aloqa ma\'lumotlarini boshqaring.',
        ),
        const SizedBox(height: 14),
        ChaqmoqCard(
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Shaxsiy ma\'lumotlar',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 16),
                AppInputField(
                  controller: _ismController,
                  label: 'Ism',
                  validator: (value) {
                    if (value == null || value.trim().isEmpty) {
                      return 'Ism majburiy';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 14),
                AppInputField(
                  controller: _familyaController,
                  label: 'Familiya',
                  validator: (value) {
                    if (value == null || value.trim().isEmpty) {
                      return 'Familiya majburiy';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 14),
                AppInputField(
                  controller: _otchestvoController,
                  label: 'Sharif',
                ),
                const SizedBox(height: 14),
                AppInputField(
                  controller: _emailController,
                  keyboardType: TextInputType.emailAddress,
                  label: 'Elektron pochta',
                  validator: (value) {
                    if (value != null &&
                        value.trim().isNotEmpty &&
                        !value.contains('@')) {
                      return 'To\'g\'ri elektron pochta kiriting';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 14),
                AppInputField(
                  controller: _phoneNumberController,
                  keyboardType: TextInputType.phone,
                  label: 'Telefon raqami',
                ),
                const SizedBox(height: 14),
                AppInputField(
                  controller: _telefon1Controller,
                  keyboardType: TextInputType.phone,
                  label: 'Asosiy telefon',
                ),
                const SizedBox(height: 14),
                AppInputField(
                  controller: _telefon2Controller,
                  keyboardType: TextInputType.phone,
                  label: 'Qo\'shimcha telefon',
                ),
                const SizedBox(height: 22),
                AppButton(
                  label: profileProvider.isSaving
                      ? 'Saqlanmoqda...'
                      : 'Profilni saqlash',
                  icon: Icons.save_rounded,
                  loading: profileProvider.isSaving,
                  onPressed: _save,
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
