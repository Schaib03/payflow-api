from rest_framework import serializers

from merchants.models import Merchant


class MerchantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Merchant
        fields = ["id", "name", "email", "created_at"]
        read_only_fields = ["id", "created_at"]


class MerchantSignupResponseSerializer(MerchantSerializer):
    api_key = serializers.CharField(help_text="Shown once. Store it, it cannot be retrieved.")

    class Meta(MerchantSerializer.Meta):
        fields = [*MerchantSerializer.Meta.fields, "api_key"]
