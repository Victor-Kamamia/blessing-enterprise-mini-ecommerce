from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any

from .common import read_json, utc_now_iso, write_json
from .config import Settings
from .migrations import run_migrations
from .models import CustomerInfo, OrderItem, OrderRecord, PaymentRecord


class Database:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = threading.Lock()

    def initialize(self) -> None:
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            run_migrations(connection)
            self._migrate_existing_orders(connection)
        self.mirror_orders_json()

    def create_order(self, order: OrderRecord) -> None:
        with self._lock, self._connect() as connection, connection:
            connection.execute(
                """
                INSERT INTO orders (
                    reference, status, payment_status, source, currency, total_amount,
                    customer_name, customer_phone, customer_email, customer_address,
                    whatsapp_message, whatsapp_url, notes, delivery_status,
                    delivery_updated_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order.reference,
                    order.status,
                    order.payment_status,
                    order.source,
                    order.currency,
                    round(order.total_amount, 2),
                    order.customer.name,
                    order.customer.phone,
                    order.customer.email,
                    order.customer.address,
                    order.whatsapp_message,
                    order.whatsapp_url,
                    order.notes,
                    order.delivery_status,
                    order.delivery_updated_at,
                    order.created_at,
                    order.updated_at,
                ),
            )
            connection.executemany(
                """
                INSERT INTO order_items (
                    order_reference, product_id, name, category, image,
                    quantity, unit_price, line_total
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        order.reference,
                        item.id,
                        item.name,
                        item.category,
                        item.image,
                        item.quantity,
                        round(item.unit_price, 2),
                        round(item.line_total, 2),
                    )
                    for item in order.items
                ],
            )

    def attach_transaction(self, payment: PaymentRecord) -> None:
        order_status = "payment_pending"
        payment_status = "pending"
        if payment.status == "paid":
            order_status = "paid"
            payment_status = "paid"
        elif payment.status == "cancelled":
            order_status = "cancelled"
            payment_status = "cancelled"
        elif payment.status == "failed":
            order_status = "payment_failed"
            payment_status = "failed"

        with self._lock, self._connect() as connection, connection:
            connection.execute(
                """
                INSERT INTO transactions (
                    order_reference, provider, provider_mode, status, amount, phone_number,
                    merchant_request_id, checkout_request_id, mpesa_receipt_number,
                    result_code, result_desc, paid_at, request_payload, response_payload,
                    raw_callback_payload, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payment.order_reference,
                    payment.provider,
                    payment.provider_mode,
                    payment.status,
                    round(payment.amount, 2),
                    payment.phone_number,
                    payment.merchant_request_id,
                    payment.checkout_request_id,
                    payment.mpesa_receipt_number,
                    payment.result_code,
                    payment.result_desc,
                    payment.paid_at,
                    json.dumps(payment.request_payload),
                    json.dumps(payment.response_payload),
                    json.dumps(payment.raw_callback_payload),
                    payment.created_at or utc_now_iso(),
                    payment.updated_at or utc_now_iso(),
                ),
            )
            connection.execute(
                """
                UPDATE orders
                SET status = ?, payment_status = ?, updated_at = ?
                WHERE reference = ?
                """,
                (order_status, payment_status, payment.updated_at or utc_now_iso(), payment.order_reference),
            )

    def finalize_transaction(self, callback_data: dict[str, Any]) -> dict[str, Any] | None:
        checkout_request_id = str(callback_data.get("checkout_request_id", ""))
        merchant_request_id = str(callback_data.get("merchant_request_id", ""))
        with self._lock, self._connect() as connection, connection:
            transaction_row = None
            if checkout_request_id:
                transaction_row = connection.execute(
                    "SELECT * FROM transactions WHERE checkout_request_id = ? ORDER BY id DESC LIMIT 1",
                    (checkout_request_id,),
                ).fetchone()
            if transaction_row is None and merchant_request_id:
                transaction_row = connection.execute(
                    "SELECT * FROM transactions WHERE merchant_request_id = ? ORDER BY id DESC LIMIT 1",
                    (merchant_request_id,),
                ).fetchone()
            if transaction_row is None:
                return None

            order_reference = str(transaction_row["order_reference"])
            payment_status = str(callback_data.get("status", "failed"))
            order_status = "payment_failed"
            if payment_status == "paid":
                order_status = "paid"
            elif payment_status == "cancelled":
                order_status = "cancelled"

            updated_at = utc_now_iso()
            connection.execute(
                """
                UPDATE transactions
                SET status = ?, mpesa_receipt_number = ?, result_code = ?, result_desc = ?,
                    paid_at = ?, raw_callback_payload = ?, updated_at = ?, phone_number = ?,
                    amount = COALESCE(NULLIF(?, 0), amount)
                WHERE id = ?
                """,
                (
                    payment_status,
                    str(callback_data.get("mpesa_receipt_number", "")),
                    callback_data.get("result_code"),
                    str(callback_data.get("result_desc", "")),
                    str(callback_data.get("paid_at", "")),
                    json.dumps(callback_data.get("raw_callback_payload", {})),
                    updated_at,
                    str(callback_data.get("phone_number", "")) or str(transaction_row["phone_number"]),
                    round(float(callback_data.get("amount", 0) or 0), 2),
                    int(transaction_row["id"]),
                ),
            )
            connection.execute(
                """
                UPDATE orders
                SET status = ?, payment_status = ?, updated_at = ?
                WHERE reference = ?
                """,
                (order_status, payment_status, updated_at, order_reference),
            )
        return self.get_order(order_reference)

    def record_email_notification(
        self,
        order_reference: str,
        event_type: str,
        recipient: str,
        subject: str,
        status: str,
        error_message: str,
        payload_snapshot: str,
        created_at: str,
        sent_at: str,
    ) -> None:
        with self._lock, self._connect() as connection, connection:
            connection.execute(
                """
                INSERT INTO email_notifications (
                    order_reference, event_type, recipient, subject, status,
                    error_message, payload_snapshot, created_at, sent_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_reference,
                    event_type,
                    recipient,
                    subject,
                    status,
                    error_message,
                    payload_snapshot,
                    created_at,
                    sent_at,
                ),
            )

    def get_order(self, reference: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            return self._load_order(connection, reference)

    def list_orders(
        self,
        limit: int | None = None,
        delivery_statuses: list[str] | None = None,
        exclude_delivery_statuses: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            query = "SELECT reference FROM orders"
            parameters: list[Any] = []
            clauses: list[str] = []
            normalized_statuses = [status.strip().lower() for status in (delivery_statuses or []) if str(status).strip()]
            normalized_excluded = [status.strip().lower() for status in (exclude_delivery_statuses or []) if str(status).strip()]
            if normalized_statuses:
                placeholders = ", ".join("?" for _ in normalized_statuses)
                clauses.append(f"LOWER(delivery_status) IN ({placeholders})")
                parameters.extend(normalized_statuses)
            if normalized_excluded:
                placeholders = ", ".join("?" for _ in normalized_excluded)
                clauses.append(f"LOWER(delivery_status) NOT IN ({placeholders})")
                parameters.extend(normalized_excluded)
            if clauses:
                query += " WHERE " + " AND ".join(clauses)
            query += " ORDER BY created_at DESC"
            if limit is not None:
                query += " LIMIT ?"
                parameters.append(limit)
            references = [str(row["reference"]) for row in connection.execute(query, tuple(parameters)).fetchall()]
            return [order for order in (self._load_order(connection, reference) for reference in references) if order]

    def get_orders_count_for_prefix(self, prefix: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM orders WHERE reference LIKE ?",
                (f"{prefix}-%",),
            ).fetchone()
        return int(row["count"]) if row else 0

    def build_dashboard_totals(self) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    COUNT(*) AS orders,
                    SUM(CASE WHEN payment_status = 'paid' THEN 1 ELSE 0 END) AS paid_orders,
                    SUM(CASE WHEN payment_status = 'pending' THEN 1 ELSE 0 END) AS pending_payments,
                    SUM(CASE WHEN payment_status IN ('failed', 'cancelled') THEN 1 ELSE 0 END) AS failed_payments,
                    SUM(CASE WHEN LOWER(delivery_status) = 'new' THEN 1 ELSE 0 END) AS new_orders,
                    SUM(CASE WHEN LOWER(delivery_status) = 'on_delivery' THEN 1 ELSE 0 END) AS on_delivery_orders,
                    SUM(CASE WHEN LOWER(delivery_status) = 'delivered' THEN 1 ELSE 0 END) AS delivered_orders,
                    ROUND(COALESCE(SUM(CASE WHEN payment_status = 'paid' THEN total_amount ELSE 0 END), 0), 2) AS revenue
                FROM orders
                """
            ).fetchone()
        return {
            "orders": int(row["orders"] or 0),
            "paidOrders": int(row["paid_orders"] or 0),
            "pendingPayments": int(row["pending_payments"] or 0),
            "failedPayments": int(row["failed_payments"] or 0),
            "newOrders": int(row["new_orders"] or 0),
            "onDeliveryOrders": int(row["on_delivery_orders"] or 0),
            "deliveredOrders": int(row["delivered_orders"] or 0),
            "revenue": round(float(row["revenue"] or 0), 2),
        }

    def build_debug_snapshot(self, preview_limit: int = 8) -> dict[str, Any]:
        safe_limit = max(1, min(25, int(preview_limit)))
        with self._connect() as connection:
            table_rows = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name ASC
                """
            ).fetchall()
            tables: list[dict[str, Any]] = []
            for row in table_rows:
                table_name = str(row["name"])
                count_row = connection.execute(f'SELECT COUNT(*) AS count FROM "{table_name}"').fetchone()
                preview_cursor = connection.execute(f'SELECT * FROM "{table_name}" ORDER BY rowid DESC LIMIT ?', (safe_limit,))
                preview_rows = [self._normalize_debug_row(dict(preview_row)) for preview_row in preview_cursor.fetchall()]
                tables.append(
                    {
                        "name": table_name,
                        "rowCount": int(count_row["count"] if count_row else 0),
                        "preview": preview_rows,
                    }
                )
        return {
            "databasePath": str(self.settings.database_file),
            "generatedAt": utc_now_iso(),
            "previewLimit": safe_limit,
            "tables": tables,
        }

    def update_order_delivery_status(self, reference: str, delivery_status: str) -> dict[str, Any] | None:
        normalized_status = delivery_status.strip().lower()
        allowed_statuses = {"new", "on_delivery", "delivered"}
        if normalized_status not in allowed_statuses:
            raise ValueError("Delivery status must be one of: new, on_delivery, delivered.")
        timestamp = utc_now_iso()
        with self._lock, self._connect() as connection, connection:
            row = connection.execute("SELECT reference FROM orders WHERE reference = ? LIMIT 1", (reference,)).fetchone()
            if row is None:
                return None
            connection.execute(
                """
                UPDATE orders
                SET delivery_status = ?, delivery_updated_at = ?, updated_at = ?
                WHERE reference = ?
                """,
                (normalized_status, timestamp, timestamp, reference),
            )
        return self.get_order(reference)

    def mirror_orders_json(self) -> None:
        write_json(self.settings.orders_file, self.list_orders())

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.settings.database_file, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _load_order(self, connection: sqlite3.Connection, reference: str) -> dict[str, Any] | None:
        order_row = connection.execute("SELECT * FROM orders WHERE reference = ?", (reference,)).fetchone()
        if order_row is None:
            return None

        item_rows = connection.execute(
            """
            SELECT product_id, name, category, image, quantity, unit_price, line_total
            FROM order_items
            WHERE order_reference = ?
            ORDER BY id ASC
            """,
            (reference,),
        ).fetchall()
        payment_row = connection.execute(
            """
            SELECT * FROM transactions
            WHERE order_reference = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (reference,),
        ).fetchone()

        order = {
            "id": str(order_row["reference"]),
            "reference": str(order_row["reference"]),
            "status": str(order_row["status"]),
            "paymentStatus": str(order_row["payment_status"]),
            "source": str(order_row["source"]),
            "deliveryStatus": str(order_row["delivery_status"] or "new"),
            "createdAt": str(order_row["created_at"]),
            "updatedAt": str(order_row["updated_at"]),
            "deliveryUpdatedAt": str(order_row["delivery_updated_at"] or order_row["updated_at"]),
            "currency": str(order_row["currency"]),
            "customer": {
                "name": str(order_row["customer_name"]),
                "phone": str(order_row["customer_phone"]),
                "email": str(order_row["customer_email"]),
                "address": str(order_row["customer_address"]),
            },
            "items": [
                {
                    "id": int(row["product_id"]),
                    "name": str(row["name"]),
                    "category": str(row["category"]),
                    "image": str(row["image"]),
                    "quantity": int(row["quantity"]),
                    "unitPrice": round(float(row["unit_price"]), 2),
                    "lineTotal": round(float(row["line_total"]), 2),
                }
                for row in item_rows
            ],
            "totalAmount": round(float(order_row["total_amount"]), 2),
            "whatsappMessage": str(order_row["whatsapp_message"]),
            "whatsappUrl": str(order_row["whatsapp_url"]),
            "notes": str(order_row["notes"]),
        }
        order["payment"] = self._serialize_payment(payment_row) if payment_row else None
        return order

    def _serialize_payment(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "provider": str(row["provider"]),
            "providerMode": str(row["provider_mode"]),
            "status": str(row["status"]),
            "amount": round(float(row["amount"]), 2),
            "phoneNumber": str(row["phone_number"]),
            "merchantRequestId": str(row["merchant_request_id"]),
            "checkoutRequestId": str(row["checkout_request_id"]),
            "mpesaReceiptNumber": str(row["mpesa_receipt_number"]),
            "resultCode": row["result_code"],
            "resultDesc": str(row["result_desc"]),
            "paidAt": str(row["paid_at"]),
            "createdAt": str(row["created_at"]),
            "updatedAt": str(row["updated_at"]),
        }

    def _migrate_existing_orders(self, connection: sqlite3.Connection) -> None:
        legacy_orders = read_json(self.settings.orders_file, [])
        if not isinstance(legacy_orders, list):
            return
        for payload in legacy_orders:
            if not isinstance(payload, dict):
                continue
            reference = str(payload.get("reference") or payload.get("id") or "").strip()
            if not reference:
                continue
            exists = connection.execute(
                "SELECT 1 FROM orders WHERE reference = ? LIMIT 1",
                (reference,),
            ).fetchone()
            if exists:
                continue
            # Older JSON-only orders are imported once so existing history remains available in SQLite.
            items = payload.get("items", [])
            customer = payload.get("customer", {})
            order = OrderRecord(
                reference=reference,
                status=str(payload.get("status", "pending")),
                payment_status=str(payload.get("paymentStatus", "pending")),
                delivery_status=self._normalize_legacy_delivery_status(payload),
                source=str(payload.get("source", "website")),
                created_at=str(payload.get("createdAt", utc_now_iso())),
                updated_at=str(payload.get("updatedAt", payload.get("createdAt", utc_now_iso()))),
                delivery_updated_at=str(payload.get("deliveryUpdatedAt", payload.get("updatedAt", payload.get("createdAt", utc_now_iso())))),
                customer=CustomerInfo(
                    name=str(customer.get("name", "")),
                    phone=str(customer.get("phone", "")),
                    email=str(customer.get("email", "")),
                    address=str(customer.get("address", "")),
                ),
                items=[
                    OrderItem(
                        id=int(item.get("id", 0)),
                        name=str(item.get("name", "")),
                        category=str(item.get("category", "")),
                        image=str(item.get("image", "")),
                        quantity=int(item.get("quantity", 0)),
                        unit_price=float(item.get("unitPrice", 0) or 0),
                        line_total=float(item.get("lineTotal", 0) or 0),
                    )
                    for item in items
                    if isinstance(item, dict)
                ],
                total_amount=float(payload.get("totalAmount", 0) or 0),
                currency=str(payload.get("currency", self.settings.currency)),
                whatsapp_message=str(payload.get("whatsappMessage", "")),
                whatsapp_url=str(payload.get("whatsappUrl", "")),
                notes=str(payload.get("notes", "")),
            )
            self._insert_migrated_order(connection, order)

    def _insert_migrated_order(self, connection: sqlite3.Connection, order: OrderRecord) -> None:
        connection.execute(
            """
            INSERT INTO orders (
                reference, status, payment_status, source, currency, total_amount,
                customer_name, customer_phone, customer_email, customer_address,
                whatsapp_message, whatsapp_url, notes, delivery_status,
                delivery_updated_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order.reference,
                order.status,
                order.payment_status,
                order.source,
                order.currency,
                round(order.total_amount, 2),
                order.customer.name,
                order.customer.phone,
                order.customer.email,
                order.customer.address,
                order.whatsapp_message,
                order.whatsapp_url,
                order.notes,
                order.delivery_status,
                order.delivery_updated_at,
                order.created_at,
                order.updated_at,
            ),
        )
        for item in order.items:
            connection.execute(
                """
                INSERT INTO order_items (
                    order_reference, product_id, name, category, image,
                    quantity, unit_price, line_total
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order.reference,
                    item.id,
                    item.name,
                    item.category,
                    item.image,
                    item.quantity,
                    round(item.unit_price, 2),
                    round(item.line_total, 2),
                ),
            )

    def _normalize_legacy_delivery_status(self, payload: dict[str, Any]) -> str:
        delivery_status = str(payload.get("deliveryStatus", "")).strip().lower()
        if delivery_status in {"new", "on_delivery", "delivered"}:
            return delivery_status
        legacy_status = str(payload.get("status", "")).strip().lower()
        if legacy_status == "delivered":
            return "delivered"
        if legacy_status == "on_delivery":
            return "on_delivery"
        return "new"

    def _normalize_debug_row(self, row: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for key, value in row.items():
            if isinstance(value, bytes):
                normalized[str(key)] = value.decode("utf-8", errors="replace")
            else:
                normalized[str(key)] = value
        return normalized
