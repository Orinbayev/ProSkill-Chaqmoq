import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:flutter/foundation.dart';

class PaymentsProvider extends ChangeNotifier {
  PaymentsProvider({required PaymentsService paymentsService})
    : _paymentsService = paymentsService;

  final PaymentsService _paymentsService;

  PaymentSummaryModel _summary = const PaymentSummaryModel(
    totalReceived: 0,
    openDebt: 0,
    thisMonth: 0,
  );
  List<PaymentModel> _items = <PaymentModel>[];
  ViewState _state = ViewState.idle;
  String _filter = 'all';
  String? _errorMessage;

  PaymentSummaryModel get summary => _summary;
  ViewState get state => _state;
  String? get errorMessage => _errorMessage;
  String get filter => _filter;

  List<PaymentModel> get allItems => List.unmodifiable(_items);

  List<PaymentModel> get filteredItems {
    return _items.where((item) {
      return switch (_filter) {
        'received' => !item.isDebt,
        'debt' => item.isDebt,
        _ => true,
      };
    }).toList();
  }

  Future<void> load(UserModel user, {bool force = false}) async {
    if (_state == ViewState.loading) {
      return;
    }
    if (!force && _items.isNotEmpty) {
      return;
    }
    _state = ViewState.loading;
    _errorMessage = null;
    notifyListeners();
    try {
      final data = await _paymentsService.fetchPayments(user);
      _summary = data.$1;
      _items = data.$2;
      _state = ViewState.success;
    } catch (error) {
      _state = ViewState.error;
      _errorMessage = _mapError(error);
    } finally {
      notifyListeners();
    }
  }

  Future<void> refresh(UserModel user) => load(user, force: true);

  void setFilter(String filter) {
    _filter = filter;
    notifyListeners();
  }

  String _mapError(Object error) {
    if (error is ApiException) {
      return error.message;
    }
    return 'To\'lovlar yuklanmadi';
  }
}
