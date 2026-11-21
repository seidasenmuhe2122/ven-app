from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import TestCase


class FirebaseAdminArticleDeleteTests(TestCase):
    url = '/api/v1/admin/firebase-articles/story_42/'
    headers = {'HTTP_AUTHORIZATION': 'Bearer test-firebase-id-token'}

    def setUp(self):
        self.claims = {
            'uid': 'article-delete-superadmin-uid',
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

    def test_verified_superadmin_deletes_article_and_cover_image(self):
        article_ref = SimpleNamespace(
            get=lambda: SimpleNamespace(exists=True),
            collection=lambda name: SimpleNamespace(
                document=lambda document_id: ('cover-ref', name, document_id),
            ),
        )
        batch = SimpleNamespace(delete=Mock(), commit=Mock())
        firestore_client = SimpleNamespace(
            collection=lambda name: SimpleNamespace(
                document=lambda article_id: article_ref,
            ),
            batch=lambda: batch,
        )
        auth_patches = self._authorize_superadmin()
        with auth_patches[0], auth_patches[1], patch(
            'news.firebase_admin_content._firestore_client',
            return_value=firestore_client,
        ):
            response = self.client.delete(self.url, **self.headers)

        self.assertEqual(response.status_code, 204, response.content)
        self.assertEqual(batch.delete.call_count, 2)
        batch.commit.assert_called_once_with()
        self.assertEqual(
            batch.delete.call_args_list[0].args[0],
            ('cover-ref', 'images', 'cover'),
        )
        self.assertIs(batch.delete.call_args_list[1].args[0], article_ref)

    def test_non_superadmin_cannot_delete_article(self):
        claims = {**self.claims, 'role': 'editor'}
        with (
            patch(
                'news.announcements.verify_firebase_id_token',
                return_value=claims,
            ),
            patch('news.firebase_admin_content._firestore_client') as delete_store,
        ):
            response = self.client.delete(self.url, **self.headers)

        self.assertEqual(response.status_code, 401)
        delete_store.assert_not_called()

    def test_missing_article_returns_not_found_without_deleting(self):
        article_ref = SimpleNamespace(
            get=lambda: SimpleNamespace(exists=False),
        )
        firestore_client = SimpleNamespace(
            collection=lambda name: SimpleNamespace(
                document=lambda article_id: article_ref,
            ),
        )
        auth_patches = self._authorize_superadmin()
        with auth_patches[0], auth_patches[1], patch(
            'news.firebase_admin_content._firestore_client',
            return_value=firestore_client,
        ):
            response = self.client.delete(self.url, **self.headers)

        self.assertEqual(response.status_code, 404)

    def test_invalid_article_id_is_rejected(self):
        auth_patches = self._authorize_superadmin()
        with auth_patches[0], auth_patches[1], patch(
            'news.firebase_admin_content._firestore_client',
        ) as firestore_client:
            response = self.client.delete(
                '/api/v1/admin/firebase-articles/bad%21/',
                **self.headers,
            )

        self.assertEqual(response.status_code, 400)
        firestore_client.assert_not_called()

