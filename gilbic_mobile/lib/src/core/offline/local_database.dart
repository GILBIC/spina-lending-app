class PendingSyncItem {
  const PendingSyncItem({
    required this.id,
    required this.type,
    required this.payload,
    required this.createdAt,
  });

  final String id;
  final String type;
  final Map<String, Object?> payload;
  final DateTime createdAt;
}

abstract interface class LocalDatabase {
  Future<void> initialize();

  Future<void> enqueue(PendingSyncItem item);

  Future<List<PendingSyncItem>> pendingItems();

  Future<void> remove(String id);
}

class MemoryLocalDatabase implements LocalDatabase {
  final List<PendingSyncItem> _items = <PendingSyncItem>[];

  @override
  Future<void> enqueue(PendingSyncItem item) async {
    if (_items.any((existing) => existing.id == item.id)) {
      return;
    }
    _items.add(item);
  }

  @override
  Future<void> initialize() async {}

  @override
  Future<List<PendingSyncItem>> pendingItems() async {
    return List<PendingSyncItem>.unmodifiable(_items);
  }

  @override
  Future<void> remove(String id) async {
    _items.removeWhere((item) => item.id == id);
  }
}
