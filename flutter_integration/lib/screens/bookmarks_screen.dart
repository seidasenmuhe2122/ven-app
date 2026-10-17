import 'package:flutter/material.dart';

import '../services/bookmark_service.dart';

class BookmarksScreen extends StatefulWidget {
  const BookmarksScreen({super.key, required this.onOpenArticle});

  final ValueChanged<String> onOpenArticle;

  @override
  State<BookmarksScreen> createState() => _BookmarksScreenState();
}

class _BookmarksScreenState extends State<BookmarksScreen> {
  List<BookmarkedArticle> _bookmarks = const [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadBookmarks();
  }

  Future<void> _loadBookmarks() async {
    final bookmarks = await BookmarkService.getBookmarks();
    if (!mounted) return;
    setState(() {
      _bookmarks = bookmarks;
      _isLoading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Bookmarks'),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _bookmarks.isEmpty
              ? const Center(
                  child: Padding(
                    padding: EdgeInsets.all(24),
                    child: Text('No saved articles yet.'),
                  ),
                )
              : ListView.separated(
                  padding: const EdgeInsets.all(16),
                  itemCount: _bookmarks.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 12),
                  itemBuilder: (context, index) {
                    final article = _bookmarks[index];
                    return Card(
                      child: ListTile(
                        title: Text(article.title),
                        subtitle: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const SizedBox(height: 4),
                            Text(article.categoryName),
                            const SizedBox(height: 6),
                            if (article.summary.isNotEmpty)
                              Text(
                                article.summary,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                          ],
                        ),
                        onTap: () =>
                            widget.onOpenArticle(article.id.toString()),
                        trailing: IconButton(
                          icon: const Icon(Icons.delete_outline),
                          onPressed: () async {
                            await BookmarkService.removeBookmark(article.id);
                            await _loadBookmarks();
                          },
                        ),
                      ),
                    );
                  },
                ),
    );
  }
}
