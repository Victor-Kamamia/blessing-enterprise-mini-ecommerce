from __future__ import annotations

import json
import smtplib
import threading
from email.message import EmailMessage
from typing import Any

from .common import utc_now_iso
from .config import Settings
from .database import Database


class EmailService:
    def __init__(self, settings: Settings, database: Database) -> None:
        self.settings = settings
        self.database = database

    def send_checkout_notification(self, order: dict[str, Any], payment: dict[str, Any] | None) -> None:
        subject = f"New checkout received: {order['reference']}"
        body = self._build_email_body("Checkout received", order, payment)
        self._dispatch_async(order, "checkout_received", subject, body, payment)

    def send_payment_update(self, order: dict[str, Any], payment: dict[str, Any] | None) -> None:
        payment_status = str((payment or {}).get("status", order.get("paymentStatus", "pending"))).strip().lower()
        if payment_status == "paid":
            heading = "Payment confirmed"
            subject = f"Payment confirmed: {order['reference']}"
        elif payment_status == "cancelled":
            heading = "Payment cancelled"
            subject = f"Payment cancelled: {order['reference']}"
        else:
            heading = "Payment update"
            subject = f"Payment update: {order['reference']}"
        body = self._build_email_body(heading, order, payment)
        self._dispatch_async(order, "payment_update", subject, body, payment)

    def _dispatch_async(
        self,
        order: dict[str, Any],
        event_type: str,
        subject: str,
        body: str,
        payment: dict[str, Any] | None,
    ) -> None:
        worker = threading.Thread(
            target=self._send_email,
            args=(order, event_type, subject, body, payment),
            daemon=True,
        )
        worker.start()

    def _send_email(
        self,
        order: dict[str, Any],
        event_type: str,
        subject: str,
        body: str,
        payment: dict[str, Any] | None,
    ) -> None:
        recipient = self.settings.admin_email.strip()
        snapshot = json.dumps({"order": order, "payment": payment or {}}, ensure_ascii=True)
        created_at = utc_now_iso()

        if not recipient:
            self.database.record_email_notification(
                order_reference=order["reference"],
                event_type=event_type,
                recipient="",
                subject=subject,
                status="skipped",
                error_message="Admin email is not configured yet.",
                payload_snapshot=snapshot,
                created_at=created_at,
                sent_at="",
            )
            return

        if not self.settings.smtp_host.strip():
            self.database.record_email_notification(
                order_reference=order["reference"],
                event_type=event_type,
                recipient=recipient,
                subject=subject,
                status="skipped",
                error_message="SMTP settings are not configured yet.",
                payload_snapshot=snapshot,
                created_at=created_at,
                sent_at="",
            )
            return

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.settings.smtp_from_email.strip() or self.settings.smtp_username.strip() or "no-reply@localhost"
        message["To"] = recipient
        message.set_content(body)

        status = "sent"
        sent_at = utc_now_iso()
        error_message = ""
        try:
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=20) as smtp:
                smtp.ehlo()
                if self.settings.smtp_use_tls:
                    smtp.starttls()
                    smtp.ehlo()
                if self.settings.smtp_username.strip():
                    smtp.login(self.settings.smtp_username, self.settings.smtp_password)
                smtp.send_message(message)
        except Exception as error:  # pragma: no cover - depends on runtime SMTP settings
            status = "failed"
            sent_at = ""
            error_message = str(error)

        self.database.record_email_notification(
            order_reference=order["reference"],
            event_type=event_type,
            recipient=recipient,
            subject=subject,
            status=status,
            error_message=error_message,
            payload_snapshot=snapshot,
            created_at=created_at,
            sent_at=sent_at,
        )

    def _build_email_body(self, heading: str, order: dict[str, Any], payment: dict[str, Any] | None) -> str:
        customer = order.get("customer", {})
        item_lines = [
            f"{index}. {item.get('name', 'Unknown item')} x{item.get('quantity', 0)} - {order.get('currency', 'KES')} {float(item.get('lineTotal', 0)):.2f}"
            for index, item in enumerate(order.get("items", []), start=1)
        ]
        payment_block = self._build_payment_lines(payment or {})
        lines = [
            heading,
            "",
            f"Order reference: {order.get('reference', '')}",
            f"Order status: {order.get('status', '')}",
            f"Payment status: {order.get('paymentStatus', '')}",
            f"Delivery status: {order.get('deliveryStatus', 'new')}",
            f"Created at: {order.get('createdAt', '')}",
            "",
            "Customer details",
            f"Name: {customer.get('name', '')}",
            f"Phone: {customer.get('phone', '')}",
            f"Email: {customer.get('email', '') or 'Not provided'}",
            f"Address: {customer.get('address', '')}",
            "",
            "Items",
            *item_lines,
            "",
            f"Total: {order.get('currency', 'KES')} {float(order.get('totalAmount', 0)):.2f}",
            "",
            "Payment details",
            *payment_block,
        ]
        return "\n".join(lines)

    def _build_payment_lines(self, payment: dict[str, Any]) -> list[str]:
        if not payment:
            return ["No payment details available yet."]
        return [
            f"Provider: {payment.get('provider', 'mpesa')}",
            f"Mode: {payment.get('providerMode', 'mock')}",
            f"Status: {payment.get('status', '')}",
            f"Phone number: {payment.get('phoneNumber', '')}",
            f"Checkout request ID: {payment.get('checkoutRequestId', '') or 'N/A'}",
            f"Merchant request ID: {payment.get('merchantRequestId', '') or 'N/A'}",
            f"M-Pesa receipt number: {payment.get('mpesaReceiptNumber', '') or 'Pending'}",
            f"Result description: {payment.get('resultDesc', '') or 'Pending confirmation'}",
            f"Paid at: {payment.get('paidAt', '') or 'Pending'}",
        ]
