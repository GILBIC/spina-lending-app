import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/client_registration_review_repository.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test(
    'loads registrations and candidates from canonical Management routes',
    () async {
      final requests = <http.Request>[];
      final repository = SpinaClientRegistrationReviewRepository(
        client: MockClient((request) async {
          requests.add(request);
          return _success(
            request.url.path.endsWith('client-link-candidates')
                ? <String, Object?>{'clients': <Object?>[]}
                : <String, Object?>{'registrations': <Object?>[]},
          );
        }),
      );

      expect(
        await repository.loadPending(_session, deviceId: 'approved-device'),
        isEmpty,
      );
      expect(
        await repository.searchCandidates(
          _session,
          deviceId: 'approved-device',
          query: '  Maria Santos  ',
        ),
        isEmpty,
      );

      expect(requests, hasLength(2));
      expect(requests[0].method, 'GET');
      expect(requests[0].url.path, '/api/v1/management/client-registrations');
      expect(requests[0].url.query, isEmpty);
      expect(requests[1].method, 'GET');
      expect(requests[1].url.path, '/api/v1/management/client-link-candidates');
      expect(requests[1].url.queryParameters, <String, String>{
        'q': 'Maria Santos',
      });
      for (final request in requests) {
        expect(request.url.path, isNot(startsWith('/api/mobile/')));
        expect(request.headers['Authorization'], 'Bearer access-token');
        expect(request.headers['X-Device-Id'], 'approved-device');
      }
    },
  );

  test(
    'approves and rejects through canonical Management action routes',
    () async {
      final requests = <http.Request>[];
      final repository = SpinaClientRegistrationReviewRepository(
        client: MockClient((request) async {
          requests.add(request);
          return _success(const <String, Object?>{});
        }),
      );

      await repository.approve(
        _session,
        deviceId: 'approved-device',
        userId: 'registration-user',
        clientId: 'client-42',
        reviewNote: '  Identity verified  ',
      );
      await repository.reject(
        _session,
        deviceId: 'approved-device',
        userId: 'rejected-user',
        reviewNote: '  Duplicate registration  ',
      );

      expect(requests, hasLength(2));
      expect(requests[0].method, 'POST');
      expect(
        requests[0].url.path,
        '/api/v1/management/client-registrations/registration-user/approve',
      );
      expect(jsonDecode(requests[0].body), <String, Object?>{
        'client_id': 'client-42',
        'review_note': 'Identity verified',
      });
      expect(requests[1].method, 'POST');
      expect(
        requests[1].url.path,
        '/api/v1/management/client-registrations/rejected-user/reject',
      );
      expect(jsonDecode(requests[1].body), <String, Object?>{
        'review_note': 'Duplicate registration',
      });
      for (final request in requests) {
        expect(request.url.path, isNot(startsWith('/api/mobile/')));
        expect(request.headers['Authorization'], 'Bearer access-token');
        expect(request.headers['X-Device-Id'], 'approved-device');
      }
    },
  );
}

const _session = UserSession(
  userId: 'management-user',
  username: 'management.one',
  displayName: 'Management One',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'access-token',
  permissions: <String>['client.registration.approve'],
);

http.Response _success(Map<String, Object?> data) => http.Response(
  jsonEncode(<String, Object?>{'success': true, 'data': data}),
  200,
  headers: const <String, String>{'content-type': 'application/json'},
);
