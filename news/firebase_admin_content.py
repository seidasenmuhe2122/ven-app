import logging
import re

from firebase_admin.exceptions import FirebaseError
from google.api_core.exceptions import GoogleAPICallError
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .announcements import (
    FirebaseConfigurationError,
    FirebaseSuperAdminAuthentication,
    _firestore_client,
)

logger = logging.getLogger(__name__)


class FirebaseAdminArticleDeleteView(APIView):
    authentication_classes = [FirebaseSuperAdminAuthentication]
    permission_classes = [permissions.IsAuthenticated]

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
