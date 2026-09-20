import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/network/staff_operations_client.dart';
import 'package:http/http.dart' as http;

const areaPermissions = [
  'area.manage',
  'area.collector.assign',
  'area.client.assign',
  'area.retire',
];

class AreaNode {
  AreaNode.fromJson(Map<String, dynamic> data)
    : id = requiredStaffText(data, 'area_id'),
      name = requiredStaffText(data, 'name'),
      path = requiredStaffText(data, 'full_path'),
      parentId = data['parent_area_id'] as String?,
      active = data['is_active'] == true,
      legacy = data['is_legacy_unmapped'] == true,
      depth = (data['depth'] as num?)?.toInt() ?? 0,
      sortOrder = (data['sort_order'] as num?)?.toInt() ?? 0,
      clients = (data['subtree_client_count'] as num?)?.toInt() ?? 0,
      explicitCollector = firstNonEmptyString([
        stringMap(data['explicit_collector'])['full_name'],
      ]),
      effectiveCollector = firstNonEmptyString([
        stringMap(data['effective_collector'])['full_name'],
      ]);
  final String id, name, path;
  final String? parentId, explicitCollector, effectiveCollector;
  final bool active, legacy;
  final int depth, sortOrder, clients;
}

class AreaRepository {
  AreaRepository({
    required DeviceIdentityProvider deviceIdentityProvider,
    http.Client? client,
  }) : _api = StaffOperationsClient(
         deviceIdentityProvider: deviceIdentityProvider,
         client: client,
       );
  final StaffOperationsClient _api;
  void close() => _api.close();

  Future<List<AreaNode>> tree(UserSession session) async {
    requireStaffPermission(session, areaPermissions);
    final data = await _api.request(
      session,
      'GET',
      '/api/v1/areas',
      query: {'include_inactive': 'true'},
    );
    return staffRecords(
      data,
      'areas',
    ).map(AreaNode.fromJson).toList(growable: false);
  }

  Future<List<Map<String, dynamic>>> collectors(UserSession s) async {
    requireStaffPermission(s, ['area.collector.assign']);
    return staffRecords(
      await _api.request(s, 'GET', '/api/v1/areas/collectors'),
      'collectors',
    );
  }

  Future<List<Map<String, dynamic>>> clients(
    UserSession s,
    String query,
  ) async {
    requireStaffPermission(s, ['area.client.assign']);
    return staffRecords(
      await _api.request(
        s,
        'GET',
        '/api/v1/areas/clients',
        query: {'q': query, 'limit': '100'},
      ),
      'clients',
    );
  }

  Future<Map<String, dynamic>> _manage(
    UserSession s,
    String method,
    String path, {
    Map<String, Object?>? body,
    Map<String, String>? query,
  }) {
    requireStaffPermission(s, ['area.manage']);
    return _api.request(s, method, path, body: body, query: query);
  }

  Future<Map<String, dynamic>> create(
    UserSession s,
    String name,
    String? parent,
  ) => _manage(
    s,
    'POST',
    '/api/v1/areas',
    body: {'name': name, 'parent_area_id': parent},
  );
  Future<Map<String, dynamic>> rename(UserSession s, String id, String name) =>
      _manage(s, 'PATCH', '/api/v1/areas/$id', body: {'name': name});
  Future<Map<String, dynamic>> movePreview(
    UserSession s,
    String id,
    String? parent,
  ) => _manage(
    s,
    'GET',
    '/api/v1/areas/$id/move-preview',
    query: parent == null ? {} : {'new_parent_area_id': parent},
  );
  Future<Map<String, dynamic>> move(UserSession s, String id, String? parent) =>
      _manage(
        s,
        'POST',
        '/api/v1/areas/$id/move',
        body: {'new_parent_area_id': parent},
      );
  Future<Map<String, dynamic>> reorder(
    UserSession s,
    String? parent,
    List<String> ids,
  ) => _manage(
    s,
    'POST',
    '/api/v1/areas/reorder',
    body: {'parent_area_id': parent, 'ordered_area_ids': ids},
  );
  Future<Map<String, dynamic>> assignCollector(
    UserSession s,
    String id,
    String collector,
  ) {
    requireStaffPermission(s, ['area.collector.assign']);
    return _api.request(
      s,
      'PUT',
      '/api/v1/areas/$id/collector',
      body: {'collector_user_id': collector},
    );
  }

  Future<Map<String, dynamic>> removeCollector(UserSession s, String id) {
    requireStaffPermission(s, ['area.collector.assign']);
    return _api.request(s, 'DELETE', '/api/v1/areas/$id/collector');
  }

  Future<Map<String, dynamic>> transferPreview(
    UserSession s,
    String client,
    String area,
  ) {
    requireStaffPermission(s, ['area.client.assign']);
    return _api.request(
      s,
      'GET',
      '/api/v1/clients/$client/area-transfer-preview',
      query: {'target_area_id': area},
    );
  }

  Future<Map<String, dynamic>> transfer(
    UserSession s,
    String client,
    String area,
  ) {
    requireStaffPermission(s, ['area.client.assign']);
    return _api.request(
      s,
      'POST',
      '/api/v1/clients/$client/area-transfer',
      body: {'target_area_id': area},
    );
  }

  Future<Map<String, dynamic>> _retirement(
    UserSession s,
    String id,
    String action,
  ) {
    requireStaffPermission(s, ['area.retire'], managementOnly: true);
    return _api.request(
      s,
      action == 'retirement-preview' ? 'GET' : 'POST',
      '/api/v1/areas/$id/$action',
    );
  }

  Future<Map<String, dynamic>> retirementPreview(UserSession s, String id) =>
      _retirement(s, id, 'retirement-preview');
  Future<Map<String, dynamic>> retire(UserSession s, String id) =>
      _retirement(s, id, 'retire');
  Future<Map<String, dynamic>> reactivate(UserSession s, String id) =>
      _retirement(s, id, 'reactivate');
}
