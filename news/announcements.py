import json
import logging
import os
import re
from threading import Lock
from urllib.parse import urlsplit

import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials, firestore
from firebase_admin.exceptions import FirebaseError
from google.api_core.exceptions import AlreadyExists, GoogleAPICallError
from rest_framework import authentication, permissions, status
from rest_framework.exceptions import APIException, AuthenticationFailed
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)
_firebase_lock = Lock()


class FirebaseConfigurationError(Exception):
    pass


class FirebaseServiceUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'Firebase services are temporarily unavailable.'
    default_code = 'firebase_unavailable'


def _firebase_app():
    project_id = os.environ.get('FIREBASE_PROJECT_ID', '').strip()
    service_account_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON', '').strip()
    if not project_id or not service_account_json:
        raise FirebaseConfigurationError(
            'FIREBASE_PROJECT_ID and FIREBASE_SERVICE_ACCOUNT_JSON must be configured.'
        )

    try:
        service_account = json.loads(service_account_json)
    except json.JSONDecodeError as error:
        raise FirebaseConfigurationError(
            'FIREBASE_SERVICE_ACCOUNT_JSON must contain valid service-account JSON.'
        ) from error
    if service_account.get('project_id') != project_id:
        raise FirebaseConfigurationError(
            'Firebase service-account project does not match FIREBASE_PROJECT_ID.'
        )

    with _firebase_lock:
        try:
            app = firebase_admin.get_app()
        except ValueError:
            try:
                app = firebase_admin.initialize_app(
                    credentials.Certificate(service_account),
                    {'projectId': project_id},
                )
            except (ValueError, KeyError) as error:
                raise FirebaseConfigurationError(
                    'Firebase service-account configuration is invalid.'
                ) from error

    if app.project_id != project_id:
        raise FirebaseConfigurationError(
            'The initialized Firebase app does not match FIREBASE_PROJECT_ID.'
        )
    return app


def _firestore_client():
    return firestore.client(app=_firebase_app())


def verify_firebase_id_token(id_token):
    return firebase_auth.verify_id_token(
        id_token,
        app=_firebase_app(),
        check_revoked=True,
    )


class FirebaseSuperAdminPrincipal:
    is_authenticated = True
    is_active = True
    is_superadmin = True

    def __init__(self, uid):
        self.uid = uid
        self.pk = uid
        self.username = uid


class FirebaseSuperAdminAuthentication(authentication.BaseAuthentication):
    def authenticate_header(self, request):
        return 'Bearer'

    def authenticate(self, request):
        credentials_header = authentication.get_authorization_header(request).split()
        if not credentials_header or credentials_header[0].lower() != b'bearer':
            return None
        if len(credentials_header) != 2:
            raise AuthenticationFailed('Invalid Firebase ID token.')
        try:
            id_token = credentials_header[1].decode('ascii')
        except UnicodeError as error:
            raise AuthenticationFailed('Invalid Firebase ID token.') from error

        try:
            claims = verify_firebase_id_token(id_token)
        except (
            firebase_auth.InvalidIdTokenError,
            firebase_auth.ExpiredIdTokenError,
            firebase_auth.RevokedIdTokenError,
            firebase_auth.UserDisabledError,
            ValueError,
        ) as error:
            raise AuthenticationFailed(
                'The Firebase ID token is invalid, expired, or revoked.'
            ) from error
        except FirebaseConfigurationError as error:
            raise FirebaseServiceUnavailable(
                'Firebase identity verification is not configured.'
            ) from error
        except FirebaseError as error:
            logger.error(
                'Firebase identity verification failed: %s',
                type(error).__name__,
            )
            raise FirebaseServiceUnavailable() from error

        uid = claims.get('uid')
        if (
            not isinstance(uid, str)
            or not uid
            or claims.get('email_verified') is not True
            or claims.get('role') != 'superadmin'
        ):
            raise AuthenticationFailed(
                'A verified Firebase Super Admin identity is required.'
            )

        try:
            role_snapshot = (
                _firestore_client()
                .collection('adminRoles')
                .document(uid)
                .get()
            )
        except FirebaseConfigurationError as error:
            raise FirebaseServiceUnavailable(
                'Firebase Firestore is not configured for admin authorization.'
            ) from error
        except (FirebaseError, GoogleAPICallError) as error:
            logger.error(
                'Firebase admin role lookup failed: %s',
                type(error).__name__,
            )
            raise FirebaseServiceUnavailable() from error

        role = role_snapshot.to_dict() if role_snapshot.exists else None
        if not isinstance(role, dict) or role.get('role') != 'superadmin':
            raise AuthenticationFailed(
                'The Firebase Super Admin role is not active.'
            )
        return FirebaseSuperAdminPrincipal(uid), claims


def _announcement_matches(existing, expected):
    if not isinstance(existing, dict):
        return False
    for field in ('title', 'body', 'audience', 'status', 'publishedBy'):
        if existing.get(field) != expected.get(field):
            return False
    for field in ('articleId', 'imageUrl'):
        if field in expected:
            if existing.get(field) != expected[field]:
                return False
        elif field in existing:
            return False
    if expected.get('status') == 'published':
        return existing.get('publishedAt') is not None
    return 'publishedAt' not in existing


