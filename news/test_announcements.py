from datetime import datetime, timezone
from unittest.mock import patch

from django.test import SimpleTestCase
from firebase_admin import firestore

from .announcements import verify_firebase_id_token


class Snapshot:
    def __init__(self, value=None):
        self.exists = value is not None
        self._value = value

    def to_dict(self):
        return self._value


class Document:
    def __init__(self, document_id, store):
        self.id = document_id
        self.store = store

    def get(self):
        return Snapshot(self.store.get(self.id))

    def create(self, data):
        if self.id in self.store:
            from google.api_core.exceptions import AlreadyExists

            raise AlreadyExists('Document already exists')
        saved = dict(data)
        if saved.get('publishedAt') is firestore.SERVER_TIMESTAMP:
            saved['publishedAt'] = datetime.now(timezone.utc)
        self.store[self.id] = saved


class Collection:
    def __init__(self, documents):
        self.documents = documents

    def document(self, document_id):
        return Document(document_id, self.documents)


class FakeFirestore:
    def __init__(self):
        self.roles = {'superadmin-uid': {'role': 'superadmin'}}
        self.articles = {'42': {'status': 'published'}}
        self.announcements = {}

    def collection(self, name):
        if name == 'adminRoles':
            return Collection(self.roles)
        if name == 'news':
            return Collection(self.articles)
        if name == 'publicAnnouncements':
            return Collection(self.announcements)
        raise AssertionError(f'Unexpected collection: {name}')


class AnnouncementApiTests(SimpleTestCase):
    headers = {
        'HTTP_AUTHORIZATION': 'Bearer test-firebase-id-token',
        'HTTP_IDEMPOTENCY_KEY': '0123456789abcdef0123456789abcdef',
    }

    def setUp(self):
        self.firestore = FakeFirestore()
        self.claims = {
            'uid': 'superadmin-uid',
            'email_verified': True,
            'role': 'superadmin',
        }

    def _post(self, payload, headers=None):
        request_headers = self.headers if headers is None else headers
        return self.client.post(
            '/api/v1/admin/announcements/',
            payload,
            content_type='application/json',
            **request_headers,
        )

    @patch('news.announcements._firestore_client')
    @patch('news.announcements.verify_firebase_id_token')
    def test_superadmin_publishes_and_idempotently_retries_firestore_document(
        self,
        verify_token,
        firestore_client,
    ):
        verify_token.return_value = self.claims
        firestore_client.return_value = self.firestore
        payload = {
            'title': ' Public update ',
            'body': ' Published to everyone. ',
            'articleId': 42,
            'imageUrl': 'https://cdn.example.test/announcement.jpg',
        }

        response = self._post(payload)

        self.assertEqual(response.status_code, 201, response.content)
        document_id = response.json()['id']
        saved = self.firestore.announcements[document_id]
        self.assertEqual(saved['title'], 'Public update')
        self.assertEqual(saved['body'], 'Published to everyone.')
        self.assertEqual(saved['articleId'], '42')
        self.assertEqual(saved['imageUrl'], payload['imageUrl'])
        self.assertEqual(saved['audience'], 'all')
        self.assertEqual(saved['status'], 'published')
        self.assertEqual(saved['publishedBy'], 'superadmin-uid')
        self.assertIsNotNone(saved['publishedAt'])

        retry = self._post(payload)

        self.assertEqual(retry.status_code, 200, retry.content)
        self.assertEqual(retry.json()['id'], document_id)
        self.assertEqual(len(self.firestore.announcements), 1)

        conflict = self._post({**payload, 'body': 'Different content.'})

        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(len(self.firestore.announcements), 1)

    @patch('news.announcements._firestore_client')
    @patch('news.announcements.verify_firebase_id_token')
    def test_unpublished_announcement_is_saved_without_publication_timestamp(
        self,
        verify_token,
        firestore_client,
    ):
        verify_token.return_value = self.claims
        firestore_client.return_value = self.firestore
        response = self._post({
            'title': 'Draft',
            'body': 'Not public yet.',
            'status': 'unpublished',
        })

        self.assertEqual(response.status_code, 201, response.content)
        saved = self.firestore.announcements[response.json()['id']]
        self.assertEqual(saved['status'], 'unpublished')
        self.assertNotIn('publishedAt', saved)
        self.assertNotIn('articleId', saved)
        self.assertNotIn('imageUrl', saved)

    def test_request_without_firebase_token_is_unauthorized(self):
        response = self.client.post(
            '/api/v1/admin/announcements/',
            '{}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 401)

    @patch('news.announcements.verify_firebase_id_token')
    def test_non_superadmin_and_unverified_firebase_identities_are_unauthorized(
        self,
        verify_token,
    ):
        for claim_updates in (
            {'role': 'editor'},
            {'email_verified': False},
        ):
            with self.subTest(claim_updates=claim_updates):
                verify_token.return_value = {**self.claims, **claim_updates}
                response = self._post({'title': 'Update', 'body': 'Message'})
                self.assertEqual(response.status_code, 401)

    @patch('news.announcements._firestore_client')
    @patch('news.announcements.verify_firebase_id_token')
    def test_firestore_role_document_must_confirm_superadmin(
        self,
        verify_token,
        firestore_client,
    ):
        verify_token.return_value = self.claims
        self.firestore.roles['superadmin-uid'] = {'role': 'editor'}
        firestore_client.return_value = self.firestore

        response = self._post({'title': 'Update', 'body': 'Message'})

        self.assertEqual(response.status_code, 401)
        self.assertFalse(self.firestore.announcements)

    @patch('news.announcements._firestore_client')
    @patch('news.announcements.verify_firebase_id_token')
    def test_invalid_or_unpublished_article_ids_are_rejected(
        self,
        verify_token,
        firestore_client,
    ):
        verify_token.return_value = self.claims
        firestore_client.return_value = self.firestore

        for article_id in (0, -1, 'not-an-id', True):
            with self.subTest(article_id=article_id):
                response = self._post({
                    'title': 'Update',
                    'body': 'Message',
                    'articleId': article_id,
                })
                self.assertEqual(response.status_code, 400)

        response = self._post({
            'title': 'Update',
            'body': 'Message',
            'articleId': 99,
        })
        self.assertEqual(response.status_code, 404)

        self.firestore.articles['43'] = {'status': 'unpublished'}
        response = self._post({
            'title': 'Update',
            'body': 'Message',
            'articleId': 43,
        })
        self.assertEqual(response.status_code, 404)
        self.assertFalse(self.firestore.announcements)

    @patch('news.announcements._firestore_client')
    @patch('news.announcements.verify_firebase_id_token')
    def test_invalid_image_url_and_publication_status_are_rejected(
        self,
        verify_token,
        firestore_client,
    ):
        verify_token.return_value = self.claims
        firestore_client.return_value = self.firestore

        for image_url in (
            'http://cdn.example.test/image.jpg',
            'https://user:password@cdn.example.test/image.jpg',
            'https://[invalid/image.jpg',
        ):
            with self.subTest(image_url=image_url):
                response = self._post({
                    'title': 'Update',
                    'body': 'Message',
                    'imageUrl': image_url,
                })
                self.assertEqual(response.status_code, 400)

        response = self._post({
            'title': 'Update',
            'body': 'Message',
            'status': [],
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.firestore.announcements)

    def test_firebase_id_tokens_are_checked_for_revocation(self):
        app = object()
        with (
            patch('news.announcements._firebase_app', return_value=app),
            patch('news.announcements.firebase_auth.verify_id_token') as verify,
        ):
            verify_firebase_id_token('token')

        verify.assert_called_once_with('token', app=app, check_revoked=True)
