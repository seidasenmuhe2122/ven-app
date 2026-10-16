import 'package:flutter/material.dart';

class LanguageService {
  static const List<Locale> supportedLocales = [
    Locale('en'),
    Locale('am'),
  ];

  static String localeLabel(Locale locale) {
    switch (locale.languageCode) {
      case 'am':
        return 'አማርኛ';
      case 'en':
      default:
        return 'English';
    }
  }
}
