import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_tts/flutter_tts.dart';

import '../config/app_config.dart';
import '../l10n/app_localizations.dart';
import '../services/ad_settings_service.dart';
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
  });

  final String articleId;
  final AdSettings? adSettings;
  final ArticleFontSize fontSize;
  final ValueChanged<ArticleFontSize>? onFontSizeChanged;

  @override
  State<ArticleDetailScreen> createState() => _ArticleDetailScreenState();
}

class _ArticleDetailScreenState extends State<ArticleDetailScreen> {
  final String baseUrl = AppConfig.apiBaseUrl;
  final TtsService _ttsService = TtsService();
  final ScrollController _scrollController = ScrollController();
  final List<String> _paragraphs = [
    'Breaking developments continue across the region as leaders weigh the economic impact of the latest policy shift.',
    'Industry analysts say the new direction could reshape consumer confidence, slow down short-term activity, and create new opportunities for long-term planning.',
    'From revised regulations to fresh spending patterns, the story is unfolding in ways that matter to both businesses and everyday readers.',
    'In this report, we examine what the decision means, how it may affect local communities, and why the timing matters for the broader market outlook.',
  ];

  bool _isPlaying = false;
  bool _isBookmarked = false;
  double _readingProgress = 0.0;
  bool _isPaused = false;
  double _rate = 1.0;
  int _activeParagraphIndex = 0;
  Timer? _progressTimer;
  final Duration _readingInterval = const Duration(milliseconds: 2000);

  @override
  void initState() {
    super.initState();
    _ttsService.initialize();
    _listenToTtsProgress();
    _loadBookmarkState();
    _saveReadHistory();
    _scrollController.addListener(_updateReadingProgress);
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
    final articleId = int.tryParse(widget.articleId);
    if (articleId == null) return;

    await BookmarkService.toggleBookmark(
      articleId: articleId,
      title: 'Royal Pro Article ${widget.articleId}',
      summary: _paragraphs.join(' '),
      categoryName: 'General',
    );

    if (!mounted) return;
    setState(() {
      _isBookmarked = !_isBookmarked;
    });
  }

  Future<void> _saveReadHistory() async {
    final articleText = _paragraphs.join(' ');
    await ReadingHistoryService.saveReadArticle(
      articleId: widget.articleId,
      title: 'Royal Pro Article ${widget.articleId}',
      summary: articleText,
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

    FlutterTts().progressHandler = (String text, int start, int end, String word) {
      if (!mounted) return;
      final totalLength = _paragraphs.join(' ').length;
      final progressRatio = (start + end) / totalLength;
      final index = (progressRatio * _paragraphs.length).floor();
      setState(() {
        _activeParagraphIndex = index.clamp(0, _paragraphs.length - 1);
      });
    };
  }

  Future<void> _play() async {
    if (_isPlaying) return;
    final articleText = _paragraphs.join(' ');
    await _ttsService.setRate(_rate);
    await _ttsService.speak(articleText);
    setState(() {
      _isPlaying = true;
      _isPaused = false;
    });

    _progressTimer?.cancel();
    _progressTimer = Timer.periodic(_readingInterval, (_) {
      if (!mounted) return;
      setState(() {
        _activeParagraphIndex = (_activeParagraphIndex + 1) % _paragraphs.length;
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
    await _ttsService.speak(_paragraphs.join(' '));
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
    final estimatedReadTime = ReadingHistoryService.estimateReadTime(articleText);
    final titleSize = FontSizeService.scale(widget.fontSize, 28);
    final bodySize = FontSizeService.scale(widget.fontSize, 16);
    final metaSize = FontSizeService.scale(widget.fontSize, 14);

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.article),
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
            icon: Icon(_isBookmarked ? Icons.bookmark : Icons.bookmark_border),
            onPressed: _toggleBookmark,
          ),
          PopupMenuButton<String>(
            tooltip: l10n.shareArticle,
            icon: const Icon(Icons.share),
            onSelected: (value) async {
              switch (value) {
                case 'general':
                  await ShareService.shareArticle(
                    title: 'Royal Pro Article',
                    articleId: widget.articleId,
                    baseUrl: baseUrl,
                  );
                  break;
                case 'telegram':
                  await ShareService.shareToTelegram(
                    title: 'Royal Pro Article',
                    articleId: widget.articleId,
                    baseUrl: baseUrl,
                  );
                  break;
                case 'whatsapp':
                  await ShareService.shareToWhatsApp(
                    title: 'Royal Pro Article',
                    articleId: widget.articleId,
                    baseUrl: baseUrl,
                  );
                  break;
                case 'facebook':
                  await ShareService.shareToFacebook(
                    title: 'Royal Pro Article',
                    articleId: widget.articleId,
                    baseUrl: baseUrl,
                  );
                  break;
                case 'x':
                  await ShareService.shareToX(
                    title: 'Royal Pro Article',
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
      body: Column(
        children: [
          LinearProgressIndicator(
            value: _readingProgress,
            minHeight: 5,
            backgroundColor: Colors.grey.shade200,
            valueColor: const AlwaysStoppedAnimation<Color>(Colors.deepPurple),
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
                              onPressed: _isPlaying ? null : _play,
                              icon: const Icon(Icons.play_arrow_rounded),
                              tooltip: l10n.play,
                            ),
                            IconButton(
                              onPressed: _isPaused ? _resume : _pause,
                              icon: Icon(_isPaused ? Icons.play_arrow_rounded : Icons.pause_rounded),
                              tooltip: _isPaused ? l10n.resume : l10n.pause,
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
                                DropdownMenuItem(value: 1.0, child: Text('1x')),
                                DropdownMenuItem(value: 1.5, child: Text('1.5x')),
                                DropdownMenuItem(value: 2.0, child: Text('2x')),
                              ],
                              onChanged: (value) {
                                if (value != null) _setRate(value);
                              },
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        LinearProgressIndicator(
                          value: (_activeParagraphIndex + 1) / _paragraphs.length,
                          minHeight: 6,
                          borderRadius: BorderRadius.circular(10),
                          backgroundColor: Colors.grey.shade300,
                          valueColor: const AlwaysStoppedAnimation<Color>(Colors.deepPurple),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 22),
                  Text(
                    l10n.articleDetailHeading,
                    style: TextStyle(
                      fontSize: titleSize,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
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
                  ...List.generate(_paragraphs.length, (index) {
                    final isActive = index == _activeParagraphIndex;
                    return Container(
                      margin: const EdgeInsets.only(bottom: 14),
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: isActive ? Colors.orange.withOpacity(0.12) : Colors.grey.shade50,
                        border: Border.all(
                          color: isActive ? Colors.orange : Colors.grey.shade200,
                          width: isActive ? 1.5 : 1,
                        ),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        _paragraphs[index],
                        style: TextStyle(
                          fontSize: bodySize,
                          height: 1.6,
                          fontWeight: isActive ? FontWeight.w700 : FontWeight.w400,
                          color: isActive ? Colors.deepPurple : Colors.black87,
                          backgroundColor: isActive ? Colors.orange.withOpacity(0.08) : null,
                        ),
                      ),
                    );
                  }),
                ],
              ),
            ),
          ),
          if ((widget.adSettings?.adsEnabled ?? true))
            BannerAdWidget(
              adUnitId: widget.adSettings?.bannerAdUnitId ?? 'ca-app-pub-3940256099942544/6300978111',
            ),
        ],
      ),
    );
  }
}
