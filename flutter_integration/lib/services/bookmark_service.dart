import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

class BookmarkedArticle {
  const BookmarkedArticle({
    required this.id,
    required this.title,
    required this.summary,
    required this.categoryName,
    required this.savedAt,
  });

  final int id;
  final String title;
  final String summary;
  final String categoryName;
  final DateTime savedAt;

  Map<String, dynamic> toJson() => {
        'id': id,
        'title': title,
        'summary': summary,
        'categoryName': categoryName,
        'savedAt': savedAt.toIso8601String(),
      };

  factory BookmarkedArticle.fromJson(Map<String, dynamic> json) {
    return BookmarkedArticle(
      id: json['id'] is int ? json['id'] as int : int.tryParse('${json['id']}') ?? 0,
      title: (json['title'] ?? 'Untitled article').toString(),
      summary: (json['summary'] ?? '').toString(),
      categoryName: (json['categoryName'] ?? 'General').toString(),
      savedAt: DateTime.tryParse((json['savedAt'] ?? DateTime.now().toIso8601String()).toString()) ?? DateTime.now(),
    );
  }
}

class BookmarkService {
  static const String _key = 'saved_articles';

  static Future<List<BookmarkedArticle>> getBookmarks() async {
    final prefs = await SharedPreferences.getInstance();
    final list = prefs.getStringList(_key) ?? const <String>[];

    return list
        .map((item) => BookmarkedArticle.fromJson(jsonDecode(item)))
        .toList()
      ..sort((a, b) => b.savedAt.compareTo(a.savedAt));
  }

  static Future<Set<int>> getBookmarkedIds() async {
    final bookmarks = await getBookmarks();
    return bookmarks.map((item) => item.id).toSet();
  }

  static Future<bool> isBookmarked(int articleId) async {
    final ids = await getBookmarkedIds();
    return ids.contains(articleId);
  }

  static Future<void> toggleBookmark({
    required int articleId,
    required String title,
    required String summary,
    String categoryName = 'General',
  }) async {
    final prefs = await SharedPreferences.getInstance();
    final existing = await getBookmarks();
    final updated = existing.where((item) => item.id != articleId).toList();

    if (updated.length == existing.length) {
      updated.add(
        BookmarkedArticle(
          id: articleId,
          title: title,
          summary: summary,
          categoryName: categoryName,
          savedAt: DateTime.now(),
        ),
      );
    }

    final jsonList = updated.map((item) => jsonEncode(item.toJson())).toList();
    await prefs.setStringList(_key, jsonList);
  }

  static Future<void> removeBookmark(int articleId) async {
    final prefs = await SharedPreferences.getInstance();
    final existing = await getBookmarks();
    final updated = existing.where((item) => item.id != articleId).toList();
    final jsonList = updated.map((item) => jsonEncode(item.toJson())).toList();
    await prefs.setStringList(_key, jsonList);
  }
}
