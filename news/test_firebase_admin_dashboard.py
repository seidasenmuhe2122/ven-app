from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from .models import Article, Category


class FirebaseAdminDashboardTests(TestCase):
    url = '/api/v1/admin/firebase-dashboard/'
    headers = {'HTTP_AUTHORIZATION': 'Bearer test-firebase-id-token'}

    def setUp(self):
        self.claims = {
            'uid': 'dashboard-superadmin-uid',
            'email_verified': True,
            'role': 'superadmin',
        }

    @patch('news.announcements._firestore_client')
    @patch('news.announcements.verify_firebase_id_token')
    def test_verified_superadmin_receives_real_dashboard_metrics(
        self,
        verify_token,
        firestore_client,
    ):
        verify_token.return_value = self.claims
        firestore_client.return_value.collection.return_value.document.return_value.get.return_value = (
            SimpleNamespace(
                exists=True,
                to_dict=lambda: {'role': 'superadmin'},
            )
        )
        category = Category.objects.create(name='Dashboard category')
        Article.objects.create(
            title='Dashboard article',
            slug='dashboard-article',
            content='Article content',
            category=category,
            views_count=7,
        )

        response = self.client.get(self.url, **self.headers)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {
            'total_articles': 1,
            'daily_views': 7,
            'pending_moderations': 0,
            'active_users': 0,
            'top_categories': [{'name': 'Dashboard category', 'count': 1}],
        })
        verify_token.assert_called_once_with('test-firebase-id-token')

    @patch('news.announcements.verify_firebase_id_token')
    def test_non_superadmin_is_rejected(self, verify_token):
        verify_token.return_value = {
            **self.claims,
            'role': 'editor',
        }

        response = self.client.get(self.url, **self.headers)

        self.assertEqual(response.status_code, 401)
        verify_token.assert_called_once_with('test-firebase-id-token')

    @patch('news.announcements._firestore_client')
    @patch('news.announcements.verify_firebase_id_token')
    def test_role_document_must_confirm_superadmin(
        self,
        verify_token,
        firestore_client,
    ):
        verify_token.return_value = self.claims
        firestore_client.return_value.collection.return_value.document.return_value.get.return_value = (
            SimpleNamespace(
                exists=True,
                to_dict=lambda: {'role': 'editor'},
            )
        )

        response = self.client.get(self.url, **self.headers)

        self.assertEqual(response.status_code, 401)
        verify_token.assert_called_once_with('test-firebase-id-token')
