import 'package:flutter/material.dart';

class AppView extends StatelessWidget {
  const AppView({
    super.key,
    required this.child,
    this.maxWidth = 1120,
  });

  final Widget child;
  final double maxWidth;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Center(
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: maxWidth),
          child: child,
        ),
      ),
    );
  }
}
