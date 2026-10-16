import 'package:flutter/foundation.dart';

class AppConfig {
  static const String _apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8000',
  );

  static String get apiBaseUrl {
    final uri = Uri.tryParse(_apiBaseUrl);
    if (uri == null || !uri.hasAuthority || !{'http', 'https'}.contains(uri.scheme)) {
      throw StateError('API_BASE_URL must be an absolute HTTP(S) URL.');
    }
    if (kReleaseMode && uri.scheme != 'https') {
      throw StateError('API_BASE_URL must use HTTPS in release builds.');
    }
    return _apiBaseUrl;
  }
}
