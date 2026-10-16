import 'dart:async';

import 'package:app_links/app_links.dart';
import 'package:flutter/foundation.dart';

class DeepLinkService {
  final AppLinks _appLinks = AppLinks();
  final StreamController<String> _linkStreamController = StreamController.broadcast();

  Stream<String> get linkStream => _linkStreamController.stream;

  static String buildArticleUrl({required String articleId, required String baseUrl}) {
    final normalizedBase = baseUrl.trim().replaceAll(RegExp(r'/+$'), '');
    return '$normalizedBase/article/$articleId';
  }

  static String? extractArticleIdFromUri(Uri? uri) {
    if (uri == null) return null;

    final segments = uri.pathSegments.where((segment) => segment.trim().isNotEmpty).toList();
    if (segments.length >= 2 && segments[0].toLowerCase() == 'article') {
      final articleId = segments[1];
      return int.tryParse(articleId) != null ? articleId : null;
    }

    if (segments.length >= 2 && segments[0].toLowerCase() == 'articles') {
      final articleId = segments[1];
      return int.tryParse(articleId) != null ? articleId : null;
    }

    if (segments.length == 1 && int.tryParse(segments[0]) != null) {
      return segments[0];
    }

    return null;
  }

  Future<void> initialize() async {
    try {
      final initialLink = await _appLinks.getInitialLink();
      if (initialLink != null && initialLink.toString().isNotEmpty) {
        _linkStreamController.add(initialLink.toString());
      }
    } catch (e) {
      if (kDebugMode) {
        print('Initial deep link failed: $e');
      }
    }

    _appLinks.uriLinkStream.listen((Uri uri) {
      _linkStreamController.add(uri.toString());
    }, onError: (error) {
      if (kDebugMode) {
        print('Deep link stream error: $error');
      }
    });
  }

  void dispose() {
    _linkStreamController.close();
  }
}
