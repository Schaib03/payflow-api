from prometheus_client import Counter

PAYMENTS = Counter(
    "payflow_payments_total", "Payments created, by outcome.", ["status", "currency"]
)
PAYMENT_AMOUNT = Counter(
    "payflow_payment_amount_minor_total",
    "Sum of succeeded payment amounts in minor units.",
    ["currency"],
)
REFUNDS = Counter("payflow_refunds_total", "Refunds created.", ["currency"])
WEBHOOK_DELIVERIES = Counter(
    "payflow_webhook_delivery_attempts_total",
    "Webhook delivery attempts, by result.",
    ["result"],
)
