from app.validation import validate_result

GOOD_INVOICE = {
    "type": "invoice",
    "sender": "accounting@stroymarket.az",
    "amount": 2350,
    "currency": "AZN",
    "due_date": "2026-10-25",
    "summary": "Invoice for cement",
    "confidence": 0.99,
}


def changed(**changes):
    return {**GOOD_INVOICE, **changes}


def has_issue(result, text):
    return any(text in issue for issue in validate_result(result))


def test_good_invoice_has_no_issues():
    assert validate_result(GOOD_INVOICE) == []


def test_unknown_type():
    assert has_issue(changed(type="bill"), "unknown type")


def test_low_confidence():
    assert has_issue(changed(confidence=0.5), "low confidence")


def test_confidence_out_of_range():
    assert has_issue(changed(confidence=1.5), "between 0 and 1")


def test_bad_date_format():
    assert has_issue(changed(due_date="25 октября 2026"), "due_date")


def test_invoice_with_zero_amount():
    assert has_issue(changed(amount=0), "positive amount")


def test_invoice_with_unknown_currency():
    assert has_issue(changed(currency="рублей"), "currency")


def test_spam_without_amount_is_fine():
    spam = {"type": "spam", "amount": 0, "currency": "", "due_date": "", "confidence": 0.95}
    assert validate_result(spam) == []
