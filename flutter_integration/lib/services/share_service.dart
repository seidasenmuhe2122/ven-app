import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';

class ShareService {
  static Uri buildArticleUri({required String articleId, required String baseUrl}) {
    final normalizedBase = baseUrl.trim().replaceAll(RegExp(r'/+$'), '');
    return Uri.parse('$normalizedBase/article/$articleId');
  }

  static Future<void> shareArticle({
    required String title,
    required String articleId,
    required String baseUrl,
  }) async {
    final articleUrl = buildArticleUri(articleId: articleId, baseUrl: baseUrl).toString();
    final message = '$title\n\n$articleUrl';

    await Share.share(
      message,
      subject: title,
      sharePositionOrigin: null,
    );
  }

  static Future<void> shareToTelegram({
    required String title,
    required String articleId,
    required String baseUrl,
  }) async {
    final articleUrl = buildArticleUri(articleId: articleId, baseUrl: baseUrl).toString();
    final shareText = '$title\n\n$articleUrl';
    final shareUri = Uri.parse(
      'https://t.me/share/url?url=${Uri.encodeComponent(articleUrl)}&text=${Uri.encodeComponent(title)}',
    );

    try {
      await Share.share(shareText, subject: title);
    } finally {
      final launched = await launchUrl(shareUri, mode: LaunchMode.externalApplication);
      if (!launched) {
        await Share.share(shareText, subject: title);
      }
    }
  }

  static Future<void> shareToWhatsApp({
    required String title,
    required String articleId,
    required String baseUrl,
  }) async {
    final articleUrl = buildArticleUri(articleId: articleId, baseUrl: baseUrl).toString();
    final shareText = '$title\n\n$articleUrl';
    final shareUri = Uri.parse(
      'https://api.whatsapp.com/send?text=${Uri.encodeComponent(shareText)}',
    );

    try {
      await Share.share(shareText, subject: title);
    } finally {
      final launched = await launchUrl(shareUri, mode: LaunchMode.externalApplication);
      if (!launched) {
        await Share.share(shareText, subject: title);
      }
    }
  }

  static Future<void> shareToFacebook({
    required String title,
    required String articleId,
    required String baseUrl,
  }) async {
    final articleUrl = buildArticleUri(articleId: articleId, baseUrl: baseUrl).toString();
    final shareText = '$title\n\n$articleUrl';
    final shareUri = Uri.parse(
      'https://www.facebook.com/sharer/sharer.php?u=${Uri.encodeComponent(articleUrl)}',
    );

    try {
      await Share.share(shareText, subject: title);
    } finally {
      final launched = await launchUrl(shareUri, mode: LaunchMode.externalApplication);
      if (!launched) {
        await Share.share(shareText, subject: title);
      }
    }
  }

  static Future<void> shareToX({
    required String title,
    required String articleId,
    required String baseUrl,
  }) async {
    final articleUrl = buildArticleUri(articleId: articleId, baseUrl: baseUrl).toString();
    final shareText = '$title\n\n$articleUrl';
    final shareUri = Uri.parse(
      'https://twitter.com/intent/tweet?text=${Uri.encodeComponent(shareText)}',
    );

    try {
      await Share.share(shareText, subject: title);
    } finally {
      final launched = await launchUrl(shareUri, mode: LaunchMode.externalApplication);
      if (!launched) {
        await Share.share(shareText, subject: title);
      }
    }
  }
}
