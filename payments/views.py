from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.response import Response

from core.exceptions import error_body
from payments import services
from payments.models import Payment
from payments.serializers import PaymentCreateSerializer, PaymentSerializer


class PaymentListCreateView(generics.ListAPIView):
    serializer_class = PaymentSerializer

    def get_queryset(self):
        queryset = Payment.objects.filter(merchant=self.request.user)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    @extend_schema(
        parameters=[OpenApiParameter("status", str, enum=Payment.Status.values)],
        summary="List payments, newest first",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        request=PaymentCreateSerializer,
        responses={201: PaymentSerializer},
        summary="Charge a card",
    )
    def post(self, request):
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = services.create_payment(merchant=request.user, **serializer.validated_data)

        if payment.status == Payment.Status.FAILED:
            body = error_body(
                "card_error",
                payment.failure_code,
                payment.failure_message,
                payment=str(payment.id),
            )
            return Response(body, status=status.HTTP_402_PAYMENT_REQUIRED)
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


class PaymentDetailView(generics.RetrieveAPIView):
    serializer_class = PaymentSerializer

    def get_queryset(self):
        return Payment.objects.filter(merchant=self.request.user)
