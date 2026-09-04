from django.urls import path

from .views import ActivityFeedView, RecentView, StatsView, TrendsView, WorkloadView

urlpatterns = [
    path('stats/', StatsView.as_view(), name='dashboard-stats'),
    path('recent/', RecentView.as_view(), name='dashboard-recent'),
    path('trends/', TrendsView.as_view(), name='dashboard-trends'),
    path('workload/', WorkloadView.as_view(), name='dashboard-workload'),
    path('activity/', ActivityFeedView.as_view(), name='dashboard-activity'),
]
