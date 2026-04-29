from __future__ import annotations

from typing import Any, Callable

from .database import Database


class AdminDashboardApi:
    def __init__(
        self,
        database: Database,
        products_loader: Callable[[], list[dict[str, Any]]],
        newsletter_loader: Callable[[], list[dict[str, Any]]],
        loyalty_loader: Callable[[], list[dict[str, Any]]],
    ) -> None:
        self.database = database
        self.products_loader = products_loader
        self.newsletter_loader = newsletter_loader
        self.loyalty_loader = loyalty_loader

    def build_dashboard_payload(self, recent_limit: int = 12) -> dict[str, Any]:
        products = self.products_loader()
        newsletter = self.newsletter_loader()
        loyalty = self.loyalty_loader()
        order_totals = self.database.build_dashboard_totals()
        recent_orders = self.database.list_orders(limit=recent_limit, exclude_delivery_statuses=["delivered"])
        categories = sorted({str(item.get("category", "")).strip() for item in products if item.get("category")})
        return {
            "totals": {
                "products": len(products),
                "categories": len(categories),
                "newsletterSubscribers": len(newsletter),
                "loyaltyMembers": len(loyalty),
                **order_totals,
            },
            "recentOrders": recent_orders,
        }

    def build_orders_payload(
        self,
        limit: int = 50,
        delivery_statuses: list[str] | None = None,
        exclude_delivery_statuses: list[str] | None = None,
    ) -> dict[str, Any]:
        orders = self.database.list_orders(
            limit=limit,
            delivery_statuses=delivery_statuses,
            exclude_delivery_statuses=exclude_delivery_statuses,
        )
        return {
            "items": orders,
            "count": len(orders),
        }

    def build_legacy_dashboard_payload(self) -> dict[str, Any]:
        dashboard = self.build_dashboard_payload(recent_limit=5)
        totals = dashboard["totals"]
        return {
            "totals": {
                "orders": totals["orders"],
                "newsletterSubscribers": totals["newsletterSubscribers"],
                "loyaltyMembers": totals["loyaltyMembers"],
                "revenue": totals["revenue"],
            },
            "recentOrders": dashboard["recentOrders"],
        }
