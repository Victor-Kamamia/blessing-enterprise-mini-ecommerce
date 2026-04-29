from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def env_bool(name: str, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Settings:
    root_dir: Path
    data_dir: Path
    products_file: Path
    orders_file: Path
    newsletter_file: Path
    loyalty_file: Path
    database_file: Path
    host: str
    port: int
    whatsapp_number: str
    currency: str
    admin_username: str
    admin_password: str
    admin_email: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_from_email: str
    smtp_use_tls: bool
    mpesa_environment: str
    mpesa_consumer_key: str
    mpesa_consumer_secret: str
    mpesa_shortcode: str
    mpesa_passkey: str
    mpesa_callback_base_url: str
    mpesa_mock_mode: bool
    mpesa_mock_result: str
    mpesa_mock_delay_seconds: int
    mpesa_transaction_type: str

    @property
    def mpesa_base_url(self) -> str:
        if self.mpesa_environment.strip().lower() == "production":
            return "https://api.safaricom.co.ke"
        return "https://sandbox.safaricom.co.ke"

    @property
    def mpesa_callback_url(self) -> str:
        base_url = self.mpesa_callback_base_url.strip().rstrip("/")
        if not base_url:
            return ""
        return f"{base_url}/api/payments/mpesa/callback"


def load_settings() -> Settings:
    root_dir = Path(__file__).resolve().parent.parent
    data_dir = root_dir / "data"
    return Settings(
        root_dir=root_dir,
        data_dir=data_dir,
        products_file=data_dir / "products.json",
        orders_file=data_dir / "orders.json",
        newsletter_file=data_dir / "newsletter.json",
        loyalty_file=data_dir / "loyalty.json",
        database_file=data_dir / "blessing_enterprise.sqlite3",
        host=os.environ.get("BLESSING_HOST", "127.0.0.1"),
        port=int(os.environ.get("BLESSING_PORT", "8000")),
        whatsapp_number=os.environ.get("BLESSING_WHATSAPP_NUMBER", "254711490385"),
        currency=os.environ.get("BLESSING_CURRENCY", "KES"),
        admin_username=os.environ.get("BLESSING_ADMIN_USERNAME", "admin"),
        admin_password=os.environ.get("BLESSING_ADMIN_PASSWORD", "BlessingAdmin2026!"),
        admin_email=os.environ.get("BLESSING_ADMIN_EMAIL", "vickyngvicky23@gmail.com"),
        smtp_host=os.environ.get("BLESSING_SMTP_HOST", ""),
        smtp_port=int(os.environ.get("BLESSING_SMTP_PORT", "587")),
        smtp_username=os.environ.get("BLESSING_SMTP_USERNAME", ""),
        smtp_password=os.environ.get("BLESSING_SMTP_PASSWORD", ""),
        smtp_from_email=os.environ.get("BLESSING_SMTP_FROM_EMAIL", ""),
        smtp_use_tls=env_bool("BLESSING_SMTP_USE_TLS", True),
        mpesa_environment=os.environ.get("BLESSING_MPESA_ENVIRONMENT", "sandbox"),
        mpesa_consumer_key=os.environ.get("BLESSING_MPESA_CONSUMER_KEY", ""),
        mpesa_consumer_secret=os.environ.get("BLESSING_MPESA_CONSUMER_SECRET", ""),
        mpesa_shortcode=os.environ.get("BLESSING_MPESA_SHORTCODE", ""),
        mpesa_passkey=os.environ.get("BLESSING_MPESA_PASSKEY", ""),
        mpesa_callback_base_url=os.environ.get("BLESSING_MPESA_CALLBACK_BASE_URL", ""),
        mpesa_mock_mode=env_bool("BLESSING_MPESA_MOCK_MODE", True),
        mpesa_mock_result=os.environ.get("BLESSING_MPESA_MOCK_RESULT", "success").strip().lower() or "success",
        mpesa_mock_delay_seconds=max(2, int(os.environ.get("BLESSING_MPESA_MOCK_DELAY_SECONDS", "8"))),
        mpesa_transaction_type=os.environ.get("BLESSING_MPESA_TRANSACTION_TYPE", "CustomerPayBillOnline"),
    )
