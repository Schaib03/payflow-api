from django.urls import path

from ledger import views

urlpatterns = [
    path("balance", views.BalanceView.as_view(), name="balance"),
]
