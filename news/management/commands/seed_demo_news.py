from django.core.management.base import BaseCommand
from django.utils import timezone

from news.models import AnalyticsEvent, Article, Category


class Command(BaseCommand):
    help = 'Create demo news data so the portal, dashboard and API pages render real content.'

    def handle(self, *args, **options):
        categories = [
            ('World', 'world'),
            ('Business', 'business'),
            ('Technology', 'technology'),
            ('Sports', 'sports'),
            ('Culture', 'culture'),
        ]

        created_categories = {}
        for name, slug in categories:
            category, _ = Category.objects.get_or_create(name=name, defaults={'slug': slug})
            created_categories[name] = category

        sample_articles = [
            {
                'title': 'Global markets reopen with cautious optimism',
                'summary': 'Investors look for stability as key sectors recover.',
                'content': 'Global markets posted a modest recovery after a period of sharp volatility. Analysts said renewed confidence in consumer demand and easing inflation pressures helped improve sentiment across major financial hubs.',
                'category': created_categories['Business'],
                'views_count': 1450,
                'read_time_minutes': 5,
            },
            {
                'title': 'City officials unveil new transit expansion plan',
                'summary': 'The project aims to reduce congestion and improve access.',
                'content': 'Urban transit planners announced a new expansion program designed to link neighborhoods, reduce commute times, and improve sustainability across the metropolitan region.',
                'category': created_categories['World'],
                'views_count': 1230,
                'read_time_minutes': 4,
            },
            {
                'title': 'AI chip makers race to build greener data centers',
                'summary': 'New infrastructure investments target lower power use and faster performance.',
                'content': 'The next wave of AI hardware is increasingly focused on energy efficiency. Startups and established firms alike are rolling out greener server architecture to cut costs and respond to sustainability goals.',
                'category': created_categories['Technology'],
                'views_count': 1825,
                'read_time_minutes': 6,
            },
            {
                'title': 'Local club lifts title after dramatic final',
                'summary': 'Fans celebrate a thrilling finish as the season reaches its peak.',
                'content': 'A dramatic late goal sealed the title for the home side, sparking celebrations across the city. Coaches praised the team’s resilience and tactical discipline during a tense final.',
                'category': created_categories['Sports'],
                'views_count': 980,
                'read_time_minutes': 3,
            },
            {
                'title': 'Creative district opens new gallery program',
                'summary': 'An arts initiative is bringing more public programming to the city center.',
                'content': 'A new cultural district has launched a gallery series featuring emerging artists, local makers, and community workshops designed to bring more public engagement to the area.',
                'category': created_categories['Culture'],
                'views_count': 760,
                'read_time_minutes': 4,
            },
        ]

        for payload in sample_articles:
            article, created = Article.objects.get_or_create(
                title=payload['title'],
                defaults={
                    'summary': payload['summary'],
                    'content': payload['content'],
                    'category': payload['category'],
                    'status': Article.STATUS_PUBLISHED,
                    'published_at': timezone.now(),
                    'views_count': payload['views_count'],
                    'read_time_minutes': payload['read_time_minutes'],
                    'is_featured': payload['views_count'] >= 1200,
                },
            )
            if created:
                AnalyticsEvent.objects.get_or_create(
                    article=article,
                    category=payload['category'],
                    event_type=AnalyticsEvent.EVENT_VIEW,
                    event_value=payload['views_count'],
                )
                AnalyticsEvent.objects.get_or_create(
                    article=article,
                    category=payload['category'],
                    event_type=AnalyticsEvent.EVENT_SHARE,
                    event_value=max(2, payload['views_count'] // 350),
                )

        self.stdout.write(self.style.SUCCESS(f'Created demo news data for {Article.objects.count()} articles.'))
