import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:url_launcher/url_launcher.dart';

import 'config/app_config.dart';
import 'l10n/app_localizations.dart';
import 'screens/article_detail_screen.dart';
import 'screens/auth_screen.dart';
import 'screens/bookmarks_screen.dart';
import 'screens/settings_screen.dart';
import 'services/ad_consent_service.dart';
import 'services/ad_settings_service.dart';
import 'services/article_service.dart';
import 'services/bookmark_service.dart';
import 'services/deep_link_service.dart';
import 'services/font_size_service.dart';
import 'services/language_service.dart';
import 'services/reading_history_service.dart';
import 'services/version_update_service.dart';
import 'widgets/banner_ad_widget.dart';
import 'widgets/native_ad_widget.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final canRequestAds = await AdConsentService.initialize();

  final deepLinkService = DeepLinkService();
  await deepLinkService.initialize();

  runApp(MyApp(
    deepLinkService: deepLinkService,
    canRequestAds: canRequestAds,
  ));
}

class MyApp extends StatefulWidget {
  const MyApp({
    super.key,
    required this.deepLinkService,
    required this.canRequestAds,
  });

  final DeepLinkService deepLinkService;
  final bool canRequestAds;

  @override
  State<MyApp> createState() => _MyAppState();
}

class _MyAppState extends State<MyApp> {
  String? currentArticleId;
  AdSettings? _adSettings;
  Locale _locale = LanguageService.supportedLocales.first;
  ArticleFontSize _fontSize = FontSizeService.defaultSize;

  @override
  void initState() {
    super.initState();
    _loadAdSettings();
    _loadFontSize();
    _checkAppVersion();
    widget.deepLinkService.linkStream.listen((link) {
      final uri = Uri.tryParse(link);
      final articleId = DeepLinkService.extractArticleIdFromUri(uri);
      if (articleId != null && mounted) {
        setState(() {
          currentArticleId = articleId;
        });
      }
    });
  }

  Future<void> _loadAdSettings() async {
    final settings = await AdSettingsService.fetchSettings(
      baseUrl: AppConfig.apiBaseUrl,
      canRequestAds: widget.canRequestAds,
    );
    if (!mounted) return;
    setState(() => _adSettings = settings);
  }

  Future<void> _loadFontSize() async {
    final fontSize = await FontSizeService.load();
    if (!mounted) return;
    setState(() => _fontSize = fontSize);
  }

