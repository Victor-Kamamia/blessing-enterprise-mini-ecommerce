from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
HOST = "127.0.0.1"
PORT = 8000
WHATSAPP_NUMBER = "254711490385"
PHONE_PATTERN = re.compile(r"^[+]?\d{10,15}$")
EMAIL_PATTERN = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.IGNORECASE)
DATA_LOCK = threading.Lock()
SESSION_LOCK = threading.Lock()

PRODUCTS_FILE = DATA_DIR / "products.json"
ORDERS_FILE = DATA_DIR / "orders.json"
NEWSLETTER_FILE = DATA_DIR / "newsletter.json"
LOYALTY_FILE = DATA_DIR / "loyalty.json"
ADMIN_SESSIONS: dict[str, dict[str, str]] = {}


def ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    defaults = {
        PRODUCTS_FILE: [],
        ORDERS_FILE: [],
        NEWSLETTER_FILE: [],
        LOYALTY_FILE: [],
    }
    for path, fallback in defaults.items():
        if path.exists():
            continue
        path.write_text(json.dumps(fallback, indent=2), encoding="utf-8")


def read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_response(payload: Any, status: HTTPStatus = HTTPStatus.OK) -> tuple[int, bytes]:
    return status, json.dumps(payload).encode("utf-8")


def get_products() -> list[dict[str, Any]]:
    products = read_json(PRODUCTS_FILE, [])
    return products if isinstance(products, list) else []


def get_orders() -> list[dict[str, Any]]:
    orders = read_json(ORDERS_FILE, [])
    return orders if isinstance(orders, list) else []


def get_newsletter_subscribers() -> list[dict[str, Any]]:
    subscribers = read_json(NEWSLETTER_FILE, [])
    return subscribers if isinstance(subscribers, list) else []


def get_loyalty_members() -> list[dict[str, Any]]:
    members = read_json(LOYALTY_FILE, [])
    return members if isinstance(members, list) else []


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


def build_next_product_id(existing_products: list[dict[str, Any]]) -> int:
    numeric_ids = [int(product["id"]) for product in existing_products if isinstance(product.get("id"), int)]
    return max(numeric_ids, default=0) + 1


def get_admin_username() -> str:
    return os.environ.get("BLESSING_ADMIN_USERNAME", "admin")


def get_admin_password() -> str:
    return os.environ.get("BLESSING_ADMIN_PASSWORD", "BlessingAdmin2026!")


def validate_email(email: str) -> str | None:
    normalized = email.strip().lower()
    if not normalized:
        return "Email is required."
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


def build_order_reference(existing_orders: list[dict[str, Any]]) -> str:
    today = datetime.now().strftime("%Y%m%d")
    daily_count = sum(1 for order in existing_orders if str(order.get("reference", "")).startswith(f"ORD-{today}-"))
    return f"ORD-{today}-{daily_count + 1:04d}"


def calculate_order(items_payload: Any, products: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], float]:
    if not isinstance(items_payload, list) or not items_payload:
        raise ValueError("Order items are required.")

    catalog = {int(product["id"]): product for product in products if "id" in product}
    line_items: list[dict[str, Any]] = []
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
        unit_price = float(product.get("price", 0))
        line_total = round(unit_price * quantity, 2)
        total = round(total + line_total, 2)
        line_items.append(
            {
                "id": product_id,
                "name": product.get("name", "Unknown Product"),
                "category": product.get("category", ""),
                "image": product.get("image", ""),
                "quantity": quantity,
                "unitPrice": round(unit_price, 2),
                "lineTotal": line_total,
            }
        )

    return line_items, total


def build_whatsapp_message(order: dict[str, Any]) -> str:
    customer = order["customer"]
    lines = [
        "Hello BLESSING ENTERPRISE,",
        "",
        f"Order Ref: {order['reference']}",
        f"My name is: {customer['name']}",
        f"Phone: {customer['phone']}",
        "",
        "I would like to place an order:",
        "",
    ]
    lines.extend(
        f"{index}. {item['name']} (x{item['quantity']}) - ${item['lineTotal']:.2f}"
        for index, item in enumerate(order["items"], start=1)
    )
    lines.extend(
        [
            "",
            f"Total: ${order['totalAmount']:.2f}",
            "",
            "Delivery Address:",
            customer["address"],
            "",
            "Thank you!",
        ]
    )
    return "\n".join(lines)


