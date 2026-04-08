import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:flutter/foundation.dart';

class PaymentsProvider extends ChangeNotifier {
  PaymentsProvider({required PaymentService paymentService})
    : _paymentService = paymentService;

  final PaymentService _paymentService;

  List<PaymentModel> items = [];
  int totalAmount = 0;
  bool isLoading = false;
  bool isSaving = false;
  String? errorMessage;

  void reset() {
    items = [];
    totalAmount = 0;
    isLoading = false;
    isSaving = false;
    errorMessage = null;
    notifyListeners();
  }

  Future<void> load({String? query}) async {
    isLoading = true;
    errorMessage = null;
    notifyListeners();

    try {
      final result = await _paymentService.fetchPayments(query: query);
      items = result.$1;
      totalAmount = result.$2;
    } catch (error) {
      errorMessage = error is ApiException
          ? error.message
          : 'To\'lovlarni yuklab bo\'lmadi';
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }

  Future<PaymentModel?> create({
    required int enrollmentId,
    required int cashAmount,
    required int cardAmount,
    required DateTime month,
    required String note,
  }) async {
    isSaving = true;
    errorMessage = null;
    notifyListeners();

    try {
      final payment = await _paymentService.createPayment(
        enrollmentId: enrollmentId,
        cashAmount: cashAmount,
        cardAmount: cardAmount,
        month: month,
        note: note,
      );
      items = [payment, ...items];
      totalAmount += payment.amount;
      return payment;
    } catch (error) {
      errorMessage = error is ApiException
          ? error.message
          : 'To\'lovni yaratib bo\'lmadi';
      return null;
    } finally {
      isSaving = false;
      notifyListeners();
    }
  }
}
