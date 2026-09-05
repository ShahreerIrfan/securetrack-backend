from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def healthz(request):
    return JsonResponse({'status': 'ok'})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('healthz/', healthz, name='healthz'),
    path('api/auth/', include('accounts.urls')),
    path('api/reports/', include('reports.urls')),
    path('api/dashboard/', include('dashboard.urls')),
    # No generic /media/ route on purpose - report attachments can be
    # sensitive (PoC screenshots, logs), so they're only ever served
    # through reports/views.py's `attachment` action, which reuses the
    # same visible_reports() scoping as viewing the report itself rather
    # than being reachable by anyone who guesses/finds the file path.
]
