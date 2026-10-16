from django import forms
from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group, Permission
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.db import models
from django.db.models import Count, Sum
from django.utils import timezone


from accounts.models import AdSenseReport, CustomUser
from .models import (
    Article,
    ArticleBookmark,
    ArticleGallery,
    ArticleLike,
    AuditLog,
    Category,
    Comment,
    Feedback,
    NewsletterBroadcast,
    NewsletterSubscriber,
    PushNotification,
    SystemSetting,
    Tag,
    UserReport,
)
from .sanitization import sanitize_rich_text


def apply_style_widget_settings(form_instance):
    for field_name, field in list(form_instance.fields.items()):
        if field_name.endswith(('_text_size', '_text_color', '_background_color')):
            field.widget = forms.HiddenInput()


def apply_rich_text_widget_settings(form_instance):
    for field in form_instance.fields.values():
        if isinstance(field.widget, forms.Textarea) and not isinstance(field.widget, forms.HiddenInput):
            existing_classes = field.widget.attrs.get('class', '').split()
            if 'rich-text-editor' not in existing_classes:
                existing_classes.append('rich-text-editor')
            field.widget.attrs['class'] = ' '.join(existing_classes)
            field.widget.attrs.setdefault('rows', 12)


def _get_client_ip(request):
    return request.META.get('REMOTE_ADDR', '')


def log_admin_action(request, model_name, obj, action, changes=None):
    if not request or not getattr(request, 'user', None) or not request.user.is_authenticated:
        return
    AuditLog.objects.create(
        user=request.user,
        action=action,
        model_name=model_name,
        object_id=str(getattr(obj, 'pk', '')),
        object_repr=str(obj) if obj is not None else '',
        changes=changes or {},
        ip_address=_get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )


class RichTextSanitizationFormMixin:
    def clean(self):
        cleaned_data = super().clean()
        for field_name, field in self.fields.items():
            if (
                field_name in cleaned_data
                and 'rich-text-editor' in field.widget.attrs.get('class', '').split()
            ):
                cleaned_data[field_name] = sanitize_rich_text(cleaned_data[field_name])
        return cleaned_data


class SystemSettingAdminForm(RichTextSanitizationFormMixin, forms.ModelForm):
    class Meta:
        model = SystemSetting
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_style_widget_settings(self)
        apply_rich_text_widget_settings(self)


class ArticleAdminForm(RichTextSanitizationFormMixin, forms.ModelForm):
    class Meta:
        model = Article
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_style_widget_settings(self)
        apply_rich_text_widget_settings(self)


class FeedbackAdminForm(RichTextSanitizationFormMixin, forms.ModelForm):
    class Meta:
        model = Feedback
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_style_widget_settings(self)
        apply_rich_text_widget_settings(self)


class CommentAdminForm(RichTextSanitizationFormMixin, forms.ModelForm):
    class Meta:
        model = Comment
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_style_widget_settings(self)
        apply_rich_text_widget_settings(self)


class UserReportAdminForm(RichTextSanitizationFormMixin, forms.ModelForm):
    class Meta:
        model = UserReport
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_style_widget_settings(self)
        apply_rich_text_widget_settings(self)


class PushNotificationAdminForm(RichTextSanitizationFormMixin, forms.ModelForm):
    class Meta:
        model = PushNotification
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_style_widget_settings(self)
        apply_rich_text_widget_settings(self)


class NewsletterBroadcastAdminForm(RichTextSanitizationFormMixin, forms.ModelForm):
    class Meta:
        model = NewsletterBroadcast
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_style_widget_settings(self)
        apply_rich_text_widget_settings(self)


class CustomUserCreationAdminForm(UserCreationForm):
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=FilteredSelectMultiple('Groups', is_stacked=False),
    )
    user_permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all(),
        required=False,
        widget=FilteredSelectMultiple('User permissions', is_stacked=False),
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'email', 'role', 'groups', 'user_permissions')


class RichTextAdminMixin:
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'class': 'rich-text-editor', 'rows': 12})},
    }

    class Media:
        js = (
            'https://cdn.jsdelivr.net/npm/tinymce@7/tinymce.min.js',
            'news/admin_rich_text_editor.js',
        )


