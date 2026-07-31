class ApiConfig {
  const ApiConfig._();

  static const String baseUrl = String.fromEnvironment(
    'GILBIC_API_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );

  static Uri endpoint(String path) {
    final normalizedPath = path.startsWith('/') ? path : '/$path';
    return Uri.parse('$baseUrl$normalizedPath');
  }
}
