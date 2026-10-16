import 'package:shared_preferences/shared_preferences.dart';

enum ArticleFontSize {
  small,
  medium,
  large,
  extraLarge,
}

extension ArticleFontSizeX on ArticleFontSize {
  String get label {
    switch (this) {
      case ArticleFontSize.small:
        return 'Small';
      case ArticleFontSize.medium:
        return 'Medium';
      case ArticleFontSize.large:
        return 'Large';
      case ArticleFontSize.extraLarge:
        return 'Extra Large';
    }
  }

  double get multiplier {
    switch (this) {
      case ArticleFontSize.small:
        return 0.9;
      case ArticleFontSize.medium:
        return 1.0;
      case ArticleFontSize.large:
        return 1.2;
      case ArticleFontSize.extraLarge:
        return 1.45;
    }
  }
}

class FontSizeService {
  static const String _key = 'article_font_size';

  static ArticleFontSize get defaultSize => ArticleFontSize.medium;

  static Future<ArticleFontSize> load() async {
    final prefs = await SharedPreferences.getInstance();
    final value = prefs.getString(_key);

    switch (value) {
      case 'small':
        return ArticleFontSize.small;
      case 'large':
        return ArticleFontSize.large;
      case 'extraLarge':
        return ArticleFontSize.extraLarge;
      case 'medium':
      default:
        return ArticleFontSize.medium;
    }
  }

  static Future<void> save(ArticleFontSize size) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, size.name);
  }

  static double scale(ArticleFontSize size, double base) {
    return base * size.multiplier;
  }
}
