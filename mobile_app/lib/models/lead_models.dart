import 'package:chaqmoq_mobile/models/app_models.dart';

class LeadModel {
  const LeadModel({
    required this.id,
    required this.fullName,
    this.phone = '',
    this.source = '',
    this.status = '',
    this.statusLabel = '',
    this.nextFollowUpDate,
    this.convertedToStudent = false,
    this.updatedAt,
  });

  final int id;
  final String fullName;
  final String phone;
  final String source;
  final String status;
  final String statusLabel;
  final DateTime? nextFollowUpDate;
  final bool convertedToStudent;
  final DateTime? updatedAt;

  factory LeadModel.fromJson(Map<String, dynamic> j) => LeadModel(
        id: jsonInt(j['id']),
        fullName: jsonString(j['full_name']),
        phone: jsonString(j['phone']),
        source: jsonString(j['source']),
        status: jsonString(j['status']),
        statusLabel: jsonString(j['status_label']),
        nextFollowUpDate: j['next_follow_up_date'] != null
            ? DateTime.tryParse(j['next_follow_up_date'] as String)
            : null,
        convertedToStudent: jsonBool(j['converted_to_student']),
        updatedAt: j['updated_at'] != null
            ? DateTime.tryParse(j['updated_at'] as String)
            : null,
      );
}
