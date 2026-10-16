from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AnalyticsDashboardView,
    ArticleViewSet,
    AuditLogViewSet,
    CategoryViewSet,
    DashboardStatsView,
    DashboardWidgetsView,
    FeedbackSubmissionView,
    ThrottledObtainAuthToken,
    RegisterView,
    SystemSettingViewSet,
    TagViewSet,
    UserDetailView,
    get_news_dashboard_metrics,
    article_notification_status,
)

router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'tags', TagViewSet)
router.register(r'articles', ArticleViewSet)
router.register(r'settings', SystemSettingViewSet)
router.register(r'audit-logs', AuditLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('login/', ThrottledObtainAuthToken.as_view(), name='api_login'),
    path('register/', RegisterView.as_view(), name='api_register'),
    path('me/', UserDetailView.as_view(), name='api_me'),
    path('dashboard-stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('dashboard-metrics/', get_news_dashboard_metrics, name='dashboard-metrics'),
    path('dashboard/widgets/', DashboardWidgetsView.as_view(), name='dashboard-widgets'),
    path('analytics-dashboard/', AnalyticsDashboardView.as_view(), name='analytics-dashboard'),
    path('admin/analytics/', AnalyticsDashboardView.as_view(), name='admin-analytics'),
    path('feedback/', FeedbackSubmissionView.as_view(), name='api_feedback'),
    path('article-notifications/<int:article_id>/', article_notification_status, name='article-notification-status'),
]