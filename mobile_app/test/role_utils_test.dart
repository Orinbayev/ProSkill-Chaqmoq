import 'package:chaqmoq_mobile/core/utils/role_utils.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('superadmin exposes expected primary sections', () {
    final sections = RoleUtils.primarySections('superadmin');

    expect(sections.map((item) => item.section), contains(AppSection.home));
    expect(sections.map((item) => item.section), contains(AppSection.students));
    expect(sections.map((item) => item.section), contains(AppSection.teachers));
    expect(sections.map((item) => item.section), contains(AppSection.payments));
  });
}
