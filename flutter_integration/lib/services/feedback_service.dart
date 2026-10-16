import 'dart:convert';

import 'package:http/http.dart' as http;

class FeedbackService {
  static Future<void> submit({
    required String baseUrl,
    required String name,
    required String email,
    required String category,
    required String message,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/feedback/'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'name': name,
        'email': email,
        'category': category,
        'message': message,
      }),
    );

    if (response.statusCode != 201) {
      final data = jsonDecode(response.body);
      throw Exception(data['errors']?['message'] ?? 'Unable to send feedback right now.');
    }
  }
}
