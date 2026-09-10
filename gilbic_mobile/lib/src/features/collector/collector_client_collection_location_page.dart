import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_collection_location.dart';
import 'package:gilbic_mobile/src/core/collector/collector_collection_location_repository.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_grouping.dart';

class CollectorClientCollectionLocationPage extends StatefulWidget {
  const CollectorClientCollectionLocationPage({
    required this.session,
    required this.client,
    this.repository,
    super.key,
  });

  final UserSession session;
  final CollectorRouteClientGroup client;
  final CollectorCollectionLocationRepository? repository;

  @override
  State<CollectorClientCollectionLocationPage> createState() =>
      _CollectorClientCollectionLocationPageState();
}

class _CollectorClientCollectionLocationPageState
    extends State<CollectorClientCollectionLocationPage> {
  late final CollectorCollectionLocationRepository _repository;
  CollectorCollectionLocation? _location;
  Object? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _repository =
        widget.repository ?? SpinaCollectorCollectionLocationRepository();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final location = await _repository.fetchCollectionLocation(
        widget.session,
        clientId: widget.client.clientId,
      );
      if (mounted) {
        setState(() => _location = location);
      }
    } on Object catch (error) {
      if (mounted) {
        setState(() => _error = error);
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: const Key('collector-client-collection-location-page'),
      appBar: AppBar(title: const Text('Collection Location')),
      body: SafeArea(child: _buildBody(context)),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (_loading && _location == null) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null && _location == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.cloud_off_outlined, size: 42),
              const SizedBox(height: 10),
              const Text(
                'The Collection Location could not be loaded. Check the connection and try again.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 14),
              FilledButton.icon(
                onPressed: _load,
                icon: const Icon(Icons.refresh),
                label: const Text('Try again'),
              ),
            ],
          ),
        ),
      );
    }

    final location = _location!;
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 14, 16, 24),
        children: [
          Text(
            widget.client.clientName,
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 6),
          const Row(
            children: [
              Icon(Icons.lock_outline, size: 18),
              SizedBox(width: 7),
              Expanded(
                child: Text('Read-only • route detail comes from the SPINA server.'),
              ),
            ],
          ),
          const SizedBox(height: 14),
          if (location.isVerified)
            _VerifiedLocationCard(location: location)
          else
            const Card(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Not verified',
                      style: TextStyle(fontWeight: FontWeight.w900),
                    ),
                    SizedBox(height: 6),
                    Text(
                      'No verified collection location is available for this Client.',
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _VerifiedLocationCard extends StatelessWidget {
  const _VerifiedLocationCard({required this.location});

  final CollectorCollectionLocation location;

  @override
  Widget build(BuildContext context) {
    final photoUrl = location.photoUrl?.trim();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Verified',
              style: TextStyle(fontWeight: FontWeight.w900),
            ),
            if (location.displayAddress != null) ...[
              const SizedBox(height: 10),
              Text(location.displayAddress!),
            ],
            if (location.landmark != null) ...[
              const SizedBox(height: 6),
              Text(location.landmark!),
            ],
            if (location.verifiedAt != null) ...[
              const SizedBox(height: 6),
              Text('Verified at: ${_date(location.verifiedAt!)}'),
            ],
            if (photoUrl != null && photoUrl.isNotEmpty) ...[
              const SizedBox(height: 12),
              ClipRRect(
                borderRadius: BorderRadius.circular(10),
                child: Image.network(
                  photoUrl,
                  key: const Key('collector-collection-location-photo'),
                  height: 180,
                  width: double.infinity,
                  fit: BoxFit.cover,
                  errorBuilder: (context, error, stackTrace) => Container(
                    height: 120,
                    alignment: Alignment.center,
                    child: const Icon(Icons.photo_outlined, size: 42),
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

String _date(DateTime value) {
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}
