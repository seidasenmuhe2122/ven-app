import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_tts/flutter_tts.dart';

import '../config/app_config.dart';
import '../l10n/app_localizations.dart';
import '../services/ad_settings_service.dart';
import '../services/article_service.dart';
import '../services/bookmark_service.dart';
import '../services/font_size_service.dart';
import '../services/reading_history_service.dart';
import '../services/review_service.dart';
import '../services/share_service.dart';
import '../services/tts_service.dart';
import '../widgets/banner_ad_widget.dart';

class ArticleDetailScreen extends StatefulWidget {
  const ArticleDetailScreen({
    super.key,
    required this.articleId,
    this.adSettings,
    this.fontSize = ArticleFontSize.medium,
    this.onFontSizeChanged,
    this.onExit,
  });

  final String articleId;
  final AdSettings? adSettings;
  final ArticleFontSize fontSize;
  final ValueChanged<ArticleFontSize>? onFontSizeChanged;
  final VoidCallback? onExit;

  @override
  State<ArticleDetailScreen> createState() => _ArticleDetailScreenState();
}

class _ArticleDetailScreenState extends State<ArticleDetailScreen> {
  final String baseUrl = AppConfig.apiBaseUrl;
  final TtsService _ttsService = TtsService();
  final ScrollController _scrollController = ScrollController();
  ArticleDetail? _article;
  Object? _loadError;
  bool _isLoading = true;

  bool _isPlaying = false;
  bool _isBookmarked = false;
  double _readingProgress = 0.0;
  bool _isPaused = false;
  double _rate = 1.0;
  int _activeParagraphIndex = 0;
  Timer? _progressTimer;
  final Duration _readingInterval = const Duration(milliseconds: 2000);

  List<String> get _paragraphs => _article?.paragraphs ?? const [];
  String get _articleText => _paragraphs.join(' ');

  @override
  void initState() {
    super.initState();
    _ttsService.initialize();
    _listenToTtsProgress();
    _loadBookmarkState();
    _loadArticle();
    _scrollController.addListener(_updateReadingProgress);
  }

