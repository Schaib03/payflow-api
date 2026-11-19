from django.urls import path

from merchants import views

urlpatterns = [
    path("merchants", views.MerchantSignupView.as_view(), name="merchant-signup"),
    path("merchants/me", views.MerchantMeView.as_view(), name="merchant-me"),
]
