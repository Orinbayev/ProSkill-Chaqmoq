import 'package:chaqmoq_mobile/models/lead_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';

class LeadsService {
  const LeadsService(this._apiClient);
  final ApiClient _apiClient;

  Future<List<LeadModel>> getLeads({String? q, String? status}) async {
    final params = <String, dynamic>{};
    if (q != null && q.isNotEmpty) params['q'] = q;
    if (status != null && status.isNotEmpty) params['status'] = status;
    final data = await _apiClient.get('/api/mobile/leads/', queryParameters: params.isEmpty ? null : params);
    final items = data['items'] as List? ?? [];
    return items.map((e) => LeadModel.fromJson(e as Map<String, dynamic>)).toList();
  }
}
