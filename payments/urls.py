from django.urls import path

from payments import views

urlpatterns = [
    path("payments", views.PaymentListCreateView.as_view(), name="payment-list"),
    path("payments/<uuid:pk>", views.PaymentDetailView.as_view(), name="payment-detail"),
    path(
        "payments/<uuid:pk>/refunds",
        views.PaymentRefundListCreateView.as_view(),
        name="payment-refunds",
    ),
]
