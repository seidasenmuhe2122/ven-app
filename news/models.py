from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template.defaultfilters import slugify
from django.utils import timezone

from .sanitization import sanitize_rich_text


class Category(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True, blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Categories'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Article(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_UNDER_REVIEW = 'under_review'
    STATUS_PUBLISHED = 'published'
    STATUS_ARCHIVED = 'archived'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_UNDER_REVIEW, 'Under Review'),
        (STATUS_PUBLISHED, 'Published'),
        (STATUS_ARCHIVED, 'Archived'),
    ]

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    summary = models.TextField(blank=True)
    summary_text_size = models.PositiveIntegerField(default=16, help_text='Text size in px for the article summary.')
    summary_text_color = models.CharField(max_length=20, blank=True, default='#111111', help_text='Text color for the article summary.')
    summary_background_color = models.CharField(max_length=20, blank=True, default='#ffffff', help_text='Background color for the article summary.')
    content = models.TextField(help_text='Main article content or rich text body.')
    content_text_size = models.PositiveIntegerField(default=16, help_text='Text size in px for the article body.')
    content_text_color = models.CharField(max_length=20, blank=True, default='#111111', help_text='Text color for the article body.')
    content_background_color = models.CharField(max_length=20, blank=True, default='#ffffff', help_text='Background color for the article body.')
    author = models.ForeignKey('accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='articles')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='articles')
    tags = models.ManyToManyField(Tag, related_name='articles', blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    is_featured = models.BooleanField(default=False)
    is_breaking = models.BooleanField(default=False)
    published_at = models.DateTimeField(blank=True, null=True)
    views_count = models.PositiveIntegerField(default=0)
    read_time_minutes = models.PositiveIntegerField(default=3)
    cover_image = models.ImageField(upload_to='articles/covers/', blank=True, null=True)
    image_url = models.URLField(blank=True, null=True, help_text='Optional external article cover URL')
    video_url = models.URLField(blank=True, null=True, help_text='Optional article video URL')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        self.summary = sanitize_rich_text(self.summary)
        self.content = sanitize_rich_text(self.content)
        if self.status == self.STATUS_PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def estimated_read_time(self):
        if self.read_time_minutes:
            return self.read_time_minutes
        return max(1, len(self.content.split()) // 200)

    def __str__(self):
        return self.title


class ArticleGallery(models.Model):
    article = models.ForeignKey(Article, related_name='gallery', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='articles/gallery/', blank=True, null=True)
    image_url = models.URLField(blank=True, null=True)
    caption = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.article.title} gallery image'


class AnalyticsEvent(models.Model):
    EVENT_VIEW = 'view'
    EVENT_SEARCH = 'search'
    EVENT_SHARE = 'share'
    EVENT_PUBLISHED = 'published'

    EVENT_CHOICES = [
        (EVENT_VIEW, 'View'),
        (EVENT_SEARCH, 'Search'),
        (EVENT_SHARE, 'Share'),
        (EVENT_PUBLISHED, 'Published'),
    ]

    article = models.ForeignKey(Article, on_delete=models.SET_NULL, null=True, blank=True, related_name='analytics_events')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='analytics_events')
    user = models.ForeignKey('accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='analytics_events')
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES, default=EVENT_VIEW)
    event_value = models.PositiveIntegerField(default=1)
    query_text = models.CharField(max_length=255, blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type', 'created_at']),
            models.Index(fields=['article', 'event_type']),
            models.Index(fields=['category', 'event_type']),
        ]

    def __str__(self):
        return f'{self.event_type} for {self.article or self.category or "system"}'


class SystemSetting(models.Model):
    AD_NETWORK_ADMOB = 'admob'
    AD_NETWORK_ADSENSE = 'adsense'
    AD_NETWORK_CUSTOM = 'custom'
    AD_NETWORK_CHOICES = (
        (AD_NETWORK_ADMOB, 'Google AdMob'),
        (AD_NETWORK_ADSENSE, 'Google AdSense'),
        (AD_NETWORK_CUSTOM, 'Custom network'),
    )

    DEFAULT_UI_BUTTONS = {
        'home': {'label': 'Home', 'url': '/'},
        'latest': {'label': 'Latest', 'url': '#latest-stories'},
        'about': {'label': 'About', 'url': '#about-policy'},
        'contact': {'label': 'Contact', 'url': '#contact-policy'},
        'admin': {'label': 'Admin', 'url': '/admin/'},
        'theme': {'label': 'Dark mode', 'light_label': 'Dark mode', 'dark_label': 'Light mode'},
        'view_all': {'label': 'View all', 'url': '#latest-stories'},
        'back_to_news': {'label': 'Back to news', 'url': '/'},
    }

    singleton_name = models.CharField(max_length=50, default='default', editable=False)
    app_name = models.CharField(max_length=120, default='Royal Pro News')
    logo = models.ImageField(upload_to='branding/', blank=True, null=True, help_text='Optional application logo shown in the web header and mobile app.')
    ui_buttons = models.JSONField(default=dict, blank=True, help_text='JSON button labels and URLs for the public UI. Leave empty to use defaults.')
    maintenance_mode = models.BooleanField(default=False)
    maintenance_message = models.TextField(blank=True, default='We are temporarily updating the platform.')
    about_content = models.TextField(blank=True, default='About our company and mission.')
    about_text_size = models.PositiveIntegerField(default=16, help_text='Text size in px for the About page content.')
    about_text_color = models.CharField(max_length=20, blank=True, default='#111111', help_text='Text color for About content.')
    about_background_color = models.CharField(max_length=20, blank=True, default='#ffffff', help_text='Background color for About content.')
    contact_content = models.TextField(blank=True, default='Contact us at support@example.com.')
    contact_text_size = models.PositiveIntegerField(default=16, help_text='Text size in px for the Contact page content.')
    contact_text_color = models.CharField(max_length=20, blank=True, default='#111111', help_text='Text color for Contact content.')
    contact_background_color = models.CharField(max_length=20, blank=True, default='#ffffff', help_text='Background color for Contact content.')
    terms_content = models.TextField(blank=True, default='Terms and conditions content.')
    terms_text_size = models.PositiveIntegerField(default=16, help_text='Text size in px for the Terms page content.')
    terms_text_color = models.CharField(max_length=20, blank=True, default='#111111', help_text='Text color for Terms content.')
    terms_background_color = models.CharField(max_length=20, blank=True, default='#ffffff', help_text='Background color for Terms content.')
    privacy_policy_content = models.TextField(blank=True, default='Privacy policy content.')
    privacy_policy_text_size = models.PositiveIntegerField(default=16, help_text='Text size in px for the Privacy Policy content.')
    privacy_policy_text_color = models.CharField(max_length=20, blank=True, default='#111111', help_text='Text color for Privacy policy content.')
    privacy_policy_background_color = models.CharField(max_length=20, blank=True, default='#ffffff', help_text='Background color for Privacy policy content.')
    latest_version = models.CharField(max_length=32, default='1.0.0', help_text='Latest available app version.')
    min_required_version = models.CharField(max_length=32, default='1.0.0', help_text='Minimum required app version for access.')
    play_store_url = models.URLField(blank=True, default='https://play.google.com/store/apps')
    app_store_url = models.URLField(blank=True, default='https://apps.apple.com/')
    api_rate_limit = models.PositiveIntegerField(default=1000)
    ads_enabled = models.BooleanField(default=True)
    banner_ad_unit_id = models.CharField(max_length=255, blank=True, default='ca-app-pub-3940256099942544/6300978111')
    native_ad_unit_id = models.CharField(max_length=255, blank=True, default='ca-app-pub-3940256099942544/2247696110')
    ad_network = models.CharField(max_length=20, choices=AD_NETWORK_CHOICES, default=AD_NETWORK_ADMOB)
    admob_app_id = models.CharField(max_length=255, blank=True, default='')
    interstitial_ad_unit_id = models.CharField(max_length=255, blank=True, default='ca-app-pub-3940256099942544/1033173712')
    rewarded_ad_unit_id = models.CharField(max_length=255, blank=True, default='ca-app-pub-3940256099942544/5224354917')
    ad_placements = models.JSONField(default=dict, blank=True, help_text='Optional placement limits, for example {"feed": 3, "article": 2}.')
    ad_networks = models.JSONField(default=list, blank=True, help_text='Unlimited list of enabled ad networks and their placement IDs.')
    ad_campaigns = models.JSONField(default=list, blank=True, help_text='Unlimited list of campaigns with network, placement, and targeting metadata.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'System Setting'
        verbose_name_plural = 'System Settings'

    def save(self, *args, **kwargs):
        self.singleton_name = 'default'
        self.pk = 1
        if not isinstance(self.ui_buttons, dict):
            self.ui_buttons = {}
        self.about_content = sanitize_rich_text(self.about_content)
        self.contact_content = sanitize_rich_text(self.contact_content)
        self.terms_content = sanitize_rich_text(self.terms_content)
        self.privacy_policy_content = sanitize_rich_text(self.privacy_policy_content)
        super().save(*args, **kwargs)

    @classmethod
    def get_instance(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return self.app_name


class Feedback(models.Model):
    CATEGORY_BUG = 'bug'
    CATEGORY_SUGGESTION = 'suggestion'
    CATEGORY_QUESTION = 'question'
    CATEGORY_OTHER = 'other'

    CATEGORY_CHOICES = [
        (CATEGORY_BUG, 'Bug'),
        (CATEGORY_SUGGESTION, 'Suggestion'),
        (CATEGORY_QUESTION, 'Question'),
        (CATEGORY_OTHER, 'Other'),
    ]

    name = models.CharField(max_length=120, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_BUG)
    message = models.TextField()
    message_text_size = models.PositiveIntegerField(default=16, help_text='Text size in px for the feedback message.')
    message_text_color = models.CharField(max_length=20, blank=True, default='#111111', help_text='Text color for the feedback message.')
    message_background_color = models.CharField(max_length=20, blank=True, default='#ffffff', help_text='Background color for the feedback message.')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Feedback'
        verbose_name_plural = 'Feedback'

    def __str__(self):
        return f'{self.category} - {self.name or "anonymous"}'


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('approve', 'Approve'),
        ('publish', 'Publish'),
        ('role_change', 'Role Change'),
        ('login', 'Login'),
    ]

    user = models.ForeignKey('accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=120)
    object_id = models.CharField(max_length=255, blank=True, default='')
    object_repr = models.CharField(max_length=255, blank=True, default='')
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'

    def __str__(self):
        return f'{self.user} - {self.action} - {self.model_name}'


class Comment(models.Model):
    STATUS_APPROVED = 'approved'
    STATUS_PENDING = 'pending'
    STATUS_SPAM = 'spam'
    STATUS_DELETED = 'deleted'

    STATUS_CHOICES = [
        (STATUS_APPROVED, 'Approved'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_SPAM, 'Spam'),
        (STATUS_DELETED, 'Deleted'),
    ]

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE, related_name='comments')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    content = models.TextField()
    content_text_size = models.PositiveIntegerField(default=16, help_text='Text size in px for comments.')
    content_text_color = models.CharField(max_length=20, blank=True, default='#111111', help_text='Text color for comments.')
    content_background_color = models.CharField(max_length=20, blank=True, default='#ffffff', help_text='Background color for comments.')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} on {self.article.title}'


class ArticleLike(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE, related_name='liked_articles')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('article', 'user')

    def __str__(self):
        return f'{self.user.username} likes {self.article.title}'


class ArticleBookmark(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='bookmarks')
    user = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE, related_name='bookmarked_articles')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('article', 'user')

    def __str__(self):
        return f'{self.user.username} bookmarked {self.article.title}'


