from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any

from .common import (
    build_whatsapp_message,
    make_whatsapp_url,
    normalize_phone,
    read_json,
    utc_now_iso,
    validate_email,
    validate_phone,
)
from .config import Settings
from .database import Database
from .email_service import EmailService
from .events import EventBroker
from .models import CustomerInfo, OrderItem, OrderRecord
from .mpesa import MpesaService


class OrderService:
    def __init__(
        self,
        settings: Settings,
        database: Database,
        events: EventBroker,
        email_service: EmailService,
        mpesa_service: MpesaService,
    ) -> None:
        self.settings = settings
        self.database = database
        self.events = events
        self.email_service = email_service
        self.mpesa_service = mpesa_service

    def create_checkout(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Order payload must be an object.")

        customer_payload = payload.get("customer")
        items_payload = payload.get("items")
        source = str(payload.get("source", "website")).strip() or "website"
        if not isinstance(customer_payload, dict):
            raise ValueError("Customer details are required.")

        customer = self._build_customer(customer_payload)
        items, total_amount = self._calculate_order(items_payload)
        created_at = utc_now_iso()
        reference = self._build_order_reference()
        order = OrderRecord(
            reference=reference,
            status="pending_payment",
            payment_status="pending",
            delivery_status="new",
            source=source,
            created_at=created_at,
            updated_at=created_at,
            delivery_updated_at=created_at,
            customer=customer,
            items=items,
            total_amount=total_amount,
            currency=self.settings.currency,
        )
        order.whatsapp_message = build_whatsapp_message(order.to_dict())
        order.whatsapp_url = make_whatsapp_url(order.whatsapp_message, self.settings.whatsapp_number)

        self.database.create_order(order)
        payment = self.mpesa_service.start_stk_push(order)
        self.database.attach_transaction(payment)
        current_order = self.database.get_order(reference)
        if current_order is None:
            raise RuntimeError("Unable to load the saved order.")
        self.database.mirror_orders_json()

        self.email_service.send_checkout_notification(current_order, current_order.get("payment"))
        self.events.publish("order.updated", {"reference": reference, "order": current_order})

        payment_payload = current_order.get("payment") or {}
        if payment_payload.get("providerMode") == "mock" and payment_payload.get("status") == "pending":
            self._schedule_mock_confirmation(current_order)
        elif payment_payload.get("status") in {"failed", "cancelled"}:
            self.email_service.send_payment_update(current_order, payment_payload)

        return current_order

    def handle_mpesa_callback(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        callback_data = self.mpesa_service.parse_callback(payload)
        order = self.database.finalize_transaction(callback_data)
        if order is None:
            return None
        self.database.mirror_orders_json()
        self.email_service.send_payment_update(order, order.get("payment"))
        self.events.publish("payment.updated", {"reference": order["reference"], "order": order})
        return order

    def _build_customer(self, customer_payload: dict[str, Any]) -> CustomerInfo:
        name = str(customer_payload.get("name", "")).strip()
        phone = normalize_phone(str(customer_payload.get("phone", "")))
        email = str(customer_payload.get("email", "")).strip().lower()
        address = str(customer_payload.get("address", "")).strip()

        if not name:
            raise ValueError("Customer name is required.")
        phone_error = validate_phone(phone)
        if phone_error:
            raise ValueError(phone_error)
        email_error = validate_email(email, required=False)
        if email_error:
            raise ValueError(email_error)
        if not address:
            raise ValueError("Delivery address is required.")

        return CustomerInfo(name=name, phone=phone, email=email, address=address)

    def _calculate_order(self, items_payload: Any) -> tuple[list[OrderItem], float]:
        if not isinstance(items_payload, list) or not items_payload:
            raise ValueError("Order items are required.")
        products = read_json(self.settings.products_file, [])
        if not isinstance(products, list):
            products = []
        catalog = {int(product["id"]): product for product in products if isinstance(product, dict) and "id" in product}

        line_items: list[OrderItem] = []
        total = 0.0
        for raw_item in items_payload:
            if not isinstance(raw_item, dict):
                raise ValueError("Each order item must be an object.")
            product_id = raw_item.get("id")
            quantity = raw_item.get("quantity")
            if not isinstance(product_id, int):
                raise ValueError("Each order item needs a numeric product id.")
            if not isinstance(quantity, int) or quantity < 1:
                raise ValueError("Each order item needs a quantity of at least 1.")
            product = catalog.get(product_id)
            if not product:
                raise ValueError(f"Product {product_id} was not found.")
            unit_price = round(float(product.get("price", 0)), 2)
            line_total = round(unit_price * quantity, 2)
            total = round(total + line_total, 2)
            line_items.append(
                OrderItem(
                    id=product_id,
                    name=str(product.get("name", "Unknown Product")),
                    category=str(product.get("category", "")),
                    image=str(product.get("image", "")),
                    quantity=quantity,
                    unit_price=unit_price,
                    line_total=line_total,
                )
            )
        return line_items, total

    def _build_order_reference(self) -> str:
        today = datetime.now().strftime("%Y%m%d")
        prefix = f"ORD-{today}"
        daily_count = self.database.get_orders_count_for_prefix(prefix)
        return f"{prefix}-{daily_count + 1:04d}"

    def _schedule_mock_confirmation(self, order: dict[str, Any]) -> None:
        payment = order.get("payment") or {}
        checkout_request_id = str(payment.get("checkoutRequestId", "")).strip()
        merchant_request_id = str(payment.get("merchantRequestId", "")).strip()
        if not checkout_request_id:
            return
        # Mock confirmations keep the checkout flow testable before live Daraja credentials are added.
        worker = threading.Thread(
            target=self._run_mock_confirmation,
            args=(order["reference"], checkout_request_id, merchant_request_id),
            daemon=True,
        )
        worker.start()

    def _run_mock_confirmation(self, reference: str, checkout_request_id: str, merchant_request_id: str) -> None:
        time.sleep(self.settings.mpesa_mock_delay_seconds)
        order = self.database.get_order(reference)
        if order is None:
            return
        if str(order.get("paymentStatus", "")).lower() != "pending":
            return

        result_mode = self.settings.mpesa_mock_result.strip().lower()
        result_code = 0
        result_desc = "The service request is processed successfully."
        callback_metadata = {
            "Amount": float(order.get("totalAmount", 0) or 0),
            "MpesaReceiptNumber": f"MOCK{checkout_request_id[-6:].upper()}",
            "TransactionDate": datetime.utcnow().strftime("%Y%m%d%H%M%S"),
            "PhoneNumber": str((order.get("payment") or {}).get("phoneNumber", order["customer"]["phone"])),
        }
        if result_mode == "cancelled":
            result_code = 1032
            result_desc = "Request cancelled by user."
            callback_metadata = {}
        elif result_mode == "failed":
            result_code = 1
            result_desc = "Mock payment failed."
            callback_metadata = {}

        payload = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": merchant_request_id,
                    "CheckoutRequestID": checkout_request_id,
                    "ResultCode": result_code,
                    "ResultDesc": result_desc,
                    "CallbackMetadata": {
                        "Item": [{"Name": name, "Value": value} for name, value in callback_metadata.items()]
                    },
                }
            }
        }
        self.handle_mpesa_callback(payload)
