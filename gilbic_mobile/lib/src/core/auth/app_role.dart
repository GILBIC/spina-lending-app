enum AppRole {
  client('Client'),
  collector('Collector'),
  employee('Employee'),
  management('Management');

  const AppRole(this.label);

  final String label;

  static AppRole? fromValue(String value) {
    final normalized = value
        .trim()
        .toLowerCase()
        .replaceAll('-', ' ')
        .replaceAll('_', ' ')
        .replaceAll(RegExp(r'\s+'), ' ');

    if (normalized == 'client' || normalized == 'borrower') {
      return AppRole.client;
    }
    if (normalized == 'collector' || normalized == 'field collector') {
      return AppRole.collector;
    }
    if (<String>{
      'employee',
      'office staff',
      'encoder',
      'viewer',
      'auditor',
      'staff',
    }.contains(normalized)) {
      return AppRole.employee;
    }
    if (<String>{
      'management',
      'manager',
      'supervisor',
      'admin',
      'administrator',
      'system',
      'system admin',
    }.contains(normalized)) {
      return AppRole.management;
    }
    return null;
  }
}