class UserReport(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_RESOLVED = 'resolved'
    STATUS_DISMISSED = 'dismissed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_RESOLVED, 'Resolved'),
        (STATUS_DISMISSED, 'Dismissed'),
    ]

    reporter = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE, related_name='reports_made')
    article = models.ForeignKey(Article, on_delete=models.CASCADE, null=True, blank=True, related_name='reports')
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True, related_name='reports')
    reason = models.TextField()
    reason_text_size = models.PositiveIntegerField(default=16, help_text='Text size in px for the report reason.')
    reason_text_color = models.CharField(max_length=20, blank=True, default='#111111', help_text='Text color for the report reason.')
    reason_background_color = models.CharField(max_length=20, blank=True, default='#ffffff', help_text='Background color for the report reason.')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        target = self.article.title if self.article else self.comment
        return f'{self.reporter.username} reported {target}'


class DashboardWidgetConfig(models.Model):
    WIDGET_TYPE_METRIC = 'metric'
    WIDGET_TYPE_CHART = 'chart'
    WIDGET_TYPE_DONUT = 'donut'

    WIDGET_TYPE_CHOICES = [
        (WIDGET_TYPE_METRIC, 'Metric'),
        (WIDGET_TYPE_CHART, 'Chart'),
        (WIDGET_TYPE_DONUT, 'Donut'),
    ]

    widget_id = models.CharField(max_length=64, unique=True)
    widget_type = models.CharField(max_length=20, choices=WIDGET_TYPE_CHOICES, default=WIDGET_TYPE_METRIC)
    title = models.CharField(max_length=120, default='Custom metric')
    value = models.IntegerField(default=0)
    source = models.CharField(max_length=64, default='live', blank=True)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'created_at']

    def __str__(self):
        return f'{self.title} ({self.widget_type})'


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    unsubscribed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-subscribed_at']

    def __str__(self):
        return self.email


