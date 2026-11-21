import logging
import os
import re
import uuid

from django.conf import settings
from django.http import HttpResponse
from firebase_admin import firestore
from firebase_admin.exceptions import FirebaseError
from google.api_core.exceptions import GoogleAPICallError, InvalidArgument
from PIL import Image, UnidentifiedImageError
from rest_framework import authentication, permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .announcements import (
    FirebaseConfigurationError,
    FirebaseSuperAdminAuthentication,
    _firestore_client,
)

logger = logging.getLogger(__name__)
MAX_FIRESTORE_IMAGE_BYTES = (1 << 20) - 1024
_IMAGE_TYPES = {
    '.jpg': ('image/jpeg', 'JPEG'),
    '.jpeg': ('image/jpeg', 'JPEG'),
    '.png': ('image/png', 'PNG'),
    '.webp': ('image/webp', 'WEBP'),
}
_ARTICLE_ID = re.compile(r'[A-Za-z0-9_-]{1,128}')


class FirebaseArticleImageAuthentication(authentication.BaseAuthentication):
    def authenticate_header(self, request):
        return FirebaseSuperAdminAuthentication().authenticate_header(request)

    def authenticate(self, request):
        if request.method == 'GET':
            return None
        return FirebaseSuperAdminAuthentication().authenticate(request)


class FirebaseArticleImageView(APIView):
    authentication_classes = [FirebaseArticleImageAuthentication]
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def _article_ref(self, article_id):
        if not _ARTICLE_ID.fullmatch(article_id):
            return None
        return _firestore_client().collection('news').document(article_id)

    def get(self, request, article_id):
        try:
            article_ref = self._article_ref(article_id)
            if article_ref is None:
                return Response(
                    {'detail': 'Article ID is invalid.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            article = article_ref.get()
            if not article.exists:
                return Response(status=status.HTTP_404_NOT_FOUND)
            article_data = article.to_dict() or {}
            if article_data.get('status') != 'published':
                return Response(status=status.HTTP_404_NOT_FOUND)
            image = article_ref.collection('images').document('cover').get()
            if not image.exists:
                return Response(status=status.HTTP_404_NOT_FOUND)
            image_data = image.to_dict() or {}
        except FirebaseConfigurationError as error:
            logger.error('Firestore article image configuration failed: %s', error)
            return Response(
                {'detail': 'Article images are temporarily unavailable.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except (FirebaseError, GoogleAPICallError) as error:
            logger.error(
                'Firestore article image read failed: %s',
                type(error).__name__,
            )
            return Response(
                {'detail': 'Article images are temporarily unavailable.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        image_bytes = image_data.get('data')
        content_type = image_data.get('contentType')
        if (
            not isinstance(image_bytes, (bytes, bytearray, memoryview))
            or not isinstance(content_type, str)
            or not _matches_image_type(bytes(image_bytes), content_type)
        ):
            logger.error('Stored Firestore article image is invalid.')
            return Response(
                {'detail': 'The stored article image is invalid.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        response = HttpResponse(bytes(image_bytes), content_type=content_type)
        response['Cache-Control'] = 'public, max-age=31536000, immutable'
        return response

    def put(self, request, article_id):
        upload = request.FILES.get('image')
        if upload is None:
            return Response(
                {'detail': 'An image file is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        content_type, image_format = _IMAGE_TYPES.get(
            os.path.splitext(upload.name)[1].lower(),
            (None, None),
        )
        if content_type is None:
            return Response(
                {'detail': 'Choose a JPEG, PNG, or WebP image.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if upload.size > MAX_FIRESTORE_IMAGE_BYTES:
            return Response(
                {'detail': 'The image exceeds the Firestore document limit.'},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        try:
            with Image.open(upload) as image:
                if image.format != image_format:
                    return Response(
                        {'detail': 'Image content does not match its file type.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                image.verify()
        except (
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
            OSError,
            UnidentifiedImageError,
            ValueError,
        ) as error:
            return Response(
                {'detail': 'Upload a valid image.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        finally:
            upload.seek(0)

        image_bytes = upload.read()
        if not _matches_image_type(image_bytes, content_type):
            return Response(
                {'detail': 'Image content does not match its file type.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            article_ref = self._article_ref(article_id)
            if article_ref is None:
                return Response(
                    {'detail': 'Article ID is invalid.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not article_ref.get().exists:
                return Response(status=status.HTTP_404_NOT_FOUND)
            scheme = 'http' if settings.DEBUG else 'https'
            image_url = (
                f'{scheme}://{request.get_host()}/api/v1/articles/{article_id}'
                f'/image/?v={uuid.uuid4().hex}'
            )
            client = _firestore_client()
            batch = client.batch()
            batch.set(
                article_ref.collection('images').document('cover'),
                {
                    'data': image_bytes,
                    'contentType': content_type,
                    'updatedAt': firestore.SERVER_TIMESTAMP,
                },
            )
            batch.update(
                article_ref,
                {
                    'imageContentType': content_type,
                    'imageUrl': image_url,
                    'imageUpdatedAt': firestore.SERVER_TIMESTAMP,
                    'updatedAt': firestore.SERVER_TIMESTAMP,
                },
            )
            batch.commit()
        except InvalidArgument:
            return Response(
                {'detail': 'The image and metadata exceed Firestore limits.'},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        except FirebaseConfigurationError as error:
            logger.error('Firestore article image configuration failed: %s', error)
            return Response(
                {'detail': 'Article images are temporarily unavailable.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except (FirebaseError, GoogleAPICallError) as error:
            logger.error(
                'Firestore article image write failed: %s',
                type(error).__name__,
            )
            return Response(
                {'detail': 'The article image could not be saved.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {'updated': True, 'imageUrl': image_url, 'imageContentType': content_type},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, article_id):
        try:
            article_ref = self._article_ref(article_id)
            if article_ref is None:
                return Response(
                    {'detail': 'Article ID is invalid.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not article_ref.get().exists:
                return Response(status=status.HTTP_404_NOT_FOUND)
            client = _firestore_client()
            batch = client.batch()
            batch.delete(article_ref.collection('images').document('cover'))
            batch.update(
                article_ref,
                {
                    'imageContentType': firestore.DELETE_FIELD,
                    'imageUrl': firestore.DELETE_FIELD,
                    'imageUpdatedAt': firestore.DELETE_FIELD,
                    'updatedAt': firestore.SERVER_TIMESTAMP,
                },
            )
            batch.commit()
        except FirebaseConfigurationError as error:
            logger.error('Firestore article image configuration failed: %s', error)
            return Response(
                {'detail': 'Article images are temporarily unavailable.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except (FirebaseError, GoogleAPICallError) as error:
            logger.error(
                'Firestore article image delete failed: %s',
                type(error).__name__,
            )
            return Response(
                {'detail': 'The article image could not be removed.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


def _matches_image_type(image_bytes, content_type):
    if not image_bytes or len(image_bytes) > MAX_FIRESTORE_IMAGE_BYTES:
        return False
    if content_type == 'image/jpeg':
        return image_bytes.startswith(b'\xff\xd8\xff')
    if content_type == 'image/png':
        return image_bytes.startswith(b'\x89PNG\r\n\x1a\n')
    return (
        content_type == 'image/webp'
        and len(image_bytes) >= 12
        and image_bytes[:4] == b'RIFF'
        and image_bytes[8:12] == b'WEBP'
    )
