import 'package:gilbic_mobile/src/core/management/management_no_collection.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ManagementNoCollectionPreview {
  const ManagementNoCollectionPreview({
    required this.loanId,
    required this.operationalVersion,
    required this.noCollectionDate,
    required this.paymentFrequency,
    required this.shifts,
  });

  final String loanId;
  final int operationalVersion;
  final DateTime noCollectionDate;
  final String paymentFrequency;
  final List<ManagementNoCollectionShift> shifts;

  factory ManagementNoCollectionPreview.fromPayload(Object? value) {
    final payload = stringMap(value);
    final rawShifts = payload['shifts'];
    if (rawShifts is! Iterable) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete No Collection preview data.',
        code: 'invalid_no_collection_preview',
      );
    }
    final loanId = firstNonEmptyString(<Object?>[payload['loan_id']]);
    final noCollectionDate = DateTime.tryParse(
      payload['no_collection_date']?.toString() ?? '',
    );
    final version = payload['operational_version'];
    final parsedVersion = version is int
        ? version
        : int.tryParse(version?.toString() ?? '');
    if (loanId == null || noCollectionDate == null || parsedVersion == null) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete No Collection preview data.',
        code: 'invalid_no_collection_preview',
      );
    }
    return ManagementNoCollectionPreview(
      loanId: loanId,
      operationalVersion: parsedVersion,
      noCollectionDate: DateTime(
        noCollectionDate.year,
        noCollectionDate.month,
        noCollectionDate.day,
      ),
      paymentFrequency: firstNonEmptyString(<Object?>[
            payload['payment_frequency'],
          ]) ??
          '',
      shifts: rawShifts
          .map(ManagementNoCollectionShift.fromPayload)
          .toList(growable: false),
    );
  }
}