class AdminAnnouncementCreateView(APIView):
    authentication_classes = [FirebaseSuperAdminAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        data = request.data
        if not isinstance(data, dict):
            return Response(
                {'detail': 'A JSON object is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if set(data) - {'title', 'body', 'articleId', 'imageUrl', 'status'}:
            return Response(
                {'detail': 'Unsupported announcement field.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        title = data.get('title')
        body = data.get('body')
        if not isinstance(title, str) or not isinstance(body, str):
            return Response(
                {'detail': 'Announcement title and body must be text.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        title = title.strip()
        body = body.strip()
        if not title or len(title) > 120:
            return Response(
                {'detail': 'Announcement title must be 1 to 120 characters.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not body or len(body) > 1000:
            return Response(
                {'detail': 'Announcement body must be 1 to 1000 characters.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        article_id = data.get('articleId')
        if article_id in (None, ''):
            article_id = None
        elif isinstance(article_id, bool) or not isinstance(article_id, (int, str)):
            return Response(
                {'detail': 'articleId must be a positive integer or blank.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        elif not re.fullmatch(r'[1-9][0-9]*', str(article_id)):
            return Response(
                {'detail': 'articleId must be a positive integer or blank.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        else:
            article_id = str(article_id)

        image_url = data.get('imageUrl')
        if image_url is not None:
            if not isinstance(image_url, str) or not image_url.strip() or len(image_url) > 2048:
                return Response(
                    {'detail': 'imageUrl must be a valid HTTPS URL or omitted.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            image_url = image_url.strip()
            try:
                parsed_url = urlsplit(image_url)
            except ValueError:
                return Response(
                    {'detail': 'imageUrl must be a valid HTTPS URL without embedded credentials.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if (
                parsed_url.scheme != 'https'
                or not parsed_url.hostname
                or parsed_url.username is not None
                or parsed_url.password is not None
            ):
                return Response(
                    {'detail': 'imageUrl must be a valid HTTPS URL without embedded credentials.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        publication_status = data.get('status', 'published')
        if (
            not isinstance(publication_status, str)
            or publication_status not in {'published', 'unpublished'}
        ):
            return Response(
                {'detail': 'status must be published or unpublished.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        idempotency_key = request.headers.get('Idempotency-Key', '')
        if not re.fullmatch(r'[a-f0-9]{32}', idempotency_key):
            return Response(
                {'detail': 'A valid Idempotency-Key header is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            firestore_client = _firestore_client()
            if article_id is not None:
                article = (
                    firestore_client.collection('news')
                    .document(article_id)
                    .get()
                )
                if not article.exists or (article.to_dict() or {}).get('status') != 'published':
                    return Response(
                        {'detail': 'The linked article is not publicly available.'},
                        status=status.HTTP_404_NOT_FOUND,
                    )
            collection = firestore_client.collection('publicAnnouncements')
        except FirebaseConfigurationError as error:
            logger.error('Firestore announcement configuration is unavailable: %s', str(error))
            return Response(
                {'detail': 'Firestore is not configured for public announcements.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except (FirebaseError, GoogleAPICallError) as error:
            logger.error(
                'Firestore announcement preflight failed: %s',
                type(error).__name__,
            )
            return Response(
                {'detail': 'Firestore could not validate the announcement.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        announcement = {
            'title': title,
            'body': body,
            'audience': 'all',
            'status': publication_status,
            'publishedBy': request.user.uid,
        }
        if publication_status == 'published':
            announcement['publishedAt'] = firestore.SERVER_TIMESTAMP
        if article_id is not None:
            announcement['articleId'] = article_id
        if image_url:
            announcement['imageUrl'] = image_url

        document = collection.document(idempotency_key)
        try:
            existing = document.get()
            if existing.exists:
                if _announcement_matches(existing.to_dict(), announcement):
                    return Response(
                        {'id': document.id, 'status': publication_status},
                        status=status.HTTP_200_OK,
                    )
                return Response(
                    {'detail': 'This idempotency key was already used for a different announcement.'},
                    status=status.HTTP_409_CONFLICT,
                )
            document.create(announcement)
            saved = document.get()
        except AlreadyExists:
            try:
                saved = document.get()
            except (FirebaseError, GoogleAPICallError) as error:
                logger.error(
                    'Firestore announcement retry verification failed: %s',
                    type(error).__name__,
                )
                return Response(
                    {'detail': 'The announcement could not be verified in Firestore.'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            if _announcement_matches(saved.to_dict() if saved.exists else None, announcement):
                return Response(
                    {'id': document.id, 'status': publication_status},
                    status=status.HTTP_200_OK,
                )
            return Response(
                {'detail': 'This idempotency key was already used for a different announcement.'},
                status=status.HTTP_409_CONFLICT,
            )
        except (FirebaseError, GoogleAPICallError) as error:
            logger.error(
                'Firestore announcement write failed: %s',
                type(error).__name__,
            )
            return Response(
                {'detail': 'The announcement could not be saved to Firestore.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not _announcement_matches(saved.to_dict() if saved.exists else None, announcement):
            logger.error('Firestore announcement write verification failed.')
            return Response(
                {'detail': 'The Firestore announcement could not be verified.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(
            {'id': document.id, 'status': publication_status},
            status=status.HTTP_201_CREATED,
        )
