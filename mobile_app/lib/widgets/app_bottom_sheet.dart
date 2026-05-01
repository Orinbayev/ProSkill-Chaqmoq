import 'package:chaqmoq_mobile/core/theme/parent_colors.dart';
import 'package:chaqmoq_mobile/core/theme/parent_text_styles.dart';
import 'package:chaqmoq_mobile/core/theme/student_colors.dart';
import 'package:flutter/material.dart';

/// Bottom sheet chrome — drag handle + title + close. Mirrors primitives.jsx.
class AppBottomSheet extends StatelessWidget {
  const AppBottomSheet({
    super.key,
    required this.title,
    required this.child,
    this.dark = false,
    this.maxHeightFraction = 0.78,
    this.onClose,
  });

  final String title;
  final Widget child;
  final bool dark;
  final double maxHeightFraction;
  final VoidCallback? onClose;

  static Future<T?> show<T>({
    required BuildContext context,
    required String title,
    required Widget Function(BuildContext) builder,
    bool dark = false,
    double maxHeightFraction = 0.78,
  }) {
    return showModalBottomSheet<T>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) => AppBottomSheet(
        title: title,
        dark: dark,
        maxHeightFraction: maxHeightFraction,
        onClose: () => Navigator.of(sheetContext).pop(),
        child: builder(sheetContext),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final bg = dark ? const Color(0xFA13131A) : Colors.white;
    final fg = dark ? StudentColors.text : ParentColors.text;
    final border = dark ? StudentColors.border : ParentColors.line;
    final handle = dark ? Colors.white.withAlpha((0.18 * 255).round()) : ParentColors.lineStrong;
    final maxHeight = MediaQuery.sizeOf(context).height * maxHeightFraction;

    return ConstrainedBox(
      constraints: BoxConstraints(maxHeight: maxHeight),
      child: Container(
        decoration: BoxDecoration(
          color: bg,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(28)),
          border: Border(
            top: BorderSide(color: border),
            left: BorderSide(color: border),
            right: BorderSide(color: border),
          ),
          boxShadow: const [
            BoxShadow(
              color: Color(0x33000000),
              blurRadius: 40,
              offset: Offset(0, -20),
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 12),
            Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: handle,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 6),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 6, 12, 14),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: ParentTextStyles.title.copyWith(
                        color: fg,
                        fontSize: 17,
                      ),
                    ),
                  ),
                  if (onClose != null)
                    Material(
                      color: dark ? StudentColors.glass : ParentColors.bgSoft,
                      borderRadius: BorderRadius.circular(10),
                      child: InkWell(
                        onTap: onClose,
                        borderRadius: BorderRadius.circular(10),
                        child: SizedBox(
                          width: 32,
                          height: 32,
                          child: Icon(Icons.close_rounded, color: fg, size: 18),
                        ),
                      ),
                    ),
                ],
              ),
            ),
            Flexible(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 28),
                child: SafeArea(top: false, child: child),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
