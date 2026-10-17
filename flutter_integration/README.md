# Digital Tech Mobile App

This is the standalone Flutter application for the Digital Tech article
service. It contains article browsing/search, article details, bookmarks,
reading history, authentication, deep links, sharing, text-to-speech, settings,
and optional AdMob placements.

## Verified local configuration

- Flutter package: `royal_pro_flutter`
- Android application ID: `com.venapp.app`
- iOS bundle ID: `com.digitaltech.app`
- Version/build: `1.0.0+1` (from `pubspec.yaml`)
- Android min/target/compile SDK: 24 / 36 / 36
- Android/iOS app display name: Digital Tech
- Default API base: `https://ven-app.onrender.com`

The current default API host returned HTTP 404 for the app's tested API routes.
Supply the correct deployed API base when running or building:

```powershell
flutter run --dart-define=API_BASE_URL=https://your-api.example
```

Use an HTTPS production endpoint. Do not put credentials or signing passwords
in Dart defines or source files.

## Android release signing and AdMob

Debug builds use Google's Android test AdMob application ID. Release builds
refuse to use the debug key or the test AdMob ID.

1. Generate an upload keystore locally:

   ```powershell
   keytool -genkeypair -v -keystore android\upload-keystore.jks `
     -alias upload -keyalg RSA -keysize 2048 -validity 10000
   ```

2. Create the ignored file `android\key.properties` with the local keystore
   details. Resolve `storeFile` relative to the `android` directory:

   ```properties
   storeFile=upload-keystore.jks
   storePassword=YOUR_LOCAL_KEYSTORE_PASSWORD
   keyAlias=upload
   keyPassword=YOUR_LOCAL_KEY_PASSWORD
   ```

3. Set the production Android AdMob application ID in the current PowerShell
   process and build:

   ```powershell
   $env:ORG_GRADLE_PROJECT_ADMOB_APP_ID = "ca-app-pub-xxxxxxxxxxxxxxxx~yyyyyyyyyy"
   flutter build appbundle --release `
     --dart-define=API_BASE_URL=https://your-api.example
   Remove-Item Env:ORG_GRADLE_PROJECT_ADMOB_APP_ID
   ```

4. Configure real banner/native ad-unit IDs in the backend settings endpoint.
   Ads remain disabled unless consent is permitted and the backend returns a
   valid banner unit ID. The Android release app ID is a separate required
   Gradle property.

Keep `key.properties` and the keystore out of source control. Back up the
upload key securely; losing it can block future Play uploads. No release key
is included in this workspace.

## iOS release configuration

Debug uses Google's iOS test AdMob application ID. For a release build, create
the ignored file `ios\Flutter\AdMob.xcconfig` with the production iOS app ID:

```xcconfig
ADMOB_APPLICATION_ID = ca-app-pub-xxxxxxxxxxxxxxxx~yyyyyyyyyy
```

Build/sign the iOS app on macOS with Xcode and the registered bundle ID
`com.digitaltech.app`. This Windows environment cannot create or validate a
signed iOS archive.

## App Links and store assets

The Android manifest uses the current production host `ven-app.onrender.com`.
Publish the matching `assetlinks.json` for `com.venapp.app` with the release
signing certificate fingerprint and verify the links in Play Console before
relying on Android App Links. iOS associated domains and the matching Apple
App Site Association file also require the confirmed domain and Apple signing
capability.

The generated DT/book icon and splash assets use the current purple/orange UI
colors and are provisional; obtain owner/brand approval before store
submission. Create localized store screenshots, listing text, feature
graphics, privacy policy, and App content declarations in the relevant
console.

## Local checks

```powershell
flutter analyze --no-fatal-infos
flutter test
flutter build apk --debug
```

See [RELEASE_READINESS.md](./RELEASE_READINESS.md) for tested results,
unresolved API/console requirements, and the exact release status.
