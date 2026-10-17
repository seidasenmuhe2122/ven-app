# Mobile application baseline and backup plan

**Recorded:** 2026-10-16  
**Workspace:** `C:\myapp`  
**Mobile package:** `C:\myapp\flutter_integration`

## Baseline finding

The workspace root is a Django project (`manage.py`, `myapp`, `news`, `accounts`, SQLite database, media/static content). The mobile package is Flutter/Dart source under `flutter_integration`; it is not currently a standalone buildable application. Its Android directory is partial and lacks Gradle settings/build files, Gradle wrapper, `MainActivity`, Android resources, and release signing configuration. No iOS Runner/Xcode project exists. There is no Git repository at the workspace root, so Git history cannot serve as a rollback mechanism.

No backend, Django database, media, or static files were changed as part of this baseline inspection.

## Existing mobile code observed

- Screens: home/feed in `lib/main.dart`, article detail, authentication, bookmarks, settings, and feedback.
- Services: article/category API, token auth, AdMob settings, bookmarks, reading history, deep links, sharing, text-to-speech, review prompts, version checks, font size, and language.
- Locales: English and Amharic ARB resources and generated localization classes.
- Preferences/cache: bookmarks, reading history, article cache, and reading size use shared preferences; the auth token uses Flutter secure storage.
- APIs declared by the mobile source include `/api/articles/`, `/api/categories/`, `/api/login/`, `/api/register/`, `/api/me/`, `/api/settings/1/`, and `/api/feedback/`.
- The Django URL configuration includes a DRF router for `articles`, `categories`, and `settings`, plus matching login, registration, profile, and feedback routes. `ArticleViewSet` is a model viewset and `ArticleSerializer` returns article `content`; the existing backend therefore has a numeric article-retrieve route at `/api/articles/<id>/`. No new endpoint is needed merely to retrieve an article by ID.
- The actual production HTTPS API hostname is not identified in the inspected files. The Flutter default is the development loopback URL `http://127.0.0.1:8000`, which is unsuitable for a production mobile release.
- The user supplied `https://ven-app.onrender.com` as the production API base. An unauthenticated probe returned HTTP 404 for `/api/categories/`, `/api/articles/`, `/api/settings/1/`, and `/api/login/`; the user asked to continue and expects to correct the API URL later. Do not claim production API workflows are verified until this is fixed and retested.
- Mobile branding assets are not included in the Flutter package. The Django `media/branding` folder has multiple candidate logos, but the correct production logo/icon and permission to repurpose any specific asset have not been confirmed.
- The requested app name is Digital Tech. The initially requested Android ID `com.digitaltech.app` resolves publicly to a Google Play listing titled “Digital Technology Pathshala,” so it is not safe for this app. The user supplied `com.venapp.app` as the replacement; it is absent from this workspace and the public Play lookup returned Not Found. The requested iOS bundle ID remains `com.digitaltech.app`; Apple's public lookup returned zero listings. Public lookups cannot establish private account registration or ownership.

## Known build/test baseline

- Flutter 3.47.6 and Dart 3.13.5 are available; Android SDK 36 is installed and licenses are accepted.
- Dependency resolution succeeds.
- `flutter analyze --no-fatal-infos` succeeds after the compatibility fixes already made to this package; informational deprecations remain.
- `flutter test` cannot run because there is no `test/` directory.
- `flutter build appbundle --release` fails before Gradle compilation because the Android project is incomplete and Flutter identifies it as using the removed v1 embedding.
- No Android emulator or physical Android device is currently connected.
- This Windows machine cannot create a genuine signed iOS release; that requires a macOS/Xcode environment and Apple signing credentials.

## Backup and rollback strategy before structural work

1. Keep all Django/backend files, SQLite databases, uploaded media, and static assets outside the mobile-app change scope.
2. Before generating/replacing platform scaffold files, create a dated archive of `flutter_integration` in the persistent Copilot session `files` directory. Exclude disposable `.dart_tool` cache and machine-specific `android/local.properties`; preserve `lib`, `pubspec.yaml`, lockfile, README, current manifest, generated registrant, and all other source/configuration files.
3. Verify the archive exists and lists the source files before running any Flutter project-generation command.
4. Generate missing platform files only in `flutter_integration`, inspect diffs/file inventory, and never use a generator mode that silently replaces existing Dart source or platform configuration.
5. If a generated change needs rollback, restore only the specific mobile files from the dated archive. Do not reset or replace the Django project or user data.

Pre-scaffold archive created at `C:\Users\XIO\.copilot\session-state\6fb2463b-0316-4772-94f7-dfa8792e27b5\files\flutter_integration_pre_scaffold_20261016.zip` before any structural edit. It contains 34 mobile package files, including Dart source, the manifest, README, and package lockfile; disposable `.dart_tool`, build output, and machine-specific `android/local.properties` were excluded. Its contents were verified.

No structural changes to the project were made before the archive was verified.

## Progress after the verified baseline

- Generated the standalone Flutter Android and iOS project scaffolding only
  inside `flutter_integration`; no Django/backend/database/media files were
  changed.
- Set display name `Digital Tech`, Android application ID `com.venapp.app`,
  and iOS bundle ID `com.digitaltech.app`. The Android ID is not publicly
  listed in the lookup performed, but private Play Console ownership remains
  unverified. The original Android ID `com.digitaltech.app` conflicts with a
  public Play listing.
- Explicitly set Android `minSdk 24`, `targetSdk 36`, and `compileSdk 36`.
  The installed Android SDK initially lacked NDK 28.2.13676358 and API 36;
  those components were installed before retrying the debug build.
- Added an article-detail API fetch/cache/error flow against the existing
  Django numeric retrieve route, corrected the root deep-link back behavior,
  and preserved leading/trailing password characters during authentication.
- Added Flutter unit tests for article parsing/cache/failure cases, bookmarks,
  reading history, deep-link parsing, auth payloads, and ad consent/config
  gating. The latest observed run passed 19 tests. Static analysis completed
  with exit code 0 and 13 informational notices.
- Updated `google_mobile_ads` from 5.3.1 to 9.1.0 after the 5.3.1 Android
  Gradle script failed under the generated Gradle 9 project; the upgraded
  plugin's Dart API passes analysis and tests.
- Added Android/iOS launcher icons, splash graphics, and a 512x512 Play icon.
  These are provisional DT/book graphics using the existing UI colors; owner
  approval is still needed.
- AdMob now fails closed when consent or production ad-unit configuration is
  missing. Release builds require secure signing configuration and a
  production Android AdMob app ID; the iOS release config requires a local
  production `AdMob.xcconfig`.
- The user-provided HTTPS API base still returns HTTP 404 on the app API
  routes. Android debug build verification is in progress; no release AAB, signed
  iOS archive, device test, Play Console action, or upload has been completed.
