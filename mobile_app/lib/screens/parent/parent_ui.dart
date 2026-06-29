import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/notifications_provider.dart';
import 'package:flutter/material.dart';

class ParentUi {
  const ParentUi._();

  static const double compactBreakpoint = 390;
  static const double narrowBreakpoint = 350;

  static const EdgeInsets screenPadding = EdgeInsets.fromLTRB(16, 12, 16, 24);
  static const EdgeInsets cardPadding = EdgeInsets.fromLTRB(16, 16, 16, 16);
  static const EdgeInsets denseCardPadding = EdgeInsets.fromLTRB(12, 12, 12, 12);
  static const EdgeInsets sheetPadding = EdgeInsets.fromLTRB(16, 12, 16, 16);
  static const EdgeInsets heroPadding = EdgeInsets.fromLTRB(16, 16, 16, 16);

  static const double sectionGap = 16;
  static const double cardGap = 12;
  static const double chipGap = 8;

  static const double cardRadius = 16;
  static const double softRadius = 16;
  static const double sheetRadius = 22;
  static const double chipRadius = 999;

  static const double iconButtonSize = 42;
  static const double avatarButtonSize = 42;
  static const double miniBadgeHeight = 16;

  static bool isCompact(BuildContext context) =>
      MediaQuery.sizeOf(context).width < compactBreakpoint;

  static bool isNarrow(BuildContext context) =>
      MediaQuery.sizeOf(context).width < narrowBreakpoint;

  static int resolveUnreadCount({
    required NotificationsProvider notifications,
    required int fallback,
  }) {
    if (notifications.state == ViewState.success ||
        notifications.items.isNotEmpty ||
        notifications.unreadCount > 0) {
      return notifications.unreadCount;
    }
    return fallback;
  }
}
