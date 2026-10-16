import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:package_info_plus/package_info_plus.dart';

class AppVersionInfo {
  const AppVersionInfo({
    required this.latestVersion,
    required this.minRequiredVersion,
    required this.appStoreUrl,
    required this.playStoreUrl,
    required this.isForceUpdate,
  });

  final String latestVersion;
  final String minRequiredVersion;
  final String appStoreUrl;
  final String playStoreUrl;
  final bool isForceUpdate;

  factory AppVersionInfo.fromJson(Map<String, dynamic> json) {
    return AppVersionInfo(
      latestVersion: json['latest_version'] ?? '1.0.0',
      minRequiredVersion: json['min_required_version'] ?? '1.0.0',
      appStoreUrl: json['app_store_url'] ?? 'https://apps.apple.com/',
      playStoreUrl: json['play_store_url'] ?? 'https://play.google.com/store',
      isForceUpdate: false,
    );
  }
}

class VersionUpdateService {
  static int _parseVersion(String? version) {
    final normalized = (version ?? '0.0.0').replaceAll(RegExp(r'[^0-9.]'), '');
    final parts = normalized.split('.').where((value) => value.isNotEmpty).toList();

    while (parts.length < 3) {
      parts.add('0');
    }

    final values = parts.take(3).map((value) => int.tryParse(value) ?? 0).toList();
    return (values[0] * 1000000) + (values[1] * 1000) + values[2];
  }

  static bool isUpdateRequired({required String currentVersion, required String minRequiredVersion}) {
    return _parseVersion(currentVersion) < _parseVersion(minRequiredVersion);
  }

  static bool isNewVersionAvailable({required String currentVersion, required String latestVersion}) {
    return _parseVersion(currentVersion) < _parseVersion(latestVersion);
  }

  static Future<AppVersionInfo> fetchVersionInfo({required String baseUrl}) async {
    final response = await http.get(Uri.parse('$baseUrl/api/settings/1/'));

    if (response.statusCode != 200) {
      return const AppVersionInfo(
        latestVersion: '1.0.0',
        minRequiredVersion: '1.0.0',
        appStoreUrl: 'https://apps.apple.com/',
        playStoreUrl: 'https://play.google.com/store',
        isForceUpdate: false,
      );
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    return AppVersionInfo.fromJson(data);
  }

  static Future<bool> shouldShowUpdateDialog({required String baseUrl}) async {
    try {
      final info = await fetchVersionInfo(baseUrl: baseUrl);
      final packageInfo = await PackageInfo.fromPlatform();
      final currentVersion = packageInfo.version;

      if (isUpdateRequired(currentVersion: currentVersion, minRequiredVersion: info.minRequiredVersion)) {
        return true;
      }

      return isNewVersionAvailable(currentVersion: currentVersion, latestVersion: info.latestVersion);
    } catch (_) {
      return false;
    }
  }
}
