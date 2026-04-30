import 'dart:typed_data';

import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/parent_models.dart';
import 'package:chaqmoq_mobile/screens/profile/profile_shared.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/parent_dashboard_service.dart';
import 'package:chaqmoq_mobile/widgets/adaptive_avatar.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

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
  late final TextEditingController _firstNameController;
  late final TextEditingController _lastNameController;
  late final TextEditingController _phoneController;
  late final TextEditingController _emailController;
  final ImagePicker _imagePicker = ImagePicker();
  XFile? _selectedImage;
  Uint8List? _selectedImageBytes;
  bool _removeAvatar = false;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _firstNameController = TextEditingController(
      text: widget.initialUser.firstName.isNotEmpty
          ? widget.initialUser.firstName
          : _splitFullName(widget.initialUser.fullName).$1,
    );
    _lastNameController = TextEditingController(
      text: widget.initialUser.lastName.isNotEmpty
          ? widget.initialUser.lastName
          : _splitFullName(widget.initialUser.fullName).$2,
    );
    _phoneController = TextEditingController(text: widget.initialUser.phone);
    _emailController = TextEditingController(text: widget.initialUser.email);
  }

  @override
  void dispose() {
    _firstNameController.dispose();
    _lastNameController.dispose();
    _phoneController.dispose();
    _emailController.dispose();
    super.dispose();
  }

  (String, String) _splitFullName(String value) {
    final parts = value
        .trim()
        .split(RegExp(r'\s+'))
        .where((part) => part.isNotEmpty)
        .toList();
    if (parts.isEmpty) {
      return ('', '');
    }
    if (parts.length == 1) {
      return (parts.first, '');
    }
    return (parts.first, parts.sublist(1).join(' '));
  }

  Future<void> _pickAvatar(ImageSource source) async {
    final XFile? image = await _imagePicker.pickImage(
      source: source,
      maxWidth: 1080,
      imageQuality: 85,
    );
    if (image == null || !mounted) {
      return;
    }
    final bytes = await image.readAsBytes();
    setState(() {
      _selectedImage = image;
      _selectedImageBytes = bytes;
      _removeAvatar = false;
    });
  }

  Future<void> _openAvatarActions() async {
    final hasAvatar =
        _selectedImageBytes != null ||
        (_removeAvatar == false && widget.initialUser.avatarUrl.isNotEmpty);
    final action = await showProfileActionSheet<String>(
      context: context,
      title: 'Profil rasmi',
      options: <ProfileActionSheetOption<String>>[
        const ProfileActionSheetOption<String>(
          value: 'camera',
          title: 'Kameradan olish',
          subtitle: 'Yangi profil rasmini hozirga tushiring',
          icon: Icons.photo_camera_outlined,
        ),
        const ProfileActionSheetOption<String>(
          value: 'gallery',
          title: 'Galereyadan tanlash',
          subtitle: 'Telefoningizdagi rasmlar ichidan tanlang',
          icon: Icons.photo_library_outlined,
        ),
        if (hasAvatar)
          const ProfileActionSheetOption<String>(
            value: 'clear',
            title: 'Rasmni o‘chirish',
            subtitle: 'Profil rasmini olib tashlaydi',
            icon: Icons.delete_outline_rounded,
            destructive: true,
          ),
        const ProfileActionSheetOption<String>(
          value: 'cancel',
          title: 'Bekor qilish',
          subtitle: 'Hech qanday o‘zgarish kiritilmaydi',
          icon: Icons.close_rounded,
        ),
      ],
    );

    if (!mounted || action == null) {
      return;
    }
    if (action == 'cancel') {
      return;
    }
    if (action == 'clear') {
      setState(() {
        _selectedImage = null;
        _selectedImageBytes = null;
        _removeAvatar = true;
      });
      return;
    }
    if (action == 'camera') {
      await _pickAvatar(ImageSource.camera);
      return;
    }
    if (action == 'gallery') {
      await _pickAvatar(ImageSource.gallery);
    }
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }
    setState(() => _saving = true);
    try {
      ParentProfileModel profile = await widget.profileService.updateProfile(
        fullName:
            '${_firstNameController.text.trim()} ${_lastNameController.text.trim()}'
                .trim(),
        phone: _phoneController.text.trim(),
        email: _emailController.text.trim(),
      );
      if (_selectedImage != null || _removeAvatar) {
        profile = await widget.profileService.updateProfileAvatar(
          image: _selectedImage,
          clear: _removeAvatar,
        );
      }
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
                        const SizedBox(height: 16),
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
                                const SizedBox(height: 16),
                                Center(
                                  child: GestureDetector(
                                    onTap: _saving ? null : _openAvatarActions,
                                    child: Stack(
                                      clipBehavior: Clip.none,
                                      children: <Widget>[
                                        Container(
                                          width: 96,
                                          height: 96,
                                          decoration: const BoxDecoration(
                                            shape: BoxShape.circle,
                                            color: Color(0xFFEAF4FF),
                                          ),
                                          clipBehavior: Clip.antiAlias,
                                          child: _selectedImageBytes != null
                                              ? Image.memory(
                                                  _selectedImageBytes!,
                                                  fit: BoxFit.cover,
                                                )
                                              : AdaptiveAvatar(
                                                  name:
                                                      '${_firstNameController.text} ${_lastNameController.text}'
                                                          .trim(),
                                                  imageUrl: _removeAvatar
                                                      ? ''
                                                      : widget
                                                            .initialUser
                                                            .avatarUrl,
                                                  size: 96,
                                                ),
                                        ),
                                        Positioned(
                                          right: -2,
                                          bottom: -2,
                                          child: Container(
                                            width: 34,
                                            height: 34,
                                            decoration: BoxDecoration(
                                              color: Colors.white,
                                              shape: BoxShape.circle,
                                              boxShadow:
                                                  ProfileUiDecorations
                                                      .softShadow,
                                              border: Border.all(
                                                color: ProfileUiColors.border,
                                              ),
                                            ),
                                            child: const Icon(
                                              Icons.photo_camera_outlined,
                                              color: ProfileUiColors.primary,
                                              size: 18,
                                            ),
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                                const SizedBox(height: 14),
                                TextFormField(
                                  controller: _firstNameController,
                                  style: ProfileUiTextStyles.input,
                                  cursorColor: ProfileUiColors.primary,
                                  textCapitalization: TextCapitalization.words,
                                  textInputAction: TextInputAction.next,
                                  decoration: profileInputDecoration(
                                    label: 'Ism',
                                    hintText: 'Ismingiz',
                                    icon: Icons.person_outline_rounded,
                                  ),
                                  validator: (String? value) {
                                    if ((value ?? '').trim().isEmpty) {
                                      return 'Ismni kiriting';
                                    }
                                    return null;
                                  },
                                ),
                                const SizedBox(height: 12),
                                TextFormField(
                                  controller: _lastNameController,
                                  style: ProfileUiTextStyles.input,
                                  cursorColor: ProfileUiColors.primary,
                                  textCapitalization: TextCapitalization.words,
                                  textInputAction: TextInputAction.next,
                                  decoration: profileInputDecoration(
                                    label: 'Familiya',
                                    hintText: 'Familiyangiz',
                                    icon: Icons.badge_outlined,
                                  ),
                                  validator: (String? value) {
                                    if ((value ?? '').trim().isEmpty) {
                                      return 'Familiyani kiriting';
                                    }
                                    return null;
                                  },
                                ),
                                const SizedBox(height: 12),
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
                                const SizedBox(height: 12),
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
                                const SizedBox(height: 18),
                                SizedBox(
                                  width: double.infinity,
                                  child: FilledButton(
                                    onPressed: _saving ? null : _save,
                                    style: FilledButton.styleFrom(
                                      backgroundColor: ProfileUiColors.primary,
                                      foregroundColor: Colors.white,
                                      padding: const EdgeInsets.symmetric(
                                        vertical: 14,
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
