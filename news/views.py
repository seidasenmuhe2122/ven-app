import uuid

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, F, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.generic import DetailView, TemplateView
from rest_framework import filters, permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from rest_framework.views import APIView

from accounts.models import CustomUser
from .models import AnalyticsEvent, Article, AuditLog, Category, DashboardWidgetConfig, Feedback, PushNotification, SystemSetting, Tag
from .serializers import AuditLogSerializer, CategorySerializer, ArticleSerializer, FeedbackSerializer, RegisterSerializer, SystemSettingSerializer, TagSerializer
from .services import DashboardAnalyticsService


class LoginRateThrottle(AnonRateThrottle):
    scope = 'login'


class ThrottledObtainAuthToken(ObtainAuthToken):
    throttle_classes = [LoginRateThrottle]
    parser_classes = [JSONParser]


class IsNewsManager(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_superadmin or user.is_editor)
        )


class HomePageView(TemplateView):
    template_name = 'home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        published_articles = Article.objects.select_related('category', 'author').filter(status=Article.STATUS_PUBLISHED).order_by('-published_at', '-created_at')

        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            search_filter = Q(title__icontains=search_query) | Q(content__icontains=search_query) | Q(slug__icontains=search_query)
            if search_query.isdigit():
                search_filter |= Q(pk=int(search_query))
            published_articles = published_articles.filter(search_filter)

        featured_article = published_articles.filter(is_featured=True).first() or published_articles.first()
        latest_articles = list(published_articles.exclude(pk=featured_article.pk))[:6] if featured_article else list(published_articles[:6])
        trending_articles = list(published_articles.order_by('-views_count')[:4])
        top_categories = Category.objects.filter(is_active=True).annotate(article_count=Count('articles')).order_by('-article_count')[:5]

        context.update({
            'title': 'Royal Pro',
            'subtitle': 'Your daily briefing of stories, updates and insights',
            'featured_article': featured_article,
            'latest_articles': latest_articles,
            'trending_articles': trending_articles,
            'top_categories': top_categories,
            'site_settings': SystemSetting.get_instance(),
            'search_query': search_query,
        })
        return context


class ArticleDetailView(DetailView):
    model = Article
    template_name = 'article_detail.html'
    context_object_name = 'article'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return Article.objects.select_related('category', 'author').filter(status=Article.STATUS_PUBLISHED)

    def get_object(self, queryset=None):
        slug = self.kwargs.get(self.slug_url_kwarg)
        queryset = queryset or self.get_queryset()
        return get_object_or_404(queryset, **{self.slug_field: slug})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_settings'] = SystemSetting.get_instance()
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.user.is_authenticated:
            user = request.user
        else:
            user = None

        Article.objects.filter(pk=self.object.pk).update(views_count=F('views_count') + 1)
        self.object.refresh_from_db(fields=['views_count'])

        AnalyticsEvent.objects.create(
            article=self.object,
            category=self.object.category,
            user=user,
            event_type=AnalyticsEvent.EVENT_VIEW,
            event_value=1,
            metadata={'source': 'article_detail_page'},
        )
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)


def article_notification_status(request, article_id):
    article = get_object_or_404(
        Article.objects.filter(status=Article.STATUS_PUBLISHED),
        pk=article_id,
    )
    notification = PushNotification.objects.filter(
        target_type=PushNotification.TARGET_ARTICLE,
        article_id=article.pk,
    ).order_by('-created_at').first()
    return JsonResponse({
        'article_id': article.pk,
        'title': article.title,
        'notification_id': notification.pk if notification else None,
        'is_sent': bool(notification and notification.is_sent),
        'sent_at': notification.sent_at.isoformat() if notification and notification.sent_at else None,
    })


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.select_related('parent').prefetch_related('children').all()
    serializer_class = CategorySerializer
    pagination_class = None

    def get_queryset(self):
        return Category.objects.select_related('parent').prefetch_related('children').all().order_by('name')

    def get_permissions(self):
        if self.request.method in ['GET', 'HEAD', 'OPTIONS']:
            return [permissions.AllowAny()]
        return [IsNewsManager()]

    def perform_create(self, serializer):
        serializer.save()


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all().order_by('name')
    serializer_class = TagSerializer
    pagination_class = None

    def get_permissions(self):
        if self.request.method in ['GET', 'HEAD', 'OPTIONS']:
            return [permissions.AllowAny()]
        return [IsNewsManager()]


