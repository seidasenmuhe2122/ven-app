import hashlib
import logging
import re
from time import time

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse

from .security import clear_login_failures, get_client_ip, is_login_ip_blocked


logger = logging.getLogger(__name__)
ADMIN_LOGIN_PATH = f'/{settings.ADMIN_URL}login/'
ADMIN_LOGIN_PATHS = {ADMIN_LOGIN_PATH, '/admin/login/'}


class BrowserSecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault('X-XSS-Protection', '0')
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        return response


class EndpointRateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _rule_for_request(request):
        path = request.path_info
        method = request.method

        if path in ADMIN_LOGIN_PATHS and method == 'POST':
            return 'admin_login'
        if path in {'/', '/home/'} and method == 'GET':
            return 'web_search' if request.GET.get('search', '').strip() else 'public_home'
        if method == 'GET' and re.fullmatch(r'/article/[^/]+/', path):
            return 'article_detail'
        if path == '/api/dashboard-metrics/' and method == 'GET':
            return 'dashboard_metrics'
        if method == 'GET' and re.fullmatch(r'/api/article-notifications/\d+/', path):
            return 'article_notification'
        return None

    @staticmethod
    def _is_login_request(request):
        return (
            request.method == 'POST'
            and request.path_info in ADMIN_LOGIN_PATHS | {'/api/login/'}
        )

    @staticmethod
    def _limited_response(request, status_code, message):
        accept = request.headers.get('Accept', '')
        if request.path_info.startswith('/api/') or 'application/json' in accept:
            return JsonResponse({'detail': message}, status=status_code)
        return HttpResponse(message, status=status_code, content_type='text/plain; charset=utf-8')

    def __call__(self, request):
        is_login_request = self._is_login_request(request)
        client_ip = get_client_ip(request)

        if is_login_request:
            try:
                if is_login_ip_blocked(client_ip):
                    response = self._limited_response(
                        request,
                        429,
                        'Too many failed login attempts. Please try again later.',
                    )
                    response['Retry-After'] = str(settings.AUTH_LOGIN_LOCKOUT_SECONDS)
                    return response
            except Exception:
                logger.exception('Login lockout cache unavailable.')
                return self._limited_response(
                    request,
                    503,
                    'Login is temporarily unavailable. Please try again shortly.',
                )

        rule_name = self._rule_for_request(request)
        if rule_name is not None:
            rule = settings.APPLICATION_RATE_LIMITS[rule_name]
            limit = rule['limit']
            period = rule['period']
            now = int(time())
            window = now // period
            ttl = max(1, period - (now % period))
            client_hash = hashlib.sha256(client_ip.encode('utf-8')).hexdigest()
            cache_key = f'app-rate-limit:{rule_name}:{client_hash}:{window}'

            try:
                if cache.add(cache_key, 1, timeout=ttl):
                    request_count = 1
                else:
                    try:
                        request_count = cache.incr(cache_key)
                    except ValueError:
                        cache.set(cache_key, 1, timeout=ttl)
                        request_count = 1
            except Exception:
                logger.exception('Rate-limit cache unavailable for rule %s.', rule_name)
                return self._limited_response(
                    request,
                    503,
                    'This endpoint is temporarily unavailable. Please try again shortly.',
                )

            if request_count > limit:
                response = self._limited_response(
                    request,
                    429,
                    'Too many requests. Please try again later.',
                )
                response['Retry-After'] = str(ttl)
                return response

        response = self.get_response(request)
        if is_login_request and (
            (request.path_info == '/api/login/' and response.status_code == 200)
            or (request.path_info in ADMIN_LOGIN_PATHS and 300 <= response.status_code < 400)
        ):
            try:
                clear_login_failures(client_ip)
            except Exception:
                logger.exception('Could not reset successful login failure counter.')
        return response