import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import TestCase


class FirebaseAdminArticleWriteTests(TestCase):
    collection_url = '/api/v1/admin/firebase-articles/'
    detail_url = f'{collection_url}article_42/'
    headers = {'HTTP_AUTHORIZATION': 'Bearer test-firebase-id-token'}

    def setUp(self):
        self.claims = {
            'uid': 'article-write-superadmin-uid',
            'email_verified': True,
            'role': 'superadmin',
        }

    def _authorize_superadmin(self, role='superadmin'):
        return (
            patch(
                'news.announcements.verify_firebase_id_token',
                return_value=self.claims,
            ),
            patch(
                'news.announcements._firestore_client',
                return_value=SimpleNamespace(
                    collection=lambda name: SimpleNamespace(
                        document=lambda uid: SimpleNamespace(
                            get=lambda: SimpleNamespace(
                                exists=True,
                                to_dict=lambda: {'role': role},
                            ),
                        ),
                    ),
                ),
            ),
        )

    def _content_store(self, *, category_active=True, article_data=None):
        article_ref = Mock()
        article_ref.id = 'article_42'
        article_ref.get.return_value = SimpleNamespace(
            exists=article_data is not None,
            to_dict=lambda: article_data,
        )
        category_ref = SimpleNamespace(
            get=lambda: SimpleNamespace(
                exists=True,
                to_dict=lambda: {
                    'name': 'World',
                    'isActive': category_active,
                },
            ),
        )
        collections = {
            'categories': SimpleNamespace(document=lambda _: category_ref),
            'news': SimpleNamespace(document=lambda *_: article_ref),
        }
        client = SimpleNamespace(collection=lambda name: collections[name])
        return client, article_ref

    def test_superadmin_can_create_a_published_article(self):
        firestore_client, article_ref = self._content_store()
        auth_patches = self._authorize_superadmin()
        payload = {
            'title': 'A new story',
            'slug': 'a-new-story',
            'summary': 'A short summary',
            'content': '<p>The full story.</p>',
            'status': 'published',
            'categoryId': 7,
            'tagIds': [2],
            'authorName': 'Reporter',
            'publisherName': 'VEN News',
        }

        with auth_patches[0], auth_patches[1], patch(
            'news.firebase_admin_content._firestore_client',
            return_value=firestore_client,
        ):
            response = self.client.post(
                self.collection_url,
                data=json.dumps(payload),
                content_type='application/json',
                **self.headers,
            )

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json(), {'id': 'article_42', 'status': 'published'})
        fields = article_ref.set.call_args.args[0]
        self.assertEqual(fields['categoryName'], 'World')
        self.assertEqual(fields['content'], '<p>The full story.</p>')
        self.assertEqual(fields['searchTokens'][:2], ['a', 'new'])
        self.assertEqual(fields['readTimeMinutes'], 1)
        self.assertEqual(fields['authorName'], 'Reporter')
        self.assertIn('publishedAt', fields)

    def test_superadmin_can_publish_a_draft_without_replacing_its_content(self):
        existing = {
            'title': 'Draft story',
            'slug': 'draft-story',
            'summary': 'Summary',
            'content': 'Body',
            'status': 'draft',
            'categoryId': 7,
            'categoryName': 'World',
            'tagIds': [],
        }
        firestore_client, article_ref = self._content_store(
            article_data=existing,
        )
        auth_patches = self._authorize_superadmin()

        with auth_patches[0], auth_patches[1], patch(
            'news.firebase_admin_content._firestore_client',
            return_value=firestore_client,
        ):
            response = self.client.patch(
                self.detail_url,
                data=json.dumps({'status': 'published'}),
                content_type='application/json',
                **self.headers,
            )

        self.assertEqual(response.status_code, 200, response.content)
        fields = article_ref.update.call_args.args[0]
        self.assertEqual(fields['title'], 'Draft story')
        self.assertEqual(fields['content'], 'Body')
        self.assertEqual(fields['status'], 'published')
        self.assertIn('publishedAt', fields)

    def test_non_superadmin_cannot_create_content(self):
        claims = {**self.claims, 'role': 'editor'}
        payload = {
            'title': 'A new story',
            'summary': 'Summary',
            'content': 'Body',
            'categoryId': 7,
        }
        with (
            patch(
                'news.announcements.verify_firebase_id_token',
                return_value=claims,
            ),
            patch('news.firebase_admin_content._firestore_client') as store,
        ):
            response = self.client.post(
                self.collection_url,
                data=json.dumps(payload),
                content_type='application/json',
                **self.headers,
            )

        self.assertEqual(response.status_code, 401)
        store.assert_not_called()

    def test_inactive_category_and_invalid_status_are_rejected(self):
        firestore_client, article_ref = self._content_store(
            category_active=False,
        )
        auth_patches = self._authorize_superadmin()
        payload = {
            'title': 'A new story',
            'summary': 'Summary',
            'content': 'Body',
            'categoryId': 7,
        }

        with auth_patches[0], auth_patches[1], patch(
            'news.firebase_admin_content._firestore_client',
            return_value=firestore_client,
        ):
            inactive_category = self.client.post(
                self.collection_url,
                data=json.dumps(payload),
                content_type='application/json',
                **self.headers,
            )
            invalid_status = self.client.post(
                self.collection_url,
                data=json.dumps({**payload, 'status': []}),
                content_type='application/json',
                **self.headers,
            )

        self.assertEqual(inactive_category.status_code, 400)
        self.assertEqual(invalid_status.status_code, 400)
        article_ref.set.assert_not_called()
