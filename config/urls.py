from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from core import views as core_views

urlpatterns = [
    path("health", core_views.health, name="health"),
    path("health/live", core_views.liveness, name="health-live"),
    path("", include("django_prometheus.urls")),
    path("v1/schema", SpectacularAPIView.as_view(), name="schema"),
    path("docs", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("v1/", include("merchants.urls")),
    path("v1/", include("payments.urls")),
    path("v1/", include("ledger.urls")),
    path("v1/", include("webhooks.urls")),
]

handler404 = "core.views.not_found"
handler500 = "core.views.server_error"
