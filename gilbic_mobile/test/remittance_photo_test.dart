import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance_photo.dart';

void main() {
  test('detects JPEG PNG and WebP handover photos', () {
    expect(
      RemittancePhotoDraft.detectContentType(
        Uint8List.fromList(<int>[0xff, 0xd8, 0xff, 0xe0]),
      ),
      'image/jpeg',
    );
    expect(
      RemittancePhotoDraft.detectContentType(
        Uint8List.fromList(
          <int>[0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a],
        ),
      ),
      'image/png',
    );
    expect(
      RemittancePhotoDraft.detectContentType(
        Uint8List.fromList(
          <int>[
            0x52,
            0x49,
            0x46,
            0x46,
            0,
            0,
            0,
            0,
            0x57,
            0x45,
            0x42,
            0x50,
          ],
        ),
      ),
      'image/webp',
    );
  });

  test('rejects unsupported or oversized photo evidence', () {
    final unsupported = RemittancePhotoDraft.fromBytes(
      filename: 'proof.txt',
      bytes: Uint8List.fromList(<int>[1, 2, 3]),
    );
    final oversized = RemittancePhotoDraft(
      filename: 'proof.jpg',
      contentType: 'image/jpeg',
      bytes: Uint8List(5 * 1024 * 1024 + 1),
    );

    expect(unsupported.validate(), contains('JPEG, PNG, or WebP'));
    expect(oversized.validate(), contains('5 MB'));
  });
}