@admin.register(Feedback)
class FeedbackAdmin(RichTextAdminMixin, admin.ModelAdmin):
    form = FeedbackAdminForm
    list_display = ('name', 'email', 'category', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('name', 'email', 'message')
    readonly_fields = ('name', 'email', 'category', 'message', 'created_at')


@admin.register(SystemSetting)
class SystemSettingAdmin(RichTextAdminMixin, admin.ModelAdmin):
    form = SystemSettingAdminForm
    list_display = ('app_name', 'maintenance_mode', 'api_rate_limit', 'updated_at')
    fieldsets = (
        ('Application', {'fields': ('app_name', 'logo', 'ui_buttons', 'maintenance_mode', 'maintenance_message')}),
        ('Policy Content', {
            'fields': (
                'about_content',
                'contact_content',
                'terms_content',
                'privacy_policy_content',
            )
        }),
        ('API Limits', {'fields': ('api_rate_limit',)}),
        ('Monetization', {'fields': (
            'ads_enabled',
            'ad_network',
            'admob_app_id',
            'banner_ad_unit_id',
            'native_ad_unit_id',
            'interstitial_ad_unit_id',
            'rewarded_ad_unit_id',
            'ad_placements',
            'ad_networks',
            'ad_campaigns',
        )}),
    )

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        if request.method == 'POST' and ('_save_app_name' in request.POST or '_save_logo' in request.POST):
            obj = self.get_object(request, object_id) or SystemSetting.get_instance()
            if '_save_app_name' in request.POST:
                obj.app_name = request.POST.get('app_name', obj.app_name).strip() or obj.app_name
            if '_save_logo' in request.POST:
                if request.POST.get('logo-clear') == 'on':
                    obj.logo = None
                elif 'logo' in request.FILES:
                    obj.logo = request.FILES['logo']
            obj.save()
            self.message_user(request, 'System settings updated.')
            return self.response_post_save_change(request, obj)
        return super().changeform_view(request, object_id, form_url, extra_context)

    def has_add_permission(self, request):
        return not SystemSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'model_name', 'object_repr', 'ip_address', 'created_at')
    list_filter = ('action', 'model_name', 'created_at')
    search_fields = ('user__username', 'model_name', 'object_repr', 'ip_address')
    readonly_fields = ('user', 'action', 'model_name', 'object_id', 'object_repr', 'changes', 'ip_address', 'user_agent', 'created_at')
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or getattr(request.user, 'is_superadmin', False)

    @staticmethod
    def _can_manage_publication(request):
        return (
            request.user.is_superuser
            or getattr(request.user, 'is_superadmin', False)
            or getattr(request.user, 'is_editor', False)
        )


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationAdminForm
    list_display = ('username', 'email', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    actions = ('grant_superuser', 'remove_superuser')
    fieldsets = UserAdmin.fieldsets + (
        ('Role Access', {'fields': ('role',)}),
    )
    add_fieldsets = (
        (None, {'classes': ('wide',), 'fields': ('username', 'email', 'password1', 'password2')}),
        ('Role Access', {'fields': ('role',)}),
        ('Permission Access', {'fields': ('groups', 'user_permissions')}),
    )
    search_fields = ('username', 'email', 'role')

    def save_model(self, request, obj, form, change):
        previous_role = None
        if change and obj.pk:
            previous_role = CustomUser.objects.filter(pk=obj.pk).values_list('role', flat=True).first()
        super().save_model(request, obj, form, change)
        if change and previous_role != obj.role:
            log_admin_action(request, 'user', obj, 'role_change', {'previous_role': previous_role, 'new_role': obj.role})
        elif not change:
            log_admin_action(request, 'user', obj, 'create', {'role': obj.role})

    def _can_manage_superusers(self, request):
        return request.user.is_authenticated and request.user.is_superuser

    def grant_superuser(self, request, queryset):
        if not self._can_manage_superusers(request):
            self.message_user(request, 'Only a superuser can grant superuser access.', level='error')
            return

        granted = 0
        for user in queryset:
            if not user.is_superuser:
                user.role = CustomUser.ROLE_SUPERADMIN
                user.is_staff = True
                user.is_superuser = True
                user.save()
                log_admin_action(request, 'user', user, 'role_change', {'new_role': CustomUser.ROLE_SUPERADMIN})
                granted += 1
        self.message_user(request, f'{granted} user(s) granted superuser access.')

    grant_superuser.short_description = 'Grant superuser access to selected users'

    def remove_superuser(self, request, queryset):
        if not self._can_manage_superusers(request):
            self.message_user(request, 'Only a superuser can remove superuser access.', level='error')
            return

        removable = queryset.filter(is_superuser=True).exclude(pk=request.user.pk)
        available_superusers = CustomUser.objects.filter(is_superuser=True).exclude(pk=request.user.pk).count()
        removable_count = removable.count()
        if removable_count > available_superusers:
            self.message_user(request, 'At least one other superuser must remain.', level='error')
            return

        removed = 0
        for user in removable:
            user.role = CustomUser.ROLE_EDITOR
            user.is_staff = True
            user.is_superuser = False
            user.save()
            log_admin_action(request, 'user', user, 'role_change', {'new_role': CustomUser.ROLE_EDITOR})
            removed += 1
        self.message_user(request, f'{removed} user(s) changed from superuser to editor.')

    remove_superuser.short_description = 'Remove superuser access from selected users'


admin.site.unregister(Group)


@admin.register(Group)
class PermissionGroupAdmin(GroupAdmin):
    list_display = ('name', 'permission_count')
    search_fields = ('name', 'permissions__codename', 'permissions__name')
    filter_horizontal = ('permissions',)

    @admin.display(description='Permissions')
    def permission_count(self, obj):
        return obj.permissions.count()


class AdminAuditMixin:
    def _log_object_action(self, request, obj, action, change=None):
        if change is None:
            change = getattr(obj, 'pk', None) is not None
        payload = {}
        if change and getattr(obj, '_meta', None) is not None:
            payload = {'changed_fields': list(getattr(obj, '_meta', object()).fields or [])}
        log_admin_action(request, obj._meta.model_name, obj, action, payload)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        action = 'update' if change else 'create'
        changes = {'changed_fields': list(form.changed_data)} if change else {'created': True}
        log_admin_action(request, obj._meta.model_name, obj, action, changes)

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        log_admin_action(request, obj._meta.model_name, obj, 'delete', {'deleted': True})

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            log_admin_action(request, obj._meta.model_name, obj, 'delete', {'deleted': True})
        super().delete_queryset(request, queryset)
@admin.register(Category)
class CategoryAdmin(AdminAuditMixin, admin.ModelAdmin):
    list_display = ('name', 'parent', 'is_active', 'created_at')
    list_filter = ('is_active', 'parent')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Category', {'fields': ('name', 'slug', 'parent', 'is_active')}),
        ('Metadata', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(Tag)
class TagAdmin(AdminAuditMixin, admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


class ArticleGalleryInline(admin.TabularInline):
    model = ArticleGallery
    extra = 1
    fields = ('image', 'image_url', 'caption')


@admin.register(Article)
class ArticleAdmin(AdminAuditMixin, RichTextAdminMixin, admin.ModelAdmin):
    form = ArticleAdminForm
    list_display = (
        'title',
        'author',
        'category',
        'status',
        'is_featured',
        'is_breaking',
        'published_at',
        'views_count',
        'read_time_minutes',
    )
    list_filter = ('status', 'is_featured', 'is_breaking', 'category', 'author')
    search_fields = ('title', 'summary', 'content', 'author__username')
    prepopulated_fields = {'slug': ('title',)}
    autocomplete_fields = ('category', 'tags', 'author')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [ArticleGalleryInline]
    fieldsets = (
        ('Content', {
            'fields': (
                'author',
                'title',
                'slug',
                'summary',
                'content',
                'category',
                'tags',
            )
        }),
        ('Publishing', {
            'fields': (
                'status',
                'is_featured',
                'is_breaking',
                'published_at',
                'views_count',
                'read_time_minutes',
            )
        }),
        ('Media', {
            'fields': ('cover_image', 'image_url', 'video_url')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    actions = [
        'mark_as_published',
        'mark_as_draft',
        'mark_as_archived',
        'send_article_notifications',
    ]

    @staticmethod
    def _can_manage_publication(request):
        return (
            request.user.is_superuser
            or getattr(request.user, 'is_superadmin', False)
            or getattr(request.user, 'is_editor', False)
        )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser or getattr(request.user, 'is_superadmin', False) or getattr(request.user, 'is_editor', False):
            return qs
        if getattr(request.user, 'is_author', False):
            return qs.filter(author=request.user)
        return qs.none()

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser or getattr(request.user, 'is_superadmin', False):
            return True
        if getattr(request.user, 'is_editor', False):
            return True
        if getattr(request.user, 'is_author', False):
            if obj is None:
                return True
            return obj.author_id == request.user.pk
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or getattr(request.user, 'is_superadmin', False)

    def save_model(self, request, obj, form, change):
        if getattr(request.user, 'is_author', False) and not obj.author_id:
            obj.author = request.user
        if getattr(request.user, 'is_author', False):
            obj.status = Article.STATUS_UNDER_REVIEW
            obj.is_featured = False
            obj.is_breaking = False
        super().save_model(request, obj, form, change)

    def mark_as_published(self, request, queryset):
        if not self._can_manage_publication(request):
            self.message_user(request, 'Only editors and administrators can publish articles.', level='error')
            return
        queryset.update(status=Article.STATUS_PUBLISHED, published_at=timezone.now())
        for article in queryset:
            log_admin_action(request, 'article', article, 'publish', {'status': Article.STATUS_PUBLISHED})

    mark_as_published.short_description = 'Mark selected articles as Published'

    def mark_as_draft(self, request, queryset):
        if not self._can_manage_publication(request):
            self.message_user(request, 'Only editors and administrators can change article status.', level='error')
            return
        queryset.update(status=Article.STATUS_DRAFT)
        for article in queryset:
            log_admin_action(request, 'article', article, 'update', {'status': Article.STATUS_DRAFT})

    mark_as_draft.short_description = 'Mark selected articles as Draft'

    def mark_as_archived(self, request, queryset):
        if not self._can_manage_publication(request):
            self.message_user(request, 'Only editors and administrators can change article status.', level='error')
            return
        queryset.update(status=Article.STATUS_ARCHIVED)
        for article in queryset:
            log_admin_action(request, 'article', article, 'update', {'status': Article.STATUS_ARCHIVED})

    mark_as_archived.short_description = 'Mark selected articles as Archived'

    def send_article_notifications(self, request, queryset):
        if not self._can_manage_publication(request):
            self.message_user(request, 'Only editors and administrators can send article notifications.', level='error')
            return
        sent_at = timezone.now()
        sent_count = 0
        for article in queryset:
            notification = PushNotification.objects.filter(
                target_type=PushNotification.TARGET_ARTICLE,
                article_id=article.pk,
            ).order_by('-created_at').first()
            if notification is None:
                notification = PushNotification(
                    target_type=PushNotification.TARGET_ARTICLE,
                    article_id=article.pk,
                    title=article.title,
                    body=article.summary or article.content,
                )
            else:
                notification.title = article.title
                notification.body = article.summary or article.content
            notification.is_sent = True
            notification.sent_at = sent_at
            notification.sent_by = request.user
            notification.save(update_fields=('title', 'body', 'is_sent', 'sent_at', 'sent_by'))
            sent_count += 1
        self.message_user(request, f'{sent_count} article notification(s) sent.')

    send_article_notifications.short_description = 'Send notification for selected articles'


@admin.register(ArticleGallery)
class ArticleGalleryAdmin(admin.ModelAdmin):
    list_display = ('article', 'caption', 'created_at')
    list_filter = ('article',)
    search_fields = ('article__title', 'caption')


@admin.register(Comment)
class CommentAdmin(AdminAuditMixin, RichTextAdminMixin, admin.ModelAdmin):
    form = CommentAdminForm
    list_display = ('article', 'user', 'parent', 'status', 'created_at')
    list_filter = ('status', 'article')
    search_fields = ('content', 'user__username', 'article__title')
    actions = ['approve_comments', 'mark_as_spam', 'mark_as_deleted']

    def approve_comments(self, request, queryset):
        queryset.update(status=Comment.STATUS_APPROVED)
        for comment in queryset:
            log_admin_action(request, 'comment', comment, 'approve', {'status': Comment.STATUS_APPROVED})

    approve_comments.short_description = 'Approve selected comments'

    def mark_as_spam(self, request, queryset):
        queryset.update(status=Comment.STATUS_SPAM)
        for comment in queryset:
            log_admin_action(request, 'comment', comment, 'update', {'status': Comment.STATUS_SPAM})

    mark_as_spam.short_description = 'Mark selected comments as Spam'

    def mark_as_deleted(self, request, queryset):
        queryset.update(status=Comment.STATUS_DELETED)
        for comment in queryset:
            log_admin_action(request, 'comment', comment, 'delete', {'status': Comment.STATUS_DELETED})

    mark_as_deleted.short_description = 'Mark selected comments as Deleted'


@admin.register(ArticleLike)
class ArticleLikeAdmin(admin.ModelAdmin):
    list_display = ('article', 'user', 'created_at')
    list_filter = ('article', 'user')
    search_fields = ('article__title', 'user__username')


@admin.register(ArticleBookmark)
class ArticleBookmarkAdmin(admin.ModelAdmin):
    list_display = ('article', 'user', 'created_at')
    list_filter = ('article', 'user')
    search_fields = ('article__title', 'user__username')


@admin.register(UserReport)
class UserReportAdmin(AdminAuditMixin, RichTextAdminMixin, admin.ModelAdmin):
    form = UserReportAdminForm
    list_display = ('reporter', 'article', 'comment', 'status', 'created_at')
    list_filter = ('status', 'article', 'comment')
    search_fields = ('reason', 'reporter__username', 'article__title')
    actions = ['resolve_reports', 'dismiss_reports']

    def resolve_reports(self, request, queryset):
        queryset.update(status=UserReport.STATUS_RESOLVED, resolved_at=timezone.now())
        for report in queryset:
            log_admin_action(request, 'userreport', report, 'resolve', {'status': UserReport.STATUS_RESOLVED})

    resolve_reports.short_description = 'Mark selected reports as Resolved'

    def dismiss_reports(self, request, queryset):
        queryset.update(status=UserReport.STATUS_DISMISSED, resolved_at=timezone.now())
        for report in queryset:
            log_admin_action(request, 'userreport', report, 'dismiss', {'status': UserReport.STATUS_DISMISSED})

    dismiss_reports.short_description = 'Mark selected reports as Dismissed'


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ('email', 'is_active', 'subscribed_at', 'unsubscribed_at')
    list_filter = ('is_active',)
    search_fields = ('email',)
    actions = ['deactivate_subscribers']

    def deactivate_subscribers(self, request, queryset):
        queryset.update(is_active=False, unsubscribed_at=timezone.now())

    deactivate_subscribers.short_description = 'Deactivate selected subscribers'


@admin.register(PushNotification)
class PushNotificationAdmin(RichTextAdminMixin, admin.ModelAdmin):
    form = PushNotificationAdminForm
    fieldsets = (
        ('Notification', {
            'fields': (
                'title',
                'body',
                'target_type',
                'topic',
                'article_id',
            )
        }),
        ('Delivery', {
            'fields': (
                'sent_by',
                'is_sent',
                'sent_at',
            )
        }),
    )
    list_display = ('title', 'target_type', 'topic', 'article_id', 'is_sent', 'sent_at', 'created_at')
    list_filter = ('target_type', 'is_sent')
    search_fields = ('title', 'body', 'topic')
    actions = ['send_selected_push_notifications']

    def send_selected_push_notifications(self, request, queryset):
        for notification in queryset:
            notification.is_sent = True
            notification.sent_at = timezone.now()
            notification.save()

    send_selected_push_notifications.short_description = 'Mark selected push notifications as sent'


@admin.register(NewsletterBroadcast)
class NewsletterBroadcastAdmin(RichTextAdminMixin, admin.ModelAdmin):
    form = NewsletterBroadcastAdminForm
    list_display = ('subject', 'sent_at', 'is_sent', 'created_at')
    list_filter = ('is_sent',)
    search_fields = ('subject', 'content')
    actions = ['mark_broadcasts_as_sent']

    def mark_broadcasts_as_sent(self, request, queryset):
        for broadcast in queryset:
            broadcast.is_sent = True
            broadcast.sent_at = timezone.now()
            broadcast.save()

    mark_broadcasts_as_sent.short_description = 'Mark selected broadcasts as sent'

admin.site.register(AdSenseReport)