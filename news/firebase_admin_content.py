import logging
import re
import uuid

from django.utils.html import strip_tags
from django.utils.text import slugify
from firebase_admin import firestore
from firebase_admin.exceptions import FirebaseError
from google.api_core.exceptions import GoogleAPICallError, InvalidArgument
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .announcements import (
    FirebaseConfigurationError,
    FirebaseSuperAdminAuthentication,
    _firestore_client,
)
from .sanitization import sanitize_rich_text

logger = logging.getLogger(__name__)
_ARTICLE_ID = re.compile(r'[A-Za-z0-9_-]{1,128}')
_ARTICLE_STATUSES = {'draft', 'under_review', 'published', 'archived'}
_ARTICLE_FIELDS = {
    'title',
    'slug',
    'summary',
    'content',
    'status',
    'categoryId',
    'tagIds',
    'authorName',
    'publisherName',
}
_MAX_ARTICLE_TEXT_BYTES = 700_000


def _article_id(value):
    if not isinstance(value, str) or not _ARTICLE_ID.fullmatch(value):
        raise ValidationError({'id': 'Article ID is invalid.'})
    return value


def _text_field(data, existing, name, maximum, *, required):
    value = data.get(name, existing.get(name))
    if not isinstance(value, str):
        if name in data:
            raise ValidationError({name: 'This field must be text.'})
        if required:
            raise ValidationError({name: 'This field is required.'})
        return ''
    value = value.strip()
    if required and not value:
        raise ValidationError({name: 'This field is required.'})
    if len(value.encode('utf-8')) > maximum:
        raise ValidationError({name: 'This field is too long.'})
    return value


def _category_details(firestore_client, category_id):
    if isinstance(category_id, bool):
        raise ValidationError({'categoryId': 'Choose an active category.'})
    try:
        category_id = int(category_id)
    except (TypeError, ValueError):
        raise ValidationError({'categoryId': 'Choose an active category.'})
    if category_id < 1:
        raise ValidationError({'categoryId': 'Choose an active category.'})

    snapshot = (
        firestore_client.collection('categories')
        .document(str(category_id))
        .get()
    )
    category = snapshot.to_dict() if snapshot.exists else None
    if not isinstance(category, dict) or category.get('isActive') is not True:
        raise ValidationError({'categoryId': 'Choose an active category.'})
    name = category.get('name')
    if not isinstance(name, str) or not name.strip():
        raise ValidationError({'categoryId': 'The category has no name.'})
    return category_id, name.strip()


