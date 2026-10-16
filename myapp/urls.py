import os
from functools import partial

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve as serve_static

from news.views import ArticleDetailView, HomePageView

urlpatterns = [
    path('', HomePageView.as_view(), name='home'),
    path('home/', HomePageView.as_view(), name='home_alias'),
    path('article/<slug:slug>/', ArticleDetailView.as_view(), name='article_detail'),
    path('admin/', admin.site.urls),
    path(settings.ADMIN_URL, include((admin.site.get_urls(), 'admin'), namespace='custom_admin')),
    path('api/', include('news.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif os.environ.get('DJANGO_ENV', '').lower() != 'production':
    urlpatterns += [
        re_path(r'^static/(?P<path>.*)$', partial(serve_static, document_root=settings.STATIC_ROOT)),
        re_path(r'^media/(?P<path>.*)$', partial(serve_static, document_root=settings.MEDIA_ROOT)),
    ]