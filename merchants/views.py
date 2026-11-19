from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.throttling import SignupRateThrottle
from merchants.models import ApiKey
from merchants.serializers import MerchantSerializer, MerchantSignupResponseSerializer


class MerchantSignupView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [SignupRateThrottle]

    @extend_schema(
        request=MerchantSerializer,
        responses={201: MerchantSignupResponseSerializer},
        auth=[],
        summary="Create a merchant account and its first API key",
    )
    def post(self, request):
        serializer = MerchantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            merchant = serializer.save()
            _, raw_key = ApiKey.issue(merchant)
        return Response({**serializer.data, "api_key": raw_key}, status=status.HTTP_201_CREATED)


class MerchantMeView(APIView):
    @extend_schema(responses=MerchantSerializer, summary="The authenticated merchant")
    def get(self, request):
        return Response(MerchantSerializer(request.user).data)
