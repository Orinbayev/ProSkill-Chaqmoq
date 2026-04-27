import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/parent_models.dart';
import 'package:chaqmoq_mobile/screens/profile/profile_shared.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/parent_dashboard_service.dart';
import 'package:flutter/material.dart';

class EditProfileScreen extends StatefulWidget {
  const EditProfileScreen({
    super.key,
    required this.initialUser,
    required this.profileService,
  });

  final UserModel initialUser;
  final ParentDashboardService profileService;

  @override
  State<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends State<EditProfileScreen> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();
  late final TextEditingController _fullNameController;
  late final TextEditingController _phoneController;
  late final TextEditingController _emailController;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _fullNameController = TextEditingController(
      text: widget.initialUser.fullName,
    );
    _phoneController = TextEditingController(text: widget.initialUser.phone);
    _emailController = TextEditingController(text: widget.initialUser.email);
  }

  @override
  void dispose() {
    _fullNameController.dispose();
    _phoneController.dispose();
    _emailController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }
    setState(() => _saving = true);
    try {
      final ParentProfileModel profile = await widget.profileService
          .updateProfile(
            fullName: _fullNameController.text.trim(),
            phone: _phoneController.text.trim(),
            email: _emailController.text.trim(),
          );
      if (!mounted) {
        return;
      }
      Navigator.of(context).pop<ParentProfileModel>(profile);
    } on ApiException catch (error) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(error.message)));
    } finally {
      if (mounted) {
        setState(() => _saving = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.viewInsetsOf(context).bottom;

    return Theme(
      data: buildProfileFormTheme(context),
      child: Scaffold(
        backgroundColor: ProfileUiColors.background,
        body: SafeArea(
          child: LayoutBuilder(
            builder: (BuildContext context, BoxConstraints constraints) {
              return GestureDetector(
                onTap: () => FocusScope.of(context).unfocus(),
                child: SingleChildScrollView(
                  keyboardDismissBehavior:
                      ScrollViewKeyboardDismissBehavior.onDrag,
                  padding: EdgeInsets.fromLTRB(16, 14, 16, 24 + bottomInset),
                  child: ConstrainedBox(
                    constraints: BoxConstraints(minHeight: constraints.maxHeight),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        const ProfilePageHeader(title: 'Shaxsiy ma’lumotlar'),
                        const SizedBox(height: 18),
                        ProfilePageCard(
                          child: Form(
                            key: _formKey,
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: <Widget>[
                                Text(
                                  'Profil ma’lumotlaringizni yangilang.',
                                  style: ProfileUiTextStyles.muted,
                                ),
                                const SizedBox(height: 18),
                                TextFormField(
                                  controller: _fullNameController,
                                  style: ProfileUiTextStyles.input,
                                  cursorColor: ProfileUiColors.primary,
                                  textCapitalization: TextCapitalization.words,
                                  textInputAction: TextInputAction.next,
                                  decoration: profileInputDecoration(
                                    label: 'To‘liq ism',
                                    hintText: 'Ism va familiyangiz',
                                    icon: Icons.person_outline_rounded,
                                  ),
                                  validator: (String? value) {
                                    if ((value ?? '').trim().isEmpty) {
                                      return 'To‘liq ismni kiriting';
                                    }
                                    return null;
                                  },
                                ),
                                const SizedBox(height: 14),
                                TextFormField(
                                  controller: _phoneController,
                                  style: ProfileUiTextStyles.input,
                                  cursorColor: ProfileUiColors.primary,
                                  keyboardType: TextInputType.phone,
                                  textInputAction: TextInputAction.next,
                                  decoration: profileInputDecoration(
                                    label: 'Telefon',
                                    hintText: '+998 90 123 45 67',
                                    icon: Icons.phone_outlined,
                                  ),
                                  validator: (String? value) {
                                    final String phone = (value ?? '').trim();
                                    if (phone.isEmpty) {
                                      return null;
                                    }
                                    final String digits = phone.replaceAll(
                                      RegExp(r'\D'),
                                      '',
                                    );
                                    final bool isValid =
                                        digits.length == 9 ||
                                        (digits.length == 12 &&
                                            digits.startsWith('998'));
                                    if (!isValid) {
                                      return 'Telefon raqam noto‘g‘ri';
                                    }
                                    return null;
                                  },
                                ),
                                const SizedBox(height: 14),
                                TextFormField(
                                  controller: _emailController,
                                  style: ProfileUiTextStyles.input,
                                  cursorColor: ProfileUiColors.primary,
                                  keyboardType: TextInputType.emailAddress,
                                  textInputAction: TextInputAction.done,
                                  decoration: profileInputDecoration(
                                    label: 'Email',
                                    hintText: 'example@chaqmoq.uz',
                                    icon: Icons.mail_outline_rounded,
                                  ),
                                  validator: (String? value) {
                                    final String email = (value ?? '').trim();
                                    if (email.isEmpty) {
                                      return 'Emailni kiriting';
                                    }
                                    final bool isValid = RegExp(
                                      r'^[^@\s]+@[^@\s]+\.[^@\s]+$',
                                    ).hasMatch(email);
                                    if (!isValid) {
                                      return 'Email noto‘g‘ri';
                                    }
                                    return null;
                                  },
                                  onFieldSubmitted: (_) => _saving ? null : _save(),
                                ),
                                const SizedBox(height: 22),
                                SizedBox(
                                  width: double.infinity,
                                  child: FilledButton(
                                    onPressed: _saving ? null : _save,
                                    style: FilledButton.styleFrom(
                                      backgroundColor: ProfileUiColors.primary,
                                      foregroundColor: Colors.white,
                                      padding: const EdgeInsets.symmetric(
                                        vertical: 15,
                                      ),
                                      shape: RoundedRectangleBorder(
                                        borderRadius: BorderRadius.circular(16),
                                      ),
                                    ),
                                    child: _saving
                                        ? const SizedBox(
                                            width: 20,
                                            height: 20,
                                            child: CircularProgressIndicator(
                                              strokeWidth: 2.2,
                                              color: Colors.white,
                                            ),
                                          )
                                        : Text(
                                            'Saqlash',
                                            style: ProfileUiTextStyles.button,
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
              );
            },
          ),
        ),
      ),
    );
  }
}
