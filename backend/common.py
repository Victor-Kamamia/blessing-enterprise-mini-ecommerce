from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote


PHONE_PATTERN = re.compile(r"^[+]?\d{10,15}$")
EMAIL_PATTERN = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.IGNORECASE)


def read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_phone(phone: str) -> str:
    return re.sub(r"\s+", "", phone.strip())


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidates = re.split(r"[\r\n,]+", value)
    elif isinstance(value, list):
        candidates = value
    else:
        raise ValueError("List fields must be sent as an array or comma-separated text.")
    return [normalize_text(item) for item in candidates if normalize_text(item)]


def parse_price_value(value: Any, field_name: str) -> float:
    try:
        amount = round(float(value), 2)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a valid number.") from error
    if amount <= 0:
        raise ValueError(f"{field_name} must be greater than 0.")
    return amount


def validate_email(email: str, required: bool = False) -> str | None:
    normalized = email.strip().lower()
    if not normalized:
        return "Email is required." if required else None
    if not EMAIL_PATTERN.fullmatch(normalized):
        return "Use a valid email address."
    return None


def validate_phone(phone: str) -> str | None:
    normalized = normalize_phone(phone)
    if not normalized:
        return "Phone number is required."
    if not PHONE_PATTERN.fullmatch(normalized):
        return "Use a valid phone number with 10 to 15 digits."
    return None


def build_whatsapp_message(order: dict[str, Any], business_name: str = "BLESSING ENTERPRISE") -> str:
    customer = order["customer"]
    lines = [
        f"Hello {business_name},",
        "",
        f"Order Ref: {order['reference']}",
        f"My name is: {customer['name']}",
        f"Phone: {customer['phone']}",
    ]
    if customer.get("email"):
        lines.append(f"Email: {customer['email']}")
    lines.extend(
        [
            "",
            "I would like to place an order:",
            "",
        ]
    )
    lines.extend(
        f"{index}. {item['name']} (x{item['quantity']}) - {order.get('currency', 'KES')} {item['lineTotal']:.2f}"
        for index, item in enumerate(order["items"], start=1)
    )
    lines.extend(
        [
            "",
            f"Total: {order.get('currency', 'KES')} {order['totalAmount']:.2f}",
            "",
            "Delivery Address:",
            customer["address"],
            "",
            "Thank you!",
        ]
    )
    return "\n".join(lines)


def make_whatsapp_url(message: str, whatsapp_number: str) -> str:
    return f"https://wa.me/{whatsapp_number}?text={quote(message)}"
