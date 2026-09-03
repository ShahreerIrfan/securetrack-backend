from django.urls import path

from .views import RecentView, StatsView

urlpatterns = [
    path('stats/', StatsView.as_view(), name='dashboard-stats'),
    path('recent/', RecentView.as_view(), name='dashboard-recent'),
]
