import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from webhooks.models import WebhookDelivery
from webhooks.services import attempt_delivery, backoff_seconds

logger = logging.getLogger(__name__)


# Attempts are counted on the delivery row so the limit survives worker restarts.
@shared_task(bind=True, max_retries=None, acks_late=True)
def deliver_webhook(self, delivery_id):
    delivery = (
        WebhookDelivery.objects.select_related("event", "endpoint").filter(pk=delivery_id).first()
    )
    if delivery is None or delivery.status != WebhookDelivery.Status.PENDING:
        return None

    if not delivery.endpoint.is_active:
        delivery.status = WebhookDelivery.Status.FAILED
        delivery.last_error = "Endpoint disabled."
        delivery.save(update_fields=["status", "last_error", "updated_at"])
        return delivery.status

    if attempt_delivery(delivery):
        return delivery.status

    if delivery.attempts >= settings.WEBHOOK_MAX_ATTEMPTS:
        delivery.status = WebhookDelivery.Status.FAILED
        delivery.next_attempt_at = None
        delivery.save(update_fields=["status", "next_attempt_at", "updated_at"])
        logger.warning(
            "Webhook delivery %s failed after %s attempts", delivery.id, delivery.attempts
        )
        return delivery.status

    countdown = backoff_seconds(delivery.attempts)
    delivery.next_attempt_at = timezone.now() + timedelta(seconds=countdown)
    delivery.save(update_fields=["next_attempt_at", "updated_at"])
    raise self.retry(countdown=countdown)
