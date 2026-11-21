from .announcements import FirebaseSuperAdminAuthentication
from .views import DashboardStatsView


class FirebaseAdminDashboardView(DashboardStatsView):
    authentication_classes = [FirebaseSuperAdminAuthentication]
