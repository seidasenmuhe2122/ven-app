import 'package:in_app_review/in_app_review.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ReviewService {
  static const String _readCountKey = 'articles_read_count';
  static const String _reviewPromptedKey = 'review_prompted';

  static Future<int> getReadCount() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getInt(_readCountKey) ?? 0;
  }

  static Future<void> registerArticleRead() async {
    final prefs = await SharedPreferences.getInstance();
    final current = prefs.getInt(_readCountKey) ?? 0;
    final next = current + 1;
    await prefs.setInt(_readCountKey, next);

    if (next >= 10 && !(prefs.getBool(_reviewPromptedKey) ?? false)) {
      await prefs.setBool(_reviewPromptedKey, true);
      await requestReview();
    }
  }

  static Future<void> requestReview() async {
    final inAppReview = InAppReview.instance;
    if (await inAppReview.isAvailable()) {
      await inAppReview.requestReview();
    }
  }
}
