import 'dart:async';
import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

class AuthService {
  static const FlutterSecureStorage _storage = FlutterSecureStorage();
  static const String _tokenKey = 'auth_token';
  static const Duration _requestTimeout = Duration(seconds: 15);
  static const Map<String, String> _jsonHeaders = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
  };

  static Future<void> saveToken(String token) async {
    await _storage.write(key: _tokenKey, value: token);
  }

  static Future<String?> getToken() async {
    return _storage.read(key: _tokenKey);
  }

  static Future<void> clearToken() async {
    await _storage.delete(key: _tokenKey);
  }

  static Future<Map<String, String>> authHeaders({String? token}) async {
    final activeToken = token ?? await getToken();
    return {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
      if (activeToken != null && activeToken.isNotEmpty)
        'Authorization': 'Token $activeToken',
    };
  }

  static Future<http.Response> _postJson({
    required Uri uri,
    required Map<String, dynamic> body,
    http.Client? client,
  }) {
    final encodedBody = jsonEncode(body);
    final request = client == null
        ? http.post(uri, headers: _jsonHeaders, body: encodedBody)
        : client.post(uri, headers: _jsonHeaders, body: encodedBody);
    return request.timeout(_requestTimeout);
  }

  static Future<Map<String, dynamic>> login({
    required String username,
    required String password,
    required String baseUrl,
    http.Client? client,
  }) async {
    final response = await _postJson(
      uri: Uri.parse('$baseUrl/api/login/'),
      body: {
        'username': username,
        'password': password,
      },
      client: client,
    );

    final decoded = jsonDecode(response.body);

    if (response.statusCode == 200 &&
        decoded is Map &&
        decoded['token'] != null) {
      return decoded as Map<String, dynamic>;
    }

    throw Exception(
      decoded is Map
          ? (decoded['non_field_errors'] ?? decoded['detail'] ?? 'Login failed')
          : 'Login failed',
    );
  }

  static Future<Map<String, dynamic>> register({
    required String username,
    required String email,
    required String password,
    required String baseUrl,
    http.Client? client,
  }) async {
    final response = await _postJson(
      uri: Uri.parse('$baseUrl/api/register/'),
      body: {
        'username': username,
        'email': email,
        'password': password,
        'password2': password,
      },
      client: client,
    );

    final decoded = jsonDecode(response.body);

    if (response.statusCode == 201 &&
        decoded is Map &&
        decoded['token'] != null) {
      return decoded as Map<String, dynamic>;
    }

    if (decoded is Map && decoded['errors'] != null) {
      throw Exception(decoded['errors'].toString());
    }

    throw Exception('Registration failed');
  }

  static Future<Map<String, dynamic>> fetchProfile({
    required String baseUrl,
    String? token,
    http.Client? client,
  }) async {
    final headers = await authHeaders(token: token);
    final uri = Uri.parse('$baseUrl/api/me/');
    final request = client == null
        ? http.get(uri, headers: headers)
        : client.get(uri, headers: headers);
    final response = await request.timeout(_requestTimeout);

    if (response.statusCode != 200) {
      throw Exception('Unable to fetch user profile');
    }

    return jsonDecode(response.body) as Map<String, dynamic>;
  }
}
