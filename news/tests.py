import json
import re

from django.conf import settings as django_settings
from django.contrib import admin
from django.contrib.auth.signals import user_login_failed
from django.contrib.auth.models import Permission
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError

from accounts.models import AdSenseReport, CustomUser
from .models import (
    AnalyticsEvent,
    Article,
    ArticleBookmark,
    ArticleLike,
    AuditLog,
    Category,
    Comment,
    DashboardWidgetConfig,
    Feedback,
    PushNotification,
    SystemSetting,
    UserReport,
)
from .serializers import SystemSettingSerializer
from .serializers import RegisterSerializer
from .services import DashboardAnalyticsService
from .middleware import EndpointRateLimitMiddleware
from .security import login_failure_cache_keys
from .admin import (
    ArticleAdminForm,
    ArticleAdmin,
    CommentAdminForm,
    FeedbackAdminForm,
    NewsletterBroadcastAdminForm,
    PushNotificationAdminForm,
    SystemSettingAdminForm,
    UserReportAdminForm,
)


def admin_path(suffix=''):
    return f'/{django_settings.ADMIN_URL}{suffix.lstrip("/")}'


class SecurityBoundaryTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Security')
        self.subscriber = CustomUser.objects.create_user(
            username='security-subscriber', password='secret123', role=CustomUser.ROLE_SUBSCRIBER,
        )
        self.author = CustomUser.objects.create_user(
            username='security-author', password='secret123', role=CustomUser.ROLE_AUTHOR,
        )
        self.editor = CustomUser.objects.create_user(
            username='security-editor', password='secret123', role=CustomUser.ROLE_EDITOR,
        )

    def test_subscriber_cannot_mutate_taxonomy_or_create_articles(self):
        self.client.force_login(self.subscriber)

        category_response = self.client.post('/api/categories/', {'name': 'Forbidden'}, content_type='application/json')
        tag_response = self.client.post('/api/tags/', {'name': 'Forbidden'}, content_type='application/json')
        article_response = self.client.post(
            '/api/articles/',
            {'title': 'Forbidden', 'content': '<script>alert(1)</script>', 'category': self.category.pk, 'status': 'published'},
            content_type='application/json',
        )

        self.assertEqual(category_response.status_code, 403)
        self.assertEqual(tag_response.status_code, 403)
        self.assertEqual(article_response.status_code, 403)

    @override_settings(AUTH_LOGIN_FAILURE_LIMIT=20)
    def test_token_login_is_rate_limited(self):
        cache.clear()
        credentials = json.dumps({'username': self.subscriber.username, 'password': 'incorrect-password'})
        responses = [
            self.client.post('/api/login/', credentials, content_type='application/json')
            for _ in range(11)
        ]

        self.assertTrue(all(response.status_code == 400 for response in responses[:10]))
        self.assertEqual(responses[-1].status_code, 429)

    def test_registration_is_rate_limited(self):
        self.client.defaults['REMOTE_ADDR'] = '192.0.2.81'
        responses = [
            self.client.post('/api/register/', {}, content_type='application/json')
            for _ in range(6)
        ]

        self.assertTrue(all(response.status_code == 400 for response in responses[:5]))
        self.assertEqual(responses[-1].status_code, 429)

    def test_feedback_is_rate_limited(self):
        self.client.defaults['REMOTE_ADDR'] = '192.0.2.82'
        responses = [
            self.client.post('/api/feedback/', {}, content_type='application/json')
            for _ in range(11)
        ]

        self.assertTrue(all(response.status_code == 400 for response in responses[:10]))
        self.assertEqual(responses[-1].status_code, 429)

    def test_author_cannot_manage_taxonomy_or_view_staff_analytics(self):
        self.client.force_login(self.author)

        category_response = self.client.post(
            '/api/categories/', {'name': 'Author-only category'}, content_type='application/json',
        )
        tag_response = self.client.post(
            '/api/tags/', {'name': 'author-only-tag'}, content_type='application/json',
        )
        stats_response = self.client.get('/api/dashboard-stats/')
        widgets_response = self.client.get('/api/dashboard/widgets/')
        analytics_response = self.client.get('/api/admin/analytics/')
        metrics_response = self.client.get('/api/dashboard-metrics/')
        audit_response = self.client.get('/api/audit-logs/')

        self.assertEqual(category_response.status_code, 403)
        self.assertEqual(tag_response.status_code, 403)
        self.assertEqual(stats_response.status_code, 403)
        self.assertEqual(widgets_response.status_code, 403)
        self.assertEqual(analytics_response.status_code, 403)
        self.assertEqual(metrics_response.status_code, 403)
        self.assertEqual(audit_response.status_code, 403)

    def test_editor_retains_taxonomy_management_access(self):
        self.client.force_login(self.editor)

        category_response = self.client.post(
            '/api/categories/', {'name': 'Editor-managed category'}, content_type='application/json',
        )
        tag_response = self.client.post(
            '/api/tags/', {'name': 'editor-managed-tag'}, content_type='application/json',
        )

        self.assertEqual(category_response.status_code, 201, category_response.content)
        self.assertEqual(tag_response.status_code, 201, tag_response.content)

    def test_author_articles_stay_under_review_and_cannot_be_deleted(self):
        self.client.force_login(self.author)
        response = self.client.post(
            '/api/articles/',
            {'title': 'Review me', 'content': 'Article body', 'category': self.category.pk, 'status': 'published'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201, response.content)
        article = Article.objects.get(title='Review me')
        self.assertEqual(article.status, Article.STATUS_UNDER_REVIEW)
        self.assertEqual(article.author_id, self.author.pk)

        update = self.client.patch(
            f'/api/articles/{article.pk}/', {'status': 'published'}, content_type='application/json',
        )
        self.assertEqual(update.status_code, 200)
        article.refresh_from_db()
        self.assertEqual(article.status, Article.STATUS_UNDER_REVIEW)

        delete = self.client.delete(f'/api/articles/{article.pk}/')
        self.assertEqual(delete.status_code, 403)

    def test_author_cannot_bypass_article_status_rules_with_admin_actions(self):
        article = Article.objects.create(
            title='Published author story',
            content='Story body',
            category=self.category,
            author=self.author,
            status=Article.STATUS_PUBLISHED,
        )
        notification = PushNotification.objects.get(article_id=article.pk)
        request = RequestFactory().post(admin_path('news/article/'))
        SessionMiddleware(lambda request: None).process_request(request)
        request.user = self.author
        request._messages = FallbackStorage(request)
        article_admin = ArticleAdmin(Article, admin.site)
        queryset = Article.objects.filter(pk=article.pk)

        article_admin.mark_as_draft(request, queryset)
        article.refresh_from_db()
        self.assertEqual(article.status, Article.STATUS_PUBLISHED)

        article_admin.mark_as_archived(request, queryset)
        article.refresh_from_db()
        self.assertEqual(article.status, Article.STATUS_PUBLISHED)

        article_admin.send_article_notifications(request, queryset)
        notification.refresh_from_db()
        self.assertFalse(notification.is_sent)

    def test_subscriber_cannot_view_or_mutate_dashboard_data(self):
        self.client.force_login(self.subscriber)

        stats = self.client.get('/api/dashboard-stats/')
        widgets = self.client.get('/api/dashboard/widgets/')
        create_widget = self.client.post('/api/dashboard/widgets/', {'widget_type': 'metric'}, content_type='application/json')

        self.assertEqual(stats.status_code, 403)
        self.assertEqual(widgets.status_code, 403)
        self.assertEqual(create_widget.status_code, 403)

    def test_non_staff_settings_response_excludes_operational_secrets(self):
        settings = SystemSetting.get_instance()
        settings.admob_app_id = 'secret-app-id'
        settings.ad_networks = [{'placement': 'secret-placement'}]
        settings.save()
        self.client.force_login(self.subscriber)

        response = self.client.get('/api/settings/')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        setting = payload['results'][0] if 'results' in payload else payload[0]
        self.assertNotIn('admob_app_id', setting)
        self.assertNotIn('ad_networks', setting)

    def test_rich_text_is_sanitized_before_public_rendering(self):
        article = Article.objects.create(
            title='Sanitized story',
            content='<p>Safe</p><script>alert(1)</script><a href="javascript:alert(1)">Unsafe</a>',
            category=self.category,
            status=Article.STATUS_PUBLISHED,
        )

        self.assertEqual(article.content, '<p>Safe</p>alert(1)<a>Unsafe</a>')
        self.assertNotIn('<script', article.content)
        self.assertNotIn('javascript:', article.content)

    def test_rich_text_new_tab_links_are_protected_from_tabnabbing(self):
        article = Article.objects.create(
            title='Safe external link',
            content='<a href="https://example.com" target="_blank">External source</a>',
            category=self.category,
            status=Article.STATUS_PUBLISHED,
        )

        self.assertIn('target="_blank"', article.content)
        self.assertIn('rel="noopener noreferrer"', article.content)

    def test_homepage_survives_malformed_ui_button_settings(self):
        settings = SystemSetting.get_instance()
        settings.ui_buttons = ['not', 'a', 'dict']
        settings.save()

        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Home')
        self.assertContains(response, 'Latest')
        self.assertNotContains(response, f'href="{admin_path()}"')

    def test_public_pages_do_not_expose_admin_login_path_as_plain_text(self):
        response = self.client.get('/')

        self.assertContains(response, 'data-admin-login-encoded=')
        self.assertNotContains(response, admin_path('login/'))


class CSRFSecurityTests(TestCase):
    def setUp(self):
        self.editor = CustomUser.objects.create_user(
            username='csrf-editor',
            password='secret123',
            role=CustomUser.ROLE_EDITOR,
        )

    def test_public_mutation_apis_reject_form_encoded_requests(self):
        for path in ('/api/login/', '/api/register/', '/api/feedback/'):
            with self.subTest(path=path):
                response = self.client.post(path, {'username': 'attacker', 'message': 'spam'})
                self.assertEqual(response.status_code, 415)

    def test_session_authenticated_api_mutation_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.editor)
        payload = json.dumps({'name': 'Session category'})

        rejected = client.post('/api/categories/', payload, content_type='application/json')
        self.assertEqual(rejected.status_code, 403)

        csrf_token = 'a' * 32
        client.cookies['csrftoken'] = csrf_token
        accepted = client.post(
            '/api/categories/',
            payload,
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(accepted.status_code, 201, accepted.content)

    def test_token_authenticated_api_mutation_uses_authorization_header(self):
        token, _ = Token.objects.get_or_create(user=self.editor)
        client = Client(enforce_csrf_checks=True)

        response = client.post(
            '/api/categories/',
            json.dumps({'name': 'Token category'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Token {token.key}',
        )

        self.assertEqual(response.status_code, 201, response.content)


class XSSAndSecurityHeadersTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='XSS checks')

    def test_response_security_headers_and_matching_csp_nonce(self):
        response = self.client.get('/')
        content = response.content.decode()
        content_security_policy = response['Content-Security-Policy']
        nonce_match = re.search(r'<script nonce="([^"]+)"', content)

        self.assertEqual(response['X-XSS-Protection'], '0')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response['X-Frame-Options'], 'DENY')
        self.assertEqual(response['Referrer-Policy'], 'same-origin')
        self.assertIsNotNone(nonce_match)
        self.assertIn(f"'nonce-{nonce_match.group(1)}'", content_security_policy)
        self.assertNotIn("'unsafe-inline'", content_security_policy.split('script-src', 1)[1].split(';', 1)[0])

    def test_hsts_is_sent_for_https_responses(self):
        with override_settings(
            SECURE_HSTS_SECONDS=3600,
            SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
            SECURE_HSTS_PRELOAD=True,
        ):
            response = self.client.get('/', secure=True)

        self.assertIn('max-age=3600', response['Strict-Transport-Security'])
        self.assertIn('includeSubDomains', response['Strict-Transport-Security'])
        self.assertIn('preload', response['Strict-Transport-Security'])

    def test_session_and_csrf_cookie_security_settings(self):
        self.assertTrue(django_settings.SESSION_COOKIE_HTTPONLY)
        self.assertTrue(django_settings.CSRF_COOKIE_HTTPONLY)
        self.assertEqual(django_settings.SESSION_COOKIE_SAMESITE, 'Lax')
        self.assertEqual(django_settings.CSRF_COOKIE_SAMESITE, 'Lax')
        self.assertEqual(django_settings.SESSION_COOKIE_SECURE, django_settings.SECURE_MODE)
        self.assertEqual(django_settings.CSRF_COOKIE_SECURE, django_settings.SECURE_MODE)

    def test_admin_and_analytics_inline_blocks_receive_csp_nonces(self):
        admin_user = CustomUser.objects.create_user(
            username='csp-admin',
            password='secret123',
            role=CustomUser.ROLE_SUPERADMIN,
        )
        self.client.force_login(admin_user)

        admin_response = self.client.get(admin_path())
        admin_content = admin_response.content.decode()
        self.assertEqual(admin_response.status_code, 200)
        self.assertRegex(admin_content, r'<style nonce="[^"]+">')
        self.assertRegex(admin_content, r'<script nonce="[^"]+">\s*const dashboardData')

        analytics_response = self.client.get('/api/admin/analytics/', HTTP_ACCEPT='text/html')
        analytics_content = analytics_response.content.decode()
        self.assertEqual(analytics_response.status_code, 200)
        self.assertRegex(analytics_content, r'<script nonce="[^"]+">\s*const data')
        self.assertContains(analytics_response, 'createElementNS')
        self.assertNotContains(analytics_response, 'points.innerHTML')

    def test_unsafe_configured_navigation_url_falls_back_to_safe_url(self):
        settings = SystemSetting.get_instance()
        settings.ui_buttons = {
            **SystemSetting.DEFAULT_UI_BUTTONS,
            'home': {'label': 'Home', 'url': 'javascript:alert(1)'},
        }
        settings.save()

        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'href="javascript:')
        self.assertContains(response, 'href="/"')

    def test_unsafe_stored_rich_text_is_sanitized_before_render(self):
        article = Article.objects.create(
            title='Unsafe stored article',
            content='Safe placeholder',
            category=self.category,
            status=Article.STATUS_PUBLISHED,
        )
        Article.objects.filter(pk=article.pk).update(
            content='<p>Safe content</p><img src="x" onerror="alert(1)"><script>alert(1)</script>',
        )
        SystemSetting.get_instance()
        SystemSetting.objects.filter(pk=1).update(
            about_content='<p>Safe policy</p><img src="x" onerror="alert(1)">',
        )

        response = self.client.get(f'/article/{article.slug}/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<p>Safe content</p>')
        self.assertContains(response, '<p>Safe policy</p>')
        self.assertNotContains(response, 'onerror=')
        self.assertNotContains(response, '<script>alert(1)</script>')


