VISA_OK = "4242424242424242"
MASTERCARD_OK = "5555555555554444"
DECLINED = "4000000000000002"
INSUFFICIENT_FUNDS = "4000000000009995"


def payment_payload(amount=15000, currency="MAD", number=VISA_OK, **extra):
    payload = {
        "amount": amount,
        "currency": currency,
        "card": {"number": number, "exp_month": 12, "exp_year": 2030, "cvc": "123"},
        "description": "Order #1042",
    }
    payload.update(extra)
    return payload


def create_payment(client, headers=None, **kwargs):
    return client.post(
        "/v1/payments", payment_payload(**kwargs), format="json", headers=headers or {}
    )
