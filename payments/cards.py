import datetime
from dataclasses import dataclass

DECLINING_TEST_CARDS = {
    "4000000000000002": ("card_declined", "The card was declined."),
    "4000000000009995": ("insufficient_funds", "The card has insufficient funds."),
    "4000000000000069": ("expired_card", "The card has expired."),
    "4000000000000127": ("incorrect_cvc", "The card's security code is incorrect."),
}

APPROVED_TEST_CARDS = ("4242424242424242", "5555555555554444", "378282246310005")


@dataclass(frozen=True)
class ChargeResult:
    approved: bool
    decline_code: str = ""
    message: str = ""


def normalize_number(number):
    return "".join(number.split()).replace("-", "")


def luhn_valid(number):
    if not number.isdigit() or not 12 <= len(number) <= 19:
        return False
    total = 0
    for index, char in enumerate(reversed(number)):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def detect_brand(number):
    if number.startswith("4"):
        return "visa"
    if number[:2] in {"34", "37"}:
        return "amex"
    prefix = int(number[:4])
    if 5100 <= prefix <= 5599 or 2221 <= prefix <= 2720:
        return "mastercard"
    return "unknown"


def is_expired(exp_month, exp_year, today=None):
    today = today or datetime.date.today()
    return (exp_year, exp_month) < (today.year, today.month)


def simulate_charge(number, exp_month, exp_year, today=None):
    if is_expired(exp_month, exp_year, today):
        return ChargeResult(False, "expired_card", "The card has expired.")
    if number in DECLINING_TEST_CARDS:
        code, message = DECLINING_TEST_CARDS[number]
        return ChargeResult(False, code, message)
    return ChargeResult(True)
