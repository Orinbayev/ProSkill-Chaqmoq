import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/lead_models.dart';
import 'package:chaqmoq_mobile/services/leads_service.dart';
import 'package:flutter/foundation.dart';

class LeadsProvider extends ChangeNotifier {
  LeadsProvider({required LeadsService service}) : _service = service;
  final LeadsService _service;

  List<LeadModel> _leads = [];
  ViewState _state = ViewState.idle;
  String _error = '';
  String _statusFilter = '';

  List<LeadModel> get leads => _leads;
  ViewState get state => _state;
  String get error => _error;
  String get statusFilter => _statusFilter;

  Future<void> load({String? q, String? status, bool force = false}) async {
    final s = status ?? _statusFilter;
    if (!force && _state == ViewState.success && s == _statusFilter && (q == null || q.isEmpty)) return;
    _statusFilter = s;
    _state = ViewState.loading;
    _error = '';
    notifyListeners();
    try {
      _leads = await _service.getLeads(q: q, status: s.isEmpty ? null : s);
      _state = ViewState.success;
    } catch (e) {
      _error = e.toString();
      _state = ViewState.error;
    }
    notifyListeners();
  }

  void setStatusFilter(String status) {
    _statusFilter = status;
    load(status: status, force: true);
  }
}
