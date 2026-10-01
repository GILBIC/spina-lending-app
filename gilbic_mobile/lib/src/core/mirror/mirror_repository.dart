import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class MirrorSession {
  const MirrorSession({
    required this.id,
    required this.state,
    required this.generation,
    required this.viewerUserId,
    required this.holderUserId,
    required this.viewerName,
    required this.holderName,
    required this.expiresAt,
    this.leaseExpiresAt,
  });
  final String id, state, viewerUserId, holderUserId, viewerName, holderName;
  final int generation;
  final DateTime expiresAt;
  final DateTime? leaseExpiresAt;
  bool get terminal => !['pending', 'active'].contains(state);
  factory MirrorSession.fromJson(Map<String, dynamic> value) {
    final state = value['state'] as String;
    final generation = value['generation'] as int;
    if (![
          'pending',
          'active',
          'stopped',
          'declined',
          'expired',
        ].contains(state) ||
        generation < 1) {
      throw const FormatException('Invalid sharing session');
    }
    return MirrorSession(
      id: value['id'] as String,
      state: state,
      generation: generation,
      viewerUserId: value['viewer_user_id'] as String,
      holderUserId: value['holder_user_id'] as String,
      viewerName: value['viewer_name'] as String,
      holderName: value['holder_name'] as String,
      expiresAt: DateTime.parse(value['expires_at'] as String),
      leaseExpiresAt: value['lease_expires_at'] == null
          ? null
          : DateTime.parse(value['lease_expires_at'] as String),
    );
  }
}

class MirrorTarget {
  const MirrorTarget({
    required this.userId,
    required this.deviceId,
    required this.name,
    required this.deviceName,
  });
  final String userId, deviceId, name, deviceName;
}

class MirrorFrame {
  MirrorFrame(this.bytes, this.generation, this.sequence);
  final Uint8List bytes;
  final int generation, sequence;
}

abstract interface class MirrorRepository {
  Future<List<MirrorTarget>> targets();
  Future<List<MirrorSession>> pending();
  Future<MirrorSession> request(MirrorTarget target);
  Future<MirrorSession> status(String id);
  Future<MirrorSession> action(MirrorSession session, String action);
  Future<void> publish(
    MirrorSession session,
    int sequence,
    Uint8List bytes, {
    required bool Function() stillCurrent,
  });
  Future<MirrorFrame?> frame(MirrorSession session);
  void close();
}