  Future<void> _loadArticle() async {
    setState(() {
      _isLoading = true;
      _loadError = null;
    });

    try {
      final article = await ArticleService.fetchArticleById(
        articleId: widget.articleId,
        baseUrl: baseUrl,
      );
      if (!mounted) return;
      setState(() {
        _article = article;
        _isLoading = false;
      });
      await _saveReadHistory(article);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loadError = error;
        _isLoading = false;
      });
    }
  }

  Future<void> _loadBookmarkState() async {
    final articleId = int.tryParse(widget.articleId);
    if (articleId == null) return;
    final isSaved = await BookmarkService.isBookmarked(articleId);
    if (!mounted) return;
    setState(() {
      _isBookmarked = isSaved;
    });
  }

  Future<void> _toggleBookmark() async {
    final article = _article;
    if (article == null) return;

    await BookmarkService.toggleBookmark(
      articleId: article.id,
      title: article.title,
      summary: article.summary,
      categoryName: article.categoryName,
    );

    if (!mounted) return;
    setState(() {
      _isBookmarked = !_isBookmarked;
    });
  }

  Future<void> _saveReadHistory(ArticleDetail article) async {
    await ReadingHistoryService.saveReadArticle(
      articleId: article.id.toString(),
      title: article.title,
      summary: article.summary.isNotEmpty ? article.summary : article.content,
    );
    await ReviewService.registerArticleRead();
  }

  void _updateReadingProgress() {
    if (!_scrollController.hasClients) return;

    final maxScrollExtent = _scrollController.position.maxScrollExtent;
    final progress = maxScrollExtent <= 0
        ? 0.0
        : (_scrollController.offset / maxScrollExtent).clamp(0.0, 1.0);

    if (progress != _readingProgress && mounted) {
      setState(() {
        _readingProgress = progress;
      });
    }
  }

  void _listenToTtsProgress() {
    FlutterTts().completionHandler = () {
      if (mounted) {
        setState(() {
          _isPlaying = false;
          _isPaused = false;
        });
      }
    };

    FlutterTts().progressHandler =
        (String text, int start, int end, String word) {
      if (!mounted || _paragraphs.isEmpty) return;
      final totalLength = _articleText.length;
      if (totalLength == 0) return;
      final progressRatio = (start + end) / totalLength;
      final index = (progressRatio * _paragraphs.length).floor();
      setState(() {
        _activeParagraphIndex = index.clamp(0, _paragraphs.length - 1);
      });
    };
  }

  Future<void> _play() async {
    if (_isPlaying || _articleText.isEmpty) return;
    await _ttsService.setRate(_rate);
    await _ttsService.speak(_articleText);
    setState(() {
      _isPlaying = true;
      _isPaused = false;
    });

    _progressTimer?.cancel();
    _progressTimer = Timer.periodic(_readingInterval, (_) {
      if (!mounted || _paragraphs.isEmpty) return;
      setState(() {
        _activeParagraphIndex =
            (_activeParagraphIndex + 1) % _paragraphs.length;
      });
    });
  }

  Future<void> _pause() async {
    await _ttsService.pause();
    _progressTimer?.cancel();
    setState(() {
      _isPlaying = false;
      _isPaused = true;
    });
  }

  Future<void> _resume() async {
    if (!_isPaused) return;
    await _ttsService.speak(_articleText);
    setState(() {
      _isPlaying = true;
      _isPaused = false;
    });
  }

  Future<void> _stop() async {
    await _ttsService.stop();
    _progressTimer?.cancel();
    setState(() {
      _isPlaying = false;
      _isPaused = false;
      _activeParagraphIndex = 0;
    });
  }

  void _setRate(double rate) {
    setState(() {
      _rate = rate;
    });
    _ttsService.setRate(rate);
  }

  @override
  void dispose() {
    _progressTimer?.cancel();
    _scrollController.dispose();
    _ttsService.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final articleText = _paragraphs.join(' ');
    final estimatedReadTime =
        ReadingHistoryService.estimateReadTime(articleText);
    final titleSize = FontSizeService.scale(widget.fontSize, 28);
    final bodySize = FontSizeService.scale(widget.fontSize, 16);
    final metaSize = FontSizeService.scale(widget.fontSize, 14);

    return PopScope<void>(
      canPop: widget.onExit == null,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) widget.onExit?.call();
      },
      child: Scaffold(
        appBar: AppBar(
          leading: widget.onExit == null
              ? null
              : IconButton(
                  tooltip: 'Back',
                  icon: const Icon(Icons.arrow_back),
                  onPressed: widget.onExit,
                ),
          title: Text(_article?.title ?? l10n.article),
          actions: [
            DropdownButton<ArticleFontSize>(
              value: widget.fontSize,
              underline: const SizedBox(),
              icon: const Icon(Icons.text_fields_rounded),
              items: ArticleFontSize.values.map((fontSize) {
                return DropdownMenuItem<ArticleFontSize>(
                  value: fontSize,
                  child: Text(fontSize.label),
                );
              }).toList(),
              onChanged: (value) {
                if (value != null && widget.onFontSizeChanged != null) {
                  widget.onFontSizeChanged!(value);
                }
              },
            ),
            IconButton(
              tooltip: _isBookmarked ? 'Remove bookmark' : 'Save article',
              icon:
                  Icon(_isBookmarked ? Icons.bookmark : Icons.bookmark_border),
              onPressed: _article == null ? null : _toggleBookmark,
            ),
            PopupMenuButton<String>(
              tooltip: l10n.shareArticle,
              icon: const Icon(Icons.share),
              onSelected: (value) async {
                switch (value) {
                  case 'general':
                    await ShareService.shareArticle(
                      title: _article?.title ?? 'Digital Tech',
                      articleId: widget.articleId,
                      baseUrl: baseUrl,
                    );
                    break;
                  case 'telegram':
                    await ShareService.shareToTelegram(
                      title: _article?.title ?? 'Digital Tech',
                      articleId: widget.articleId,
                      baseUrl: baseUrl,
                    );
                    break;
                  case 'whatsapp':
                    await ShareService.shareToWhatsApp(
                      title: _article?.title ?? 'Digital Tech',
                      articleId: widget.articleId,
                      baseUrl: baseUrl,
                    );
                    break;
                  case 'facebook':
                    await ShareService.shareToFacebook(
                      title: _article?.title ?? 'Digital Tech',
                      articleId: widget.articleId,
                      baseUrl: baseUrl,
                    );
                    break;
                  case 'x':
                    await ShareService.shareToX(
                      title: _article?.title ?? 'Digital Tech',
                      articleId: widget.articleId,
                      baseUrl: baseUrl,
                    );
                    break;
                }
              },
              itemBuilder: (context) => const [
                PopupMenuItem(value: 'general', child: Text('Share')),
                PopupMenuItem(value: 'telegram', child: Text('Telegram')),
                PopupMenuItem(value: 'whatsapp', child: Text('WhatsApp')),
                PopupMenuItem(value: 'facebook', child: Text('Facebook')),
                PopupMenuItem(value: 'x', child: Text('X')),
              ],
            ),
          ],
        ),
        body: _isLoading
            ? const Center(child: CircularProgressIndicator())
            : _loadError != null
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.article_outlined, size: 40),
                          const SizedBox(height: 12),
                          const Text('Unable to load this article.'),
                          const SizedBox(height: 8),
                          Text(
                            _loadError.toString(),
                            textAlign: TextAlign.center,
                          ),
                          const SizedBox(height: 16),
                          FilledButton.icon(
                            onPressed: _loadArticle,
                            icon: const Icon(Icons.refresh),
                            label: const Text('Try again'),
                          ),
                        ],
                      ),
                    ),
                  )
                : Column(
                    children: [
                      LinearProgressIndicator(
                        value: _readingProgress,
                        minHeight: 5,
                        backgroundColor: Colors.grey.shade200,
                        valueColor: const AlwaysStoppedAnimation<Color>(
                            Colors.deepPurple),
                      ),
                      Expanded(
                        child: SingleChildScrollView(
                          controller: _scrollController,
                          padding: const EdgeInsets.all(20),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Container(
                                padding: const EdgeInsets.all(12),
                                decoration: BoxDecoration(
                                  color: Colors.deepPurple.withOpacity(0.08),
                                  borderRadius: BorderRadius.circular(16),
                                ),
                                child: Column(
                                  children: [
                                    Row(
                                      children: [
                                        IconButton(
                                          onPressed:
                                              _isPlaying || _paragraphs.isEmpty
                                                  ? null
                                                  : _play,
                                          icon: const Icon(
                                              Icons.play_arrow_rounded),
                                          tooltip: l10n.play,
                                        ),
                                        IconButton(
                                          onPressed:
                                              _isPaused ? _resume : _pause,
                                          icon: Icon(_isPaused
                                              ? Icons.play_arrow_rounded
                                              : Icons.pause_rounded),
                                          tooltip: _isPaused
                                              ? l10n.resume
                                              : l10n.pause,
                                        ),
                                        IconButton(
                                          onPressed: _stop,
                                          icon: const Icon(Icons.stop_rounded),
                                          tooltip: l10n.stop,
                                        ),
                                        const Spacer(),
                                        DropdownButton<double>(
                                          value: _rate,
                                          underline: const SizedBox(),
                                          items: const [
                                            DropdownMenuItem(
                                                value: 1.0, child: Text('1x')),
                                            DropdownMenuItem(
                                                value: 1.5,
                                                child: Text('1.5x')),
                                            DropdownMenuItem(
                                                value: 2.0, child: Text('2x')),
                                          ],
                                          onChanged: (value) {
                                            if (value != null) _setRate(value);
                                          },
                                        ),
                                      ],
                                    ),
                                    const SizedBox(height: 8),
                                    LinearProgressIndicator(
                                      value: _paragraphs.isEmpty
                                          ? 0
                                          : (_activeParagraphIndex + 1) /
                                              _paragraphs.length,
                                      minHeight: 6,
                                      borderRadius: BorderRadius.circular(10),
                                      backgroundColor: Colors.grey.shade300,
                                      valueColor:
                                          const AlwaysStoppedAnimation<Color>(
                                              Colors.deepPurple),
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(height: 22),
                              Text(
                                _article?.title ?? l10n.articleDetailHeading,
                                style: TextStyle(
                                  fontSize: titleSize,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              if (_article?.categoryName.isNotEmpty ??
                                  false) ...[
                                const SizedBox(height: 8),
                                Text(_article!.categoryName,
                                    style: TextStyle(
                                        fontSize: metaSize,
                                        color: Colors.grey)),
                              ],
                              const SizedBox(height: 8),
                              Text(
                                '$estimatedReadTime min read',
                                style: TextStyle(
                                  fontSize: metaSize,
                                  color: Colors.grey,
                                ),
                              ),
                              const SizedBox(height: 16),
                              Text(
                                '${l10n.articleId}: ${widget.articleId}',
                                style: TextStyle(fontSize: metaSize),
                              ),
                              const SizedBox(height: 8),
                              Text(
                                '${l10n.deepLinkResolved}: $baseUrl/article/${widget.articleId}',
                                style: TextStyle(fontSize: metaSize),
                              ),
                              const SizedBox(height: 24),
                              if (_paragraphs.isEmpty)
                                const Text('Article content is not available.')
                              else
                                ...List.generate(_paragraphs.length, (index) {
                                  final isActive =
                                      index == _activeParagraphIndex;
                                  return Container(
                                    margin: const EdgeInsets.only(bottom: 14),
                                    padding: const EdgeInsets.all(14),
                                    decoration: BoxDecoration(
                                      color: isActive
                                          ? Colors.orange.withOpacity(0.12)
                                          : Colors.grey.shade50,
                                      border: Border.all(
                                        color: isActive
                                            ? Colors.orange
                                            : Colors.grey.shade200,
                                        width: isActive ? 1.5 : 1,
                                      ),
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                    child: Text(
                                      _paragraphs[index],
                                      style: TextStyle(
                                        fontSize: bodySize,
                                        height: 1.6,
                                        fontWeight: isActive
                                            ? FontWeight.w700
                                            : FontWeight.w400,
                                        color: isActive
                                            ? Colors.deepPurple
                                            : Colors.black87,
                                        backgroundColor: isActive
                                            ? Colors.orange.withOpacity(0.08)
                                            : null,
                                      ),
                                    ),
                                  );
                                }),
                            ],
                          ),
                        ),
                      ),
                      if ((widget.adSettings?.adsEnabled ?? false) &&
                          widget.adSettings!.bannerAdUnitId.isNotEmpty)
                        BannerAdWidget(
                          adUnitId: widget.adSettings!.bannerAdUnitId,
                        ),
                    ],
                  ),
      ),
    );
  }
}
