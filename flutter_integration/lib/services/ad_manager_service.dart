import 'dart:async';

import 'package:google_mobile_ads/google_mobile_ads.dart';

class AdManagerService {
  static Future<bool> showInterstitial({required String adUnitId}) async {
    if (adUnitId.trim().isEmpty) return false;

    final result = Completer<bool>();
    await InterstitialAd.load(
      adUnitId: adUnitId,
      request: const AdRequest(),
      adLoadCallback: InterstitialAdLoadCallback(
        onAdLoaded: (ad) {
          ad.fullScreenContentCallback = FullScreenContentCallback(
            onAdDismissedFullScreenContent: (ad) => ad.dispose(),
            onAdFailedToShowFullScreenContent: (ad, error) => ad.dispose(),
          );
          result.complete(true);
          ad.show();
        },
        onAdFailedToLoad: (_) => result.complete(false),
      ),
    );
    return result.future;
  }

  static Future<bool> showRewarded({required String adUnitId, required void Function(RewardItem reward) onRewarded}) async {
    if (adUnitId.trim().isEmpty) return false;

    final result = Completer<bool>();
    await RewardedAd.load(
      adUnitId: adUnitId,
      request: const AdRequest(),
      rewardedAdLoadCallback: RewardedAdLoadCallback(
        onAdLoaded: (ad) {
          ad.fullScreenContentCallback = FullScreenContentCallback(
            onAdDismissedFullScreenContent: (ad) => ad.dispose(),
            onAdFailedToShowFullScreenContent: (ad, error) => ad.dispose(),
          );
          result.complete(true);
          ad.show(onUserEarnedReward: (_, reward) => onRewarded(reward));
        },
        onAdFailedToLoad: (_) => result.complete(false),
      ),
    );
    return result.future;
  }
}
