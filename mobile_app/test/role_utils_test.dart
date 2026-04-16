import 'package:chaqmoq_mobile/core/utils/role_utils.dart';
import 'package:chaqmoq_mobile/core/theme/app_colors.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('role utils normalizes and maps director scope', () {
    expect(RoleUtils.normalize('superadmin'), 'superuser');
    expect(RoleUtils.roleLabel('director'), 'Direktor');
    expect(RoleUtils.roleColor('teacher'), AppColors.success);
    expect(RoleUtils.isDirectorScope('manager'), isTrue);
    expect(RoleUtils.isDirectorScope('student'), isFalse);
  });
}