class SpinaMirrorRepository implements MirrorRepository {
  SpinaMirrorRepository({
    required this.session,
    required this.deviceId,
    http.Client? client,
  }) : _client = client ?? http.Client();
  final UserSession? Function() session;
  final Future<String> Function() deviceId;
  final http.Client _client;
  static const base = '/api/v1/screen-shares';
  Future<http.Response> _send(
    String method,
    String path, {
    Object? body,
    bool Function()? stillCurrent,
    Map<String, String> extra = const {},
  }) async {
    final current = session();
    if (current == null || current.isExpired) {
      throw const SpinaApiException('Sign in again.', statusCode: 401);
    }
    final device = await deviceId();
    if (!identical(current, session())) {
      throw const SpinaApiException('Session changed.', statusCode: 401);
    }
    final request = http.Request(method, ApiConfig.endpoint('$base$path'))
      ..headers.addAll({
        'Authorization': 'Bearer ${current.accessToken}',
        'X-Device-Id': device,
        'Accept': 'application/json',
        ...extra,
      });
    if (body is Uint8List) {
      request.bodyBytes = body;
    } else if (body != null) {
      request.headers['Content-Type'] = 'application/json';
      request.body = jsonEncode(body);
    }
    // Device resolution is asynchronous: Stop/navigation may have happened meanwhile.
    if (stillCurrent != null && !stillCurrent()) {
      throw const SpinaApiException('Screen sharing was cancelled.');
    }
    final stream = await _client
        .send(request)
        .timeout(const Duration(seconds: 8));
    final maximum = path.endsWith('/frame') ? 524288 : 1048576;
    final builder = BytesBuilder(copy: false);
    await for (final chunk in stream.stream.timeout(
      const Duration(seconds: 8),
    )) {
      if (builder.length + chunk.length > maximum) {
        throw const FormatException('Sharing response exceeds limit');
      }
      builder.add(chunk);
    }
    final response = http.Response.bytes(
      builder.takeBytes(),
      stream.statusCode,
      headers: stream.headers,
    );
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw SpinaApiException(
        'Screen sharing ended or is unavailable.',
        statusCode: response.statusCode,
      );
    }
    if (!response.headers['cache-control']
        .toString()
        .toLowerCase()
        .split(',')
        .map((s) => s.trim())
        .contains('no-store')) {
      throw const FormatException('Sharing response must not be cached');
    }
    return response;
  }

  Future<MirrorSession> _session(
    String method,
    String path, [
    Object? body,
  ]) async => MirrorSession.fromJson(
    decodeJsonObject((await _send(method, path, body: body)).body),
  );
  @override
  Future<List<MirrorTarget>> targets() async {
    final value = decodeJsonObject((await _send('GET', '/targets')).body);
    return (value['targets'] as List).map((item) {
      final target = stringMap(item);
      return MirrorTarget(
        userId: target['user_id'] as String,
        deviceId: target['device_id'] as String,
        name: target['display_name'] as String,
        deviceName: target['device_name'] as String,
      );
    }).toList();
  }

  @override
  Future<List<MirrorSession>> pending() async =>
      (decodeJsonObject((await _send('GET', '/pending')).body)['sessions']
              as List)
          .map((item) => MirrorSession.fromJson(stringMap(item)))
          .toList();
  @override
  Future<MirrorSession> request(MirrorTarget target) => _session('POST', '', {
    'holder_user_id': target.userId,
    'holder_device_id': target.deviceId,
  });
  @override
  Future<MirrorSession> status(String id) =>
      _session('GET', '/${Uri.encodeComponent(id)}');
  @override
  Future<MirrorSession> action(MirrorSession session, String action) {
    if (!['accept', 'decline', 'stop'].contains(action)) {
      throw ArgumentError('Invalid sharing action');
    }
    return _session('POST', '/${Uri.encodeComponent(session.id)}/$action', {
      'generation': session.generation,
    });
  }

  @override
  Future<void> publish(
    MirrorSession session,
    int sequence,
    Uint8List bytes, {
    required bool Function() stillCurrent,
  }) async {
    if (bytes.length > 524288) {
      throw const FormatException('Frame exceeds limit');
    }
    final response = await _send(
      'PUT',
      '/${Uri.encodeComponent(session.id)}/frame',
      body: bytes,
      stillCurrent: stillCurrent,
      extra: {
        'Content-Type': 'image/png',
        'X-Screen-Share-Generation': '${session.generation}',
        'X-Screen-Share-Sequence': '$sequence',
      },
    );
    if (response.statusCode != 204) {
      throw const FormatException('Invalid frame response');
    }
  }

  @override
  Future<MirrorFrame?> frame(MirrorSession session) async {
    final response = await _send(
      'GET',
      '/${Uri.encodeComponent(session.id)}/frame',
      extra: {'Accept': 'image/png'},
    );
    if (response.statusCode == 204) return null;
    final bytes = response.bodyBytes;
    final generation = int.tryParse(
      response.headers['x-screen-share-generation'] ?? '',
    );
    final sequence = int.tryParse(
      response.headers['x-screen-share-sequence'] ?? '',
    );
    final png = [137, 80, 78, 71, 13, 10, 26, 10];
    if (response.statusCode != 200 ||
        response.headers['content-type']?.split(';').first != 'image/png' ||
        bytes.length < 24 ||
        bytes.length > 524288 ||
        generation != session.generation ||
        sequence == null ||
        sequence < 1 ||
        List.generate(8, (i) => bytes[i] == png[i]).contains(false)) {
      throw const FormatException('Invalid shared frame');
    }
    final data = ByteData.sublistView(bytes);
    if (data.getUint32(16) < 1 ||
        data.getUint32(16) > 1024 ||
        data.getUint32(20) < 1 ||
        data.getUint32(20) > 1024) {
      throw const FormatException('Invalid shared dimensions');
    }
    return MirrorFrame(bytes, generation!, sequence);
  }

  @override
  void close() => _client.close();
}
