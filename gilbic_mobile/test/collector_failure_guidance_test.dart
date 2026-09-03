import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/collector/collector_failure_guidance.dart';

void main() {
  test('revoked-device guidance tells the Collector what to do next', () {
    const error = SpinaApiException(
      'This device has been revoked.',
      statusCode: 403,
    );

    expect(
      collectorFailureMessage(error, task: CollectorFailureTask.loadRoute),
      'This device is no longer approved. Ask Management to approve this device, then sign in again.',
    );
  });

  test('stale-route guidance requires refresh and review', () {
    const error = SpinaApiException(
      'Internal route revision conflict.',
      statusCode: 409,
      code: 'route_revision_changed',
    );

    expect(
      collectorFailureMessage(
        error,
        task: CollectorFailureTask.recordCollection,
      ),
      'This route changed after you opened it. Refresh the route, review the client, then try again.',
    );
  });

  test('possible duplicate guidance sends the Collector to the receipt', () {
    const error = SpinaApiException(
      'Unable-to-pay was already recorded for this client.',
      statusCode: 409,
      code: 'pass_already_recorded',
    );

    expect(
      collectorFailureMessage(
        error,
        task: CollectorFailureTask.recordCollection,
      ),
      "This collection may already be recorded. Refresh the route and check today's receipt before trying again.",
    );
  });

  test('technical route-load errors are not shown to the Collector', () {
    expect(
      collectorFailureMessage(
        StateError('SocketException: connection refused at 10.0.2.2'),
        task: CollectorFailureTask.loadRoute,
      ),
      "Gilbic could not load today's route. Check your connection, then tap Try again.",
    );
  });

  test('safe validation guidance remains specific', () {
    const error = SpinaApiException(
      'Choose a Past Due reason.',
      statusCode: 422,
      code: 'past_due_reason_required',
    );

    expect(
      collectorFailureMessage(
        error,
        task: CollectorFailureTask.recordCollection,
      ),
      'Choose a Past Due reason.',
    );
  });

  test('technical correction failure gives safe recovery guidance', () {
    expect(
      collectorFailureMessage(
        StateError('database host 10.0.2.2 did not respond'),
        task: CollectorFailureTask.correctCollection,
      ),
      "Gilbic could not save this correction. Refresh the route, check today's entry, then try again.",
    );
  });

  test('technical correction-history failure does not expose internals', () {
    expect(
      collectorFailureMessage(
        StateError('SocketException: connection refused at 10.0.2.2'),
        task: CollectorFailureTask.loadCorrectionHistory,
      ),
      'Gilbic could not load correction history. Check your connection, then tap Retry.',
    );
  });

  test('other-area load failure gives a safe retry action', () {
    expect(
      collectorFailureMessage(
        StateError('SocketException: connection refused at 10.0.2.2'),
        task: CollectorFailureTask.loadOtherAreaWork,
      ),
      'Gilbic could not load other-area work. Check your connection, then tap Retry.',
    );
  });

  test('changed remittance tells the Collector to refresh the summary', () {
    const error = SpinaApiException(
      'Internal remittance preview conflict.',
      statusCode: 409,
      code: 'remittance_preview_changed',
    );

    expect(
      collectorFailureMessage(
        error,
        task: CollectorFailureTask.submitRemittance,
      ),
      'The remittance changed before submission. Refresh the summary, review the entries, then try again.',
    );
  });
}
