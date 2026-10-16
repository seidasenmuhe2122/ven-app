from django import template

from news.services import DashboardAnalyticsService


register = template.Library()


@register.simple_tag
def control_center_data():
    return DashboardAnalyticsService.build_dashboard_payload(days=30, timeframe='daily')