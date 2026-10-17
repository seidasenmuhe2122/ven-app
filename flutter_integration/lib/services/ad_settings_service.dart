import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

class AdSettings {
  const AdSettings({
    this.adsEnabled = false,
    this.bannerAdUnitId = '',
    this.nativeAdUnitId = '',
    this.logoUrl,
    this.adNetwork = 'admob',
    this.admobAppId = '',
    this.interstitialAdUnitId = '',
    this.rewardedAdUnitId = '',
    this.adPlacements = const <String, dynamic>{},
    this.adNetworks = const <Map<String, dynamic>>[],
    this.adCampaigns = const <Map<String, dynamic>>[],
    this.aboutContent = '',
    this.aboutTextSize = 16,
    this.aboutTextColor = '#111111',
    this.aboutBackgroundColor = '#ffffff',
    this.contactContent = '',
    this.contactTextSize = 16,
    this.contactTextColor = '#111111',
    this.contactBackgroundColor = '#ffffff',
    this.termsContent = '',
    this.termsTextSize = 16,
    this.termsTextColor = '#111111',
    this.termsBackgroundColor = '#ffffff',
    this.privacyPolicyContent = '',
    this.privacyPolicyTextSize = 16,
    this.privacyPolicyTextColor = '#111111',
    this.privacyPolicyBackgroundColor = '#ffffff',
  });

  final bool adsEnabled;
  final String bannerAdUnitId;
  final String nativeAdUnitId;
  final String? logoUrl;
  final String adNetwork;
  final String admobAppId;
  final String interstitialAdUnitId;
  final String rewardedAdUnitId;
  final Map<String, dynamic> adPlacements;
  final List<Map<String, dynamic>> adNetworks;
  final List<Map<String, dynamic>> adCampaigns;
  final String aboutContent;
  final int aboutTextSize;
  final String aboutTextColor;
  final String aboutBackgroundColor;
  final String contactContent;
  final int contactTextSize;
  final String contactTextColor;
  final String contactBackgroundColor;
  final String termsContent;
  final int termsTextSize;
  final String termsTextColor;
  final String termsBackgroundColor;
  final String privacyPolicyContent;
  final int privacyPolicyTextSize;
  final String privacyPolicyTextColor;
  final String privacyPolicyBackgroundColor;

  factory AdSettings.fromJson(
    Map<String, dynamic> json, {
    bool canRequestAds = false,
  }) {
    final bannerAdUnitId = (json['banner_ad_unit_id'] ?? '').toString();
    final nativeAdUnitId = (json['native_ad_unit_id'] ?? '').toString();
    final hasProductionBannerId = bannerAdUnitId.isNotEmpty &&
        !bannerAdUnitId.contains('ca-app-pub-3940256099942544');
    final productionNativeAdUnitId =
        nativeAdUnitId.contains('ca-app-pub-3940256099942544')
            ? ''
            : nativeAdUnitId;
    return AdSettings(
      adsEnabled:
          json['ads_enabled'] == true && canRequestAds && hasProductionBannerId,
      bannerAdUnitId: bannerAdUnitId,
      nativeAdUnitId: productionNativeAdUnitId,
      logoUrl: json['logo'] == null || json['logo'].toString().isEmpty
          ? null
          : json['logo'].toString(),
      adNetwork: json['ad_network'] ?? 'admob',
      admobAppId: json['admob_app_id'] ?? '',
      interstitialAdUnitId: json['interstitial_ad_unit_id'] ?? '',
      rewardedAdUnitId: json['rewarded_ad_unit_id'] ?? '',
      adPlacements: Map<String, dynamic>.from(
          json['ad_placements'] ?? const <String, dynamic>{}),
      adNetworks: _mapList(json['ad_networks']),
      adCampaigns: _mapList(json['ad_campaigns']),
      aboutContent: json['about_content'] ?? '',
      aboutTextSize: (json['about_text_size'] ?? 16) as int,
      aboutTextColor: json['about_text_color'] ?? '#111111',
      aboutBackgroundColor: json['about_background_color'] ?? '#ffffff',
      contactContent: json['contact_content'] ?? '',
      contactTextSize: (json['contact_text_size'] ?? 16) as int,
      contactTextColor: json['contact_text_color'] ?? '#111111',
      contactBackgroundColor: json['contact_background_color'] ?? '#ffffff',
      termsContent: json['terms_content'] ?? '',
      termsTextSize: (json['terms_text_size'] ?? 16) as int,
      termsTextColor: json['terms_text_color'] ?? '#111111',
      termsBackgroundColor: json['terms_background_color'] ?? '#ffffff',
      privacyPolicyContent: json['privacy_policy_content'] ?? '',
      privacyPolicyTextSize: (json['privacy_policy_text_size'] ?? 16) as int,
      privacyPolicyTextColor: json['privacy_policy_text_color'] ?? '#111111',
      privacyPolicyBackgroundColor:
          json['privacy_policy_background_color'] ?? '#ffffff',
    );
  }

  static List<Map<String, dynamic>> _mapList(dynamic value) {
    if (value is! List) return const <Map<String, dynamic>>[];
    return value
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList(growable: false);
  }
}

class AdSettingsService {
  static const Duration _requestTimeout = Duration(seconds: 15);

  static Future<AdSettings> fetchSettings({
    required String baseUrl,
    required bool canRequestAds,
  }) async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/api/settings/1/'))
          .timeout(_requestTimeout);

      if (response.statusCode != 200) {
        debugPrint(
          'Ad settings request failed with HTTP ${response.statusCode}; ads are disabled.',
        );
        return const AdSettings();
      }

      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return AdSettings.fromJson(data, canRequestAds: canRequestAds);
    } on FormatException catch (error) {
      debugPrint('Ad settings response was invalid; ads are disabled: $error');
      return const AdSettings();
    } on TypeError catch (error) {
      debugPrint(
          'Ad settings response had an invalid shape; ads are disabled: $error');
      return const AdSettings();
    } on http.ClientException catch (error) {
      debugPrint('Ad settings HTTP request failed; ads are disabled: $error');
      return const AdSettings();
    } on SocketException catch (error) {
      debugPrint(
          'Ad settings network request failed; ads are disabled: $error');
      return const AdSettings();
    } on TimeoutException catch (error) {
      debugPrint('Ad settings request timed out; ads are disabled: $error');
      return const AdSettings();
    }
  }
}
