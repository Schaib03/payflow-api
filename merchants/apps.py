from django.apps import AppConfig


class MerchantsConfig(AppConfig):
    name = "merchants"

    def ready(self):
        from merchants import schema  # noqa: F401  registers the OpenAPI auth scheme
