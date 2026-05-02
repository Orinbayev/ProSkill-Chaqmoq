import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:flutter/foundation.dart';

class ChaqmoqHistoryProvider extends ChangeNotifier {
  ChaqmoqHistoryProvider({required ChaqmoqService service}) : _service = service;

  final ChaqmoqService _service;

  List<ChaqmoqEntryModel> _items = const <ChaqmoqEntryModel>[];
  int _balance = 0;
  ViewState _state = ViewState.idle;
  String? _errorMessage;

  List<ChaqmoqEntryModel> get items => _items;
  int get balance => _balance;
  ViewState get state => _state;
  String? get errorMessage => _errorMessage;

  Future<void> load({bool force = false}) async {
    if (_state == ViewState.loading) return;
    if (!force && _items.isNotEmpty) return;
    _state = ViewState.loading;
    _errorMessage = null;
    notifyListeners();
    try {
      final result = await _service.fetchHistory();
      _balance = result.balance;
      _items = result.items;
      _state = ViewState.success;
    } catch (error) {
      _state = ViewState.error;
      _errorMessage = error is ApiException ? error.message : 'Tarix yuklanmadi';
    } finally {
      notifyListeners();
    }
  }

  Future<void> refresh() => load(force: true);

  /// All entries on the given calendar day.
  List<ChaqmoqEntryModel> entriesOn(DateTime date) {
    return _items.where((e) {
      final d = e.createdAt;
      return d.year == date.year && d.month == date.month && d.day == date.day;
    }).toList()
      ..sort((a, b) => a.createdAt.compareTo(b.createdAt));
  }

  /// Distinct calendar dates that have at least one positive entry — used as
  /// a proxy for "Kelgan kunlar" until a dedicated lessons API exists.
  Set<DateTime> get attendedDays {
    final s = <DateTime>{};
    for (final e in _items) {
      if (e.points <= 0) continue;
      final d = e.createdAt;
      s.add(DateTime(d.year, d.month, d.day));
    }
    return s;
  }

  /// Distinct dates where the only entries are negative (likely davomatsizlik).
  Set<DateTime> get absentDays {
    final byDay = <DateTime, List<int>>{};
    for (final e in _items) {
      final d = DateTime(e.createdAt.year, e.createdAt.month, e.createdAt.day);
      byDay.putIfAbsent(d, () => <int>[]).add(e.points);
    }
    final out = <DateTime>{};
    byDay.forEach((d, ps) {
      if (ps.every((p) => p < 0)) out.add(d);
    });
    return out;
  }

  /// All distinct group names the student has received chaqmoq from.
  /// Used as a best-effort "ro'yxatdagi kurslar" derivation.
  List<String> get groupNames {
    final seen = <String>{};
    for (final e in _items) {
      if (e.groupName.isNotEmpty) seen.add(e.groupName);
    }
    return seen.toList();
  }
}