def _article_fields(data, existing, firestore_client, *, creating):
    if not isinstance(data, dict):
        raise ValidationError({'detail': 'A JSON object is required.'})
    unsupported = set(data) - _ARTICLE_FIELDS
    if unsupported:
        raise ValidationError({'detail': 'Unsupported article field.'})

    title = _text_field(data, existing, 'title', 255, required=True)
    summary = _text_field(data, existing, 'summary', 20_000, required=True)
    content = _text_field(data, existing, 'content', 650_000, required=True)
    summary = sanitize_rich_text(summary)
    content = sanitize_rich_text(content)
    text = strip_tags(f'{title} {summary} {content}')
    words = re.findall(r'[\w]+', text, flags=re.UNICODE)
    search_tokens = list(dict.fromkeys(word.casefold() for word in words))[:1000]

    status_value = data.get('status', existing.get('status', 'draft'))
    if not isinstance(status_value, str) or status_value not in _ARTICLE_STATUSES:
        raise ValidationError({'status': 'Choose a valid article status.'})

    category_name = existing.get('categoryName', 'Uncategorized')
    category_id = existing.get('categoryId')
    if creating or 'categoryId' in data:
        category_id, category_name = _category_details(
            firestore_client,
            data.get('categoryId', category_id),
        )

    tags = data.get('tagIds', existing.get('tagIds', []))
    if (
        not isinstance(tags, list)
        or len(tags) > 25
        or any(
            isinstance(tag, bool)
            or not isinstance(tag, int)
            or tag < 1
            for tag in tags
        )
    ):
        raise ValidationError({'tagIds': 'Choose valid tags.'})

    raw_slug = data.get('slug', existing.get('slug', ''))
    if raw_slug is not None and not isinstance(raw_slug, str):
        raise ValidationError({'slug': 'Slug must be text.'})
    slug = slugify(raw_slug or title, allow_unicode=True)
    if not slug:
        slug = f'news-{uuid.uuid4().hex[:8]}'

    author_name = _text_field(
        data,
        existing,
        'authorName',
        120,
        required=False,
    )
    publisher_name = _text_field(
        data,
        existing,
        'publisherName',
        120,
        required=False,
    )

    fields = {
        'title': title,
        'slug': slug,
        'summary': summary,
        'content': content,
        'status': status_value,
        'categoryId': category_id,
        'categoryName': category_name,
        'category_name': category_name,
        'tagIds': tags,
        'searchTokens': search_tokens,
        'readTimeMinutes': max(1, (len(words) + 199) // 200),
        'authorName': author_name,
        'publisherName': publisher_name,
        'publisher': publisher_name,
        'updatedAt': firestore.SERVER_TIMESTAMP,
    }
    if creating:
        fields['viewsCount'] = 0
        fields['createdAt'] = firestore.SERVER_TIMESTAMP
    else:
        fields['viewsCount'] = existing.get('viewsCount', 0)
    if status_value == 'published' and existing.get('status') != 'published':
        fields['publishedAt'] = firestore.SERVER_TIMESTAMP
    elif (
        not creating
        and status_value != 'published'
        and 'publishedAt' in existing
    ):
        fields['publishedAt'] = firestore.DELETE_FIELD

    if len(repr(fields).encode('utf-8')) > _MAX_ARTICLE_TEXT_BYTES:
        raise ValidationError({'content': 'This article is too large to publish.'})
    return fields


class FirebaseAdminArticleView(APIView):
    authentication_classes = [FirebaseSuperAdminAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        try:
            firestore_client = _firestore_client()
            fields = _article_fields(
                request.data,
                {},
                firestore_client,
                creating=True,
            )
            article_ref = firestore_client.collection('news').document(
                uuid.uuid4().hex,
            )
            article_ref.set(fields)
        except ValidationError:
            raise
        except FirebaseConfigurationError as error:
            logger.error(
                'Firestore article publishing is not configured: %s',
                type(error).__name__,
            )
            return Response(
                {'detail': 'Firebase article publishing is not configured.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except InvalidArgument:
            return Response(
                {'detail': 'The article is too large to save.'},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        except (FirebaseError, GoogleAPICallError) as error:
            logger.error(
                'Firestore article create failed: %s',
                type(error).__name__,
            )
            return Response(
                {'detail': 'The article could not be saved.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {'id': article_ref.id, 'status': fields['status']},
            status=status.HTTP_201_CREATED,
        )

    def patch(self, request, article_id):
        try:
            article_id = _article_id(article_id)
            firestore_client = _firestore_client()
            article_ref = firestore_client.collection('news').document(article_id)
            snapshot = article_ref.get()
            if not snapshot.exists:
                return Response(status=status.HTTP_404_NOT_FOUND)
            existing = snapshot.to_dict() or {}
            fields = _article_fields(
                request.data,
                existing,
                firestore_client,
                creating=False,
            )
            article_ref.update(fields)
        except ValidationError:
            raise
        except FirebaseConfigurationError as error:
            logger.error(
                'Firestore article publishing is not configured: %s',
                type(error).__name__,
            )
            return Response(
                {'detail': 'Firebase article publishing is not configured.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except InvalidArgument:
            return Response(
                {'detail': 'The article is too large to save.'},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        except (FirebaseError, GoogleAPICallError) as error:
            logger.error(
                'Firestore article update failed: %s',
                type(error).__name__,
            )
            return Response(
                {'detail': 'The article could not be saved.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {'id': article_id, 'status': fields['status']},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, article_id):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', article_id):
            return Response(
                {'detail': 'Article ID is invalid.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            firestore_client = _firestore_client()
            article_ref = firestore_client.collection('news').document(article_id)
            if not article_ref.get().exists:
                return Response(status=status.HTTP_404_NOT_FOUND)

            batch = firestore_client.batch()
            batch.delete(article_ref.collection('images').document('cover'))
            batch.delete(article_ref)
            batch.commit()
        except FirebaseConfigurationError as error:
            logger.error(
                'Firestore article deletion is not configured: %s',
                type(error).__name__,
            )
            return Response(
                {'detail': 'Firebase article deletion is not configured.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except (FirebaseError, GoogleAPICallError) as error:
            logger.error(
                'Firestore article deletion failed: %s',
                type(error).__name__,
            )
            return Response(
                {'detail': 'The article could not be deleted.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)
