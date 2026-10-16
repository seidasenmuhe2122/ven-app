from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.template.defaultfilters import slugify
from rest_framework import serializers

from accounts.models import CustomUser
from .models import Article, ArticleGallery, AuditLog, Category, Feedback, SystemSetting, Tag
from .sanitization import sanitize_rich_text


class TagSerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(required=False, allow_blank=True)

    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug')

    def create(self, validated_data):
        if not validated_data.get('slug'):
            validated_data['slug'] = slugify(validated_data.get('name', ''))
        return super().create(validated_data)


class CategorySerializer(serializers.ModelSerializer):
    parent_name = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()
    slug = serializers.SlugField(required=False, allow_blank=True)

    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'parent', 'parent_name', 'is_active', 'children')

    def get_parent_name(self, obj):
        return obj.parent.name if obj.parent else None

    def get_children(self, obj):
        return [
            {
                'id': child.id,
                'name': child.name,
                'slug': child.slug,
                'parent': child.parent_id,
            }
            for child in obj.children.filter(is_active=True)
        ]

    def create(self, validated_data):
        if not validated_data.get('slug'):
            validated_data['slug'] = slugify(validated_data.get('name', ''))
        return super().create(validated_data)


class ArticleGallerySerializer(serializers.ModelSerializer):
    class Meta:
        model = ArticleGallery
        fields = ('id', 'image', 'image_url', 'caption')


class ArticleSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')
    tags = TagSerializer(many=True, read_only=True)
    gallery = ArticleGallerySerializer(many=True, read_only=True)

    class Meta:
        model = Article
        fields = (
            'id',
            'title',
            'slug',
            'summary',
            'content',
            'category',
            'category_name',
            'tags',
            'status',
            'is_featured',
            'is_breaking',
            'published_at',
            'views_count',
            'read_time_minutes',
            'cover_image',
            'image_url',
            'video_url',
            'gallery',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('views_count', 'created_at', 'updated_at')


class SystemSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSetting
        fields = (
            'id',
            'app_name',
            'logo',
            'ui_buttons',
            'maintenance_mode',
            'maintenance_message',
            'about_content',
            'about_text_size',
            'about_text_color',
            'about_background_color',
            'contact_content',
            'contact_text_size',
            'contact_text_color',
            'contact_background_color',
            'terms_content',
            'terms_text_size',
            'terms_text_color',
            'terms_background_color',
            'privacy_policy_content',
            'privacy_policy_text_size',
            'privacy_policy_text_color',
            'privacy_policy_background_color',
            'latest_version',
            'min_required_version',
            'play_store_url',
            'app_store_url',
            'api_rate_limit',
            'ads_enabled',
            'banner_ad_unit_id',
            'native_ad_unit_id',
            'ad_network',
            'admob_app_id',
            'interstitial_ad_unit_id',
            'rewarded_ad_unit_id',
            'ad_placements',
            'ad_networks',
            'ad_campaigns',
            'updated_at',
        )

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        if not request or not getattr(request.user, 'is_staff', False):
            for field_name in (
                'api_rate_limit',
                'admob_app_id',
                'banner_ad_unit_id',
                'native_ad_unit_id',
                'interstitial_ad_unit_id',
                'rewarded_ad_unit_id',
                'ad_placements',
                'ad_networks',
                'ad_campaigns',
            ):
                fields.pop(field_name, None)
        return fields


class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ('id', 'name', 'email', 'category', 'message', 'created_at')

    def validate_message(self, value):
        return sanitize_rich_text(value)


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = (
            'id',
            'user',
            'user_name',
            'action',
            'model_name',
            'object_id',
            'object_repr',
            'changes',
            'ip_address',
            'user_agent',
            'created_at',
        )

    def get_user_name(self, obj):
        return obj.user.username if obj.user else None


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=12)
    password2 = serializers.CharField(write_only=True, min_length=12)

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'password', 'password2')

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({'password': "Password fields didn't match."})
        candidate = CustomUser(
            username=attrs['username'],
            email=attrs.get('email', ''),
        )
        try:
            validate_password(attrs['password'], candidate)
        except DjangoValidationError as error:
            raise serializers.ValidationError({'password': error.messages}) from error
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        user = CustomUser.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=password,
            role=CustomUser.ROLE_SUBSCRIBER,
        )
        return user