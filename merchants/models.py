import hashlib
import secrets
import uuid

from django.db import models


class Merchant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    # request.user is a Merchant, and DRF's IsAuthenticated checks this.
    @property
    def is_authenticated(self):
        return True


class ApiKeyQuerySet(models.QuerySet):
    def active(self):
        return self.filter(revoked_at__isnull=True)


class ApiKey(models.Model):
    PREFIX = "sk_test_"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="api_keys")
    prefix = models.CharField(max_length=16)
    # sha256 is enough for 256-bit random keys; the raw key is only shown once.
    key_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    objects = ApiKeyQuerySet.as_manager()

    def __str__(self):
        return f"{self.prefix}..."

    @staticmethod
    def hash_key(raw_key):
        return hashlib.sha256(raw_key.encode()).hexdigest()

    @classmethod
    def issue(cls, merchant):
        raw_key = cls.PREFIX + secrets.token_urlsafe(32)
        api_key = cls.objects.create(
            merchant=merchant, prefix=raw_key[:12], key_hash=cls.hash_key(raw_key)
        )
        return api_key, raw_key
