import 'package:flutter/material.dart';

import '../config/app_config.dart';
import '../l10n/app_localizations.dart';
import '../screens/feedback_screen.dart';
import '../services/ad_consent_service.dart';
import '../services/ad_settings_service.dart';
import '../services/font_size_service.dart';
import '../services/language_service.dart';
import '../services/review_service.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({
    super.key,
    required this.locale,
    required this.fontSize,
    required this.onLanguageChanged,
    required this.onFontSizeChanged,
    this.adSettings,
  });

  final Locale locale;
  final ArticleFontSize fontSize;
  final ValueChanged<Locale> onLanguageChanged;
  final ValueChanged<ArticleFontSize> onFontSizeChanged;
  final AdSettings? adSettings;

  String _stripHtml(String value) {
    return value
        .replaceAll(RegExp(r'<[^>]*>', multiLine: true), ' ')
        .replaceAll(RegExp(r'\s+'), ' ')
        .trim();
  }

  Color _parseColor(String value) {
    final normalized = value.trim();
    final hex =
        normalized.startsWith('#') ? normalized.substring(1) : normalized;
    if (hex.length == 3) {
      final expanded = hex.split('').expand((char) => [char, char]).join();
      return Color(int.parse('0xFF$expanded'));
    }
    if (hex.length == 6) {
      return Color(int.parse('0xFF$hex'));
    }
    return const Color(0xFF111111);
  }

  List<MapEntry<String, Map<String, dynamic>>> _policySections() {
    return [
      MapEntry('About', {
        'content': adSettings?.aboutContent ?? '',
        'fontSize': adSettings?.aboutTextSize ?? 16,
        'color': adSettings?.aboutTextColor ?? '#111111',
        'backgroundColor': adSettings?.aboutBackgroundColor ?? '#ffffff',
      }),
      MapEntry('Contact', {
        'content': adSettings?.contactContent ?? '',
        'fontSize': adSettings?.contactTextSize ?? 16,
        'color': adSettings?.contactTextColor ?? '#111111',
        'backgroundColor': adSettings?.contactBackgroundColor ?? '#ffffff',
      }),
      MapEntry('Terms and Conditions', {
        'content': adSettings?.termsContent ?? '',
        'fontSize': adSettings?.termsTextSize ?? 16,
        'color': adSettings?.termsTextColor ?? '#111111',
        'backgroundColor': adSettings?.termsBackgroundColor ?? '#ffffff',
      }),
      MapEntry('Privacy Policy', {
        'content': adSettings?.privacyPolicyContent ?? '',
        'fontSize': adSettings?.privacyPolicyTextSize ?? 16,
        'color': adSettings?.privacyPolicyTextColor ?? '#111111',
        'backgroundColor':
            adSettings?.privacyPolicyBackgroundColor ?? '#ffffff',
      }),
    ];
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final policySections = _policySections();

    return Scaffold(
      appBar: AppBar(title: Text(l10n.settingsTitle)),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(18),
          children: [
            Align(
              alignment: Alignment.centerLeft,
              child: Text(
                l10n.languageSelector,
                style:
                    const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<Locale>(
              value: locale,
              isExpanded: true,
              decoration: InputDecoration(
                labelText: l10n.language,
                border: const OutlineInputBorder(),
              ),
              items: LanguageService.supportedLocales.map((supportedLocale) {
                return DropdownMenuItem<Locale>(
                  value: supportedLocale,
                  child: Text(LanguageService.localeLabel(supportedLocale)),
                );
              }).toList(),
              onChanged: (selectedLocale) {
                if (selectedLocale != null) {
                  onLanguageChanged(selectedLocale);
                }
              },
            ),
            const SizedBox(height: 18),
            Align(
              alignment: Alignment.centerLeft,
              child: Text(
                'Reading Size',
                style:
                    const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<ArticleFontSize>(
              value: fontSize,
              isExpanded: true,
              decoration: const InputDecoration(
                labelText: 'Font Size',
                border: OutlineInputBorder(),
              ),
              items: ArticleFontSize.values.map((size) {
                return DropdownMenuItem<ArticleFontSize>(
                  value: size,
                  child: Text(size.label),
                );
              }).toList(),
              onChanged: (selectedSize) {
                if (selectedSize != null) {
                  onFontSizeChanged(selectedSize);
                }
              },
            ),
            const SizedBox(height: 18),
            ListTile(
              leading: const Icon(Icons.language),
              title: Text(l10n.language),
              subtitle: Text(LanguageService.localeLabel(locale)),
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 0, vertical: 4),
            ),
            ListTile(
              leading: const Icon(Icons.text_fields_rounded),
              title: const Text('Reading Size'),
              subtitle: Text(fontSize.label),
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 0, vertical: 4),
            ),
            const SizedBox(height: 20),
            const Divider(),
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerLeft,
              child: Text(
                'Policy Pages',
                style:
                    const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
            ),
            const SizedBox(height: 12),
            ...policySections.map((entry) {
              final content =
                  _stripHtml((entry.value['content'] as String?) ?? '');
              final fontSize =
                  ((entry.value['fontSize'] as num?) ?? 16).toDouble();
              final textColor =
                  _parseColor((entry.value['color'] as String?) ?? '#111111');
              final bgColor = _parseColor(
                  (entry.value['backgroundColor'] as String?) ?? '#ffffff');

              if (content.isEmpty) {
                return const SizedBox.shrink();
              }

              return Card(
                margin: const EdgeInsets.only(bottom: 12),
                child: ExpansionTile(
                  title: Text(entry.key),
                  childrenPadding: const EdgeInsets.all(16),
                  children: [
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: bgColor,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: SelectableText(
                        content,
                        style: TextStyle(
                          fontSize: fontSize,
                          color: textColor,
                          height: 1.5,
                        ),
                      ),
                    ),
                  ],
                ),
              );
            }),
            const Divider(),
            FutureBuilder<bool>(
              future: AdConsentService.privacyOptionsRequired(),
              builder: (context, snapshot) {
                if (snapshot.data != true) {
                  return const SizedBox.shrink();
                }
                return ListTile(
                  leading: const Icon(Icons.privacy_tip_outlined),
                  title: const Text('Privacy options'),
                  subtitle: const Text('Review your advertising consent'),
                  onTap: () async {
                    final error = await AdConsentService.showPrivacyOptions();
                    if (error != null && context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text(
                            'Unable to open privacy options: $error',
                          ),
                        ),
                      );
                    }
                  },
                );
              },
            ),
            const Divider(),
            ListTile(
              leading: const Icon(Icons.star_rate_rounded),
              title: const Text('Rate Us'),
              subtitle: const Text('Share your feedback with the app store'),
              onTap: () async {
                await ReviewService.requestReview();
              },
            ),
            ListTile(
              leading: const Icon(Icons.feedback_outlined),
              title: const Text('Send Feedback'),
              subtitle: const Text('Help us improve the app'),
              onTap: () {
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) =>
                        FeedbackScreen(baseUrl: AppConfig.apiBaseUrl),
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}
