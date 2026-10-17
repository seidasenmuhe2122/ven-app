# Google Play release-readiness audit

**Audit date:** 2026-10-16  
**Scope:** `C:\myapp\flutter_integration` only. The Django project at `C:\myapp` is not evidence that this mobile app is release-ready.

## Executive result

**Not ready for Google Play submission.** This workspace contains Flutter/Dart app code and a partial Android directory, but it is not a buildable Android application project. No Android App Bundle was produced. The app identity, Android SDK levels, production API endpoint, release signing, device compatibility, and Play Console status cannot be verified from the files available here.

The Google Play target API requirement currently applicable to a new app or update is **Android 16 / API 36 or higher**, effective August 31, 2026. The project does not declare a target API level.

## Project identity and build configuration

| Item | Evidence and result |
|---|---|
| Framework | Flutter/Dart. `pubspec.yaml` identifies the Flutter package `royal_pro_flutter`; installed tools report Flutter 3.47.6 and Dart 3.13.5. |
| Mobile project directory | `C:\myapp\flutter_integration` is the only Flutter package found. It contains `lib/`, `pubspec.yaml`, and a partial `android/` directory. It is described as a Flutter integration, not a complete platform project. |
| Application ID | **Not configured / not verifiable.** No `applicationId`, Gradle namespace, or Android manifest package is present. The package name `royal_pro_flutter` is not proof of an Android application ID. |
| Version | `pubspec.yaml` declares `1.0.0+1`. This is Flutter package metadata; without Android Gradle configuration, the packaged Android version name and version code are **not verified**. |
| `minSdk` | **Not declared / not verifiable.** |
| `targetSdk` | **Not declared / not verifiable.** Current Play requirement for new apps and updates is API 36+. |
| `compileSdk` | **Not declared / not verifiable.** The machine has Android SDK/build tools installed, but that does not establish the app's compile SDK. |
| Android build scaffold | **Missing.** No `settings.gradle(.kts)`, app/module `build.gradle(.kts)`, Gradle wrapper, or `MainActivity` exists. The manifest also references absent Android resources, including `@mipmap/ic_launcher` and launch/normal theme styles. |
| Release signing | **Not configured / not verifiable.** No signing config, key properties, or release keystore is present. Do not put a keystore or passwords in source control. |
| AAB | **Not generated.** `flutter build appbundle --release` exits with `Build failed due to use of deleted Android v1 embedding.` There is no `.aab` output. |
| Connected Android test device | **None.** Flutter detects Windows, Chrome, and Edge only. No Android device or running emulator was available. Android toolchain is installed and licenses are accepted. |

## Current Play target API requirement

Google Play's [target API level requirements](https://support.google.com/googleplay/android-developer/answer/11926878?hl=en) state that, starting August 31, 2026, new apps and app updates must target Android 16 (API 36) or higher. Existing apps have a separate API 35 availability requirement; it does not establish compliance for this unverified new release. Set and verify `targetSdk` at API 36 or later when completing the Android build configuration, and build/test against a compatible compile SDK.

## Feature and workflow review

Source inspection found these implemented surfaces; **none were verified end-to-end on Android**:

- Home feed, category selection, search, connectivity handling, article cache, and retry/refresh.
- Article bookmarking, recent-reading history, and font-size preferences stored locally.
- Login/registration UI and token storage using `flutter_secure_storage`.
- Article sharing through the system share sheet and links for Telegram, WhatsApp, Facebook, and X.
- Deep-link parsing for numeric `/article/<id>` and `/articles/<id>` paths.
- Text-to-speech controls, reading-progress UI, and in-app review prompts.
- Settings for English/Amharic, font size, backend-provided policy text, and feedback submission.
- Backend-driven ad settings plus banner/native AdMob widgets.
- App-version/update check.

**Verified functional blocker:** `ArticleDetailScreen` currently renders fixed sample paragraphs and a generated “Royal Pro Article” title; it does not load the selected article from the API. Thus opening an article does not display the article selected in the feed. The existing Django backend supports public numeric retrieval at `/api/articles/<id>/` through `ArticleViewSet.retrieve`, and its serializer returns article content, so no new backend endpoint is needed. The mobile service still needs a detail-fetch method and appropriate loading/error behavior.

## Security, permissions, network, and privacy

