import base64
from urllib.parse import urlsplit

from django.urls import reverse

from .models import SystemSetting


def _safe_navigation_url(value, fallback):
    if not isinstance(value, str):
        return fallback

    value = value.strip()
    if (
        not value
        or value.startswith('//')
        or '\\' in value
        or any(ord(character) < 32 for character in value)
    ):
        return fallback

    try:
        parsed = urlsplit(value)
    except ValueError:
        return fallback

    if parsed.scheme.lower() in {'http', 'https'}:
        return value if parsed.netloc and not parsed.username and not parsed.password else fallback
    if parsed.scheme.lower() in {'mailto', 'tel'}:
        return value if parsed.path and not parsed.netloc else fallback
    return value if not parsed.scheme and not parsed.netloc else fallback


def site_settings(request):
    settings = SystemSetting.get_instance()
    buttons = dict(SystemSetting.DEFAULT_UI_BUTTONS)
    ui_buttons = settings.ui_buttons
    if isinstance(ui_buttons, dict):
        for key, value in ui_buttons.items():
            if key in buttons and isinstance(value, dict):
                buttons[key] = {**buttons[key], **value}
            elif key not in buttons:
                buttons[key] = value
            elif value is not None:
                buttons[key] = value

    for key, default in SystemSetting.DEFAULT_UI_BUTTONS.items():
        button = buttons.get(key)
        if isinstance(button, dict):
            fallback_url = default.get('url', '/') if isinstance(default, dict) else '/'
            button = dict(button)
            button['url'] = _safe_navigation_url(button.get('url'), fallback_url)
            buttons[key] = button

    admin_login_url = reverse('admin:login')
    return {
        'site_settings': settings,
        'ui_buttons': buttons,
        'admin_login_url_encoded': base64.urlsafe_b64encode(admin_login_url.encode()).decode(),
    }
