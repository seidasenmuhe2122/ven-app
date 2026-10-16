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
- Mobile branding assets are not included in the Flutter package. The Django `media/branding` folder has multiple candidate logos, but the correct production logo/icon and permission to repurpose any specific asset have not been confirmed.

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

The archive will be created immediately before the first structural edit, after the permanent Android application ID, iOS bundle ID, and production API URL are confirmed. No structural edits have been made as part of this baseline phase.
