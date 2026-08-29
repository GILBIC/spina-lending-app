import 'package:gilbic_mobile/src/core/network/spina_api.dart';

enum CollectorFailureTask {
  loadRoute,
  recordCollection,
  recordCombinedCollection,
  correctCollection,
  loadCorrectionHistory,
  loadOtherAreaWork,
  loadRemittance,
  submitRemittance,
}

String collectorFailureMessage(
  Object error, {
  required CollectorFailureTask task,
}) {
  if (error is! SpinaApiException) {
    return _fallbackFor(task);
  }

  final status = error.statusCode;
  final code = (error.code ?? '').trim().toLowerCase();
  final message = error.message.trim();
  final normalizedMessage = message.toLowerCase();

  if (status == 401) {
    return 'Your session expired. Sign in again before continuing.';
  }
  if (status == 403 && _describesDeviceAccess(normalizedMessage, code)) {
    return 'This device is no longer approved. Ask Management to approve this device, then sign in again.';
  }
  if (status == 403) {
    return switch (task) {
      CollectorFailureTask.loadRoute =>
        'Your current account is not allowed to view this route. Ask Management to check your Collector assignment.',
      CollectorFailureTask.recordCollection ||
      CollectorFailureTask.recordCombinedCollection =>
        'Your current account is not allowed to record this collection. Ask Management to check your Collector access.',
      CollectorFailureTask.correctCollection =>
        'Your current account is not allowed to correct this collection. Ask Management to check your Collector access.',
      CollectorFailureTask.loadCorrectionHistory =>
        'Your current account is not allowed to view correction history. Ask Management to check your Collector access.',
      CollectorFailureTask.loadOtherAreaWork =>
        'Your current account is not allowed to view other-area work. Ask Management to check your area delegation.',
      CollectorFailureTask.loadRemittance ||
      CollectorFailureTask.submitRemittance =>
        'Your current account is not allowed to handle this remittance. Ask Management to check your Collector access.',
    };
  }
  if (_describesStaleRoute(normalizedMessage, code)) {
    return _conflictFor(task);
  }
  if (_describesPossibleDuplicate(normalizedMessage, code)) {
    return switch (task) {
      CollectorFailureTask.recordCombinedCollection =>
        "These payments may already be recorded. Refresh the route and check today's receipts before trying again.",
      CollectorFailureTask.correctCollection =>
        "This correction may already be saved. Refresh the route and check today's entry before trying again.",
      CollectorFailureTask.submitRemittance =>
        'This remittance may already be submitted. Refresh the summary and check its status before trying again.',
      CollectorFailureTask.loadRoute ||
      CollectorFailureTask.loadCorrectionHistory ||
      CollectorFailureTask.loadOtherAreaWork ||
      CollectorFailureTask.loadRemittance ||
      CollectorFailureTask.recordCollection =>
        "This collection may already be recorded. Refresh the route and check today's receipt before trying again.",
    };
  }
  if (status == 409) {
    return _conflictFor(task);
  }
  if (status == null || status == 429 || status >= 500) {
    return _fallbackFor(task);
  }
  return message.isEmpty ? _fallbackFor(task) : message;
}

bool _describesDeviceAccess(String message, String code) {
  final mentionsDevice = message.contains('device') || code.contains('device');
  return mentionsDevice &&
      (message.contains('revoked') ||
          message.contains('not registered') ||
          message.contains('approval') ||
          message.contains('approved') ||
          code.contains('revoked') ||
          code.contains('approval') ||
          code.contains('not_registered'));
}

bool _describesStaleRoute(String message, String code) {
  return code == 'route_revision_changed' ||
      code == 'combined_route_revision_changed' ||
      code == 'route_entry_changed' ||
      code == 'route_revision_required' ||
      (message.contains('route') &&
          (message.contains('changed') || message.contains('stale')));
}

bool _describesPossibleDuplicate(String message, String code) {
  return code.contains('already_recorded') ||
      code.contains('duplicate') ||
      code.contains('idempotency') ||
      code == 'device_sequence_reused' ||
      message.contains('already recorded') ||
      message.contains('duplicate');
}

String _fallbackFor(CollectorFailureTask task) => switch (task) {
  CollectorFailureTask.loadRoute =>
    "Gilbic could not load today's route. Check your connection, then tap Try again.",
  CollectorFailureTask.recordCollection =>
    'Gilbic could not confirm this collection. Check your connection, then use Retry for the same entry.',
  CollectorFailureTask.recordCombinedCollection =>
    'Gilbic could not confirm the Regular + 7x7 payment. Check your connection, then use Retry for the same payment.',
  CollectorFailureTask.correctCollection =>
    "Gilbic could not save this correction. Refresh the route, check today's entry, then try again.",
  CollectorFailureTask.loadCorrectionHistory =>
    'Gilbic could not load correction history. Check your connection, then tap Retry.',
  CollectorFailureTask.loadOtherAreaWork =>
    'Gilbic could not load other-area work. Check your connection, then tap Retry.',
  CollectorFailureTask.loadRemittance =>
    'Gilbic could not load the remittance summary. Check your connection, then tap Retry.',
  CollectorFailureTask.submitRemittance =>
    'Gilbic could not confirm this remittance. Check your connection, then refresh the summary before trying again.',
};

String _conflictFor(CollectorFailureTask task) => switch (task) {
  CollectorFailureTask.loadRemittance ||
  CollectorFailureTask.submitRemittance =>
    'The remittance changed before submission. Refresh the summary, review the entries, then try again.',
  CollectorFailureTask.loadOtherAreaWork ||
  CollectorFailureTask.loadRoute ||
  CollectorFailureTask.recordCollection ||
  CollectorFailureTask.recordCombinedCollection ||
  CollectorFailureTask.correctCollection ||
  CollectorFailureTask.loadCorrectionHistory =>
    'This route changed after you opened it. Refresh the route, review the client, then try again.',
};
