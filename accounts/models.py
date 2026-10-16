from django.contrib.auth.models import AbstractUser, BaseUserManager, Permission
from django.db import models


class CustomUserManager(BaseUserManager):
    def _create_user(self, username, email, password, **extra_fields):
        if not username:
            raise ValueError('The username field is required.')
        email = self.normalize_email(email) if email else ''
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        extra_fields.setdefault('role', CustomUser.ROLE_SUBSCRIBER)
        return self._create_user(username, email, password, **extra_fields)

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', CustomUser.ROLE_SUPERADMIN)
        return self._create_user(username, email, password, **extra_fields)


class CustomUser(AbstractUser):
    ROLE_SUPERADMIN = 'superadmin'
    ROLE_EDITOR = 'editor'
    ROLE_AUTHOR = 'author'
    ROLE_SUBSCRIBER = 'subscriber'

    ROLE_CHOICES = [
        (ROLE_SUPERADMIN, 'SuperAdmin'),
        (ROLE_EDITOR, 'Editor'),
        (ROLE_AUTHOR, 'Author / Journalist'),
        (ROLE_SUBSCRIBER, 'Subscriber / User'),
    ]

    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default=ROLE_SUBSCRIBER)
    objects = CustomUserManager()

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'

    @classmethod
    def _permissions_for_role(cls, role, is_superuser=False):
        if is_superuser or role == cls.ROLE_SUPERADMIN:
            return Permission.objects.filter(content_type__app_label__in=['accounts', 'news', 'auth'])
        if role == cls.ROLE_EDITOR:
            return Permission.objects.filter(
                content_type__app_label='news',
                codename__in=[
                    'view_article', 'add_article', 'change_article',
                    'view_category', 'add_category', 'change_category',
                    'view_tag', 'add_tag', 'change_tag',
                    'view_comment', 'add_comment', 'change_comment', 'delete_comment',
                    'view_feedback', 'view_userreport', 'change_userreport',
                    'view_systemsetting',
                    'view_pushnotification', 'add_pushnotification', 'change_pushnotification',
                ],
            )
        if role == cls.ROLE_AUTHOR:
            return Permission.objects.filter(
                content_type__app_label='news',
                codename__in=['view_article', 'add_article', 'change_article'],
            )
        return Permission.objects.none()

    def _apply_role_permissions(self, manually_assigned_permissions):
        permissions = self._permissions_for_role(self.role, self.is_superuser)
        self.user_permissions.set(permissions | manually_assigned_permissions)

    def save(self, *args, **kwargs):
        previous = None
        manually_assigned_permissions = Permission.objects.none()
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values('role', 'is_superuser').first()
        if previous:
            previous_permissions = self._permissions_for_role(
                previous['role'],
                previous['is_superuser'],
            )
            manually_assigned_permissions = self.user_permissions.exclude(
                pk__in=previous_permissions.values('pk'),
            )
        elif self.pk:
            manually_assigned_permissions = self.user_permissions.all()

        if self.is_superuser or self.role == self.ROLE_SUPERADMIN:
            self.role = self.ROLE_SUPERADMIN
            self.is_staff = True
            self.is_superuser = True
        elif self.role in [self.ROLE_EDITOR, self.ROLE_AUTHOR]:
            self.is_staff = True
            self.is_superuser = False
        else:
            self.is_staff = False
            self.is_superuser = False

        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            kwargs['update_fields'] = set(update_fields) | {'role', 'is_staff', 'is_superuser'}

        super().save(*args, **kwargs)
        self._apply_role_permissions(manually_assigned_permissions)

    @property
    def is_superadmin(self):
        return self.role == self.ROLE_SUPERADMIN or getattr(self, 'is_superuser', False)

    @property
    def is_editor(self):
        return self.role == self.ROLE_EDITOR

    @property
    def is_author(self):
        return self.role == self.ROLE_AUTHOR

    @property
    def is_subscriber(self):
        return self.role == self.ROLE_SUBSCRIBER

    def can_manage_article(self, article=None):
        if self.is_superadmin or self.is_editor:
            return True
        if self.is_author and article is not None:
            return article.author_id == self.pk
        return False

    def __str__(self):
        return f'{self.username} ({self.role})'
 
class AdSenseReport(models.Model):
    date = models.DateField(auto_now_add=True)
    impressions = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Report {self.date} - ${self.earnings}"
