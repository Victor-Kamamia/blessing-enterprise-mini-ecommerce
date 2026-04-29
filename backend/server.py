from __future__ import annotations

import argparse
import json
import queue
import secrets
import threading
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parent.parent))

    from backend.admin_routes import AdminDashboardApi
    from backend.common import normalize_phone, normalize_string_list, normalize_text, parse_price_value, read_json, validate_email, validate_phone, write_json
    from backend.config import Settings, load_settings
    from backend.database import Database
    from backend.email_service import EmailService
    from backend.events import EventBroker
    from backend.mpesa import MpesaService
    from backend.order_service import OrderService
else:
    from .admin_routes import AdminDashboardApi
    from .common import normalize_phone, normalize_string_list, normalize_text, parse_price_value, read_json, validate_email, validate_phone, write_json
    from .config import Settings, load_settings
    from .database import Database
    from .email_service import EmailService
    from .events import EventBroker
    from .mpesa import MpesaService
    from .order_service import OrderService


DATA_LOCK = threading.Lock()
SESSION_LOCK = threading.Lock()
ADMIN_SESSIONS: dict[str, dict[str, str]] = {}


def ensure_data_files(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    defaults = {
        settings.products_file: [],
        settings.orders_file: [],
        settings.newsletter_file: [],
        settings.loyalty_file: [],
    }
    for path, fallback in defaults.items():
        if path.exists():
            continue
        write_json(path, fallback)


def build_response(payload: Any, status: HTTPStatus = HTTPStatus.OK) -> tuple[int, bytes]:
    return status.value, json.dumps(payload).encode("utf-8")


def get_products(settings: Settings) -> list[dict[str, Any]]:
    products = read_json(settings.products_file, [])
    return products if isinstance(products, list) else []


def get_newsletter_subscribers(settings: Settings) -> list[dict[str, Any]]:
    subscribers = read_json(settings.newsletter_file, [])
    return subscribers if isinstance(subscribers, list) else []


def get_loyalty_members(settings: Settings) -> list[dict[str, Any]]:
    members = read_json(settings.loyalty_file, [])
    return members if isinstance(members, list) else []


def build_catalog_payload(settings: Settings) -> dict[str, Any]:
    products = get_products(settings)
    categories = ["All", *sorted({str(product.get("category", "")) for product in products if product.get("category")})]
    return {"items": products, "count": len(products), "categories": categories}


def build_newsletter_payload(settings: Settings) -> dict[str, Any]:
    subscribers = list(reversed(get_newsletter_subscribers(settings)))
    return {"items": subscribers, "count": len(subscribers)}


def build_next_product_id(existing_products: list[dict[str, Any]]) -> int:
    numeric_ids = [int(product["id"]) for product in existing_products if isinstance(product, dict) and isinstance(product.get("id"), int)]
    return max(numeric_ids, default=0) + 1


class BlessingRequestHandler(SimpleHTTPRequestHandler):
    server_version = "BlessingBackend/2.0"
    settings: Settings
    database: Database
    event_broker: EventBroker
    order_service: OrderService
    admin_api: AdminDashboardApi

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(self.settings.root_dir), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {self.address_string()} - {format % args}")

    def send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        status_code, content = build_response(payload, status)
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def parse_json_body(self) -> Any:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length else b""
        if not raw_body:
            return {}
        try:
            return json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("Request body must be valid JSON.") from error

    def get_auth_token(self, parsed: Any | None = None) -> str:
        auth_header = self.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            return auth_header[7:].strip()
        token = self.headers.get("X-Admin-Token", "").strip()
        if token:
            return token
        if parsed is not None:
            query = parse_qs(parsed.query)
            token_values = query.get("token") or []
            if token_values:
                return str(token_values[0]).strip()
        return ""

    def require_admin_auth(self, parsed: Any | None = None) -> bool:
        token = self.get_auth_token(parsed)
        if not token:
            self.send_json({"error": "Admin authentication required."}, HTTPStatus.UNAUTHORIZED)
            return False
        with SESSION_LOCK:
            if token not in ADMIN_SESSIONS:
                self.send_json({"error": "Your admin session has expired. Please sign in again."}, HTTPStatus.UNAUTHORIZED)
                return False
        return True

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api_get(parsed)
            return
        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return
        self.handle_api_post(parsed)

    def handle_api_get(self, parsed: Any) -> None:
        path = parsed.path
        if path == "/api/health":
            self.send_json(
                {
                    "status": "ok",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "database": str(self.settings.database_file),
                    "mpesaMockMode": self.settings.mpesa_mock_mode,
                }
            )
            return
        if path == "/api/products":
            self.send_json(build_catalog_payload(self.settings))
            return
        if path.startswith("/api/products/"):
            product_id = path.rsplit("/", 1)[-1]
            if not product_id.isdigit():
                self.send_json({"error": "Product id must be numeric."}, HTTPStatus.BAD_REQUEST)
                return
            product = next((item for item in get_products(self.settings) if int(item.get("id", -1)) == int(product_id)), None)
            if not product:
                self.send_json({"error": "Product not found."}, HTTPStatus.NOT_FOUND)
                return
            self.send_json({"item": product})
            return
        if path == "/api/newsletter":
            if not self.require_admin_auth(parsed):
                return
            self.send_json(build_newsletter_payload(self.settings))
            return
        if path == "/api/orders":
            self.send_json({"items": self.database.list_orders()})
            return
        if path.startswith("/api/orders/"):
            reference = path.rsplit("/", 1)[-1].strip()
            order = self.database.get_order(reference)
            if order is None:
                self.send_json({"error": "Order not found."}, HTTPStatus.NOT_FOUND)
                return
            self.send_json({"item": order})
            return
        if path == "/api/dashboard":
            self.send_json(self.admin_api.build_legacy_dashboard_payload())
            return
        if path == "/api/admin/dashboard":
            if not self.require_admin_auth(parsed):
                return
            self.send_json(self.admin_api.build_dashboard_payload())
            return
        if path == "/api/admin/orders":
            if not self.require_admin_auth(parsed):
                return
            query = parse_qs(parsed.query)
            limit_raw = str((query.get("limit") or ["50"])[0])
            status_values = [
                str(value).strip().lower()
                for value in query.get("status", [])
                if str(value).strip()
            ]
            exclude_status_values = [
                str(value).strip().lower()
                for value in query.get("excludeStatus", [])
                if str(value).strip()
            ]
            limit = 50
            if limit_raw.isdigit():
                limit = max(1, min(200, int(limit_raw)))
            self.send_json(
                self.admin_api.build_orders_payload(
                    limit=limit,
                    delivery_statuses=status_values or None,
                    exclude_delivery_statuses=exclude_status_values or None,
                )
            )
            return
        if path == "/api/admin/debug-db":
            if not self.require_admin_auth(parsed):
                return
            query = parse_qs(parsed.query)
            limit_raw = str((query.get("limit") or ["8"])[0])
            limit = 8
            if limit_raw.isdigit():
                limit = max(1, min(25, int(limit_raw)))
            self.send_json(self.database.build_debug_snapshot(preview_limit=limit))
            return
        if path == "/api/admin/events":
            if not self.require_admin_auth(parsed):
                return
            self.stream_admin_events()
            return
        self.send_json({"error": "Endpoint not found."}, HTTPStatus.NOT_FOUND)

    def handle_api_post(self, parsed: Any) -> None:
        path = parsed.path
        try:
            payload = self.parse_json_body()
        except ValueError as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return

        if path in {"/api/orders", "/api/checkout"}:
            self.create_checkout(payload)
            return
        if path == "/api/payments/mpesa/callback":
            self.handle_mpesa_callback(payload)
            return
        if path == "/api/admin/login":
            self.login_admin(payload)
            return
        if path == "/api/admin/logout":
            if not self.require_admin_auth(parsed):
                return
            self.logout_admin(parsed)
            return
        if path == "/api/admin/orders/status":
            if not self.require_admin_auth(parsed):
                return
            self.update_admin_order_delivery_status_from_payload(payload)
            return
        if path.startswith("/api/admin/orders/") and path.endswith("/delivery-status"):
            if not self.require_admin_auth(parsed):
                return
            self.update_admin_order_delivery_status(path, payload)
            return
        if path == "/api/products":
            if not self.require_admin_auth(parsed):
                return
            self.create_product(payload)
            return
        if path == "/api/newsletter/subscribe":
            self.subscribe_newsletter(payload)
            return
        if path == "/api/loyalty/join":
            self.join_loyalty(payload)
            return
        self.send_json({"error": "Endpoint not found."}, HTTPStatus.NOT_FOUND)

    def login_admin(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            self.send_json({"error": "Login payload must be an object."}, HTTPStatus.BAD_REQUEST)
            return

        username = normalize_text(payload.get("username"))
        password = str(payload.get("password", ""))
        if username != self.settings.admin_username or password != self.settings.admin_password:
            self.send_json({"error": "Invalid admin username or password."}, HTTPStatus.UNAUTHORIZED)
            return

        token = secrets.token_urlsafe(32)
        session = {"username": username, "createdAt": datetime.utcnow().isoformat() + "Z"}
        with SESSION_LOCK:
            ADMIN_SESSIONS[token] = session
        self.send_json({"message": "Signed in successfully.", "token": token, "session": session})

    def logout_admin(self, parsed: Any) -> None:
        token = self.get_auth_token(parsed)
        with SESSION_LOCK:
            ADMIN_SESSIONS.pop(token, None)
        self.send_json({"message": "Signed out successfully."})

    def update_admin_order_delivery_status(self, path: str, payload: Any) -> None:
        if not isinstance(payload, dict):
            self.send_json({"error": "Delivery status payload must be an object."}, HTTPStatus.BAD_REQUEST)
            return
        prefix = "/api/admin/orders/"
        reference = path[len(prefix):-len("/delivery-status")].strip("/")
        if not reference:
            self.send_json({"error": "Order reference is required."}, HTTPStatus.BAD_REQUEST)
            return
        delivery_status = normalize_text(payload.get("deliveryStatus")).lower()
        self._update_order_delivery_status(reference, delivery_status)

    def update_admin_order_delivery_status_from_payload(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            self.send_json({"error": "Delivery status payload must be an object."}, HTTPStatus.BAD_REQUEST)
            return
        reference = normalize_text(payload.get("reference"))
        if not reference:
            self.send_json({"error": "Order reference is required."}, HTTPStatus.BAD_REQUEST)
            return
        delivery_status = normalize_text(payload.get("deliveryStatus")).lower()
        self._update_order_delivery_status(reference, delivery_status)

    def _update_order_delivery_status(self, reference: str, delivery_status: str) -> None:
        if not delivery_status:
            self.send_json({"error": "Delivery status is required."}, HTTPStatus.BAD_REQUEST)
            return
        try:
            order = self.database.update_order_delivery_status(reference, delivery_status)
        except ValueError as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        if order is None:
            self.send_json({"error": "Order not found."}, HTTPStatus.NOT_FOUND)
            return
        self.database.mirror_orders_json()
        self.event_broker.publish("order.updated", {"reference": order["reference"], "order": order})
        self.send_json({"message": "Delivery status updated successfully.", "order": order})

    def create_product(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            self.send_json({"error": "Product payload must be an object."}, HTTPStatus.BAD_REQUEST)
            return

        name = normalize_text(payload.get("name"))
        category = normalize_text(payload.get("category"))
        description = normalize_text(payload.get("description"))
        image = normalize_text(payload.get("image"))
        usage = normalize_text(payload.get("usage"))
        if not name:
            self.send_json({"error": "Product name is required."}, HTTPStatus.BAD_REQUEST)
            return
        if not category:
            self.send_json({"error": "Product category is required."}, HTTPStatus.BAD_REQUEST)
            return
        if not description:
            self.send_json({"error": "Product description is required."}, HTTPStatus.BAD_REQUEST)
            return
        if not image:
            self.send_json({"error": "Product image is required."}, HTTPStatus.BAD_REQUEST)
            return

        try:
            price = parse_price_value(payload.get("price"), "Price")
            benefits = normalize_string_list(payload.get("benefits"))
            ingredients = normalize_string_list(payload.get("ingredients"))
        except ValueError as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return

        offer_payload = payload.get("offer")
        offer: dict[str, Any] | None = None
        if isinstance(offer_payload, dict) and any(offer_payload.values()):
            offer_label = normalize_text(offer_payload.get("label"))
            if not offer_label:
                self.send_json({"error": "Offer label is required when offer pricing is provided."}, HTTPStatus.BAD_REQUEST)
                return
            try:
                original_price = parse_price_value(offer_payload.get("originalPrice"), "Original price")
            except ValueError as error:
                self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            if original_price <= price:
                self.send_json({"error": "Original price must be greater than the sale price."}, HTTPStatus.BAD_REQUEST)
                return
            offer = {"label": offer_label, "originalPrice": original_price}

        with DATA_LOCK:
            products = get_products(self.settings)
            product = {
                "id": build_next_product_id(products),
                "name": name,
                "category": category,
                "description": description,
                "price": price,
                "image": image,
                "benefits": benefits,
                "usage": usage,
                "ingredients": ingredients,
                "offer": offer,
            }
            products.append(product)
            write_json(self.settings.products_file, products)

        self.send_json({"message": "Product added successfully.", "item": product}, HTTPStatus.CREATED)

    def create_checkout(self, payload: Any) -> None:
        try:
            order = self.order_service.create_checkout(payload)
        except ValueError as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        except Exception as error:  # pragma: no cover - defensive branch
            self.send_json({"error": f"Unable to process checkout right now: {error}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        payment = order.get("payment") or {}
        payment_status = str(payment.get("status", order.get("paymentStatus", "pending"))).lower()
        message = "Checkout submitted successfully. Complete the M-Pesa prompt on your phone."
        if payment_status == "failed":
            message = "Order saved, but M-Pesa STK Push could not start. You can fall back to WhatsApp while credentials are being finalized."
        elif payment_status == "cancelled":
            message = "Order saved, but the M-Pesa payment was cancelled."
        self.send_json(
            {
                "message": message,
                "order": order,
                "whatsappUrl": order.get("whatsappUrl", ""),
            },
            HTTPStatus.CREATED,
        )

    def handle_mpesa_callback(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            self.send_json({"error": "Callback payload must be an object."}, HTTPStatus.BAD_REQUEST)
            return
        order = self.order_service.handle_mpesa_callback(payload)
        if order is None:
            self.send_json({"message": "Callback received, but no matching transaction was found."})
            return
        self.send_json({"message": "Callback processed successfully.", "order": order})

    def subscribe_newsletter(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            self.send_json({"error": "Newsletter payload must be an object."}, HTTPStatus.BAD_REQUEST)
            return

        email = str(payload.get("email", "")).strip().lower()
        email_error = validate_email(email, required=True)
        if email_error:
            self.send_json({"error": email_error}, HTTPStatus.BAD_REQUEST)
            return

        with DATA_LOCK:
            subscribers = get_newsletter_subscribers(self.settings)
            if any(entry.get("email") == email for entry in subscribers):
                self.send_json({"message": "This email is already subscribed.", "alreadySubscribed": True})
                return
            entry = {"email": email, "createdAt": datetime.utcnow().isoformat() + "Z"}
            subscribers.append(entry)
            write_json(self.settings.newsletter_file, subscribers)

        self.send_json(
            {
                "message": "Thanks for subscribing. Your welcome offer is on the way.",
                "subscriber": entry,
                "alreadySubscribed": False,
            },
            HTTPStatus.CREATED,
        )

    def join_loyalty(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            self.send_json({"error": "Loyalty payload must be an object."}, HTTPStatus.BAD_REQUEST)
            return

        phone = normalize_phone(str(payload.get("phone", "")))
        phone_error = validate_phone(phone)
        if phone_error:
            self.send_json({"error": phone_error}, HTTPStatus.BAD_REQUEST)
            return

        with DATA_LOCK:
            members = get_loyalty_members(self.settings)
            if any(entry.get("phone") == phone for entry in members):
                self.send_json({"message": "You are already a loyalty member.", "alreadyMember": True})
                return
            entry = {"phone": phone, "createdAt": datetime.utcnow().isoformat() + "Z"}
            members.append(entry)
            write_json(self.settings.loyalty_file, members)

        self.send_json(
            {
                "message": "You have joined the loyalty program.",
                "member": entry,
                "alreadyMember": False,
            },
            HTTPStatus.CREATED,
        )

    def stream_admin_events(self) -> None:
        subscriber = self.event_broker.subscribe()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        try:
            self.wfile.write(b"retry: 2000\n\n")
            self.wfile.flush()
            while True:
                try:
                    # SSE keeps the admin dashboard in sync without requiring manual refreshes.
                    event = subscriber.get(timeout=15)
                    payload = json.dumps(event)
                    self.wfile.write(f"event: {event['type']}\n".encode("utf-8"))
                    self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                except queue.Empty:
                    self.wfile.write(b": keep-alive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return
        finally:
            self.event_broker.unsubscribe(subscriber)


def create_server(host: str | None = None, port: int | None = None) -> ThreadingHTTPServer:
    settings = load_settings()
    if host is not None:
        settings.host = host
    if port is not None:
        settings.port = port

    ensure_data_files(settings)
    database = Database(settings)
    database.initialize()
    event_broker = EventBroker()
    email_service = EmailService(settings, database)
    mpesa_service = MpesaService(settings)
    order_service = OrderService(settings, database, event_broker, email_service, mpesa_service)
    admin_api = AdminDashboardApi(
        database=database,
        products_loader=lambda: get_products(settings),
        newsletter_loader=lambda: get_newsletter_subscribers(settings),
        loyalty_loader=lambda: get_loyalty_members(settings),
    )

    BlessingRequestHandler.settings = settings
    BlessingRequestHandler.database = database
    BlessingRequestHandler.event_broker = event_broker
    BlessingRequestHandler.order_service = order_service
    BlessingRequestHandler.admin_api = admin_api
    return ThreadingHTTPServer((settings.host, settings.port), BlessingRequestHandler)


def parse_args() -> argparse.Namespace:
    settings = load_settings()
    parser = argparse.ArgumentParser(description="Run the Blessing Enterprise backend server.")
    parser.add_argument("--host", default=settings.host, help="Host interface to bind to.")
    parser.add_argument("--port", type=int, default=settings.port, help="Port to listen on.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = create_server(args.host, args.port)
    print(f"Serving Blessing Enterprise on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
