import 'package:chaqmoq_mobile/screens/profile/profile_shared.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/parent_dashboard_service.dart';
import 'package:flutter/material.dart';

class SecurityScreen extends StatefulWidget {
  const SecurityScreen({super.key, required this.profileService});

  final ParentDashboardService profileService;

  @override
  State<SecurityScreen> createState() => _SecurityScreenState();
}

class _SecurityScreenState extends State<SecurityScreen> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();
  final TextEditingController _currentPasswordController =
      TextEditingController();
  final TextEditingController _newPasswordController = TextEditingController();
  final TextEditingController _confirmPasswordController =
      TextEditingController();
  bool _submitting = false;

  @override
  void dispose() {
    _currentPasswordController.dispose();
    _newPasswordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }
    setState(() => _submitting = true);
    try {
      await widget.profileService.changePassword(
        currentPassword: _currentPasswordController.text,
        newPassword: _newPasswordController.text,
        confirmPassword: _confirmPasswordController.text,
      );
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Parol muvaffaqiyatli yangilandi')),
      );
      Navigator.of(context).pop(true);
    } on ApiException catch (error) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(error.message)));
    } finally {
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.viewInsetsOf(context).bottom;

    return Theme(
      data: buildProfileFormTheme(context),
      child: Scaffold(
        backgroundColor: ProfileUiColors.of(context).background,
        body: SafeArea(
          child: SingleChildScrollView(
            keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
            padding: EdgeInsets.fromLTRB(16, 14, 16, 24 + bottomInset),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                const ProfilePageHeader(title: 'Hisob xavfsizligi'),
                const SizedBox(height: 18),
                ProfilePageCard(
                  child: Form(
                    key: _formKey,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          'Parolingizni xavfsiz yangilang.',
                          style: ProfileUiTextStyles.of(context).muted,
                        ),
                        const SizedBox(height: 18),
                        TextFormField(
                          controller: _currentPasswordController,
                          style: ProfileUiTextStyles.of(context).input,
                          cursorColor: ProfileUiColors.of(context).primary,
                          obscureText: true,
                          textInputAction: TextInputAction.next,
                          decoration: profileInputDecoration(context, 
                            label: 'Joriy parol',
                            icon: Icons.lock_outline_rounded,
                          ),
                          validator: (String? value) {
                            if ((value ?? '').isEmpty) {
                              return 'Joriy parolni kiriting';
                            }
                            return null;
                          },
                        ),
                        const SizedBox(height: 14),
                        TextFormField(
                          controller: _newPasswordController,
                          style: ProfileUiTextStyles.of(context).input,
                          cursorColor: ProfileUiColors.of(context).primary,
                          obscureText: true,
                          textInputAction: TextInputAction.next,
                          decoration: profileInputDecoration(context, 
                            label: 'Yangi parol',
                            icon: Icons.password_rounded,
                            helperText: 'Kamida 8 ta belgi',
                          ),
                          validator: (String? value) {
                            if ((value ?? '').length < 8) {
                              return 'Yangi parol kamida 8 ta belgidan iborat bo‘lsin';
                            }
                            return null;
                          },
                        ),
                        const SizedBox(height: 14),
                        TextFormField(
                          controller: _confirmPasswordController,
                          style: ProfileUiTextStyles.of(context).input,
                          cursorColor: ProfileUiColors.of(context).primary,
                          obscureText: true,
                          textInputAction: TextInputAction.done,
                          decoration: profileInputDecoration(context, 
                            label: 'Parolni tasdiqlang',
                            icon: Icons.verified_user_outlined,
                          ),
                          validator: (String? value) {
                            if ((value ?? '') != _newPasswordController.text) {
                              return 'Parollar mos kelmadi';
                            }
                            return null;
                          },
                        ),
                        const SizedBox(height: 22),
                        SizedBox(
                          width: double.infinity,
                          child: FilledButton(
                            onPressed: _submitting ? null : _submit,
                            style: FilledButton.styleFrom(
                              backgroundColor: ProfileUiColors.of(context).primary,
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(vertical: 15),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(16),
                              ),
                            ),
                            child: _submitting
                                ? const SizedBox(
                                    width: 20,
                                    height: 20,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2.2,
                                      color: Colors.white,
                                    ),
                                  )
                                : Text(
                                    'Parolni yangilash',
                                    style: ProfileUiTextStyles.of(context).button,
                                  ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
