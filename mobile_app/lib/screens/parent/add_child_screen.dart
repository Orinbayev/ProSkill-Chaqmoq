import 'package:chaqmoq_mobile/models/parent_models.dart';
import 'package:chaqmoq_mobile/screens/profile/profile_shared.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/parent_dashboard_service.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class AddChildScreen extends StatefulWidget {
  const AddChildScreen({super.key});

  @override
  State<AddChildScreen> createState() => _AddChildScreenState();
}

class _AddChildScreenState extends State<AddChildScreen> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();
  final TextEditingController _childCodeController = TextEditingController();
  bool _submitting = false;

  @override
  void dispose() {
    _childCodeController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }
    setState(() => _submitting = true);
    try {
      final ParentChildModel child = await context
          .read<ParentDashboardService>()
          .addChild(
        _childCodeController.text.trim(),
      );
      if (!mounted) {
        return;
      }
      Navigator.of(context).pop<ParentChildModel>(child);
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
                        const ProfilePageHeader(title: 'Farzand qo‘shish'),
                        const SizedBox(height: 18),
                        ProfilePageCard(
                          child: Form(
                            key: _formKey,
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: <Widget>[
                                Text(
                                  'Farzandni maxsus kod orqali profilingizga bog‘lang.',
                                  style: ProfileUiTextStyles.muted,
                                ),
                                const SizedBox(height: 18),
                                TextFormField(
                                  controller: _childCodeController,
                                  style: ProfileUiTextStyles.input,
                                  cursorColor: ProfileUiColors.primary,
                                  textCapitalization:
                                      TextCapitalization.characters,
                                  textInputAction: TextInputAction.done,
                                  decoration: profileInputDecoration(
                                    label: 'Farzand kodi',
                                    hintText: 'Masalan: CHQ-000123',
                                    helperText:
                                        'Farzandingiz profilini bog‘lash uchun o‘quv markazidan berilgan maxsus kodni kiriting.',
                                    icon: Icons.badge_outlined,
                                  ),
                                  validator: (String? value) {
                                    if ((value ?? '').trim().isEmpty) {
                                      return 'Farzand kodini kiriting';
                                    }
                                    return null;
                                  },
                                  onFieldSubmitted: (_) =>
                                      _submitting ? null : _submit(),
                                ),
                                const SizedBox(height: 22),
                                SizedBox(
                                  width: double.infinity,
                                  child: FilledButton(
                                    onPressed: _submitting ? null : _submit,
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
                                            'Farzand qo‘shish',
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
