import datetime

import pytest

from payments import cards


@pytest.mark.parametrize(
    "number",
    ["4242424242424242", "5555555555554444", "378282246310005", *cards.DECLINING_TEST_CARDS],
)
def test_test_cards_pass_luhn(number):
    assert cards.luhn_valid(number)


@pytest.mark.parametrize("number", ["4242424242424241", "1234", "abcd424242424242", ""])
def test_invalid_numbers_fail_luhn(number):
    assert not cards.luhn_valid(number)


def test_normalize_strips_spaces_and_dashes():
    assert cards.normalize_number("4242 4242-4242 4242") == "4242424242424242"


@pytest.mark.parametrize(
    ("number", "brand"),
    [
        ("4242424242424242", "visa"),
        ("5555555555554444", "mastercard"),
        ("2223003122003222", "mastercard"),
        ("378282246310005", "amex"),
        ("6011111111111117", "unknown"),
    ],
)
def test_brand_detection(number, brand):
    assert cards.detect_brand(number) == brand


def test_declining_card_returns_code():
    result = cards.simulate_charge("4000000000009995", 12, 2030)
    assert not result.approved
    assert result.decline_code == "insufficient_funds"


def test_expired_card_declined():
    today = datetime.date(2026, 5, 10)
    assert cards.simulate_charge("4242424242424242", 4, 2026, today).decline_code == "expired_card"
    assert cards.simulate_charge("4242424242424242", 5, 2026, today).approved
