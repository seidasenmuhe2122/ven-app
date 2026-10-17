import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:royal_pro_flutter/services/bookmark_service.dart';
import 'package:royal_pro_flutter/services/deep_link_service.dart';
import 'package:royal_pro_flutter/services/reading_history_service.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('DeepLinkService', () {
    test('extracts numeric article IDs from supported paths', () {
      expect(
        DeepLinkService.extractArticleIdFromUri(
            Uri.parse('https://news.example/article/123')),
        '123',
      );
      expect(
        DeepLinkService.extractArticleIdFromUri(
            Uri.parse('https://news.example/articles/456/')),
        '456',
      );
    });

    test('rejects missing or nonnumeric article IDs', () {
      expect(DeepLinkService.extractArticleIdFromUri(null), isNull);
      expect(
        DeepLinkService.extractArticleIdFromUri(
            Uri.parse('https://news.example/article/latest')),
        isNull,
      );
      expect(
        DeepLinkService.extractArticleIdFromUri(
            Uri.parse('https://news.example/')),
        isNull,
      );
    });

    test('builds a normalized article URL', () {
      expect(
        DeepLinkService.buildArticleUrl(
          articleId: '42',
          baseUrl: 'https://news.example///',
        ),
        'https://news.example/article/42',
      );
    });
  });

  group('BookmarkService', () {
    test('toggles a saved article and returns most recent first', () async {
      await BookmarkService.toggleBookmark(
        articleId: 1,
        title: 'First',
        summary: 'Summary',
      );
      await BookmarkService.toggleBookmark(
        articleId: 2,
        title: 'Second',
        summary: 'Summary',
      );

      final bookmarks = await BookmarkService.getBookmarks();
      expect(bookmarks.map((item) => item.id), [2, 1]);
      expect(await BookmarkService.getBookmarkedIds(), {1, 2});

      await BookmarkService.toggleBookmark(
        articleId: 1,
        title: 'First',
        summary: 'Summary',
      );
      expect(await BookmarkService.getBookmarkedIds(), {2});
    });
  });

  group('ReadingHistoryService', () {
    test('updates an existing item and retains only the six newest articles',
        () async {
      for (var id = 1; id <= 7; id++) {
        await ReadingHistoryService.saveReadArticle(
          articleId: '$id',
          title: 'Article $id',
          summary: 'A short article summary.',
        );
      }
      await ReadingHistoryService.saveReadArticle(
        articleId: '3',
        title: 'Updated Article 3',
        summary: 'Updated summary.',
      );

      final history = await ReadingHistoryService.getRecentArticles();
      expect(history, hasLength(6));
      expect(history.first.articleId, '3');
      expect(history.first.title, 'Updated Article 3');
      expect(history.map((item) => item.articleId), isNot(contains('1')));
    });
  });
}