def make_whatsapp_url(message: str) -> str:
    return f"https://wa.me/{WHATSAPP_NUMBER}?text={quote(message)}"


def build_catalog_payload() -> dict[str, Any]:
    products = get_products()
    categories = ["All", *sorted({str(product.get("category", "")) for product in products if product.get("category")})]
    return {"items": products, "count": len(products), "categories": categories}


def build_newsletter_payload() -> dict[str, Any]:
    subscribers = list(reversed(get_newsletter_subscribers()))
    return {"items": subscribers, "count": len(subscribers)}


def build_dashboard_payload() -> dict[str, Any]:
    orders = get_orders()
    newsletter = get_newsletter_subscribers()
    loyalty = get_loyalty_members()
    revenue = round(sum(float(order.get("totalAmount", 0)) for order in orders), 2)
    recent_orders = list(reversed(orders[-5:]))
    return {
        "totals": {
            "orders": len(orders),
            "newsletterSubscribers": len(newsletter),
            "loyaltyMembers": len(loyalty),
            "revenue": revenue,
        },
        "recentOrders": recent_orders,
    }


class BlessingRequestHandler(SimpleHTTPRequestHandler):
    server_version = "BlessingBackend/1.0"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT_DIR), **kwargs)

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

    def get_auth_token(self) -> str:
        auth_header = self.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            return auth_header[7:].strip()
        return self.headers.get("X-Admin-Token", "").strip()

    def require_admin_auth(self) -> bool:
        token = self.get_auth_token()
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
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api_get(parsed.path)
            return
        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return
        self.handle_api_post(parsed.path)

    def handle_api_get(self, path: str) -> None:
        if path == "/api/health":
            self.send_json({"status": "ok", "timestamp": utc_now_iso()})
            return
        if path == "/api/products":
            self.send_json(build_catalog_payload())
            return
        if path == "/api/newsletter":
            if not self.require_admin_auth():
                return
            self.send_json(build_newsletter_payload())
            return
        if path.startswith("/api/products/"):
            product_id = path.rsplit("/", 1)[-1]
            if not product_id.isdigit():
                self.send_json({"error": "Product id must be numeric."}, HTTPStatus.BAD_REQUEST)
                return
            product = next((item for item in get_products() if int(item.get("id", -1)) == int(product_id)), None)
            if not product:
                self.send_json({"error": "Product not found."}, HTTPStatus.NOT_FOUND)
                return
            self.send_json({"item": product})
            return
        if path == "/api/orders":
            self.send_json({"items": list(reversed(get_orders()))})
            return
        if path == "/api/dashboard":
            self.send_json(build_dashboard_payload())
            return
        self.send_json({"error": "Endpoint not found."}, HTTPStatus.NOT_FOUND)

    def handle_api_post(self, path: str) -> None:
        try:
            payload = self.parse_json_body()
        except ValueError as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return

        if path == "/api/orders":
            self.create_order(payload)
            return
        if path == "/api/admin/login":
            self.login_admin(payload)
            return
        if path == "/api/admin/logout":
            if not self.require_admin_auth():
                return
            self.logout_admin()
            return
        if path == "/api/products":
            if not self.require_admin_auth():
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
        if username != get_admin_username() or password != get_admin_password():
            self.send_json({"error": "Invalid admin username or password."}, HTTPStatus.UNAUTHORIZED)
            return

        token = secrets.token_urlsafe(32)
        session = {"username": username, "createdAt": utc_now_iso()}
        with SESSION_LOCK:
            ADMIN_SESSIONS[token] = session

        self.send_json(
            {
                "message": "Signed in successfully.",
                "token": token,
                "session": session,
            }
        )

    def logout_admin(self) -> None:
        token = self.get_auth_token()
        with SESSION_LOCK:
            ADMIN_SESSIONS.pop(token, None)
        self.send_json({"message": "Signed out successfully."})

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
            raw_original_price = offer_payload.get("originalPrice")
            if not offer_label:
                self.send_json({"error": "Offer label is required when offer pricing is provided."}, HTTPStatus.BAD_REQUEST)
                return
            try:
                original_price = parse_price_value(raw_original_price, "Original price")
            except ValueError as error:
                self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            if original_price <= price:
                self.send_json({"error": "Original price must be greater than the sale price."}, HTTPStatus.BAD_REQUEST)
                return
            offer = {"label": offer_label, "originalPrice": original_price}

        with DATA_LOCK:
            products = get_products()
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
            write_json(PRODUCTS_FILE, products)

        self.send_json(
            {
                "message": "Product added successfully.",
                "item": product,
            },
            HTTPStatus.CREATED,
        )

    def create_order(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            self.send_json({"error": "Order payload must be an object."}, HTTPStatus.BAD_REQUEST)
            return

        customer = payload.get("customer")
        items_payload = payload.get("items")
        source = str(payload.get("source", "website"))

        if not isinstance(customer, dict):
            self.send_json({"error": "Customer details are required."}, HTTPStatus.BAD_REQUEST)
            return

        name = str(customer.get("name", "")).strip()
        phone = normalize_phone(str(customer.get("phone", "")))
        address = str(customer.get("address", "")).strip()

        if not name:
            self.send_json({"error": "Customer name is required."}, HTTPStatus.BAD_REQUEST)
            return
        phone_error = validate_phone(phone)
        if phone_error:
            self.send_json({"error": phone_error}, HTTPStatus.BAD_REQUEST)
            return
        if not address:
            self.send_json({"error": "Delivery address is required."}, HTTPStatus.BAD_REQUEST)
            return

        products = get_products()
        try:
            line_items, total_amount = calculate_order(items_payload, products)
        except ValueError as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return

        with DATA_LOCK:
            orders = get_orders()
            reference = build_order_reference(orders)
            order = {
                "id": reference,
                "reference": reference,
                "status": "pending",
                "source": source,
                "createdAt": utc_now_iso(),
                "customer": {
                    "name": name,
                    "phone": phone,
                    "address": address,
                },
                "items": line_items,
                "totalAmount": total_amount,
            }
            message = build_whatsapp_message(order)
            order["whatsappMessage"] = message
            orders.append(order)
            write_json(ORDERS_FILE, orders)

        self.send_json(
            {
                "message": "Order created successfully.",
                "order": order,
                "whatsappUrl": make_whatsapp_url(message),
            },
            HTTPStatus.CREATED,
        )

    def subscribe_newsletter(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            self.send_json({"error": "Newsletter payload must be an object."}, HTTPStatus.BAD_REQUEST)
            return

        email = str(payload.get("email", ""))
        email_error = validate_email(email)
        if email_error:
            self.send_json({"error": email_error}, HTTPStatus.BAD_REQUEST)
            return
        normalized_email = email.strip().lower()

        with DATA_LOCK:
            subscribers = get_newsletter_subscribers()
            if any(entry.get("email") == normalized_email for entry in subscribers):
                self.send_json(
                    {
                        "message": "This email is already subscribed.",
                        "alreadySubscribed": True,
                    }
                )
                return
            entry = {"email": normalized_email, "createdAt": utc_now_iso()}
            subscribers.append(entry)
            write_json(NEWSLETTER_FILE, subscribers)

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
            members = get_loyalty_members()
            if any(entry.get("phone") == phone for entry in members):
                self.send_json(
                    {
                        "message": "You are already a loyalty member.",
                        "alreadyMember": True,
                    }
                )
                return
            entry = {"phone": phone, "createdAt": utc_now_iso()}
            members.append(entry)
            write_json(LOYALTY_FILE, members)

        self.send_json(
            {
                "message": "You have joined the loyalty program.",
                "member": entry,
                "alreadyMember": False,
            },
            HTTPStatus.CREATED,
        )


def create_server(host: str = HOST, port: int = PORT) -> ThreadingHTTPServer:
    ensure_data_files()
    return ThreadingHTTPServer((host, port), BlessingRequestHandler)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Blessing Enterprise backend server.")
    parser.add_argument("--host", default=os.environ.get("BLESSING_HOST", HOST), help="Host interface to bind to.")
    parser.add_argument("--port", type=int, default=int(os.environ.get("BLESSING_PORT", PORT)), help="Port to listen on.")
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
