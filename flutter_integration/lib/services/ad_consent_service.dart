import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:google_mobile_ads/google_mobile_ads.dart';

class AdConsentService {
  static const Duration _consentUpdateTimeout = Duration(seconds: 10);

  static Future<bool> initialize() async {
    final consentInfoUpdated = Completer<bool>();
    try {
      ConsentInformation.instance.requestConsentInfoUpdate(
        ConsentRequestParameters(),
        () => consentInfoUpdated.complete(true),
        (error) {
          debugPrint('Ad consent information update failed: $error');
          consentInfoUpdated.complete(false);
        },
      );

      final updated = await consentInfoUpdated.future.timeout(
        _consentUpdateTimeout,
        onTimeout: () {
          debugPrint('Ad consent information update timed out.');
          return false;
        },
      );
      if (updated) {
        await ConsentForm.loadAndShowConsentFormIfRequired((error) {
          if (error != null) {
            debugPrint('Ad consent form failed: $error');
          }
        });
      }

      final canRequestAds = await ConsentInformation.instance.canRequestAds();
      if (canRequestAds) {
        await MobileAds.instance.initialize();
      }
      return canRequestAds;
    } on PlatformException catch (error) {
      debugPrint('Ad consent platform operation failed: $error');
      return false;
    } on MissingPluginException catch (error) {
      debugPrint('Ad consent plugin is unavailable: $error');
      return false;
    }
  }

  static Future<bool> privacyOptionsRequired() async {
    final status =
        await ConsentInformation.instance.getPrivacyOptionsRequirementStatus();
    return status == PrivacyOptionsRequirementStatus.required;
  }

  static Future<FormError?> showPrivacyOptions() async {
    final result = Completer<FormError?>();
    await ConsentForm.showPrivacyOptionsForm(result.complete);
    return result.future;
  }
}
