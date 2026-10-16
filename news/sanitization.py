import bleach
from bleach.html5lib_shim import Filter


ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS).union({
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'p', 'br', 'hr', 'div', 'span',
    'ul', 'ol', 'li', 'blockquote',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'img',
})
ALLOWED_ATTRIBUTES = {
    **bleach.sanitizer.ALLOWED_ATTRIBUTES,
    '*': ['class', 'title'],
    'a': ['href', 'title', 'target', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'table': ['class'],
    'td': ['colspan', 'rowspan'],
    'th': ['colspan', 'rowspan'],
}
ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']


class SecureExternalLinkFilter(Filter):
    def __iter__(self):
        for token in self.source:
            if token['type'] == 'StartTag' and token['name'] == 'a':
                attributes = token['data']
                target = attributes.get((None, 'target'), '')
                if target.lower() == '_blank':
                    rel_values = set(attributes.get((None, 'rel'), '').lower().split())
                    rel_values.update({'noopener', 'noreferrer'})
                    attributes[(None, 'rel')] = ' '.join(sorted(rel_values))
            yield token


def sanitize_rich_text(value):
    cleaner = bleach.Cleaner(
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
        filters=[SecureExternalLinkFilter],
    )
    return cleaner.clean(value or '')
