import 'dart:convert';
import 'dart:io';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../config/app_config.dart';

class ArticleSummary {
  const ArticleSummary({
    required this.id,
    required this.title,
    required this.summary,
    required this.categoryName,
    required this.status,
    required this.viewsCount,
    required this.readTimeMinutes,
    required this.imageUrl,
    required this.publishedAt,
  });

  final int id;
  final String title;
  final String summary;
  final String categoryName;
  final String status;
  final int viewsCount;
  final int readTimeMinutes;
  final String? imageUrl;
  final DateTime? publishedAt;

  static String _plainText(String value) {
    return value
        .replaceAll(RegExp(r'<[^>]*>'), ' ')
        .replaceAll(RegExp(r'&nbsp;|&amp;|&lt;|&gt;|&quot;|&#39;'), ' ')
        .replaceAll(RegExp(r'\s+'), ' ')
        .trim();
  }

  factory ArticleSummary.fromJson(Map<String, dynamic> json) {
    final imageValue = json['image_url'] ?? json['cover_image'];
    final summaryValue = json['summary'] ?? json['content'] ?? '';
    return ArticleSummary(
      id: json['id'] is int ? json['id'] as int : int.tryParse('${json['id']}') ?? 0,
      title: (json['title'] ?? 'Untitled article').toString(),
      summary: _plainText(summaryValue.toString()),
      categoryName: (json['category_name'] ?? json['category'] ?? 'General').toString(),
      status: (json['status'] ?? 'published').toString(),
      viewsCount: json['views_count'] is int ? json['views_count'] as int : int.tryParse('${json['views_count']}') ?? 0,
      readTimeMinutes: json['read_time_minutes'] is int ? json['read_time_minutes'] as int : int.tryParse('${json['read_time_minutes']}') ?? 0,
      imageUrl: imageValue == null || imageValue.toString().isEmpty ? null : imageValue.toString(),
      publishedAt: json['published_at'] == null ? null : DateTime.tryParse(json['published_at'].toString()),
    );
  }
}

class ArticleCategory {
  const ArticleCategory({
    required this.id,
    required this.name,
    required this.slug,
  });

  final int id;
  final String name;
  final String slug;

  factory ArticleCategory.fromJson(Map<String, dynamic> json) {
    return ArticleCategory(
      id: json['id'] is int ? json['id'] as int : int.tryParse('${json['id']}') ?? 0,
      name: (json['name'] ?? 'General').toString(),
      slug: (json['slug'] ?? '').toString(),
    );
  }
}

class ArticleService {
  static const String _cachedArticlesKey = 'cached_articles';

  static Future<bool> hasInternetConnection() async {
    final connectivityResult = await Connectivity().checkConnectivity();
    return !connectivityResult.contains(ConnectivityResult.none);
  }

  static Future<String> _cacheKey({String? search, int? categoryId}) {
    final safeSearch = (search ?? '').trim();
    final safeCategory = categoryId?.toString() ?? 'all';
    return Future.value('${_cachedArticlesKey}_${safeCategory}_${safeSearch}');
  }

  static Future<List<ArticleSummary>> getCachedArticles({String? search, int? categoryId}) async {
    final prefs = await SharedPreferences.getInstance();
    final key = await _cacheKey(search: search, categoryId: categoryId);
    final cached = prefs.getString(key);
    if (cached == null || cached.isEmpty) {
      return const <ArticleSummary>[];
    }

    final decoded = jsonDecode(cached);
    final List<dynamic> items = decoded is List
        ? decoded
        : decoded is Map && decoded['results'] is List
            ? decoded['results'] as List<dynamic>
            : <dynamic>[];

    return items
        .map((item) => ArticleSummary.fromJson(Map<String, dynamic>.from(item as Map)))
        .where((article) => article.status.toLowerCase() == 'published')
        .toList();
  }

  static Future<void> cacheArticlesResponse({
    required List<ArticleSummary> articles,
    String? search,
    int? categoryId,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    final key = await _cacheKey(search: search, categoryId: categoryId);
    final payload = articles
        .map((article) => {
              'id': article.id,
              'title': article.title,
              'summary': article.summary,
              'content': article.summary,
              'category': article.categoryName,
              'category_name': article.categoryName,
              'status': article.status,
              'views_count': article.viewsCount,
              'read_time_minutes': article.readTimeMinutes,
              'image_url': article.imageUrl,
              'published_at': article.publishedAt?.toIso8601String(),
            })
        .toList();
    await prefs.setString(key, jsonEncode(payload));
  }

  static Future<List<ArticleCategory>> fetchCategories({String? baseUrl}) async {
    final url = Uri.parse('${baseUrl ?? AppConfig.apiBaseUrl}/api/categories/');
    final response = await http.get(
      url,
      headers: {'Accept': 'application/json'},
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to load categories (${response.statusCode})');
    }

    final decoded = jsonDecode(response.body);
    final List<dynamic> items = decoded is List
        ? decoded
        : decoded is Map && decoded['results'] is List
            ? decoded['results'] as List<dynamic>
            : <dynamic>[];

    return items
        .map((item) => ArticleCategory.fromJson(Map<String, dynamic>.from(item as Map)))
        .toList();
  }

  static Future<List<ArticleSummary>> fetchPublishedArticles({
    String? baseUrl,
    String? search,
    int? categoryId,
  }) async {
    final hasConnection = await hasInternetConnection();
    final cacheKey = await _cacheKey(search: search, categoryId: categoryId);

    if (!hasConnection) {
      final prefs = await SharedPreferences.getInstance();
      final cached = prefs.getString(cacheKey);
      if (cached != null && cached.isNotEmpty) {
        final decoded = jsonDecode(cached);
        final items = decoded is List
            ? decoded
            : decoded is Map && decoded['results'] is List
                ? decoded['results'] as List<dynamic>
                : <dynamic>[];

        return items
            .map((item) => ArticleSummary.fromJson(Map<String, dynamic>.from(item as Map)))
            .where((article) => article.status.toLowerCase() == 'published')
            .toList();
      }
      throw const SocketException('No internet connection');
    }

    final queryParameters = <String, String>{};
    if ((search ?? '').trim().isNotEmpty) {
      queryParameters['search'] = search!.trim();
    }
    if (categoryId != null) {
      queryParameters['category'] = categoryId.toString();
    }

    final uri = Uri.parse('${baseUrl ?? AppConfig.apiBaseUrl}/api/articles/').replace(
      queryParameters: queryParameters,
    );

    final response = await http.get(
      uri,
      headers: {'Accept': 'application/json'},
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to load articles (${response.statusCode})');
    }

    final decoded = jsonDecode(response.body);
    final List<dynamic> items = decoded is List
        ? decoded
        : decoded is Map && decoded['results'] is List
            ? decoded['results'] as List<dynamic>
            : <dynamic>[];

    final articles = items
        .map((item) => ArticleSummary.fromJson(Map<String, dynamic>.from(item as Map)))
        .where((article) => article.status.toLowerCase() == 'published')
        .toList()
      ..sort((a, b) {
        final aTime = a.publishedAt ?? DateTime.fromMillisecondsSinceEpoch(0);
        final bTime = b.publishedAt ?? DateTime.fromMillisecondsSinceEpoch(0);
        return bTime.compareTo(aTime);
      });

    await cacheArticlesResponse(articles: articles, search: search, categoryId: categoryId);
    return articles;
  }
}
