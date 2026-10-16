import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

class AuthService {
  static const FlutterSecureStorage _storage = FlutterSecureStorage();
  static const String _tokenKey = 'auth_token';

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
      if (activeToken != null && activeToken.isNotEmpty) 'Authorization': 'Token $activeToken',
    };
  }

  static Future<Map<String, dynamic>> login({
    required String username,
    required String password,
    required String baseUrl,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/login/'),
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: jsonEncode({
        'username': username,
        'password': password,
      }),
    );

    final decoded = jsonDecode(response.body);

    if (response.statusCode == 200 && decoded is Map && decoded['token'] != null) {
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
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/register/'),
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: jsonEncode({
        'username': username,
        'email': email,
        'password': password,
        'password2': password,
      }),
    );

    final decoded = jsonDecode(response.body);

    if (response.statusCode == 201 && decoded is Map && decoded['token'] != null) {
      return decoded as Map<String, dynamic>;
    }

    if (decoded is Map && decoded['errors'] != null) {
      throw Exception(decoded['errors'].toString());
    }

    throw Exception('Registration failed');
  }

  static Future<Map<String, dynamic>> fetchProfile({required String baseUrl}) async {
    final headers = await authHeaders();
    final response = await http.get(
      Uri.parse('$baseUrl/api/me/'),
      headers: headers,
    );

    if (response.statusCode != 200) {
      throw Exception('Unable to fetch user profile');
    }

    return jsonDecode(response.body) as Map<String, dynamic>;
  }
}
