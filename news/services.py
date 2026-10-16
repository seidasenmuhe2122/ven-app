from datetime import date, datetime, timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone

from accounts.models import AdSenseReport, CustomUser
from .models import AnalyticsEvent, Article, Comment, SystemSetting, UserReport


class DashboardAnalyticsService:
    @staticmethod
    def _normalize_timeframe(timeframe):
        timeframe = (timeframe or 'daily').strip().lower()
        return timeframe if timeframe in {'hourly', 'daily', 'weekly', 'monthly', 'all'} else 'daily'

    @staticmethod
    def _timeframe_days(timeframe):
        mapping = {'hourly': 1, 'daily': 7, 'weekly': 30, 'monthly': 180, 'all': 3650}
        return mapping.get(timeframe, 7)

    @staticmethod
    def _coerce_date(value):
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value).date()
            except ValueError:
                return date.fromisoformat(value)
        return value

    @staticmethod
    def _format_date(value):
        if isinstance(value, str):
            return value
        if hasattr(value, 'strftime'):
            return value.strftime('%Y-%m-%d')
        return str(value)

    @staticmethod
    def _group_by_timeframe(items, timeframe):
        grouped = {}
        for item in items:
            key = DashboardAnalyticsService._coerce_date(item['date'])
            if timeframe == 'weekly':
                key = key - timedelta(days=key.weekday())
            elif timeframe == 'monthly':
                key = key.replace(day=1)
            bucket = grouped.setdefault(key, {'date': key, 'active_users': 0, 'read_count': 0})
            bucket['active_users'] += item.get('active_users') or 0
            bucket['read_count'] += item.get('read_count') or 0

        ordered = []
        for key in sorted(grouped.keys()):
            ordered.append({
                'date': key,
                'active_users': grouped[key]['active_users'],
                'read_count': grouped[key]['read_count'],
            })
        return ordered

    @staticmethod
    def get_summary_metrics():
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        last_30_days = now - timedelta(days=30)

        total_articles = Article.objects.count()
        total_views = Article.objects.aggregate(total_views=Sum('views_count'))['total_views'] or 0
        daily_views = AnalyticsEvent.objects.filter(
            event_type=AnalyticsEvent.EVENT_VIEW,
            created_at__gte=today_start,
        ).aggregate(total_views=Sum('event_value'))['total_views'] or 0
        engagement_volume = AnalyticsEvent.objects.filter(
            event_type=AnalyticsEvent.EVENT_VIEW,
            created_at__gte=last_30_days,
        ).aggregate(total_views=Sum('event_value'))['total_views'] or 0
        active_users = AnalyticsEvent.objects.filter(
            created_at__gte=last_30_days,
            user__isnull=False,
        ).values('user').distinct().count()
        pending_moderations = (
            Comment.objects.filter(status=Comment.STATUS_PENDING).count()
            + UserReport.objects.filter(status=UserReport.STATUS_PENDING).count()
        )
        article_status_counts = {
            item['status']: item['count']
            for item in Article.objects.values('status').annotate(count=Count('id'))
        }
        top_categories = list(
            Article.objects.values('category__name').annotate(article_count=Count('id')).order_by('-article_count')[:5]
        )
        return {
            'total_articles': total_articles,
            'published_articles': article_status_counts.get(Article.STATUS_PUBLISHED, 0),
            'draft_articles': article_status_counts.get(Article.STATUS_DRAFT, 0),
            'articles_in_review': article_status_counts.get(Article.STATUS_UNDER_REVIEW, 0),
            'daily_views': daily_views,
            'engagement_volume': engagement_volume,
            'active_users': active_users or CustomUser.objects.filter(is_active=True).count(),
            'pending_moderations': pending_moderations,
            'top_categories': top_categories,
        }

    @staticmethod
    def build_dashboard_payload(days=30, timeframe='daily'):
        timeframe = DashboardAnalyticsService._normalize_timeframe(timeframe)
        now = timezone.now()
        if timeframe == 'hourly':
            start_time = now - timedelta(hours=23)
            start_date = now.date() - timedelta(days=1)
            raw_points = list(
                AnalyticsEvent.objects.filter(created_at__gte=start_time, event_type=AnalyticsEvent.EVENT_VIEW)
                .annotate(date=TruncHour('created_at'))
                .values('date')
                .annotate(active_users=Count('user', distinct=True), read_count=Sum('event_value'))
                .order_by('date')
            )
            daily_activity = [
                {
                    'date': item['date'].strftime('%Y-%m-%d %H:00') if item.get('date') else '',
                    'active_users': item['active_users'],
                    'read_count': item['read_count'] or 0,
                }
                for item in raw_points
            ]
        else:
            start_date = None if timeframe == 'all' else now.date() - timedelta(days=max(DashboardAnalyticsService._timeframe_days(timeframe) - 1, 0))
            event_filter = AnalyticsEvent.objects.filter(event_type=AnalyticsEvent.EVENT_VIEW)
            if start_date is not None:
                event_filter = event_filter.filter(created_at__date__gte=start_date)
            raw_points = list(
                event_filter.annotate(date=TruncDate('created_at'))
                .values('date')
                .annotate(active_users=Count('user', distinct=True), read_count=Sum('event_value'))
                .order_by('date')
            )
            daily_activity = [
                {
                    'date': item['date'],
                    'active_users': item['active_users'],
                    'read_count': item['read_count'] or 0,
                }
                for item in raw_points
            ]
            if timeframe in {'weekly', 'monthly'}:
                grouped = DashboardAnalyticsService._group_by_timeframe(daily_activity, timeframe)
                daily_activity = [{
                    'date': DashboardAnalyticsService._format_date(item['date']),
                    'active_users': item['active_users'],
                    'read_count': item['read_count'],
                } for item in grouped]
            else:
                daily_activity = [{
                    'date': DashboardAnalyticsService._format_date(item['date']),
                    'active_users': item['active_users'],
                    'read_count': item['read_count'],
                } for item in daily_activity]

        if not daily_activity:
            if timeframe == 'hourly':
                marker = now - timedelta(hours=23)
                slots = []
                for index in range(24):
                    stamp = marker + timedelta(hours=index)
                    slots.append({
                        'date': stamp.strftime('%Y-%m-%d %H:00'),
                        'active_users': 0,
                        'read_count': 0,
                    })
                daily_activity = slots
            elif timeframe == 'all':
                daily_activity = [{
                    'date': DashboardAnalyticsService._format_date(now.date()),
                    'active_users': 0,
                    'read_count': 0,
                }]
            else:
                bucket_count = {'daily': 7, 'weekly': 4, 'monthly': 6}.get(timeframe, 7)
                bucket_start = start_date
                daily_activity = []
                for index in range(bucket_count):
                    point_date = bucket_start + timedelta(days=index)
                    daily_activity.append({
                        'date': DashboardAnalyticsService._format_date(point_date),
                        'active_users': 0,
                        'read_count': 0,
                    })

        category_filter = AnalyticsEvent.objects.filter(event_type=AnalyticsEvent.EVENT_VIEW, category__isnull=False)
        release_filter = AnalyticsEvent.objects.filter(event_type=AnalyticsEvent.EVENT_PUBLISHED)
        share_filter = AnalyticsEvent.objects.filter(event_type=AnalyticsEvent.EVENT_SHARE, article__isnull=False)
        search_filter = AnalyticsEvent.objects.filter(event_type=AnalyticsEvent.EVENT_SEARCH, query_text__isnull=False)

        if start_date is not None:
            category_filter = category_filter.filter(created_at__date__gte=start_date)
            release_filter = release_filter.filter(created_at__date__gte=start_date)
            share_filter = share_filter.filter(created_at__date__gte=start_date)
            search_filter = search_filter.filter(created_at__date__gte=start_date)

        category_breakdown = list(
            category_filter.values('category__name').annotate(total_views=Sum('event_value')).order_by('-total_views')[:6]
        )

        release_trends = list(
            release_filter.annotate(date=TruncDate('created_at')).values('date').annotate(published_count=Count('id')).order_by('date')
        )

        most_shared_articles = list(
            share_filter.values('article__title').annotate(share_count=Sum('event_value')).order_by('-share_count')[:5]
        )

        top_search_terms = list(
            search_filter.exclude(query_text='').values('query_text').annotate(search_count=Count('id')).order_by('-search_count')[:10]
        )

        site_settings = SystemSetting.get_instance()
        ads_enabled = site_settings.ads_enabled
        ad_report_filter = AdSenseReport.objects.all()
        if start_date is not None:
            ad_report_filter = ad_report_filter.filter(date__gte=start_date)

        ad_totals = ad_report_filter.aggregate(
            impressions=Sum('impressions'),
            clicks=Sum('clicks'),
            earnings=Sum('earnings'),
        )
        total_ad_views = int(ad_totals['impressions'] or 0) if ads_enabled else 0
        total_ad_clicks = int(ad_totals['clicks'] or 0) if ads_enabled else 0
        ad_revenue = round(float(ad_totals['earnings'] or 0), 2) if ads_enabled else 0
        ad_click_rate = round((total_ad_clicks / max(total_ad_views, 1)) * 100, 2) if total_ad_views else 0

        ad_report_rows = list(
            ad_report_filter.values('date')
            .annotate(impressions=Sum('impressions'), clicks=Sum('clicks'), earnings=Sum('earnings'))
            .order_by('date')
        )
        ad_revenue_trend = [
            {
                'date': DashboardAnalyticsService._format_date(item['date']),
                'ad_views': int(item['impressions'] or 0) if ads_enabled else 0,
                'clicks': int(item['clicks'] or 0) if ads_enabled else 0,
                'revenue': round(float(item['earnings'] or 0), 2) if ads_enabled else 0,
            }
            for item in ad_report_rows
        ]

        top_articles = []
        article_rows = list(
            Article.objects.filter(status=Article.STATUS_PUBLISHED)
            .order_by('-views_count', '-published_at', '-created_at')[:5]
            .values('title', 'views_count')
        )
        article_total = sum(item['views_count'] or 0 for item in article_rows)
        if article_rows:
            for item in article_rows:
                views_value = item['views_count'] or 0
                percent = round((views_value / article_total) * 100, 1) if article_total else 0
                top_articles.append({
                    'label': item['title'],
                    'value': views_value,
                    'percent': percent,
                    'sales_percent': percent,
                })
        else:
            top_articles = [
                {'label': 'No published articles yet', 'value': 0, 'percent': 0, 'sales_percent': 0},
            ]
        top_products = list(top_articles)

        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        revenue_breakdown = []
        month_cursor = now.date().replace(day=1)
        for month_index in range(5):
            month_start = month_cursor.replace(month=((month_cursor.month - month_index - 1 - 1) % 12) + 1, year=month_cursor.year + ((month_cursor.month - month_index - 1 - 1) // 12))
            month_name = month_names[month_start.month - 1]
            month_total = 0
            month_impressions = 0
            month_clicks = 0
            for item in ad_report_rows:
                item_date = item.get('date')
                if item_date and item_date.year == month_start.year and item_date.month == month_start.month:
                    month_total += float(item.get('earnings') or 0)
                    month_impressions += int(item.get('impressions') or 0)
                    month_clicks += int(item.get('clicks') or 0)
            revenue_breakdown.append({
                'month': month_name,
                'organic': round(month_total, 2) if ads_enabled else 0,
                'social': month_impressions if ads_enabled else 0,
                'referral': month_clicks if ads_enabled else 0,
                'total': round(month_total, 2) if ads_enabled else 0,
            })
        if not any(item['total'] for item in revenue_breakdown):
            revenue_breakdown = [
                {'month': 'Jan', 'organic': 0, 'social': 0, 'referral': 0, 'total': 0},
                {'month': 'Feb', 'organic': 0, 'social': 0, 'referral': 0, 'total': 0},
                {'month': 'Mar', 'organic': 0, 'social': 0, 'referral': 0, 'total': 0},
                {'month': 'Apr', 'organic': 0, 'social': 0, 'referral': 0, 'total': 0},
                {'month': 'May', 'organic': 0, 'social': 0, 'referral': 0, 'total': 0},
            ]
        readership_breakdown = list(revenue_breakdown)
        for item in readership_breakdown:
            item.pop('total', None)

        summary_metrics = DashboardAnalyticsService.get_summary_metrics()
        unique_recent_users = AnalyticsEvent.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=30),
            user__isnull=False,
        ).values('user').distinct().count()
        returning_users = AnalyticsEvent.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=30),
            user__isnull=False,
        ).values('user').annotate(event_count=Count('id')).filter(event_count__gt=1).count()
        avg_views_per_user = round((summary_metrics['engagement_volume'] / max(unique_recent_users, 1)), 2)
        customer_insights = {
            'new_users': max(summary_metrics.get('active_users', 0) - returning_users, 0),
            'returning_users': returning_users,
            'avg_views_per_user': avg_views_per_user,
            'engagement_rate': round((returning_users / max(unique_recent_users, 1)) * 100, 1) if unique_recent_users else 0,
            'active_users': summary_metrics.get('active_users', 0),
            'daily_views': summary_metrics.get('daily_views', 0),
        }

        system_architecture = {
            'nodes': [
                {
                    'name': 'Web',
                    'status': 'healthy' if summary_metrics.get('daily_views', 0) > 0 else 'degraded',
                    'health': 'Live',
                    'data_flow': 'reader traffic',
                },
                {
                    'name': 'Mobile',
                    'status': 'healthy' if summary_metrics.get('total_articles', 0) > 0 else 'degraded',
                    'health': 'Editor',
                    'data_flow': 'content ops',
                },
                {
                    'name': 'API',
                    'status': 'healthy' if len(daily_activity) or len(category_breakdown) or len(release_trends) else 'degraded',
                    'health': 'Online',
                    'data_flow': 'article feed',
                },
                {
                    'name': 'POS',
                    'status': 'healthy' if summary_metrics.get('total_articles', 0) > 0 else 'degraded',
                    'health': 'Indexed',
                    'data_flow': 'stories & tags',
                },
                {
                    'name': 'Inventory',
                    'status': 'healthy' if summary_metrics.get('engagement_volume', 0) > 0 else 'degraded',
                    'health': 'Tracked',
                    'data_flow': 'engagement metrics',
                },
                {
                    'name': 'Marketing',
                    'status': 'healthy' if total_ad_views > 0 else 'degraded',
                    'health': 'Campaigns',
                    'data_flow': 'ad impressions',
                },
            ],
        }

        payload = {
            'timeframe': timeframe,
            'summary_metrics': summary_metrics,
            'daily_activity': [
                {
                    'date': DashboardAnalyticsService._format_date(item['date']) if item.get('date') else '',
                    'active_users': item['active_users'],
                    'read_count': item['read_count'] or 0,
                }
                for item in daily_activity
            ],
            'category_breakdown': [
                {
                    'label': item['category__name'],
                    'value': item['total_views'] or 0,
                }
                for item in category_breakdown
            ],
            'release_trends': [
                {
                    'date': DashboardAnalyticsService._format_date(item['date']) if item.get('date') else '',
                    'count': item['published_count'],
                }
                for item in release_trends
            ],
            'most_shared_articles': [
                {
                    'label': item['article__title'],
                    'share_count': item['share_count'] or 0,
                }
                for item in most_shared_articles
            ],
            'top_search_terms': [
                {
                    'label': item['query_text'],
                    'count': item['search_count'],
                }
                for item in top_search_terms
            ],
            'ad_metrics': {
                'total_ad_views': total_ad_views,
                'total_ad_clicks': total_ad_clicks,
                'ad_revenue': ad_revenue,
                'ad_ctr': ad_click_rate,
                'ads_enabled': ads_enabled,
                'average_cpm': round((ad_revenue / max(total_ad_views, 1)) * 1000, 2) if total_ad_views else 0,
                'ad_network': site_settings.ad_network,
                'ad_unit_ids': {
                    'banner': site_settings.banner_ad_unit_id,
                    'native': site_settings.native_ad_unit_id,
                    'interstitial': site_settings.interstitial_ad_unit_id,
                    'rewarded': site_settings.rewarded_ad_unit_id,
                },
            },
            'ad_revenue_trend': ad_revenue_trend,
            'top_products': top_products,
            'top_articles': top_articles,
            'revenue_breakdown': revenue_breakdown,
            'readership_breakdown': readership_breakdown,
            'customer_insights': customer_insights,
            'system_architecture': system_architecture,
        }
        return payload
