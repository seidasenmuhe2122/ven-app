"""
Django settings for myapp project.
"""

import os
import re
import secrets
from pathlib import Path

import dj_database_url
from django.utils.csp import CSP

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
IS_PRODUCTION = os.environ.get('DJANGO_ENV', '').lower() == 'production'
admin_url = os.environ.get('DJANGO_ADMIN_URL', '').strip().strip('/')
ADMIN_URL = admin_url or 'control-desk-7c4a91e2'
if ADMIN_URL.lower() == 'admin' or not re.fullmatch(r'[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*', ADMIN_URL):
    raise RuntimeError('DJANGO_ADMIN_URL must contain only URL-safe path segments.')
ADMIN_URL += '/'


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
DEBUG = not IS_PRODUCTION and os.environ.get('DJANGO_DEBUG', 'False').lower() in {'1', 'true', 'yes', 'on'}

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if IS_PRODUCTION:
        raise RuntimeError('DJANGO_SECRET_KEY must be set in production.')
    SECRET_KEY = secrets.token_urlsafe(64)

configured_hosts = os.environ.get('DJANGO_ALLOWED_HOSTS', '')
if IS_PRODUCTION and not configured_hosts.strip():
    raise RuntimeError('DJANGO_ALLOWED_HOSTS must be configured in production.')
ALLOWED_HOSTS = [host.strip() for host in (configured_hosts or 'localhost,127.0.0.1,testserver').split(',') if host.strip()]
if IS_PRODUCTION and '*' in ALLOWED_HOSTS:
    raise RuntimeError('Wildcard DJANGO_ALLOWED_HOSTS is not allowed in production.')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework.authtoken',
    'accounts',
    'news.apps.NewsConfig',
]

AUTH_USER_MODEL = 'accounts.CustomUser'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csp.ContentSecurityPolicyMiddleware',
    'news.middleware.BrowserSecurityHeadersMiddleware',
    'django.middleware.common.CommonMiddleware',
    'news.middleware.EndpointRateLimitMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'myapp.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.csp',
                'news.context_processors.site_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'myapp.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600),
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 12},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

AUTH_LOGIN_FAILURE_LIMIT = int(os.environ.get('DJANGO_LOGIN_FAILURE_LIMIT', '5'))
AUTH_LOGIN_LOCKOUT_SECONDS = int(os.environ.get('DJANGO_LOGIN_LOCKOUT_SECONDS', '900'))
if AUTH_LOGIN_FAILURE_LIMIT < 1 or AUTH_LOGIN_LOCKOUT_SECONDS < 1:
    raise RuntimeError('Login lockout limits must be positive integers.')


# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.1/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage' if IS_PRODUCTION else 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_FILTER_BACKENDS': [
        'rest_framework.filters.SearchFilter',
    ],
    'SEARCH_PARAM': 'search',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day',
        'login': '10/hour',
        'registration': '5/hour',
        'feedback': '10/hour',
    },
    'NUM_PROXIES': int(os.environ.get('DJANGO_NUM_PROXIES', '0')),
}

APPLICATION_RATE_LIMITS = {
    'admin_login': {'limit': 10, 'period': 3600},
    'public_home': {'limit': 120, 'period': 60},
    'web_search': {'limit': 30, 'period': 60},
    'article_detail': {'limit': 120, 'period': 60},
    'dashboard_metrics': {'limit': 120, 'period': 60},
    'article_notification': {'limit': 120, 'period': 60},
}

cache_url = os.environ.get('DJANGO_CACHE_URL', '').strip()
if cache_url:
    if not cache_url.startswith(('redis://', 'rediss://', 'unix://')):
        raise RuntimeError('DJANGO_CACHE_URL must be a Redis connection URL.')
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': cache_url,
            'KEY_PREFIX': 'myapp',
            'OPTIONS': {
                'socket_connect_timeout': 5,
                'socket_timeout': 5,
                'health_check_interval': 30,
            },
        },
    }

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = os.environ.get('CORS_ALLOW_CREDENTIALS', 'False').lower() in {'1', 'true', 'yes', 'on'}

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        'DJANGO_CORS_ALLOWED_ORIGINS',
        '' if IS_PRODUCTION else (
            'http://localhost:8000,http://127.0.0.1:8000,http://10.0.2.2:8000,'
            'http://localhost:3000,http://127.0.0.1:3000'
        ),
    ).split(',')
    if origin.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        'DJANGO_CSRF_TRUSTED_ORIGINS',
        '' if IS_PRODUCTION else 'http://localhost:8000,http://127.0.0.1:8000,http://10.0.2.2:8000',
    ).split(',')
    if origin.strip()
]

SECURE_MODE = IS_PRODUCTION or os.environ.get('DJANGO_SECURE', 'False').lower() in {'1', 'true', 'yes', 'on'}
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'same-origin'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = SECURE_MODE
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = SECURE_MODE
SECURE_CSP = {
    'default-src': [CSP.SELF],
    'base-uri': [CSP.SELF],
    'object-src': [CSP.NONE],
    'frame-ancestors': [CSP.SELF],
    'form-action': [CSP.SELF],
    'script-src': [CSP.SELF, CSP.NONCE, 'https://cdn.jsdelivr.net'],
    'style-src': [CSP.SELF, CSP.NONCE, 'https://cdn.jsdelivr.net'],
    'style-src-attr': [CSP.UNSAFE_INLINE],
    'img-src': [CSP.SELF, 'data:', 'http:', 'https:'],
    'font-src': [CSP.SELF, 'data:', 'https:'],
    'connect-src': [CSP.SELF, 'https:'],
    'frame-src': [CSP.SELF, 'https:'],
}
if SECURE_MODE:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    if os.environ.get('DJANGO_TRUST_X_FORWARDED_PROTO', 'False').lower() in {'1', 'true', 'yes', 'on'}:
        SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')


# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration

MAILERS = {
    'default': {
        'BACKEND': os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend'),
        'HOST': os.environ.get('EMAIL_HOST', ''),
        'PORT': int(os.environ.get('EMAIL_PORT', '587')),
        'USERNAME': os.environ.get('EMAIL_HOST_USER', ''),
        'PASSWORD': os.environ.get('EMAIL_HOST_PASSWORD', ''),
        'USE_TLS': os.environ.get('EMAIL_USE_TLS', 'True').lower() in {'1', 'true', 'yes', 'on'},
    },
}