  Future<void> _checkAppVersion() async {
    final versionInfo = await VersionUpdateService.fetchVersionInfo(
        baseUrl: AppConfig.apiBaseUrl);
    if (!mounted) return;

    final packageInfo = await PackageInfo.fromPlatform();
    final currentVersion = packageInfo.version;
    final forceUpdate = VersionUpdateService.isUpdateRequired(
      currentVersion: currentVersion,
      minRequiredVersion: versionInfo.minRequiredVersion,
    );
    final updateAvailable = VersionUpdateService.isNewVersionAvailable(
      currentVersion: currentVersion,
      latestVersion: versionInfo.latestVersion,
    );

    if (forceUpdate || updateAvailable) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        showDialog(
          context: context,
          barrierDismissible: !forceUpdate,
          builder: (_) => AlertDialog(
            title: const Text('Update Available'),
            content: Text(
              forceUpdate
                  ? 'A required update is available. Please update to continue using the app.'
                  : 'A new version (${versionInfo.latestVersion}) is available. Would you like to update now?',
            ),
            actions: [
              if (!forceUpdate)
                TextButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('Later'),
                ),
              TextButton(
                onPressed: () async {
                  Navigator.of(context).pop();
                  final url = versionInfo.playStoreUrl.isNotEmpty
                      ? versionInfo.playStoreUrl
                      : versionInfo.appStoreUrl;
                  if (url.isNotEmpty) {
                    await launchUrl(Uri.parse(url),
                        mode: LaunchMode.externalApplication);
                  }
                },
                child: const Text('Update Now'),
              ),
            ],
          ),
        );
      });
    }
  }

  void _handleLanguageChanged(Locale locale) {
    setState(() {
      _locale = locale;
    });
  }

  void _handleFontSizeChanged(ArticleFontSize fontSize) {
    setState(() {
      _fontSize = fontSize;
    });
    FontSizeService.save(fontSize);
  }

  Future<void> _openAuthScreen() async {
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const AuthScreen()),
    );
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Digital Tech',
      locale: _locale,
      supportedLocales: LanguageService.supportedLocales,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      theme: ThemeData(useMaterial3: true),
      home: currentArticleId == null
          ? HomeScreen(
              adSettings: _adSettings,
              locale: _locale,
              fontSize: _fontSize,
              onLanguageChanged: _handleLanguageChanged,
              onFontSizeChanged: _handleFontSizeChanged,
              onOpenAuth: _openAuthScreen,
            )
          : ArticleDetailScreen(
              articleId: currentArticleId!,
              adSettings: _adSettings,
              fontSize: _fontSize,
              onFontSizeChanged: _handleFontSizeChanged,
              onExit: () => setState(() => currentArticleId = null),
            ),
    );
  }
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({
    super.key,
    required this.adSettings,
    required this.locale,
    required this.fontSize,
    required this.onLanguageChanged,
    required this.onFontSizeChanged,
    required this.onOpenAuth,
  });

  final AdSettings? adSettings;
  final Locale locale;
  final ArticleFontSize fontSize;
  final ValueChanged<Locale> onLanguageChanged;
  final ValueChanged<ArticleFontSize> onFontSizeChanged;
  final VoidCallback onOpenAuth;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final TextEditingController _searchController = TextEditingController();
  StreamSubscription<List<ConnectivityResult>>? _connectivitySubscription;
  Timer? _adminAccessTimer;
  List<ReadingHistoryItem> _recentlyRead = const [];
  List<ArticleSummary> _latestArticles = const [];
  List<ArticleCategory> _categories = const [];
  Set<int> _bookmarkedIds = const <int>{};
  int? _selectedCategoryId;
  String _searchQuery = '';
  bool _isLoadingLatestArticles = true;
  bool _isLoadingCategories = true;
  bool _isOffline = false;
  bool _adminAccessTriggered = false;
  bool _ignoreNextAccountTap = false;

  @override
  void initState() {
    super.initState();
    _connectivitySubscription =
        Connectivity().onConnectivityChanged.listen((result) {
      if (!mounted) return;
      _loadLatestArticles();
    });
    _loadRecentlyRead();
    _loadCategories();
    _loadBookmarkIds();
    _loadLatestArticles();
  }

  @override
  void dispose() {
    _connectivitySubscription?.cancel();
    _adminAccessTimer?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadCategories() async {
    try {
      final categories =
          await ArticleService.fetchCategories(baseUrl: AppConfig.apiBaseUrl);
      if (!mounted) return;
      setState(() {
        _categories = categories;
        _isLoadingCategories = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _categories = const [];
        _isLoadingCategories = false;
      });
    }
  }

  Future<void> _loadBookmarkIds() async {
    final ids = await BookmarkService.getBookmarkedIds();
    if (!mounted) return;
    setState(() {
      _bookmarkedIds = ids;
    });
  }

  Future<void> _loadLatestArticles() async {
    final isConnected = await ArticleService.hasInternetConnection();
    if (!mounted) return;

    if (!isConnected) {
      final cached = await ArticleService.getCachedArticles(
        search: _searchQuery,
        categoryId: _selectedCategoryId,
      );
      setState(() {
        _isOffline = true;
        _latestArticles = cached;
        _isLoadingLatestArticles = false;
      });
      return;
    }

    try {
      final articles = await ArticleService.fetchPublishedArticles(
        baseUrl: AppConfig.apiBaseUrl,
        search: _searchQuery,
        categoryId: _selectedCategoryId,
      );
      if (!mounted) return;
      setState(() {
        _isOffline = false;
        _latestArticles = articles;
        _isLoadingLatestArticles = false;
      });
    } catch (_) {
      if (!mounted) return;
      final cached = await ArticleService.getCachedArticles(
        search: _searchQuery,
        categoryId: _selectedCategoryId,
      );
      setState(() {
        _isOffline = true;
        _latestArticles = cached;
        _isLoadingLatestArticles = false;
      });
    }
  }

  Future<void> _refreshArticles() async {
    await _loadCategories();
    await _loadBookmarkIds();
    await _loadLatestArticles();
  }

  Future<void> _loadRecentlyRead() async {
    final items = await ReadingHistoryService.getRecentArticles();
    if (!mounted) return;
    setState(() {
      _recentlyRead = items;
    });
  }

  void _startAdminAccessHold({bool suppressAccountTap = true}) {
    _adminAccessTimer?.cancel();
    _adminAccessTriggered = false;
    _ignoreNextAccountTap = false;
    _adminAccessTimer = Timer(const Duration(seconds: 15), () {
      _adminAccessTimer = null;
      _adminAccessTriggered = true;
      _ignoreNextAccountTap = suppressAccountTap;
      unawaited(_openAdminLogin());
    });
  }

  void _cancelAdminAccessHold() {
    _adminAccessTimer?.cancel();
    _adminAccessTimer = null;
    if (!_adminAccessTriggered) {
      _ignoreNextAccountTap = false;
    }
  }

  Future<void> _openAdminLogin() async {
    final baseUri = Uri.tryParse(AppConfig.apiBaseUrl);
    if (baseUri == null || !baseUri.hasAuthority) return;
    await launchUrl(
      baseUri.resolve('/admin/login/'),
      mode: LaunchMode.externalApplication,
    );
  }

  void _handleAccountTap() {
    if (_ignoreNextAccountTap) {
      _ignoreNextAccountTap = false;
      _adminAccessTriggered = false;
      return;
    }
    widget.onOpenAuth();
  }

  Future<void> _openArticle(BuildContext context, String articleId) async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ArticleDetailScreen(
          articleId: articleId,
          adSettings: widget.adSettings,
          fontSize: widget.fontSize,
          onFontSizeChanged: widget.onFontSizeChanged,
        ),
      ),
    );
    await _loadRecentlyRead();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final shouldShowAds = widget.adSettings?.adsEnabled ?? false;

    return Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (widget.adSettings?.logoUrl != null) ...[
              Image.network(
                widget.adSettings!.logoUrl!,
                width: 32,
                height: 32,
                fit: BoxFit.contain,
                errorBuilder: (_, __, ___) => const SizedBox.shrink(),
              ),
              const SizedBox(width: 8),
            ],
            Text(l10n.appTitle),
          ],
        ),
        actions: [
          IconButton(
            tooltip: 'Saved',
            icon: const Icon(Icons.bookmark_outline),
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => BookmarksScreen(
                    onOpenArticle: (articleId) =>
                        _openArticle(context, articleId),
                  ),
                ),
              );
            },
          ),
          Listener(
            onPointerDown: (_) => _startAdminAccessHold(),
            onPointerUp: (_) => _cancelAdminAccessHold(),
            onPointerCancel: (_) => _cancelAdminAccessHold(),
            child: IconButton(
              tooltip: 'Account',
              icon: const Icon(Icons.person_outline),
              onPressed: _handleAccountTap,
            ),
          ),
          IconButton(
            tooltip: l10n.settings,
            icon: const Icon(Icons.settings_outlined),
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => SettingsScreen(
                    locale: widget.locale,
                    fontSize: widget.fontSize,
                    onLanguageChanged: widget.onLanguageChanged,
                    onFontSizeChanged: widget.onFontSizeChanged,
                    adSettings: widget.adSettings,
                  ),
                ),
              );
            },
          ),
        ],
      ),
      body: Column(
        children: [
          if (_isOffline)
            Container(
              width: double.infinity,
              margin: const EdgeInsets.fromLTRB(16, 16, 16, 0),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.red.shade50,
                border: Border.all(color: Colors.red.shade200),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  const Icon(Icons.signal_wifi_off, color: Colors.red),
                  const SizedBox(width: 10),
                  const Expanded(
                    child: Text(
                      'No Internet Connection',
                      style: TextStyle(fontWeight: FontWeight.w600),
                    ),
                  ),
                  TextButton(
                    onPressed: _loadLatestArticles,
                    child: const Text('Try Again'),
                  ),
                ],
              ),
            ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
            child: TextField(
              controller: _searchController,
              decoration: InputDecoration(
                hintText: 'Search by article name or code...',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _searchController.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () {
                          _searchController.clear();
                          setState(() {
                            _searchQuery = '';
                          });
                          _loadLatestArticles();
                        },
                      )
                    : null,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(14),
                ),
                filled: true,
              ),
              onChanged: (value) {
                setState(() {
                  _searchQuery = value;
                });
                _loadLatestArticles();
              },
              onSubmitted: (_) => _loadLatestArticles(),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: SizedBox(
              height: 42,
              child: _isLoadingCategories
                  ? const Center(
                      child: SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2)))
                  : ListView.separated(
                      scrollDirection: Axis.horizontal,
                      itemCount: _categories.length + 1,
                      separatorBuilder: (_, __) => const SizedBox(width: 8),
                      itemBuilder: (context, index) {
                        if (index == 0) {
                          final isSelected = _selectedCategoryId == null;
                          return ChoiceChip(
                            label: const Text('All'),
                            selected: isSelected,
                            onSelected: (_) {
                              setState(() => _selectedCategoryId = null);
                              _loadLatestArticles();
                            },
                          );
                        }

                        final category = _categories[index - 1];
                        final isSelected = _selectedCategoryId == category.id;
                        return ChoiceChip(
                          label: Text(category.name),
                          selected: isSelected,
                          onSelected: (_) {
                            setState(() => _selectedCategoryId =
                                isSelected ? null : category.id);
                            _loadLatestArticles();
                          },
                        );
                      },
                    ),
            ),
          ),
          if (_recentlyRead.isNotEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Recently Read',
                    style: TextStyle(
                      fontSize: FontSizeService.scale(widget.fontSize, 18),
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  SizedBox(
                    height: 120,
                    child: ListView.builder(
                      scrollDirection: Axis.horizontal,
                      itemCount: _recentlyRead.length,
                      itemBuilder: (context, index) {
                        final item = _recentlyRead[index];
                        return Container(
                          width: 180,
                          margin: const EdgeInsets.only(right: 12),
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: Colors.deepPurple.withOpacity(0.08),
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: InkWell(
                            onTap: () {
                              _openArticle(context, item.articleId);
                            },
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  item.title,
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                  style: TextStyle(
                                    fontWeight: FontWeight.w700,
                                    fontSize: FontSizeService.scale(
                                        widget.fontSize, 14),
                                  ),
                                ),
                                const Spacer(),
                                Text(
                                  '${item.readMinutes} min read',
                                  style: TextStyle(
                                    fontSize: FontSizeService.scale(
                                        widget.fontSize, 12),
                                    color: Colors.grey,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                ],
              ),
            ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: _refreshArticles,
              child: _isLoadingLatestArticles
                  ? const Center(child: CircularProgressIndicator())
                  : _latestArticles.isEmpty
                      ? ListView(
                          children: [
                            const SizedBox(height: 120),
                            Center(
                              child: Padding(
                                padding: const EdgeInsets.all(24),
                                child: Text(
                                  'No articles found for this filter.',
                                  style: TextStyle(
                                    fontSize: FontSizeService.scale(
                                        widget.fontSize, 16),
                                    color: Colors.grey,
                                  ),
                                ),
                              ),
                            ),
                          ],
                        )
                      : ListView.builder(
                          padding: const EdgeInsets.all(16),
                          itemCount: _latestArticles.length,
                          itemBuilder: (context, index) {
                            final article = _latestArticles[index];
                            final isNativeSlot = index == 2;

                            return Column(
                              children: [
                                if (isNativeSlot &&
                                    shouldShowAds &&
                                    widget
                                        .adSettings!.nativeAdUnitId.isNotEmpty)
                                  NativeAdWidget(
                                    adUnitId: widget.adSettings!.nativeAdUnitId,
                                  ),
                                Card(
                                  child: ListTile(
                                    title: Text(
                                      article.title,
                                      style: TextStyle(
                                          fontSize: FontSizeService.scale(
                                              widget.fontSize, 17)),
                                    ),
                                    subtitle: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        const SizedBox(height: 4),
                                        if (article.summary.isNotEmpty)
                                          Text(
                                            article.summary,
                                            maxLines: 2,
                                            overflow: TextOverflow.ellipsis,
                                            style: TextStyle(
                                                fontSize: FontSizeService.scale(
                                                    widget.fontSize, 13)),
                                          ),
                                        const SizedBox(height: 6),
                                        Text(
                                          '${article.categoryName} • ${article.viewsCount} views',
                                          style: TextStyle(
                                            fontSize: FontSizeService.scale(
                                                widget.fontSize, 12),
                                            color: Colors.grey,
                                          ),
                                        ),
                                      ],
                                    ),
                                    trailing: IconButton(
                                      icon: Icon(
                                        _bookmarkedIds.contains(article.id)
                                            ? Icons.bookmark
                                            : Icons.bookmark_border,
                                      ),
                                      onPressed: () async {
                                        await BookmarkService.toggleBookmark(
                                          articleId: article.id,
                                          title: article.title,
                                          summary: article.summary,
                                          categoryName: article.categoryName,
                                        );
                                        await _loadBookmarkIds();
                                      },
                                    ),
                                    onTap: () {
                                      _openArticle(
                                          context, article.id.toString());
                                    },
                                  ),
                                ),
                              ],
                            );
                          },
                        ),
            ),
          ),
          if (shouldShowAds && widget.adSettings!.bannerAdUnitId.isNotEmpty)
            BannerAdWidget(
              adUnitId: widget.adSettings!.bannerAdUnitId,
            ),
        ],
      ),
    );
  }
}
