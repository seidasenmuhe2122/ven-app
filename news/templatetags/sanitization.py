from django import template
from django.utils.safestring import mark_safe

from news.sanitization import sanitize_rich_text as clean_rich_text


register = template.Library()


@register.filter
def sanitize_html(value):
    return mark_safe(clean_rich_text(value))