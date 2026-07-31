enum AppRole {
  client('Client'),
  collector('Collector'),
  employee('Employee'),
  management('Management');

  const AppRole(this.label);

  final String label;

  static AppRole? fromValue(String value) {
    final normalized = value.trim().toLowerCase();
    for (final role in AppRole.values) {
      if (role.name == normalized || role.label.toLowerCase() == normalized) {
        return role;
      }
    }
    return null;
  }
}
