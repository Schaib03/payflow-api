from django.urls import include, path

from core import views as core_views

urlpatterns = [
    path("health", core_views.health, name="health"),
    path("health/live", core_views.liveness, name="health-live"),
    path("", include("django_prometheus.urls")),
    path("v1/", include("merchants.urls")),
]

handler404 = "core.views.not_found"
handler500 = "core.views.server_error"
