import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:royal_pro_flutter/services/auth_service.dart';

void main() {
  group('AuthService', () {
    test('posts the exact login password to the existing endpoint', () async {
      late Uri requestedUri;
      late Map<String, dynamic> sentBody;
      final client = MockClient((request) async {
        requestedUri = request.url;
        sentBody = jsonDecode(request.body) as Map<String, dynamic>;
        return http.Response(jsonEncode({'token': 'test-token'}), 200);
      });

      final result = await AuthService.login(
        username: 'reader',
        password: '  valid password  ',
        baseUrl: 'https://api.example.test',
        client: client,
      );

      expect(requestedUri.path, '/api/login/');
      expect(sentBody['password'], '  valid password  ');
      expect(result['token'], 'test-token');
      client.close();
    });

    test('sends the existing registration payload and handles rejection',
        () async {
      late Map<String, dynamic> sentBody;
      final client = MockClient((request) async {
        sentBody = jsonDecode(request.body) as Map<String, dynamic>;
        return http.Response(
          jsonEncode({
            'errors': {
              'username': ['Already in use']
            }
          }),
          400,
        );
      });

      await expectLater(
        AuthService.register(
          username: 'reader',
          email: 'reader@example.test',
          password: 'a secure test password',
          baseUrl: 'https://api.example.test',
          client: client,
        ),
        throwsA(isA<Exception>()),
      );

      expect(sentBody['password'], 'a secure test password');
      expect(sentBody['password2'], sentBody['password']);
      client.close();
    });

    test('uses a supplied token without reading platform storage', () async {
      expect(
        await AuthService.authHeaders(token: 'private-token'),
        containsPair('Authorization', 'Token private-token'),
      );
    });
  });
}