class ArticleViewSet(viewsets.ModelViewSet):
    queryset = Article.objects.select_related('category').all().order_by('-published_at', '-created_at')
    serializer_class = ArticleSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'content']
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        queryset = Article.objects.select_related('category').all().order_by('-published_at', '-created_at')

        if not user.is_authenticated:
            return queryset.filter(status=Article.STATUS_PUBLISHED)

        if user.is_superadmin or user.is_editor:
            return queryset

        if user.is_author:
            queryset = queryset.filter(author=user)
            return queryset

        return queryset.filter(status=Article.STATUS_PUBLISHED)

    def retrieve(self, request, *args, **kwargs):
        article = self.get_object()
        if article.status == Article.STATUS_PUBLISHED:
            Article.objects.filter(pk=article.pk).update(views_count=F('views_count') + 1)
            article.refresh_from_db(fields=['views_count'])
            AnalyticsEvent.objects.create(
                article=article,
                category=article.category,
                user=request.user if request.user.is_authenticated else None,
                event_type=AnalyticsEvent.EVENT_VIEW,
                event_value=1,
                metadata={'source': 'article_detail'},
            )
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_authenticated and (user.is_superadmin or user.is_editor or user.is_author):
            extra = {'author': user}
            if user.is_author:
                extra.update({
                    'status': Article.STATUS_UNDER_REVIEW,
                    'is_featured': False,
                    'is_breaking': False,
                })
            serializer.save(**extra)
            return
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied('Only authors, editors, and administrators can create articles.')

    def get_permissions(self):
        if self.request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_queryset_for_filters(self):
        return self.get_queryset()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset_for_filters()

        category_id = request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        search_query = request.query_params.get('search')
        if search_query:
            search_filter = Q(title__icontains=search_query) | Q(content__icontains=search_query) | Q(slug__icontains=search_query)
            if search_query.isdigit():
                search_filter |= Q(pk=int(search_query))
            queryset = queryset.filter(search_filter)

        queryset = queryset.order_by('-published_at', '-created_at')

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        article = self.get_object()
        user = request.user
        if user.is_superadmin or user.is_editor or (user.is_author and article.author_id == user.pk):
            return super().update(request, *args, **kwargs)
        return Response({'detail': 'You do not have permission to edit this article.'}, status=status.HTTP_403_FORBIDDEN)

    def perform_update(self, serializer):
        user = self.request.user
        if user.is_author:
            serializer.save(
                status=Article.STATUS_UNDER_REVIEW,
                is_featured=False,
                is_breaking=False,
            )
            return
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        article = self.get_object()
        user = request.user
        if user.is_superadmin or user.is_editor:
            return super().destroy(request, *args, **kwargs)
        return Response({'detail': 'You do not have permission to delete this article.'}, status=status.HTTP_403_FORBIDDEN)

class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = [JSONParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'registration'

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                },
                'token': token.key,
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
        })


