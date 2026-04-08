# Chaqmoq Mobile

Professional Flutter mobile CRM for ChaqmoqApp.

This app is built only with Flutter + Dart for real Android and iOS devices.

## Main features

- Material 3 design system
- secure token storage
- slug-based tenant login
- role-based dashboards for `superadmin`, `director`, `manager`, `teacher`, `student`, and `parent`
- students, teachers, groups, attendance, payments, notifications, and profile screens
- loading, empty, error, and pull-to-refresh states

## Folder structure

```text
mobile_app/
  lib/
    main.dart
    core/
      config/
        app_config.dart
      theme/
        app_foundation.dart
        app_theme.dart
      utils/
        formatters.dart
        role_utils.dart
    models/
      app_models.dart
    providers/
      attendance_provider.dart
      auth_provider.dart
      dashboard_provider.dart
      groups_provider.dart
      notifications_provider.dart
      payments_provider.dart
      profile_provider.dart
      students_provider.dart
      teachers_provider.dart
    screens/
      attendance/
      auth/
      dashboard/
      groups/
      notifications/
      payments/
      profile/
      shell/
      students/
      teachers/
    services/
      api_client.dart
      api_services.dart
      storage_service.dart
    widgets/
      app_button.dart
      app_drawer.dart
      app_input_field.dart
      app_list_item_card.dart
      app_page_header.dart
      app_shell_title.dart
      app_view.dart
      chaqmoq_card.dart
      empty_state.dart
      loading_state.dart
      metric_card.dart
```

## Install dependencies

```bash
cd /Users/amirxon/Desktop/ChaqmoqApp/mobile_app
flutter pub get
```

## Run the app

```bash
cd /Users/amirxon/Desktop/ChaqmoqApp/mobile_app
flutter run
```

To run on a specific device:

```bash
flutter devices
flutter run -d <device_id>
```

## Local backend setup

Current local mobile app default URL:

```dart
defaultValue: 'http://127.0.0.1:8001',
```

Start the backend:

```bash
cd /Users/amirxon/Desktop/ChaqmoqApp
python3 manage.py runserver 127.0.0.1:8001
```

For Android over USB:

```bash
export PATH=/Users/amirxon/Library/Android/sdk/platform-tools:$PATH
adb reverse tcp:8001 tcp:8001
```

## Where to change theme and colors

Main design system files:

- `lib/core/theme/app_foundation.dart`
- `lib/core/theme/app_theme.dart`

Use them for:

- brand colors
- gradients
- spacing
- radius values
- shadows
- button/input/card styling

## Where to change API base URL

Change:

- `lib/core/config/app_config.dart`

## How to add a new screen

1. Create a new folder and screen file inside `lib/screens/`
2. If the screen needs API data, add service methods in `lib/services/api_services.dart`
3. Add state handling in a provider inside `lib/providers/`
4. Reuse shared widgets from `lib/widgets/`
5. Register the section in `lib/core/utils/role_utils.dart`
6. Add the screen route switch inside `lib/screens/shell/app_shell.dart`

## Build APK

Debug APK:

```bash
cd /Users/amirxon/Desktop/ChaqmoqApp/mobile_app
flutter build apk --debug
```

Release APK:

```bash
cd /Users/amirxon/Desktop/ChaqmoqApp/mobile_app
flutter build apk --release
```

Generated APK folder:

```text
build/app/outputs/flutter-apk/
```

## iOS

Simulator build:

```bash
cd /Users/amirxon/Desktop/ChaqmoqApp/mobile_app
flutter build ios --simulator --no-codesign
```

For a real iPhone release:

1. Open `ios/Runner.xcworkspace` in Xcode
2. Select your Apple Team
3. Configure signing
4. Build or archive from Xcode
