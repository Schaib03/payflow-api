# PayFlow-Signature: t=<unix time>,v1=<hex hmac-sha256 of "<t>.<raw body>">

import hashlib
import hmac
import time

SIGNATURE_HEADER = "PayFlow-Signature"
DEFAULT_TOLERANCE_SECONDS = 300


class SignatureVerificationError(Exception):
    pass


def compute_signature(secret, timestamp, payload):
    message = f"{timestamp}.".encode() + payload
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def build_header(secret, payload, timestamp=None):
    timestamp = int(time.time()) if timestamp is None else timestamp
    return f"t={timestamp},v1={compute_signature(secret, timestamp, payload)}"


def verify_header(header, payload, secret, tolerance=DEFAULT_TOLERANCE_SECONDS, now=None):
    timestamp = None
    signatures = []
    for item in header.split(","):
        name, _, value = item.strip().partition("=")
        if name == "t" and value.isdigit():
            timestamp = int(value)
        elif name == "v1":
            signatures.append(value)

    if timestamp is None or not signatures:
        raise SignatureVerificationError("Malformed signature header.")

    now = int(time.time()) if now is None else now
    if abs(now - timestamp) > tolerance:
        raise SignatureVerificationError("Timestamp outside the tolerance window.")

    expected = compute_signature(secret, timestamp, payload)
    # constant-time comparison
    if not any(hmac.compare_digest(expected, signature) for signature in signatures):
        raise SignatureVerificationError("No matching signature.")
    return True
