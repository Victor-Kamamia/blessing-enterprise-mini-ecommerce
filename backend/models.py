from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class CustomerInfo:
    name: str
    phone: str
    address: str
    email: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class OrderItem:
    id: int
    name: str
    category: str
    image: str
    quantity: int
    unit_price: float
    line_total: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "image": self.image,
            "quantity": self.quantity,
            "unitPrice": round(self.unit_price, 2),
            "lineTotal": round(self.line_total, 2),
        }


@dataclass(slots=True)
class PaymentRecord:
    order_reference: str
    amount: float
    phone_number: str
    status: str
    provider: str = "mpesa"
    provider_mode: str = "mock"
    merchant_request_id: str = ""
    checkout_request_id: str = ""
    mpesa_receipt_number: str = ""
    result_code: int | None = None
    result_desc: str = ""
    paid_at: str = ""
    request_payload: dict[str, Any] = field(default_factory=dict)
    response_payload: dict[str, Any] = field(default_factory=dict)
    raw_callback_payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "providerMode": self.provider_mode,
            "status": self.status,
            "amount": round(self.amount, 2),
            "phoneNumber": self.phone_number,
            "merchantRequestId": self.merchant_request_id,
            "checkoutRequestId": self.checkout_request_id,
            "mpesaReceiptNumber": self.mpesa_receipt_number,
            "resultCode": self.result_code,
            "resultDesc": self.result_desc,
            "paidAt": self.paid_at,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


@dataclass(slots=True)
class OrderRecord:
    reference: str
    status: str
    payment_status: str
    delivery_status: str
    source: str
    created_at: str
    updated_at: str
    delivery_updated_at: str
    customer: CustomerInfo
    items: list[OrderItem]
    total_amount: float
    currency: str = "KES"
    whatsapp_message: str = ""
    whatsapp_url: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.reference,
            "reference": self.reference,
            "status": self.status,
            "paymentStatus": self.payment_status,
            "deliveryStatus": self.delivery_status,
            "source": self.source,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "deliveryUpdatedAt": self.delivery_updated_at,
            "currency": self.currency,
            "customer": self.customer.to_dict(),
            "items": [item.to_dict() for item in self.items],
            "totalAmount": round(self.total_amount, 2),
            "whatsappMessage": self.whatsapp_message,
            "whatsappUrl": self.whatsapp_url,
            "notes": self.notes,
        }
