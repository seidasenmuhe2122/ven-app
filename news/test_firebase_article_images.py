from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient


class FirebaseArticleImageTests(TestCase):
    url = '/api/v1/articles/article_42/image/'
    headers = {'HTTP_AUTHORIZATION': 'Bearer test-firebase-id-token'}

    def setUp(self):
        self.api = APIClient()
        self.claims = {
            'uid': 'article-image-superadmin-uid',
            'email_verified': True,
            'role': 'superadmin',
        }

    def _authorize_superadmin(self):
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
                                to_dict=lambda: {'role': 'superadmin'},
                            ),
                        ),
                    ),
                ),
            ),
        )

    def _jpeg(self):
        stream = BytesIO()
        Image.new('RGB', (4, 4), color='blue').save(stream, format='JPEG')
        return stream.getvalue()

    def test_public_can_read_only_a_published_article_cover(self):
        article_data = {'status': 'published'}
        image_ref = SimpleNamespace(
            get=lambda: SimpleNamespace(
                exists=True,
                to_dict=lambda: {
                    'data': self._jpeg(),
                    'contentType': 'image/jpeg',
                },
            ),
        )
        article_ref = SimpleNamespace(
            get=lambda: SimpleNamespace(
                exists=True,
                to_dict=lambda: article_data,
            ),
            collection=lambda name: SimpleNamespace(
                document=lambda document_id: image_ref,
            ),
        )
        firestore_client = SimpleNamespace(
            collection=lambda name: SimpleNamespace(
                document=lambda article_id: article_ref,
            ),
        )

        with patch(
            'news.firebase_article_images._firestore_client',
            return_value=firestore_client,
        ):
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'image/jpeg')
            self.assertEqual(response.content, self._jpeg())

            article_data['status'] = 'draft'
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 404)

    def test_superadmin_can_upload_a_gallery_image(self):
        article_ref = Mock()
        article_ref.get.return_value = SimpleNamespace(exists=True)
        image_ref = Mock()
        article_ref.collection.return_value.document.return_value = image_ref
        batch = Mock()
        firestore_client = SimpleNamespace(
            collection=lambda name: SimpleNamespace(
                document=lambda article_id: article_ref,
            ),
            batch=lambda: batch,
        )
        auth_patches = self._authorize_superadmin()
        upload = SimpleUploadedFile(
            'cover.jpg',
            self._jpeg(),
            content_type='image/jpeg',
        )

        with auth_patches[0], auth_patches[1], patch(
            'news.firebase_article_images._firestore_client',
            return_value=firestore_client,
        ):
            response = self.api.put(
                self.url,
                data={'image': upload},
                format='multipart',
                **self.headers,
            )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['updated'])
        batch.set.assert_called_once()
        batch.update.assert_called_once()
        batch.commit.assert_called_once()

    def test_upload_rejects_anonymous_users_and_invalid_image_data(self):
        anonymous = self.api.put(
            self.url,
            data={'image': SimpleUploadedFile('cover.jpg', b'not-image')},
            format='multipart',
        )
        self.assertEqual(anonymous.status_code, 401)

        auth_patches = self._authorize_superadmin()
        with auth_patches[0], auth_patches[1], patch(
            'news.firebase_article_images._firestore_client',
        ) as firestore_client:
            response = self.api.put(
                self.url,
                data={
                    'image': SimpleUploadedFile(
                        'cover.jpg',
                        b'not-image',
                        content_type='image/jpeg',
                    ),
                },
                format='multipart',
                **self.headers,
            )

        self.assertEqual(response.status_code, 400)
        firestore_client.assert_not_called()