class EndpointRateLimitMiddlewareTests(TestCase):
    def setUp(self):
        cache.clear()
        self.forwarded_requests = 0
        self.middleware = EndpointRateLimitMiddleware(self._get_response)
        self.request_factory = RequestFactory()

    def _get_response(self, request):
        self.forwarded_requests += 1
        return HttpResponse(status=204)

    @override_settings(APPLICATION_RATE_LIMITS={'admin_login': {'limit': 1, 'period': 60}})
    def test_admin_login_returns_429_with_retry_after(self):
        first_response = self.middleware(self.request_factory.post(admin_path('login/')))
        limited_response = self.middleware(self.request_factory.post(admin_path('login/')))

        self.assertEqual(first_response.status_code, 204)
        self.assertEqual(limited_response.status_code, 429)
        self.assertIn('Retry-After', limited_response)
        self.assertEqual(self.forwarded_requests, 1)

    @override_settings(APPLICATION_RATE_LIMITS={'web_search': {'limit': 1, 'period': 60}})
    def test_search_returns_429_after_configured_limit(self):
        first_response = self.middleware(self.request_factory.get('/?search=security'))
        limited_response = self.middleware(self.request_factory.get('/?search=security'))

        self.assertEqual(first_response.status_code, 204)
        self.assertEqual(limited_response.status_code, 429)
        self.assertEqual(self.forwarded_requests, 1)

    @override_settings(APPLICATION_RATE_LIMITS={'public_home': {'limit': 1, 'period': 60}})
    def test_homepage_returns_429_after_configured_limit(self):
        first_response = self.middleware(self.request_factory.get('/'))
        limited_response = self.middleware(self.request_factory.get('/'))

        self.assertEqual(first_response.status_code, 204)
        self.assertEqual(limited_response.status_code, 429)
        self.assertEqual(self.forwarded_requests, 1)

    @override_settings(
        REST_FRAMEWORK={'NUM_PROXIES': 2},
        APPLICATION_RATE_LIMITS={'public_home': {'limit': 1, 'period': 60}},
    )
    def test_forwarded_clients_have_separate_rate_limit_buckets(self):
        first_client = self.request_factory.get(
            '/', HTTP_X_FORWARDED_FOR='198.51.100.1, 10.0.0.1', REMOTE_ADDR='10.0.0.2',
        )
        second_client = self.request_factory.get(
            '/', HTTP_X_FORWARDED_FOR='198.51.100.2, 10.0.0.1', REMOTE_ADDR='10.0.0.2',
        )
        repeated_client = self.request_factory.get(
            '/', HTTP_X_FORWARDED_FOR='198.51.100.1, 10.0.0.1', REMOTE_ADDR='10.0.0.2',
        )

        self.assertEqual(self.middleware(first_client).status_code, 204)
        self.assertEqual(self.middleware(second_client).status_code, 204)
        self.assertEqual(self.middleware(repeated_client).status_code, 429)

    @override_settings(APPLICATION_RATE_LIMITS={'article_notification': {'limit': 1, 'period': 60}})
    def test_api_rate_limit_response_is_json(self):
        self.middleware(self.request_factory.get('/api/article-notifications/1/'))
        limited_response = self.middleware(self.request_factory.get('/api/article-notifications/1/'))

        self.assertEqual(limited_response.status_code, 429)
        self.assertEqual(
            json.loads(limited_response.content)['detail'],
            'Too many requests. Please try again later.',
        )


class LoginLockoutTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client_ip = '198.51.100.91'
        self.user = CustomUser.objects.create_user(
            username='lockout-user',
            password='StrongSecureExample2026!',
            role=CustomUser.ROLE_SUBSCRIBER,
        )

    def _record_failed_login(self, path):
        request = RequestFactory().post(path, REMOTE_ADDR=self.client_ip)
        user_login_failed.send(
            sender='login-lockout-test',
            credentials={'username': self.user.username},
            request=request,
        )

    def test_five_failed_attempts_temporarily_block_both_login_endpoints(self):
        self.client.defaults['REMOTE_ADDR'] = self.client_ip
        failed_paths = ('/api/login/', admin_path('login/')) * 2 + ('/api/login/',)
        for path in failed_paths:
            credentials = {'username': self.user.username, 'password': 'incorrect'}
            if path.startswith('/api/'):
                response = self.client.post(path, credentials, content_type='application/json')
            else:
                response = self.client.post(path, credentials)
            self.assertEqual(response.status_code, 400 if path.startswith('/api/') else 200)

        failure_key, _ = login_failure_cache_keys(self.client_ip)
        self.assertEqual(cache.get(failure_key), 5)
        api_response = self.client.post(
            '/api/login/',
            {'username': self.user.username, 'password': 'incorrect'},
            content_type='application/json',
        )
        admin_response = self.client.post(
            admin_path('login/'),
            {'username': self.user.username, 'password': 'incorrect'},
        )

        self.assertEqual(api_response.status_code, 429)
        self.assertEqual(admin_response.status_code, 429)
        self.assertEqual(api_response['Retry-After'], '900')

    def test_successful_api_login_resets_failure_streak(self):
        for _ in range(4):
            self._record_failed_login('/api/login/')
        failure_key, block_key = login_failure_cache_keys(self.client_ip)
        self.assertEqual(cache.get(failure_key), 4)
        self.client.defaults['REMOTE_ADDR'] = self.client_ip

        response = self.client.post(
            '/api/login/',
            {'username': self.user.username, 'password': 'StrongSecureExample2026!'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(cache.get(failure_key))
        self.assertIsNone(cache.get(block_key))

    @override_settings(REST_FRAMEWORK={'NUM_PROXIES': 2})
    def test_forwarded_clients_have_separate_login_failure_buckets(self):
        first_request = RequestFactory().post(
            '/api/login/',
            HTTP_X_FORWARDED_FOR='198.51.100.1, 10.0.0.1',
            REMOTE_ADDR='10.0.0.2',
        )
        second_request = RequestFactory().post(
            '/api/login/',
            HTTP_X_FORWARDED_FOR='198.51.100.2, 10.0.0.1',
            REMOTE_ADDR='10.0.0.2',
        )

        user_login_failed.send(sender='login-lockout-test', credentials={}, request=first_request)
        user_login_failed.send(sender='login-lockout-test', credentials={}, request=second_request)

        first_failure_key, _ = login_failure_cache_keys('198.51.100.1')
        second_failure_key, _ = login_failure_cache_keys('198.51.100.2')
        self.assertEqual(cache.get(first_failure_key), 1)
        self.assertEqual(cache.get(second_failure_key), 1)


class UserRoleAccessControlTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='World News')
        self.superadmin = CustomUser.objects.create_user(
            username='superadmin',
            password='secret123',
            role=CustomUser.ROLE_SUPERADMIN,
        )
        self.editor = CustomUser.objects.create_user(
            username='editor',
            password='secret123',
            role=CustomUser.ROLE_EDITOR,
        )
        self.author = CustomUser.objects.create_user(
            username='author',
            password='secret123',
            role=CustomUser.ROLE_AUTHOR,
        )
        self.subscriber = CustomUser.objects.create_user(
            username='subscriber',
            password='secret123',
            role=CustomUser.ROLE_SUBSCRIBER,
        )

    def test_role_flags_are_correct(self):
        self.assertTrue(self.superadmin.is_superadmin)
        self.assertTrue(self.editor.is_editor)
        self.assertTrue(self.author.is_author)
        self.assertTrue(self.subscriber.is_subscriber)

    def test_author_can_manage_only_own_article(self):
        article = Article.objects.create(
            title='My Draft Article',
            summary='Summary',
            content='Body content',
            category=self.category,
            author=self.author,
            status=Article.STATUS_DRAFT,
        )

        self.assertTrue(self.author.can_manage_article(article))
        self.assertTrue(self.superadmin.can_manage_article(article))
        self.assertTrue(self.editor.can_manage_article(article))
        self.assertFalse(self.subscriber.can_manage_article(article))

    def test_superadmin_and_editor_can_manage_any_article(self):
        article = Article.objects.create(
            title='Another Article',
            summary='Summary',
            content='Body content',
            category=self.category,
            author=self.author,
            status=Article.STATUS_UNDER_REVIEW,
        )

        self.assertTrue(self.superadmin.can_manage_article(article))
        self.assertTrue(self.editor.can_manage_article(article))
        self.assertFalse(self.subscriber.can_manage_article(article))

    def test_staff_roles_have_admin_module_access(self):
        self.assertTrue(self.superadmin.has_module_perms('news'))
        self.assertTrue(self.editor.has_module_perms('news'))
        self.assertTrue(self.author.has_module_perms('news'))
        self.assertFalse(self.subscriber.has_module_perms('news'))

    def test_role_based_permissions_are_restricted_to_their_scope(self):
        self.assertTrue(self.superadmin.has_perm('news.change_article'))
        self.assertTrue(self.superadmin.has_perm('news.delete_article'))

        self.assertTrue(self.editor.has_perm('news.change_article'))
        self.assertTrue(self.editor.has_perm('news.view_article'))
        self.assertTrue(self.editor.has_perm('news.change_comment'))
        self.assertTrue(self.editor.has_perm('news.change_userreport'))
        self.assertTrue(self.editor.has_perm('news.view_pushnotification'))
        self.assertTrue(self.editor.has_perm('news.add_pushnotification'))
        self.assertTrue(self.editor.has_perm('news.change_pushnotification'))
        self.assertFalse(self.editor.has_perm('auth.delete_user'))

        self.assertTrue(self.author.has_perm('news.add_article'))
        self.assertTrue(self.author.has_perm('news.change_article'))
        self.assertFalse(self.author.has_perm('news.delete_article'))
        self.assertFalse(self.author.has_perm('news.change_comment'))
        self.assertFalse(self.subscriber.has_perm('news.change_article'))

    def test_admin_can_keep_manually_assigned_user_permission(self):
        permission = Permission.objects.get(codename='delete_article')
        self.editor.user_permissions.add(permission)
        self.editor.save()
        self.editor.refresh_from_db()

        self.assertTrue(self.editor.has_perm('news.delete_article'))

    def test_role_demotion_revokes_permissions_granted_by_previous_role(self):
        self.assertTrue(self.superadmin.has_perm('auth.delete_user'))

        self.superadmin.role = CustomUser.ROLE_EDITOR
        self.superadmin.is_superuser = False
        self.superadmin.save()
        self.superadmin.refresh_from_db()

        self.assertTrue(self.superadmin.has_perm('news.change_article'))
        self.assertFalse(self.superadmin.has_perm('auth.delete_user'))


class EngagementModerationTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Tech')
        self.article = Article.objects.create(
            title='Featured Story',
            summary='Summary',
            content='Body text',
            category=self.category,
            status=Article.STATUS_PUBLISHED,
        )
        self.editor = CustomUser.objects.create_user(
            username='moderator',
            password='secret123',
            role=CustomUser.ROLE_EDITOR,
        )
        self.user = CustomUser.objects.create_user(
            username='reader',
            password='secret123',
            role=CustomUser.ROLE_SUBSCRIBER,
        )

    def test_comment_thread_and_status_lifecycle_are_supported(self):
        parent = Comment.objects.create(
            article=self.article,
            user=self.user,
            content='Original comment',
            status=Comment.STATUS_PENDING,
        )
        reply = Comment.objects.create(
            article=self.article,
            user=self.user,
            parent=parent,
            content='Reply to the original comment',
            status=Comment.STATUS_APPROVED,
        )

        self.assertIsNotNone(parent)
        self.assertEqual(reply.parent_id, parent.id)
        self.assertEqual(parent.replies.count(), 1)
        self.assertEqual(parent.status, Comment.STATUS_PENDING)
        self.assertEqual(reply.status, Comment.STATUS_APPROVED)

    def test_like_bookmark_and_report_tracking_model_is_available(self):
        ArticleLike.objects.create(article=self.article, user=self.user)
        ArticleBookmark.objects.create(article=self.article, user=self.user)

        report = UserReport.objects.create(
            reporter=self.user,
            article=self.article,
            reason='Inappropriate article content',
            status=UserReport.STATUS_PENDING,
        )

        self.assertEqual(self.article.likes.count(), 1)
        self.assertEqual(self.article.bookmarks.count(), 1)
        self.assertEqual(report.status, UserReport.STATUS_PENDING)
        self.assertEqual(report.article_id, self.article.id)


class AuditLogAdminTests(TestCase):
    def test_admin_article_creation_is_logged_with_user_and_ip(self):
        admin_user = CustomUser.objects.create_user(
            username='auditadmin',
            password='secret123',
            role=CustomUser.ROLE_SUPERADMIN,
        )
        category = Category.objects.create(name='Environment')
        request = RequestFactory().post(admin_path('news/article/add/'))
        request.user = admin_user
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        request.META['HTTP_USER_AGENT'] = 'AuditTestAgent'

        article = Article(
            title='Audit logged article',
            slug='audit-logged-article',
            summary='Summary',
            content='Body content',
            category=category,
            status=Article.STATUS_DRAFT,
            author=admin_user,
            views_count=0,
            read_time_minutes=3,
        )

        admin_model = admin.site._registry[Article]
        admin_model.save_model(request, article, admin_model.form(), False)

        self.assertTrue(Article.objects.filter(title='Audit logged article').exists())
        self.assertTrue(AuditLog.objects.filter(model_name='article', action='create').exists())
        self.assertTrue(AuditLog.objects.filter(model_name='article', ip_address='127.0.0.1').exists())

    def test_admin_article_update_logs_changed_field_names(self):
        admin_user = CustomUser.objects.create_user(
            username='auditupdateadmin',
            password='secret123',
            role=CustomUser.ROLE_SUPERADMIN,
        )
        category = Category.objects.create(name='Environment')
        article = Article.objects.create(
            title='Original title',
            content='Body content',
            category=category,
            status=Article.STATUS_DRAFT,
        )
        request = RequestFactory().post(admin_path(f'news/article/{article.pk}/change/'))
        request.user = admin_user
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        request.META['HTTP_USER_AGENT'] = 'AuditUpdateTestAgent'

        form = admin.site._registry[Article].form({'title': 'Updated title', 'content': article.content, 'category': category.pk, 'status': article.status}, instance=article)
        article.title = 'Updated title'
        admin_model = admin.site._registry[Article]
        admin_model.save_model(request, article, form, True)

        audit_log = AuditLog.objects.filter(model_name='article', action='update').latest('created_at')
        self.assertIn('title', audit_log.changes['changed_fields'])


class HomepageRouteTests(TestCase):
    def test_root_url_serves_homepage_without_redirecting_to_admin(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')

    def test_home_alias_route_serves_homepage_without_redirecting_to_admin(self):
        response = self.client.get('/home/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')

    def test_articles_have_clickable_links_to_read_full_story(self):
        category = Category.objects.create(name='Technology')
        article = Article.objects.create(
            title='AI Startup Funding Surges',
            summary='A short summary for the homepage.',
            content='The full article body is here for reading.',
            category=category,
            status=Article.STATUS_PUBLISHED,
        )

        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="/article/{article.slug}/"')

    def test_homepage_lists_published_articles_by_publish_time(self):
        category = Category.objects.create(name='Technology')
        older = Article.objects.create(
            title='Older story',
            content='Older content',
            category=category,
            status=Article.STATUS_PUBLISHED,
            published_at=timezone.now() - timezone.timedelta(days=2),
        )
        newer = Article.objects.create(
            title='Newer story',
            content='Newer content',
            category=category,
            status=Article.STATUS_PUBLISHED,
            published_at=timezone.now() - timezone.timedelta(days=1),
        )

        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertLess(response.content.decode().find(newer.title), response.content.decode().find(older.title))

    def test_homepage_article_summary_hides_rich_text_markup(self):
        category = Category.objects.create(name='Technology')
        article = Article.objects.create(
            title='Readable card summary',
            summary='<p><strong>Important update</strong></p>',
            content='Article content',
            category=category,
            status=Article.STATUS_PUBLISHED,
        )
        Article.objects.create(
            title='Featured lead story',
            content='Featured content',
            category=category,
            status=Article.STATUS_PUBLISHED,
            is_featured=True,
        )

        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Important update')
        self.assertNotContains(response, '&lt;p&gt;')
        self.assertNotContains(response, '&lt;strong&gt;')

    def test_api_lists_articles_by_publish_time(self):
        category = Category.objects.create(name='Technology')
        Article.objects.create(
            title='Older API story',
            content='Older content',
            category=category,
            status=Article.STATUS_PUBLISHED,
            published_at=timezone.now() - timezone.timedelta(days=2),
        )
        newer = Article.objects.create(
            title='Newer API story',
            content='Newer content',
            category=category,
            status=Article.STATUS_PUBLISHED,
            published_at=timezone.now() - timezone.timedelta(days=1),
        )

        response = self.client.get('/api/articles/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]['id'], newer.id)

    def test_policy_content_is_available_from_settings(self):
        settings = SystemSetting.get_instance()
        settings.about_content = '<h1>About us</h1>'
        settings.contact_content = '<p>Contact us</p>'
        settings.terms_content = '<p>Terms and Conditions</p>'
        settings.privacy_policy_content = '<p>Privacy Policy</p>'
        settings.save()

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

        html = response.content.decode()
        self.assertIn('About us', html)
        self.assertIn('Contact us', html)
        self.assertIn('Terms and Conditions', html)
        self.assertIn('Privacy Policy', html)


class PolicyContentAPITests(TestCase):
    def test_system_settings_expose_policy_content_text_in_api_response(self):
        settings = SystemSetting.get_instance()
        settings.about_content = '<h1>About us</h1><p>We publish daily news.</p>'
        settings.contact_content = '<p>Email us at hello@example.com</p>'
        settings.terms_content = '<h2>Terms</h2><p>Use this app responsibly.</p>'
        settings.privacy_policy_content = '<h2>Privacy</h2><p>We protect your data.</p>'
        settings.save()

        payload = SystemSettingSerializer(settings).data

        self.assertIn('about_content', payload)
        self.assertIn('contact_content', payload)
        self.assertIn('terms_content', payload)
        self.assertIn('privacy_policy_content', payload)
        self.assertNotIn('about_url', payload)
        self.assertNotIn('contact_url', payload)
        self.assertIn('About us', payload['about_content'])
        self.assertIn('hello@example.com', payload['contact_content'])


class AdminLoginPageTests(TestCase):
    def test_admin_urls_keep_the_original_reverse_and_expose_custom_alias(self):
        self.assertEqual(reverse('admin:index'), '/admin/')
        self.assertEqual(reverse('custom_admin:index'), admin_path())

    def test_admin_login_page_loads_without_recursion(self):
        response = self.client.get(admin_path('login/'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')
        self.assertContains(response, 'Log in')

    def test_legacy_admin_login_url_remains_available(self):
        response = self.client.get('/admin/login/')

        self.assertEqual(response.status_code, 200)

    def test_legacy_admin_index_remains_available(self):
        admin_user = CustomUser.objects.create_user(
            username='legacy-route-admin',
            password='secret123',
            role=CustomUser.ROLE_SUPERADMIN,
        )
        self.client.force_login(admin_user)

        response = self.client.get('/admin/')

        self.assertEqual(response.status_code, 200)

    def test_admin_login_page_displays_app_logo_and_name(self):
        settings_obj = SystemSetting.get_instance()
        settings_obj.app_name = 'Royal Pro News'
        settings_obj.logo = SimpleUploadedFile('logo.png', b'fake-image-content', content_type='image/png')
        settings_obj.save()

        response = self.client.get(admin_path('login/'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Royal Pro News')
        self.assertContains(response, '/media/branding/')
        self.assertContains(response, 'logo')

    def test_system_setting_logo_save_and_clear_actions_work(self):
        admin_user = CustomUser.objects.create_user(
            username='logoadmin',
            password='secret123',
            role=CustomUser.ROLE_SUPERADMIN,
        )
        self.client.force_login(admin_user)

        settings_obj = SystemSetting.get_instance()
        settings_obj.app_name = 'Old Brand'
        settings_obj.logo = None
        settings_obj.save()

        app_name_response = self.client.post(
            admin_path('news/systemsetting/1/change/'),
            {
                'app_name': 'Updated Brand',
                '_save_app_name': 'Save app name',
            },
            follow=False,
        )

        self.assertIn(app_name_response.status_code, (200, 302))
        settings_obj.refresh_from_db()
        self.assertEqual(settings_obj.app_name, 'Updated Brand')

        first_logo = SimpleUploadedFile('new-logo.png', b'new-image-content', content_type='image/png')
        logo_response = self.client.post(
            admin_path('news/systemsetting/1/change/'),
            {
                'app_name': 'Updated Brand',
                'logo': first_logo,
                '_save_logo': 'Save logo',
            },
            follow=False,
        )

        self.assertIn(logo_response.status_code, (200, 302))
        settings_obj.refresh_from_db()
        self.assertTrue(settings_obj.logo and 'new-logo' in settings_obj.logo.name)

        clear_response = self.client.post(
            admin_path('news/systemsetting/1/change/'),
            {
                'app_name': 'Updated Brand',
                'logo-clear': 'on',
                '_save_logo': 'Save logo',
            },
            follow=False,
        )

        self.assertIn(clear_response.status_code, (200, 302))
        settings_obj.refresh_from_db()
        self.assertFalse(bool(settings_obj.logo))


class ArticleSearchTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name='Technology')
        self.article = Article.objects.create(
            title='Searchable Product Name',
            content='Article body',
            category=category,
            status=Article.STATUS_PUBLISHED,
        )

    def test_home_search_matches_article_name(self):
        response = self.client.get('/', {'search': 'Product Name'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.article.title)

    def test_api_search_matches_article_slug_and_numeric_code(self):
        for search_value in (self.article.slug, str(self.article.pk)):
            response = self.client.get('/api/articles/', {'search': search_value})

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(len(payload), 1)
            self.assertEqual(payload[0]['id'], self.article.pk)

    def test_public_article_pages_show_article_notification_bells(self):
        home_response = self.client.get('/')
        detail_response = self.client.get(f'/article/{self.article.slug}/')

        self.assertContains(home_response, f'data-article-id="{self.article.pk}"')
        self.assertContains(home_response, 'class="notification-bell"')
        self.assertContains(detail_response, f'data-article-id="{self.article.pk}"')
        self.assertContains(detail_response, 'class="notification-bell"')

    def test_article_notification_status_is_connected_by_article_id(self):
        notification = PushNotification.objects.get(article_id=self.article.pk)
        notification.is_sent = True
        notification.sent_at = timezone.now()
        notification.save(update_fields=('is_sent', 'sent_at'))

        response = self.client.get(f'/api/article-notifications/{self.article.pk}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['article_id'], self.article.pk)
        self.assertTrue(response.json()['is_sent'])

    def test_article_notification_status_hides_unpublished_articles(self):
        self.article.status = Article.STATUS_DRAFT
        self.article.save(update_fields=('status',))

        response = self.client.get(f'/api/article-notifications/{self.article.pk}/')

        self.assertEqual(response.status_code, 404)


class AdminRichTextEditorTests(TestCase):
    def test_shared_admin_base_loads_editor_assets(self):
        admin_user = CustomUser.objects.create_user(
            username='globaleditoradmin',
            password='secret123',
            role=CustomUser.ROLE_SUPERADMIN,
        )
        self.client.force_login(admin_user)

        response = self.client.get(admin_path())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'tinymce@7/tinymce.min.js')
        self.assertContains(response, 'news/admin_rich_text_editor.js?v=3')

    def test_admin_editor_script_is_served_as_javascript(self):
        response = self.client.get('/static/news/admin_rich_text_editor.js?v=3')
        content = b''.join(response.streaming_content)

        self.assertEqual(response.status_code, 200)
        self.assertIn('javascript', response.headers.get('Content-Type', ''))
        self.assertIn(b'tinymce.init', content)

    def test_all_rich_text_admin_forms_use_the_shared_editor_widget(self):
        form_fields = (
            (SystemSettingAdminForm, 'maintenance_message'),
            (SystemSettingAdminForm, 'about_content'),
            (ArticleAdminForm, 'content'),
            (ArticleAdminForm, 'summary'),
            (FeedbackAdminForm, 'message'),
            (CommentAdminForm, 'content'),
            (UserReportAdminForm, 'reason'),
            (PushNotificationAdminForm, 'body'),
            (NewsletterBroadcastAdminForm, 'content'),
        )

        for form_class, field_name in form_fields:
            with self.subTest(form=form_class.__name__, field=field_name):
                field = form_class().fields[field_name]
                self.assertIn('rich-text-editor', field.widget.attrs.get('class', ''))

    def test_rich_text_admin_form_sanitizes_submitted_html(self):
        form = FeedbackAdminForm(data={
            'category': 'bug',
            'message': '<p>Safe message</p><script>alert(1)</script>',
            'message_text_size': 16,
        })

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['message'], '<p>Safe message</p>alert(1)')

    def test_article_admin_uses_rich_text_editor_for_writable_content_fields(self):
        admin_user = CustomUser.objects.create_user(
            username='richtextadmin',
            password='secret123',
            role=CustomUser.ROLE_SUPERADMIN,
        )
        self.client.force_login(admin_user)

        response = self.client.get(admin_path('news/article/add/'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'tinymce')
        self.assertContains(response, 'rich-text-editor')

    def test_article_admin_uses_builtin_editor_style_controls(self):
        admin_user = CustomUser.objects.create_user(
            username='articlestyleadmin',
            password='secret123',
            role=CustomUser.ROLE_SUPERADMIN,
        )
        self.client.force_login(admin_user)

        response = self.client.get(admin_path('news/article/add/'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="content_text_size"')
        self.assertNotContains(response, 'name="content_text_color"')
        self.assertNotContains(response, 'name="content_background_color"')
        self.assertContains(response, 'admin_rich_text_editor.js')

    def test_article_detail_renders_rich_text_content_as_html(self):
        category = Category.objects.create(name='Technology')
        article = Article.objects.create(
            title='Formatted article',
            content='<p><strong>Important update</strong></p>',
            category=category,
            status=Article.STATUS_PUBLISHED,
        )

        response = self.client.get(f'/article/{article.slug}/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<p><strong>Important update</strong></p>', html=False)
        self.assertNotContains(response, '&lt;p&gt;')

    def test_created_article_gets_article_linked_notification(self):
        category = Category.objects.create(name='Notifications')
        article = Article.objects.create(
            title='Notify readers',
            summary='Short update',
            content='Full article body',
            category=category,
        )

        notification = PushNotification.objects.get(article_id=article.pk)

        self.assertEqual(notification.target_type, PushNotification.TARGET_ARTICLE)
        self.assertEqual(notification.title, article.title)
        self.assertEqual(notification.body, article.summary)
        self.assertFalse(notification.is_sent)

    def test_article_admin_action_sends_notification_for_article_id(self):
        admin_user = CustomUser.objects.create_user(
            username='notificationadmin',
            password='secret123',
            role=CustomUser.ROLE_SUPERADMIN,
        )
        category = Category.objects.create(name='Send Notifications')
        article = Article.objects.create(
            title='Send this update',
            content='Notification body',
            category=category,
        )
        notification = PushNotification.objects.get(article_id=article.pk)
        request = RequestFactory().post(admin_path('news/article/'))
        request.user = admin_user
        SessionMiddleware(lambda request: None).process_request(request)
        request._messages = FallbackStorage(request)

        ArticleAdmin(Article, admin.site).send_article_notifications(
            request,
            Article.objects.filter(pk=article.pk),
        )
        notification.refresh_from_db()

        self.assertTrue(notification.is_sent)
        self.assertEqual(notification.sent_by_id, admin_user.pk)
        self.assertIsNotNone(notification.sent_at)
        self.assertEqual(notification.article_id, article.pk)


class EnterpriseTaxonomyAPITests(TestCase):
    def setUp(self):
        self.superadmin = CustomUser.objects.create_user(
            username='taxonomyadmin',
            password='secret123',
            role=CustomUser.ROLE_SUPERADMIN,
        )
        self.parent_category = Category.objects.create(name='Business', slug='business')
        self.child_category = Category.objects.create(name='Finance', slug='finance', parent=self.parent_category)

    def test_category_hierarchy_is_exposed_by_the_api(self):
        response = self.client.get('/api/categories/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreater(len(payload), 0)
        category = next(item for item in payload if item['id'] == self.parent_category.id)
        self.assertEqual(category['parent'], None)
        self.assertIn('children', category)

    def test_admin_can_create_category_and_tag_via_api(self):
        self.client.force_login(self.superadmin)

        post_category = self.client.post('/api/categories/', {'name': 'Sports', 'parent': self.parent_category.id}, content_type='application/json')
        self.assertEqual(post_category.status_code, 201, post_category.content)

        post_tag = self.client.post('/api/tags/', {'name': 'Breaking'}, content_type='application/json')
        self.assertEqual(post_tag.status_code, 201, post_tag.content)
        self.assertEqual(post_tag.json()['name'], 'Breaking')

    def test_admin_article_form_includes_enterprise_management_fields(self):
        self.client.force_login(self.superadmin)
        response = self.client.get(admin_path('news/article/add/'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="status"')
        self.assertContains(response, 'name="is_featured"')
        self.assertContains(response, 'name="is_breaking"')
        self.assertContains(response, 'name="published_at_0"')
        self.assertContains(response, 'name="published_at_1"')
        self.assertContains(response, 'name="views_count"')
        self.assertContains(response, 'name="read_time_minutes"')
        self.assertContains(response, 'name="cover_image"')
        self.assertContains(response, 'name="video_url"')


class AdminDashboardWidgetTests(TestCase):
    def test_admin_control_cards_use_live_news_and_ad_metrics(self):
        admin_user = CustomUser.objects.create_user(
            username='controlmetricsadmin',
            password='secret123',
            role=CustomUser.ROLE_SUPERADMIN,
        )
        category = Category.objects.create(name='Dashboard')
        Article.objects.create(
            title='Published story',
            content='Story body',
            category=category,
            status=Article.STATUS_PUBLISHED,
        )
        Article.objects.create(
            title='Draft story',
            content='Draft body',
            category=category,
            status=Article.STATUS_DRAFT,
        )
        AdSenseReport.objects.create(impressions=73, clicks=9, earnings='18.25')
        self.client.force_login(admin_user)

        response = self.client.get(admin_path())
        content = response.content.decode()
        payload_script = content.split('id="dashboard-data" type="application/json">', 1)[1].split('</script>', 1)[0]
        dashboard_data = json.loads(payload_script)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(dashboard_data['summary_metrics']['total_articles'], 2)
        self.assertEqual(dashboard_data['summary_metrics']['published_articles'], 1)
        self.assertEqual(dashboard_data['summary_metrics']['draft_articles'], 1)
        self.assertEqual(dashboard_data['ad_metrics']['total_ad_views'], 73)
        self.assertEqual(dashboard_data['ad_metrics']['total_ad_clicks'], 9)
        self.assertEqual(dashboard_data['ad_metrics']['ad_revenue'], 18.25)
        self.assertContains(response, 'data-metric="published-articles"')
        self.assertContains(response, 'data-metric="ad-revenue"')

    def test_admin_dashboard_has_add_button(self):
        admin_user = CustomUser.objects.create_user(
            username='dashboardadmin',
            password='secret123',
            role=CustomUser.ROLE_SUPERADMIN,
        )
        self.client.force_login(admin_user)

        response = self.client.get(admin_path())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add')

    def test_admin_dashboard_uses_safe_json_payload_instead_of_raw_script_literals(self):
        admin_user = CustomUser.objects.create_user(
            username='dashboardjsonadmin',
            password='secret123',
            role=CustomUser.ROLE_SUPERADMIN,
        )
        self.client.force_login(admin_user)

        response = self.client.get(admin_path())
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="dashboard-data"', content)
        self.assertNotIn('const categoryBreakdown = {{', content)
        self.assertNotIn('const initialAdMetrics = {{', content)
        self.assertIn('JSON.parse(document.getElementById(\'dashboard-data\')', content)

    def test_dashboard_widget_endpoint_persists_widget_in_session(self):
        admin_user = CustomUser.objects.create_user(
            username='widgetadmin',
            password='secret123',
            role=CustomUser.ROLE_SUPERADMIN,
        )
        self.client.force_login(admin_user)

        response = self.client.post('/api/dashboard/widgets/', {'widget_type': 'metric'}, content_type='application/json')

        self.assertEqual(response.status_code, 201)
        self.assertIn('dashboard_widgets', self.client.session)
        self.assertGreaterEqual(len(self.client.session['dashboard_widgets']), 1)

    def test_dashboard_widget_endpoint_updates_and_removes_widget_from_session(self):
        admin_user = CustomUser.objects.create_user(
            username='widgetcrud',
            password='secret123',
            role=CustomUser.ROLE_SUPERADMIN,
        )
        self.client.force_login(admin_user)

        create_response = self.client.post('/api/dashboard/widgets/', {'widget_type': 'chart'}, content_type='application/json')
        widget = create_response.json()['widgets'][-1]
        widget_id = widget['widget_id']

        patch_response = self.client.patch(
            '/api/dashboard/widgets/',
            {'widget_id': widget_id, 'title': 'Updated chart'},
            content_type='application/json',
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.json()['widgets'][-1]['title'], 'Updated chart')

        delete_response = self.client.delete(
            '/api/dashboard/widgets/',
            {'widget_id': widget_id},
            content_type='application/json',
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertNotIn(widget_id, [item.get('widget_id') for item in self.client.session['dashboard_widgets']])

    def test_dashboard_widget_persists_to_database(self):
        admin_user = CustomUser.objects.create_user(
            username='widgetdb',
            password='secret123',
            role=CustomUser.ROLE_SUPERADMIN,
        )
        self.client.force_login(admin_user)

        response = self.client.post('/api/dashboard/widgets/', {'widget_type': 'metric'}, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(DashboardWidgetConfig.objects.count(), 1)

        widget = DashboardWidgetConfig.objects.get()
        self.assertEqual(widget.widget_type, 'metric')
        self.assertTrue(widget.title)

        patched = self.client.patch(
            '/api/dashboard/widgets/',
            {'widget_id': widget.widget_id, 'title': 'Live metric'},
            content_type='application/json',
        )
        self.assertEqual(patched.status_code, 200)
        widget.refresh_from_db()
        self.assertEqual(widget.title, 'Live metric')

        deleted = self.client.delete(
            '/api/dashboard/widgets/',
            {'widget_id': widget.widget_id},
            content_type='application/json',
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(DashboardWidgetConfig.objects.count(), 0)


class FeedbackAPITests(TestCase):
    def test_feedback_endpoint_accepts_submissions(self):
        payload = {
            'name': 'Ada',
            'email': 'ada@example.com',
            'category': 'bug',
            'message': 'The article page crashes when opened on low network.',
        }

        response = self.client.post('/api/feedback/', payload, content_type='application/json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['status'], 'success')
        self.assertEqual(response.json()['data']['category'], 'bug')

    def test_feedback_api_sanitizes_submitted_html(self):
        response = self.client.post(
            '/api/feedback/',
            {
                'name': 'Ada',
                'email': 'ada@example.com',
                'category': 'bug',
                'message': '<p>Safe feedback</p><img src=x onerror=alert(1)>',
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Feedback.objects.get().message, '<p>Safe feedback</p><img src="x">')

    def test_register_endpoint_creates_custom_user(self):
        payload = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }

        response = self.client.post('/api/register/', payload, content_type='application/json')

        self.assertEqual(response.status_code, 201)
        self.assertTrue(CustomUser.objects.filter(username='newuser').exists())
        self.assertEqual(response.json()['user']['email'], 'newuser@example.com')

    def test_registration_rejects_short_and_numeric_passwords(self):
        self.client.defaults['REMOTE_ADDR'] = '192.0.2.84'
        for username, password in (
            ('short-password-user', 'Short123!'),
            ('numeric-password-user', '123456789012'),
        ):
            response = self.client.post(
                '/api/register/',
                {
                    'username': username,
                    'email': f'{username}@example.com',
                    'password': password,
                    'password2': password,
                },
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn('password', response.json())

    def test_registration_uses_common_password_validator(self):
        serializer = RegisterSerializer()

        with self.assertRaises(ValidationError) as raised:
            serializer.validate({
                'username': 'unrelated-user',
                'email': '',
                'password': 'password',
                'password2': 'password',
            })

        self.assertTrue(
            any('too common' in str(message).lower() for message in raised.exception.detail['password'])
        )


class AnalyticsDashboardTests(TestCase):
    def test_ad_metrics_use_ad_reports_not_news_views(self):
        category = Category.objects.create(name='Advertising')
        article = Article.objects.create(
            title='Tracked story',
            content='Body',
            category=category,
            status=Article.STATUS_PUBLISHED,
            views_count=1000,
        )
        AnalyticsEvent.objects.create(
            article=article,
            category=category,
            event_type=AnalyticsEvent.EVENT_VIEW,
            event_value=1000,
            created_at=timezone.now(),
        )
        AdSenseReport.objects.create(impressions=42, clicks=7, earnings='12.50')

        payload = DashboardAnalyticsService.build_dashboard_payload(days=7)

        self.assertEqual(payload['ad_metrics']['total_ad_views'], 42)
        self.assertEqual(payload['ad_metrics']['total_ad_clicks'], 7)
        self.assertEqual(payload['ad_metrics']['ad_revenue'], 12.5)
        self.assertEqual(payload['ad_revenue_trend'][0]['ad_views'], 42)
        self.assertEqual(payload['ad_revenue_trend'][0]['revenue'], 12.5)
        self.assertEqual(payload['daily_activity'][0]['read_count'], 1000)

    def test_dashboard_service_builds_chart_ready_analytics(self):
        category = Category.objects.create(name='Business')
        article = Article.objects.create(
            title='Market Report',
            summary='Summary',
            content='Body',
            category=category,
            status=Article.STATUS_PUBLISHED,
        )
        author = CustomUser.objects.create_user(username='writer', password='secret123', role=CustomUser.ROLE_AUTHOR)

        AnalyticsEvent.objects.create(article=article, category=category, user=author, event_type=AnalyticsEvent.EVENT_VIEW, event_value=8, created_at=timezone.now())
        AnalyticsEvent.objects.create(article=article, category=category, user=author, event_type=AnalyticsEvent.EVENT_VIEW, event_value=7, created_at=timezone.now())
        AnalyticsEvent.objects.create(article=article, category=category, user=author, event_type=AnalyticsEvent.EVENT_SHARE, event_value=3, created_at=timezone.now())
        AnalyticsEvent.objects.create(article=article, category=category, user=author, event_type=AnalyticsEvent.EVENT_SEARCH, query_text='market report', created_at=timezone.now())
        AnalyticsEvent.objects.create(article=article, category=category, user=author, event_type=AnalyticsEvent.EVENT_PUBLISHED, created_at=timezone.now())

        payload = DashboardAnalyticsService.build_dashboard_payload(days=7)

        self.assertIn('daily_activity', payload)
        self.assertIn('category_breakdown', payload)
        self.assertIn('release_trends', payload)
        self.assertIn('most_shared_articles', payload)
        self.assertIn('top_search_terms', payload)
        self.assertGreaterEqual(payload['daily_activity'][0]['read_count'], 15)
        self.assertGreaterEqual(payload['most_shared_articles'][0]['share_count'], 3)
        self.assertGreaterEqual(len(payload['top_search_terms']), 1)

    def test_admin_analytics_endpoint_returns_aggregated_metrics(self):
        admin_user = CustomUser.objects.create_user(
            username='analyticsadmin',
            password='secret123',
            role=CustomUser.ROLE_SUPERADMIN,
        )
        self.client.force_login(admin_user)

        response = self.client.get('/api/admin/analytics/')

        self.assertEqual(response.status_code, 200)
        self.assertIn('daily_activity', response.json())
        self.assertIn('category_breakdown', response.json())
        self.assertIn('release_trends', response.json())
        self.assertIn('most_shared_articles', response.json())
        self.assertIn('top_search_terms', response.json())

    def test_admin_analytics_endpoint_supports_timeframe_filtering(self):
        admin_user = CustomUser.objects.create_user(
            username='analyticsfilter',
            password='secret123',
            role=CustomUser.ROLE_SUPERADMIN,
        )
        self.client.force_login(admin_user)

        response = self.client.get('/api/admin/analytics/?timeframe=weekly')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['timeframe'], 'weekly')
        self.assertIn('daily_activity', response.json())
        self.assertTrue(len(response.json()['daily_activity']) >= 1)

        all_response = self.client.get('/api/admin/analytics/?timeframe=all')

        self.assertEqual(all_response.status_code, 200)
        self.assertEqual(all_response.json()['timeframe'], 'all')
        self.assertIn('daily_activity', all_response.json())
        self.assertTrue(len(all_response.json()['daily_activity']) >= 1)

    def test_admin_dashboard_metrics_endpoint_returns_real_values(self):
        admin_user = CustomUser.objects.create_user(
            username='metricsadmin',
            password='secret123',
            role=CustomUser.ROLE_SUPERADMIN,
        )
        self.client.force_login(admin_user)

        category = Category.objects.create(name='Business')
        article = Article.objects.create(
            title='Metrics Story',
            summary='Summary',
            content='Body',
            category=category,
            status=Article.STATUS_PUBLISHED,
            views_count=120,
        )
        AnalyticsEvent.objects.create(
            article=article,
            category=category,
            user=admin_user,
            event_type=AnalyticsEvent.EVENT_VIEW,
            event_value=120,
            created_at=timezone.now(),
        )

        response = self.client.get('/api/dashboard-metrics/')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('active_readers', payload)
        self.assertIn('total_news', payload)
        self.assertIn('daily_ad_views', payload)
        self.assertIn('ad_revenue', payload)
        self.assertIn('ctr', payload)
        self.assertIn('cpm', payload)
        self.assertGreaterEqual(payload['total_news'], 1)

    def test_dashboard_service_builds_product_and_revenue_breakdown_data(self):
        category = Category.objects.create(name='Business')
        article_one = Article.objects.create(
            title='Alpha Report',
            summary='Summary',
            content='Body',
            category=category,
            status=Article.STATUS_PUBLISHED,
            views_count=120,
        )
        article_two = Article.objects.create(
            title='Beta Report',
            summary='Summary',
            content='Body',
            category=category,
            status=Article.STATUS_PUBLISHED,
            views_count=90,
        )
        article_three = Article.objects.create(
            title='Gamma Report',
            summary='Summary',
            content='Body',
            category=category,
            status=Article.STATUS_PUBLISHED,
            views_count=60,
        )

        AnalyticsEvent.objects.create(article=article_one, category=category, user=article_one.author, event_type=AnalyticsEvent.EVENT_VIEW, event_value=120, created_at=timezone.now())
        AnalyticsEvent.objects.create(article=article_two, category=category, user=article_two.author, event_type=AnalyticsEvent.EVENT_VIEW, event_value=90, created_at=timezone.now())
        AnalyticsEvent.objects.create(article=article_three, category=category, user=article_three.author, event_type=AnalyticsEvent.EVENT_VIEW, event_value=60, created_at=timezone.now())

        payload = DashboardAnalyticsService.build_dashboard_payload(days=30)

        self.assertIn('top_products', payload)
        self.assertIn('revenue_breakdown', payload)
        self.assertTrue(len(payload['top_products']) >= 3)
        self.assertGreater(payload['top_products'][0]['percent'], 0)
        self.assertGreater(len(payload['revenue_breakdown']), 0)

    def test_dashboard_service_builds_system_architecture_statuses(self):
        category = Category.objects.create(name='Business')
        article = Article.objects.create(
            title='System Overview',
            summary='Summary',
            content='Body',
            category=category,
            status=Article.STATUS_PUBLISHED,
            views_count=75,
        )
        AnalyticsEvent.objects.create(article=article, category=category, event_type=AnalyticsEvent.EVENT_VIEW, event_value=75, created_at=timezone.now())

        payload = DashboardAnalyticsService.build_dashboard_payload(days=7)

        self.assertIn('system_architecture', payload)
        self.assertTrue(any(node['name'] == 'Web' for node in payload['system_architecture']['nodes']))
        self.assertTrue(any(node['name'] == 'Mobile' for node in payload['system_architecture']['nodes']))
        self.assertTrue(any(node['name'] == 'API' for node in payload['system_architecture']['nodes']))
        self.assertTrue(any(node['name'] == 'POS' for node in payload['system_architecture']['nodes']))
        self.assertTrue(any(node['name'] == 'Inventory' for node in payload['system_architecture']['nodes']))
        self.assertTrue(any(node['name'] == 'Marketing' for node in payload['system_architecture']['nodes']))
        self.assertIn(payload['system_architecture']['nodes'][0]['status'], {'healthy', 'degraded'})

    def test_admin_dashboard_includes_ad_tracking_metrics(self):
        admin_user = CustomUser.objects.create_user(
            username='adtracker',
            password='secret123',
            role=CustomUser.ROLE_SUPERADMIN,
        )
        self.client.force_login(admin_user)

        payload = DashboardAnalyticsService.build_dashboard_payload(days=7)
        self.assertIn('ad_metrics', payload)
        self.assertIn('ad_revenue_trend', payload)
        self.assertGreaterEqual(payload['ad_metrics']['total_ad_views'], 0)

        response = self.client.get(admin_path())
        self.assertContains(response, 'News views')
        self.assertContains(response, 'Ad revenue')

    def test_dashboard_service_builds_live_customer_insights_and_news_labels(self):
        category = Category.objects.create(name='Business')
        article = Article.objects.create(
            title='Live Metrics Story',
            summary='Summary',
            content='Body',
            category=category,
            status=Article.STATUS_PUBLISHED,
            views_count=150,
        )
        user_one = CustomUser.objects.create_user(username='reader1', password='secret123', role=CustomUser.ROLE_SUBSCRIBER)
        user_two = CustomUser.objects.create_user(username='reader2', password='secret123', role=CustomUser.ROLE_SUBSCRIBER)
        AnalyticsEvent.objects.create(article=article, category=category, user=user_one, event_type=AnalyticsEvent.EVENT_VIEW, event_value=75, created_at=timezone.now())
        AnalyticsEvent.objects.create(article=article, category=category, user=user_two, event_type=AnalyticsEvent.EVENT_VIEW, event_value=75, created_at=timezone.now())
        AnalyticsEvent.objects.create(article=article, category=category, user=user_one, event_type=AnalyticsEvent.EVENT_SHARE, event_value=4, created_at=timezone.now())

        payload = DashboardAnalyticsService.build_dashboard_payload(days=7)

        self.assertIn('customer_insights', payload)
        self.assertIn('top_articles', payload)
        self.assertIn('readership_breakdown', payload)
        self.assertGreaterEqual(payload['customer_insights']['returning_users'], 0)
        self.assertGreaterEqual(payload['customer_insights']['avg_views_per_user'], 0)

        admin_user = CustomUser.objects.create_user(
            username='labeladmin',
            password='secret123',
            role=CustomUser.ROLE_SUPERADMIN,
        )
        self.client.force_login(admin_user)

        response = self.client.get(admin_path())
        self.assertContains(response, 'Advertising tracking')
        self.assertContains(response, 'Top Stories')
        self.assertContains(response, 'Traffic / Readership Breakdown')

    def test_article_retrieval_tracks_live_view_event(self):
        category = Category.objects.create(name='Technology')
        article = Article.objects.create(
            title='Live view article',
            summary='Summary',
            content='Body',
            category=category,
            status=Article.STATUS_PUBLISHED,
            views_count=12,
        )

        response = self.client.get(f'/api/articles/{article.id}/')

        self.assertEqual(response.status_code, 200)
        article.refresh_from_db()
        self.assertGreater(article.views_count, 12)
        self.assertTrue(
            AnalyticsEvent.objects.filter(
                article=article,
                event_type=AnalyticsEvent.EVENT_VIEW,
            ).exists()
        )
