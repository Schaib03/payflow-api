from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from ledger.services import merchant_balances

BalanceSerializer = inline_serializer(
    "Balance",
    fields={
        "balances": inline_serializer(
            "CurrencyBalance",
            fields={"currency": serializers.CharField(), "available": serializers.IntegerField()},
            many=True,
        )
    },
)


class BalanceView(APIView):
    @extend_schema(responses=BalanceSerializer, summary="Merchant balance per currency")
    def get(self, request):
        return Response({"balances": merchant_balances(request.user)})