- The checked-in manifest declares only `INTERNET` and `ACCESS_NETWORK_STATE`. No runtime sensitive-permission requests (camera, location, contacts, SMS, or notifications) were found in the inspected Dart source. This is not a substitute for reviewing the final merged manifest; dependencies can contribute permissions.
- `AppConfig` enforces an absolute HTTP(S) API URL and throws in release mode unless it uses HTTPS. However, the configured default is `http://127.0.0.1:8000`, which is a loopback address and not a production API. A release build must be supplied a real HTTPS `API_BASE_URL`; none is configured or confirmed here. App endpoints use that base URL for feed, authentication, feedback, settings, and version requests.
- Authentication sends credentials to the configured API and stores the returned token using secure storage. Bookmarks, article cache, and reading history use local `shared_preferences`; their data collection/retention implications need to be reflected accurately in the privacy disclosures.
- AdMob is integrated. The Android manifest currently contains Google's **sample/test AdMob application ID** (`ca-app-pub-3940256099942544~3347511713`), and Dart defaults include Google test ad-unit IDs. These are not production identifiers. Replace them with the app's real AdMob configuration and complete consent/privacy work before release.
- `myapp.com` is a placeholder host in the Android App Links manifest and integration README. No Android `assetlinks.json`, production domain ownership, package ID, or signing-certificate fingerprint is supplied. Verified App Links cannot be confirmed.
- The user-provided Android ID `com.digitaltech.app` conflicts with an existing public Google Play listing titled “Digital Technology Pathshala.” Do not use it for this app. A replacement candidate `com.venapp.app` returned Not Found in the public Play lookup and is absent from the workspace; private account registration is not publicly verifiable. The iOS ID `com.digitaltech.app` returned no public Apple listing; private registration is likewise unverified.
- The user supplied `https://ven-app.onrender.com` as the API base. Unauthenticated requests to the existing API paths `/api/categories/`, `/api/articles/`, `/api/settings/1/`, and `/api/login/` returned HTTP 404. The user requested continuing and expects to correct the API URL later; production workflows are not verified.
- The Settings screen can display backend-provided privacy-policy text, but an active privacy-policy URL both in the app and on the store listing is not established by this workspace.
- The final collection/sharing behavior of dependencies, merged Android permissions, server-side collection, retention, and advertising consent were not dynamically inspected. Complete Data safety answers only after a full SDK/backend data inventory.

## Automated checks and build results

| Check | Result |
|---|---|
| `flutter pub get` | **Passed.** Dependencies resolved; the selected compatible versions include `app_links 6.4.1` and `connectivity_plus 6.1.5`. |
| Initial `flutter analyze` | Found compile/analyzer errors: localization generation was not enabled, the initial-link method did not match the resolved `app_links` API, and the connectivity stream used an obsolete type. |
| Fixes applied | Enabled Flutter localization generation; updated to `AppLinks.getInitialLink()`; updated the connectivity subscription type; corrected the newer list-based connectivity check so an offline result is not treated as connected; removed unused version state. |
| Final `flutter analyze --no-fatal-infos` | **Passed with exit code 0.** No analyzer errors or warnings; 7 informational deprecation notices remain (`withOpacity` and form-field `value`). Plain `flutter analyze` reports those informational notices and exits nonzero in this environment. |
| `flutter test` | **Not run: unavailable.** Flutter reports `Test directory "test" not found.` No mobile Dart tests exist in this package. The 94 Django tests mentioned separately are not mobile-app test evidence. |
| `flutter build appbundle --release` | **Failed.** Flutter exits before Gradle compilation with `Build failed due to use of deleted Android v1 embedding.` The Android project is incomplete and has no Gradle scaffold or launcher activity; no release artifact was created. |
| Android runtime/device tests | **Not run.** No Android device/emulator was connected. |

## Store listing, app declarations, and manual Play Console work

No Play Console access or account metadata is available in this audit. The following items therefore remain **unverified and require manual action**:

- Create/confirm the Play Console app record and its permanent application ID.
- Complete account identity/contact verification and any account-specific production-access requirements.
- Complete App content declarations: privacy policy, ads (the source integrates AdMob), app access instructions/test credentials if login is required, target audience/content, content rating, Data safety, and the News declaration if the app is submitted as a news app.
- Publish a privacy-policy URL that applies to this app and make it accessible within the app.
- Provide store listing text, screenshots, high-resolution icon, feature graphic, and any other required localized assets. No image assets were found in this mobile package.
- Replace placeholder App Links host and test AdMob identifiers; publish matching `assetlinks.json` using the final package name and signing-certificate SHA-256 fingerprint.
- Configure Play App Signing/release signing, upload and validate an AAB, and review Play pre-launch report/device coverage.
- For **personal developer accounts created after November 13, 2023**, Google requires a closed test with at least 12 opted-in testers continuously for at least 14 days, followed by a production-access application. Whether this rule applies depends on the account type/creation date and cannot be checked here. See Google's [testing requirements](https://support.google.com/googleplay/android-developer/answer/14151465?hl=en).

Google Play's [App content guidance](https://support.google.com/googleplay/android-developer/answer/9859455?hl=en) explains the privacy-policy, ads, app-access, audience/content, rating, and data-safety declarations. Google Play's [testing-track guidance](https://support.google.com/googleplay/android-developer/answer/9845334?hl=en) describes internal, closed, and open testing.

## Changes made during this audit

- Fixed confirmed Flutter localization/API compatibility and offline connectivity defects in the Dart source.
- Added Flutter localization generation to `pubspec.yaml`.
- Removed unused version-state storage.
- No release artifact was built or uploaded, no app was published, and no Play Console actions were taken.