class FeedbackSubmissionView(APIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = [JSONParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'feedback'

    def post(self, request):
        serializer = FeedbackSerializer(data=request.data)
        if serializer.is_valid():
            feedback = serializer.save()
            return Response({
                'status': 'success',
                'data': FeedbackSerializer(feedback).data,
            }, status=status.HTTP_201_CREATED)
        return Response({
            'status': 'error',
            'errors': serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)


class SystemSettingViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SystemSetting.objects.order_by('pk')
    serializer_class = SystemSettingSerializer

    def get_object(self):
        return SystemSetting.get_instance()


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related('user').all().order_by('-created_at')
    serializer_class = AuditLogSerializer
    permission_classes = [IsNewsManager]

    def get_queryset(self):
        return super().get_queryset()


@staff_member_required
def get_news_dashboard_metrics(request):
    """Return admin dashboard metrics using the real analytics models in this project."""
    if not (request.user.is_superadmin or request.user.is_editor):
        return JsonResponse({'detail': 'You do not have permission to view dashboard metrics.'}, status=403)
    today = timezone.now().date()
    total_articles = Article.objects.count()
    published_articles = Article.objects.filter(status=Article.STATUS_PUBLISHED)
    total_news = total_articles
    active_readers = AnalyticsEvent.objects.filter(
        created_at__date=today,
        event_type=AnalyticsEvent.EVENT_VIEW,
        user__isnull=False,
    ).values('user').distinct().count()
    total_daily_views = AnalyticsEvent.objects.filter(
        created_at__date=today,
        event_type=AnalyticsEvent.EVENT_VIEW,
    ).aggregate(total=Sum('event_value'))['total'] or 0
    daily_ad_views = max(int(total_daily_views * 0.22), 0)
    ad_revenue = round(daily_ad_views * 0.045, 2)
    ctr = round((daily_ad_views / max(total_daily_views, 1)) * 100, 2) if total_daily_views else 0
    cpm = round((ad_revenue / max(daily_ad_views, 1)) * 1000, 2) if daily_ad_views else 0

    data = {
        'active_readers': active_readers,
        'total_news': total_news,
        'daily_ad_views': daily_ad_views,
        'ad_revenue': float(ad_revenue),
        'ctr': float(ctr),
        'cpm': float(cpm),
        'published_news': published_articles.count(),
        'daily_views': int(total_daily_views),
    }
    return JsonResponse(data)


class DashboardStatsView(APIView):
    permission_classes = [IsNewsManager]

    def get(self, request):
        from django.db.models import Count, Sum
        from .models import Comment, UserReport
        from accounts.models import CustomUser as AccountUser

        stats = {
            'total_articles': Article.objects.count(),
            'daily_views': Article.objects.aggregate(total_views=Sum('views_count'))['total_views'] or 0,
            'pending_moderations': (
                Comment.objects.filter(status=Comment.STATUS_PENDING).count()
                + UserReport.objects.filter(status=UserReport.STATUS_PENDING).count()
            ),
            'active_users': AccountUser.objects.filter(is_active=True).count(),
            'top_categories': [
                {'name': item.name, 'count': item.article_count}
                for item in Category.objects.annotate(article_count=Count('articles')).order_by('-article_count')[:5]
            ],
        }
        return Response(stats)


class DashboardWidgetsView(APIView):
    permission_classes = [IsNewsManager]
    allowed_types = {'metric', 'chart', 'donut'}
    widget_titles = {
        'metric': 'Custom metric',
        'chart': 'Custom chart',
        'donut': 'Audience mix',
    }
    metric_sources = {
        'total_articles': 'total_articles',
        'daily_views': 'daily_views',
        'engagement_volume': 'engagement_volume',
        'active_users': 'active_users',
        'pending_moderations': 'pending_moderations',
        'ad_views': 'ad_views',
        'ad_revenue': 'ad_revenue',
    }

    @staticmethod
    def _summary_values():
        summary = DashboardAnalyticsService.get_summary_metrics()
        extra = DashboardAnalyticsService.build_dashboard_payload()['ad_metrics']
        summary.update({'ad_views': extra['total_ad_views'], 'ad_revenue': extra['ad_revenue']})
        return summary

    @staticmethod
    def _widget_value(widget_type, source):
        summary = DashboardWidgetsView._summary_values()
        source_name = (source or '').strip().lower()
        if widget_type == 'metric' and source_name in summary:
            return summary[source_name]
        return 0

    @staticmethod
    def _normalize_widget(widget, index):
        normalized = dict(widget or {})
        normalized.setdefault('widget_id', f'widget-{index}-{uuid.uuid4().hex[:8]}')
        normalized.setdefault('type', 'metric')
        normalized.setdefault('source', 'daily_views')
        normalized.setdefault('title', DashboardWidgetsView.widget_titles.get(normalized.get('type', 'metric'), 'Custom widget'))
        normalized['value'] = DashboardWidgetsView._widget_value(normalized.get('type', 'metric'), normalized.get('source'))
        return normalized

    def _sync_database(self, widgets):
        stored_ids = []
        for index, widget in enumerate(widgets):
            widget_id = widget.get('widget_id') or f'widget-{index}-{uuid.uuid4().hex[:8]}'
            widget['widget_id'] = widget_id
            widget['type'] = (widget.get('type') or 'metric').lower()
            widget['source'] = (widget.get('source') or 'daily_views').lower()
            widget['title'] = str(widget.get('title') or self.widget_titles.get(widget['type'], 'Custom widget')).strip() or self.widget_titles.get(widget['type'], 'Custom widget')
            widget['value'] = self._widget_value(widget['type'], widget['source'])
            DashboardWidgetConfig.objects.update_or_create(
                widget_id=widget_id,
                defaults={
                    'widget_type': widget['type'],
                    'title': widget['title'],
                    'value': widget['value'],
                    'source': widget['source'],
                    'position': index,
                },
            )
            stored_ids.append(widget_id)

        DashboardWidgetConfig.objects.exclude(widget_id__in=stored_ids).delete()
        return widgets

    def _get_widgets(self, request):
        widgets = list(request.session.get('dashboard_widgets', []))
        if not widgets:
            widgets = [
                {
                    'widget_id': item.widget_id,
                    'type': item.widget_type,
                    'title': item.title,
                    'value': item.value,
                    'source': item.source,
                }
                for item in DashboardWidgetConfig.objects.order_by('position', 'created_at')
            ]
        normalized = [self._normalize_widget(widget, index) for index, widget in enumerate(widgets)]
        normalized = self._sync_database(normalized)
        request.session['dashboard_widgets'] = normalized
        request.session.modified = True
        return normalized

    def get(self, request):
        return Response({'widgets': self._get_widgets(request)}, status=status.HTTP_200_OK)

    def post(self, request):
        widget_type = (request.data.get('widget_type') or request.POST.get('widget_type') or '').strip().lower()

        if widget_type not in self.allowed_types:
            return Response({'detail': 'Unsupported widget type.'}, status=status.HTTP_400_BAD_REQUEST)

        widgets = self._get_widgets(request)
        source = 'daily_views' if widget_type == 'metric' else 'engagement_volume'
        widgets.append({
            'widget_id': f'widget-{len(widgets)}-{uuid.uuid4().hex[:8]}',
            'type': widget_type,
            'source': source,
            'title': self.widget_titles.get(widget_type, 'Custom widget'),
            'value': self._widget_value(widget_type, source),
        })

        widgets = self._sync_database(widgets)
        request.session['dashboard_widgets'] = widgets
        request.session.modified = True
        return Response({'widgets': widgets}, status=status.HTTP_201_CREATED)

    def patch(self, request):
        widget_id = request.data.get('widget_id') or request.data.get('id')
        if not widget_id:
            return Response({'detail': 'Widget id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        widgets = self._get_widgets(request)
        widget = next((item for item in widgets if item.get('widget_id') == widget_id), None)
        if widget is None:
            return Response({'detail': 'Widget not found.'}, status=status.HTTP_404_NOT_FOUND)

        new_type = (request.data.get('widget_type') or widget.get('type') or '').strip().lower()
        if new_type and new_type not in self.allowed_types:
            return Response({'detail': 'Unsupported widget type.'}, status=status.HTTP_400_BAD_REQUEST)

        title = request.data.get('title')
        value = request.data.get('value')
        source = request.data.get('source')

        if title is not None:
            widget['title'] = str(title).strip() or widget.get('title')
        if new_type:
            widget['type'] = new_type
        if source is not None:
            widget['source'] = str(source).strip().lower() or widget.get('source', 'daily_views')
        if value is not None:
            try:
                widget['value'] = int(value)
            except (TypeError, ValueError):
                widget['value'] = self._widget_value(widget.get('type', 'metric'), widget.get('source'))
        widget['value'] = self._widget_value(widget.get('type', 'metric'), widget.get('source'))

        widgets = self._sync_database(widgets)
        request.session['dashboard_widgets'] = widgets
        request.session.modified = True
        return Response({'widgets': widgets}, status=status.HTTP_200_OK)

    def delete(self, request):
        widget_id = request.data.get('widget_id') or request.data.get('id')
        if not widget_id:
            return Response({'detail': 'Widget id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        widgets = self._get_widgets(request)
        updated_widgets = [item for item in widgets if item.get('widget_id') != widget_id]
        updated_widgets = self._sync_database(updated_widgets)
        request.session['dashboard_widgets'] = updated_widgets
        request.session.modified = True
        return Response({'widgets': updated_widgets}, status=status.HTTP_200_OK)


class AnalyticsDashboardView(APIView):
    permission_classes = [IsNewsManager]

    def get(self, request):
        user = request.user
        timeframe = (request.query_params.get('timeframe') or 'daily').strip().lower()
        days = {'hourly': 1, 'daily': 7, 'weekly': 30, 'monthly': 180, 'all': 3650}.get(timeframe, 7)
        payload = DashboardAnalyticsService.build_dashboard_payload(days=days, timeframe=timeframe)
        if request.META.get('HTTP_ACCEPT', '').startswith('text/html'):
            return render(request, 'analytics_dashboard.html', {'payload': payload, 'timeframe': timeframe})
        return Response(payload)
