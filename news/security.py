import hashlib
import logging

from django.conf import settings
from django.contrib.auth.signals import user_login_failed
from django.core.cache import cache
from django.dispatch import receiver
from rest_framework.throttling import BaseThrottle


logger = logging.getLogger(__name__)
LOGIN_PATHS = {
    f'/{settings.ADMIN_URL}login'.rstrip('/'),
    '/admin/login',
    '/api/login',
}


def get_client_ip(request):
    return BaseThrottle().get_ident(request) or 'unknown'


def login_failure_cache_keys(client_ip):
    client_hash = hashlib.sha256((client_ip or 'unknown').encode('utf-8')).hexdigest()
    return (
        f'auth-login-failures:{client_hash}',
        f'auth-login-block:{client_hash}',
    )


def is_login_ip_blocked(client_ip):
    _, block_key = login_failure_cache_keys(client_ip)
    return bool(cache.get(block_key))


def clear_login_failures(client_ip):
    cache.delete_many(login_failure_cache_keys(client_ip))


@receiver(user_login_failed, dispatch_uid='news.temporary_login_ip_lockout')
def record_failed_login(sender, credentials, request=None, **kwargs):
    if (
        request is None
        or request.method != 'POST'
        or request.path_info.rstrip('/') not in LOGIN_PATHS
    ):
        return

    client_ip = get_client_ip(request)

    failure_key, block_key = login_failure_cache_keys(client_ip)
    lockout_seconds = settings.AUTH_LOGIN_LOCKOUT_SECONDS

    try:
        if cache.add(failure_key, 1, timeout=lockout_seconds):
            failures = 1
        else:
            try:
                failures = cache.incr(failure_key)
            except ValueError:
                cache.set(failure_key, 1, timeout=lockout_seconds)
                failures = 1

        if failures >= settings.AUTH_LOGIN_FAILURE_LIMIT:
            cache.set(block_key, True, timeout=lockout_seconds)
    except Exception:
        logger.exception('Could not record failed login attempt.')