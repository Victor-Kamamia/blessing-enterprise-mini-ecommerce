from __future__ import annotations

import base64
import json
import secrets
from datetime import datetime, timezone
from typing import Any
from urllib import error, request

from .common import normalize_phone, utc_now_iso
from .config import Settings
from .models import OrderRecord, PaymentRecord


class MpesaService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def is_configured(self) -> bool:
        return all(
            [
                self.settings.mpesa_consumer_key.strip(),
                self.settings.mpesa_consumer_secret.strip(),
                self.settings.mpesa_shortcode.strip(),
                self.settings.mpesa_passkey.strip(),
                self.settings.mpesa_callback_url.strip(),
            ]
        )

    def start_stk_push(self, order: OrderRecord) -> PaymentRecord:
        created_at = utc_now_iso()
        amount = max(1, int(round(order.total_amount)))
        phone_number = self.format_phone_number(order.customer.phone)

        if not self.is_configured():
            status = "pending" if self.settings.mpesa_mock_mode else "failed"
            mode = "mock" if self.settings.mpesa_mock_mode else "unconfigured"
            description = (
                "M-Pesa credentials are not configured yet. Running a mock STK Push for local testing."
                if self.settings.mpesa_mock_mode
                else "M-Pesa credentials are not configured yet."
            )
            return PaymentRecord(
                order_reference=order.reference,
                amount=amount,
                phone_number=phone_number,
                status=status,
                provider_mode=mode,
                merchant_request_id=f"mock-merchant-{secrets.token_hex(4)}",
                checkout_request_id=f"mock-checkout-{secrets.token_hex(6)}",
                result_desc=description,
                created_at=created_at,
                updated_at=created_at,
            )

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(
            f"{self.settings.mpesa_shortcode}{self.settings.mpesa_passkey}{timestamp}".encode("utf-8")
        ).decode("utf-8")
        payload = {
            "BusinessShortCode": self.settings.mpesa_shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": self.settings.mpesa_transaction_type,
            "Amount": amount,
            "PartyA": phone_number,
            "PartyB": self.settings.mpesa_shortcode,
            "PhoneNumber": phone_number,
            "CallBackURL": self.settings.mpesa_callback_url,
            "AccountReference": order.reference,
            "TransactionDesc": f"Checkout payment for {order.reference}",
        }

        try:
            access_token = self._get_access_token()
            response_payload = self._request_json(
                url=f"{self.settings.mpesa_base_url}/mpesa/stkpush/v1/processrequest",
                payload=payload,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            response_code = str(response_payload.get("ResponseCode", "")).strip()
            status = "pending" if response_code == "0" else "failed"
            return PaymentRecord(
                order_reference=order.reference,
                amount=amount,
                phone_number=phone_number,
                status=status,
                provider_mode="live",
                merchant_request_id=str(response_payload.get("MerchantRequestID", "")),
                checkout_request_id=str(response_payload.get("CheckoutRequestID", "")),
                result_desc=str(
                    response_payload.get("CustomerMessage")
                    or response_payload.get("ResponseDescription")
                    or "M-Pesa STK Push request sent."
                ),
                request_payload=payload,
                response_payload=response_payload,
                created_at=created_at,
                updated_at=created_at,
            )
        except Exception as error_message:  # pragma: no cover - network is environment-specific
            return PaymentRecord(
                order_reference=order.reference,
                amount=amount,
                phone_number=phone_number,
                status="failed",
                provider_mode="live",
                result_desc=f"Unable to start M-Pesa STK Push: {error_message}",
                request_payload=payload,
                created_at=created_at,
                updated_at=created_at,
            )

    def parse_callback(self, payload: dict[str, Any]) -> dict[str, Any]:
        callback = payload.get("Body", {}).get("stkCallback", {})
        metadata_items = callback.get("CallbackMetadata", {}).get("Item", []) or []
        metadata: dict[str, Any] = {}
        for item in metadata_items:
            name = str(item.get("Name", "")).strip()
            if not name:
                continue
            metadata[name] = item.get("Value")

        result_code = int(callback.get("ResultCode", -1))
        result_desc = str(callback.get("ResultDesc", "") or "No response received from M-Pesa.")
        status = "paid"
        if result_code != 0:
            status = "cancelled" if result_code == 1032 else "failed"

        return {
            "merchant_request_id": str(callback.get("MerchantRequestID", "")),
            "checkout_request_id": str(callback.get("CheckoutRequestID", "")),
            "result_code": result_code,
            "result_desc": result_desc,
            "amount": float(metadata.get("Amount", 0) or 0),
            "mpesa_receipt_number": str(metadata.get("MpesaReceiptNumber", "") or ""),
            "phone_number": str(metadata.get("PhoneNumber", "") or ""),
            "paid_at": self._format_callback_date(metadata.get("TransactionDate")),
            "status": status,
            "raw_callback_payload": payload,
        }

    def format_phone_number(self, phone: str) -> str:
        normalized = normalize_phone(phone)
        digits = normalized[1:] if normalized.startswith("+") else normalized
        if digits.startswith("0"):
            digits = f"254{digits[1:]}"
        if digits.startswith("7") and len(digits) == 9:
            digits = f"254{digits}"
        return digits

    def _get_access_token(self) -> str:
        credentials = f"{self.settings.mpesa_consumer_key}:{self.settings.mpesa_consumer_secret}".encode("utf-8")
        encoded_credentials = base64.b64encode(credentials).decode("utf-8")
        response_payload = self._request_json(
            url=f"{self.settings.mpesa_base_url}/oauth/v1/generate?grant_type=client_credentials",
            payload=None,
            headers={
                "Authorization": f"Basic {encoded_credentials}",
                "Accept": "application/json",
            },
            method="GET",
        )
        access_token = str(response_payload.get("access_token", "")).strip()
        if not access_token:
            raise RuntimeError("M-Pesa access token was not returned.")
        return access_token

    def _request_json(
        self,
        url: str,
        payload: dict[str, Any] | None,
        headers: dict[str, str],
        method: str = "POST",
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        http_request = request.Request(url=url, data=body, headers=headers, method=method)
        try:
            with request.urlopen(http_request, timeout=25) as response:  # pragma: no cover - network is environment-specific
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as http_error:  # pragma: no cover - network is environment-specific
            details = http_error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {http_error.code}: {details}") from http_error
        except error.URLError as url_error:  # pragma: no cover - network is environment-specific
            raise RuntimeError(str(url_error.reason)) from url_error

    def _format_callback_date(self, raw_value: Any) -> str:
        if raw_value in (None, ""):
            return ""
        raw_text = str(raw_value)
        try:
            timestamp = datetime.strptime(raw_text, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        except ValueError:
            return raw_text
        return timestamp.isoformat()
