from datetime import date

ALLOWED_TYPES = {"invoice", "complaint", "request", "spam", "other"}
ALLOWED_CURRENCIES = {"AZN", "USD", "EUR", "RUB", "TRY", "GBP"}
CONFIDENCE_THRESHOLD = 0.8


def validate_result(result: dict) -> list[str]:
    issues = []
    doc_type = result.get("type")
    if doc_type not in ALLOWED_TYPES:
        issues.append(f"unknown type: {doc_type!r}")

    confidence = result.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        issues.append("confidence must be a number between 0 and 1")
    elif confidence < CONFIDENCE_THRESHOLD:
        issues.append("low confidence")

    due_date = result.get("due_date") or ""
    if due_date:
        try:
            date.fromisoformat(due_date)
        except ValueError:
            issues.append("due_date is not a valid YYYY-MM-DD date")

    if doc_type == "invoice":
        amount = result.get("amount")
        if not isinstance(amount, (int, float)) or amount <= 0:
            issues.append("invoice without a positive amount")
        if result.get("currency") not in ALLOWED_CURRENCIES:
            issues.append("invoice with unknown currency")

    return issues
