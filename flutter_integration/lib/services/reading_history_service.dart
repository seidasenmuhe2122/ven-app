import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

class ReadingHistoryItem {
  const ReadingHistoryItem({
    required this.articleId,
    required this.title,
    required this.summary,
    required this.savedAt,
    required this.readMinutes,
  });

  final String articleId;
  final String title;
  final String summary;
  final int savedAt;
  final int readMinutes;

  factory ReadingHistoryItem.fromJson(Map<String, dynamic> json) {
    return ReadingHistoryItem(
      articleId: json['articleId'] ?? '',
      title: json['title'] ?? 'Article',
      summary: json['summary'] ?? '',
      savedAt: json['savedAt'] ?? 0,
      readMinutes: json['readMinutes'] ?? 1,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'articleId': articleId,
      'title': title,
      'summary': summary,
      'savedAt': savedAt,
      'readMinutes': readMinutes,
    };
  }
}

class ReadingHistoryService {
  static const String _key = 'recently_read_articles';

  static int estimateReadTime(String content) {
    final wordCount = RegExp(r'\S+').allMatches(content).length;
    if (wordCount <= 0) return 1;
    return (wordCount / 200).ceil();
  }

  static Future<void> saveReadArticle({
    required String articleId,
    required String title,
    required String summary,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    final history = await getRecentArticles();

    final item = ReadingHistoryItem(
      articleId: articleId,
      title: title,
      summary: summary,
      savedAt: DateTime.now().millisecondsSinceEpoch,
      readMinutes: estimateReadTime(summary),
    );

    final updated = history
        .where((entry) => entry.articleId != articleId)
        .toList()
      ..insert(0, item);

    final trimmed = updated.take(6).toList();
    final encoded = trimmed.map((entry) => jsonEncode(entry.toJson())).toList();
    await prefs.setStringList(_key, encoded);
  }

  static Future<List<ReadingHistoryItem>> getRecentArticles() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getStringList(_key) ?? const [];

    return raw
        .map((entry) => ReadingHistoryItem.fromJson(jsonDecode(entry)))
        .where((entry) => entry.articleId.isNotEmpty)
        .toList();
  }
}
