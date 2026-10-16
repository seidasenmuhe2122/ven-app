# Flutter Social Sharing + Deep Linking Integration

This folder contains a drop-in Flutter integration for:

- social sharing via `share_plus`
- deep linking via `app_links`
- linking a shared article URL like `https://myapp.com/article/123` directly to an article detail screen

## Android deep link config

The Android manifest is included at
`android/app/src/main/AndroidManifest.xml`. It configures the Flutter launch
activity and verified HTTPS links for `/article/` and `/articles/` URLs on
`myapp.com`. Replace `myapp.com` with the production domain in the manifest,
and publish a matching `assetlinks.json` file for Android App Links verification.

The manifest uses Google's sample AdMob application ID. Replace it with your
AdMob application ID before publishing.

Host the asset links file at
`https://myapp.com/.well-known/assetlinks.json`:

```json
[
  {
    "relation": ["delegate_permission/common.handle_all_urls"],
    "target": {
      "namespace": "android_app",
      "package_name": "YOUR_ANDROID_APPLICATION_ID",
      "sha256_cert_fingerprints": ["YOUR_SIGNING_CERTIFICATE_SHA256"]
    }
  }
]
```

## iOS universal link config

Add the following to `ios/Runner/Info.plist`:

```xml
<key>CFBundleURLTypes</key>
<array>
  <dict>
    <key>CFBundleURLSchemes</key>
    <array>
      <string>myapp</string>
    </array>
  </dict>
</array>
<key>com.apple.developer.associated-domains</key>
<array>
  <string>applinks:myapp.com</string>
</array>
```

## Share examples

```dart
await ShareService.shareArticle(
  title: article.title,
  articleId: article.id.toString(),
  baseUrl: 'https://myapp.com',
);
```

## Deep link handling

```dart
final uri = Uri.tryParse(link);
if (uri != null && uri.pathSegments.length >= 2 && uri.pathSegments[0] == 'article') {
  final articleId = uri.pathSegments[1];
  // open ArticleDetailScreen(articleId: articleId)
}
```
