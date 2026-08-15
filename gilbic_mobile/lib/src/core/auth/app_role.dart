enum AppRole {
  client('Client'),
  collector('Collector'),
  employee('Employee'),
  management('Management');

  const AppRole(this.label);

  final String label;

  static AppRole? fromValue(String value) {
    final normalized = value.trim().toLowerCase();
    return switch (normalized) {
      'client' => AppRole.client,
      'collector' => AppRole.collector,
      'employee' => AppRole.employee,
      'management' => AppRole.management,
      _ => null,
    };
  }
}
