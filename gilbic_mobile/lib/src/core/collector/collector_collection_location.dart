import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class CollectorCollectionLocation {
  const CollectorCollectionLocation({
    required this.clientId,
    required this.collectionLocationStatus,
    required this.displayAddress,
    required this.landmark,
    required this.photoUrl,
    required this.verifiedAt,
  });

  final String clientId;
  final String collectionLocationStatus;
  final String? displayAddress;
  final String? landmark;
  final String? photoUrl;
  final DateTime? verifiedAt;

  bool get isVerified => collectionLocationStatus == 'verified';

  static CollectorCollectionLocation fromPayload(Object? value) {
    final data = stringMap(value);
    final rawStatus = firstNonEmptyString(
      <Object?>[data['collection_location_status']],
    );
    final status = rawStatus?.trim().toLowerCase() == 'verified'
        ? 'verified'
        : 'not_verified';
    final verified = status == 'verified';

    return CollectorCollectionLocation(
      clientId: firstNonEmptyString(<Object?>[data['client_id']]) ?? '',
      collectionLocationStatus: status,
      displayAddress: verified
          ? firstNonEmptyString(<Object?>[data['display_address']])
          : null,
      landmark: verified
          ? firstNonEmptyString(<Object?>[data['landmark']])
          : null,
      photoUrl: verified
          ? firstNonEmptyString(<Object?>[data['photo_url']])
          : null,
      verifiedAt: verified ? _dateTime(data['verified_at']) : null,
    );
  }
}

DateTime? _dateTime(Object? value) {
  final text = firstNonEmptyString(<Object?>[value]);
  return text == null ? null : DateTime.tryParse(text);
}
