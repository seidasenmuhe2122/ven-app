import 'package:flutter_test/flutter_test.dart';
import 'package:royal_pro_flutter/services/ad_settings_service.dart';

void main() {
  group('AdSettings.fromJson', () {
    const response = {
      'ads_enabled': true,
      'banner_ad_unit_id': 'ca-app-pub-123/banner',
      'native_ad_unit_id': 'ca-app-pub-123/native',
    };

    test('keeps ads disabled until consent permits requests', () {
      final settings = AdSettings.fromJson(response);

      expect(settings.adsEnabled, isFalse);
      expect(settings.bannerAdUnitId, 'ca-app-pub-123/banner');
    });

    test('enables configured ads after consent permits requests', () {
      final settings = AdSettings.fromJson(
        response,
        canRequestAds: true,
      );

      expect(settings.adsEnabled, isTrue);
      expect(settings.nativeAdUnitId, 'ca-app-pub-123/native');
    });

    test('does not enable ads without a configured banner unit', () {
      final settings = AdSettings.fromJson(
        const {'ads_enabled': true},
        canRequestAds: true,
      );

      expect(settings.adsEnabled, isFalse);
      expect(settings.bannerAdUnitId, isEmpty);
    });

    test('rejects Google sample ad units in production settings', () {
      final settings = AdSettings.fromJson(
        const {
          'ads_enabled': true,
          'banner_ad_unit_id': 'ca-app-pub-3940256099942544/6300978111',
          'native_ad_unit_id': 'ca-app-pub-3940256099942544/2247696110',
        },
        canRequestAds: true,
      );

      expect(settings.adsEnabled, isFalse);
      expect(settings.nativeAdUnitId, isEmpty);
    });
  });
}