class PushNotification(models.Model):
    TARGET_ALL = 'all'
    TARGET_TOPIC = 'topic'
    TARGET_ARTICLE = 'article'

    TARGET_CHOICES = [
        (TARGET_ALL, 'All Users'),
        (TARGET_TOPIC, 'Target Topic'),
        (TARGET_ARTICLE, 'Target Article'),
    ]

    title = models.CharField(max_length=200)
    body = models.TextField()
    body_text_size = models.PositiveIntegerField(default=16, help_text='Text size in px for the notification body.')
    body_text_color = models.CharField(max_length=20, blank=True, default='#111111', help_text='Text color for the notification body.')
    body_background_color = models.CharField(max_length=20, blank=True, default='#ffffff', help_text='Background color for the notification body.')
    target_type = models.CharField(max_length=20, choices=TARGET_CHOICES, default=TARGET_ALL)
    topic = models.CharField(max_length=100, blank=True, default='')
    article_id = models.PositiveIntegerField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    sent_by = models.ForeignKey('accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='push_notifications')
    is_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


@receiver(post_save, sender=Article)
def create_article_notification(sender, instance, created, **kwargs):
    if not created:
        return
    PushNotification.objects.create(
        title=instance.title,
        body=instance.summary or instance.content,
        target_type=PushNotification.TARGET_ARTICLE,
        article_id=instance.pk,
    )


class NewsletterBroadcast(models.Model):
    subject = models.CharField(max_length=255)
    content = models.TextField()
    content_text_size = models.PositiveIntegerField(default=16, help_text='Text size in px for the newsletter content.')
    content_text_color = models.CharField(max_length=20, blank=True, default='#111111', help_text='Text color for the newsletter content.')
    content_background_color = models.CharField(max_length=20, blank=True, default='#ffffff', help_text='Background color for the newsletter content.')
    sent_at = models.DateTimeField(blank=True, null=True)
    sent_by = models.ForeignKey('accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='broadcasts')
    is_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.subject