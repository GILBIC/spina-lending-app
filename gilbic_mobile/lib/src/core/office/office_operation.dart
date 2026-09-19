import 'package:flutter/foundation.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

/// In-memory request lifetime for one office screen. Never queues writes.
class OfficeOperation extends ChangeNotifier {
  bool busy = false;
  bool blocked = false;
  bool denied = false;
  String? error;
  int? lastStatus;
  int _generation = 0;
  bool _disposed = false;
  bool _writing = false;

  bool get canWrite => !busy && !blocked && !denied;
  void invalidate() {
    _generation++;
    if (busy && _writing) blocked = true;
    busy = false;
    error = null;
  }

  Future<T?> run<T>(
    Future<T> Function() action, {
    bool mutation = false,
    bool reconcile = false,
    bool idempotentRetry = false,
  }) async {
    if (_disposed ||
        busy ||
        denied ||
        (mutation && blocked && !idempotentRetry)) {
      return null;
    }
    final generation = ++_generation;
    busy = true;
    _writing = mutation;
    error = null;
    lastStatus = null;
    notifyListeners();
    try {
      final result = await action();
      if (_disposed || generation != _generation) return null;
      if (reconcile) blocked = false;
      return result;
    } on Object catch (failure) {
      if (_disposed || generation != _generation) return null;
      final api = failure is SpinaApiException ? failure : null;
      lastStatus = api?.statusCode;
      denied = [401, 403, 426].contains(api?.statusCode);
      if (mutation && ![400, 422].contains(api?.statusCode)) blocked = true;
      if (api?.statusCode == 409) blocked = true;
      error =
          api?.message ??
          'The result could not be verified. Reload the saved record.';
      return null;
    } finally {
      if (!_disposed && generation == _generation) {
        busy = false;
        _writing = false;
        notifyListeners();
      }
    }
  }

  @override
  void dispose() {
    _disposed = true;
    _generation++;
    super.dispose();
  }
}
