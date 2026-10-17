import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:royal_pro_flutter/services/article_service.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('ArticleDetail.fromJson', () {
    test('parses the backend detail payload and formats rich text', () {
      final article = ArticleDetail.fromJson({
        'id': 12,
        'title': 'A test article',
        'slug': 'a-test-article',
        'summary': '<p>A &amp; B</p>',
        'content': '<p>First paragraph.</p><p>Second<br>line.</p>',
        'category_name': 'Technology',
        'views_count': 7,
        'read_time_minutes': 3,
        'published_at': '2026-10-01T12:00:00Z',
      });

      expect(article.id, 12);
      expect(article.slug, 'a-test-article');
      expect(article.summary, 'A & B');
      expect(article.paragraphs, ['First paragraph.', 'Second', 'line.']);
      expect(article.categoryName, 'Technology');
      expect(article.viewsCount, 7);
      expect(article.publishedAt, DateTime.utc(2026, 10, 1, 12));
    });

    test('falls back to summary when backend content is empty', () {
      final article = ArticleDetail.fromJson({
        'id': 2,
        'title': 'Summary only',
        'summary': '<p>Readable summary</p>',
        'content': '',
      });

      expect(article.content, 'Readable summary');
      expect(article.paragraphs, ['Readable summary']);
    });
  });

  group('ArticleService.fetchArticleById', () {
    test('requests the existing numeric detail endpoint and caches the article',
        () async {
      late Uri requestedUri;
      final client = MockClient((request) async {
        requestedUri = request.url;
        expect(request.headers['accept'], 'application/json');
        return http.Response(
          jsonEncode({
            'id': 12,
            'title': 'API article',
            'slug': 'api-article',
            'summary': 'Short summary',
            'content': '<p>Full text</p>',
            'category_name': 'News',
          }),
          200,
        );
      });

      final article = await ArticleService.fetchArticleById(
        articleId: '12',
        baseUrl: 'https://api.example.test/',
        client: client,
      );

      expect(
          requestedUri.toString(), 'https://api.example.test/api/articles/12/');
      expect(article.title, 'API article');
      expect(article.content, 'Full text');
      expect(article.isOffline, isFalse);
      expect((await ArticleService.getCachedArticleDetail(12))?.title,
          'API article');
      client.close();
    });

    test('rejects invalid IDs before making a request', () async {
      final client = MockClient((_) async => http.Response('{}', 200));

      await expectLater(
        ArticleService.fetchArticleById(
          articleId: 'not-an-id',
          baseUrl: 'https://api.example.test',
          client: client,
        ),
        throwsA(isA<FormatException>()),
      );

      client.close();
    });

    test(
        'reports not-found responses instead of displaying a fabricated article',
        () async {
      final client = MockClient((_) async => http.Response('{}', 404));

      await expectLater(
        ArticleService.fetchArticleById(
          articleId: '404',
          baseUrl: 'https://api.example.test',
          client: client,
        ),
        throwsA(
          isA<HttpException>().having(
              (error) => error.message, 'message', 'Article not found.'),
        ),
      );

      client.close();
    });

    test('uses a previously fetched article when the network is unavailable',
        () async {
      final client =
          MockClient((_) async => throw const SocketException('offline'));
      final onlineClient = MockClient(
        (_) async => http.Response(
          jsonEncode({
            'id': 8,
            'title': 'Cached article',
            'summary': 'Summary',
            'content': '<p>Cached body</p>',
          }),
          200,
        ),
      );

      await ArticleService.fetchArticleById(
        articleId: '8',
        baseUrl: 'https://api.example.test',
        client: onlineClient,
      );
      final article = await ArticleService.fetchArticleById(
        articleId: '8',
        baseUrl: 'https://api.example.test',
        client: client,
      );

      expect(article.title, 'Cached article');
      expect(article.content, 'Cached body');
      expect(article.isOffline, isTrue);
      onlineClient.close();
      client.close();
    });

    test('rejects malformed JSON shapes and mismatched response IDs', () async {
      final malformedClient = MockClient((_) async => http.Response('[]', 200));
      await expectLater(
        ArticleService.fetchArticleById(
          articleId: '4',
          baseUrl: 'https://api.example.test',
          client: malformedClient,
        ),
        throwsA(isA<FormatException>()),
      );
      malformedClient.close();

      final mismatchClient = MockClient(
        (_) async =>
            http.Response(jsonEncode({'id': 5, 'title': 'Wrong article'}), 200),
      );
      await expectLater(
        ArticleService.fetchArticleById(
          articleId: '4',
          baseUrl: 'https://api.example.test',
          client: mismatchClient,
        ),
        throwsA(isA<FormatException>()),
      );
      mismatchClient.close();
    });
  });
}
