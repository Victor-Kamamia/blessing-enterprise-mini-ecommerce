# Blessing Enterprise Backend

This project now includes a lightweight Python backend that serves the storefront, stores checkout/payment history in SQLite, and exposes a JSON API for the storefront plus admin dashboard.

## Start the app

```bash
python backend/server.py
```

Open `http://127.0.0.1:8000`.

To preview it on your phone, run:

```powershell
.\start-phone-preview.ps1
```

Then open one of these on your phone browser:

- `http://10.50.4.117:8000`
- `http://192.168.137.1:8000` if your phone is connected to your PC hotspot

## VS Code Emulator Setup

This workspace now includes VS Code tasks for:

- `Start Phone Preview Server`
- `Start Android Emulator - Medium_Phone_API_36.1`
- `Start Android Emulator - Medium_Phone`
- `ADB Devices`

Open `Terminal -> Run Task`, start the preview server, then start one of the Android emulator tasks.

Inside the Android emulator browser, open:

- `http://10.0.2.2:8000`

`10.0.2.2` is the Android emulator alias for your computer's local server.

## What the backend handles

- Serves the existing frontend files
- `GET /api/products` for the product catalog
- `POST /api/products` to add a new product from the admin dashboard
- `POST /api/admin/login` to sign in to the admin dashboard
- `POST /api/admin/logout` to sign out of the admin dashboard
- `POST /api/orders` and `POST /api/checkout` to save checkout orders and trigger M-Pesa STK Push
- `POST /api/payments/mpesa/callback` to receive M-Pesa payment callbacks
- `GET /api/orders/<reference>` to poll an order/payment status after checkout
- `GET /api/newsletter` to view newsletter subscribers
- `POST /api/newsletter/subscribe` to save newsletter signups
- `POST /api/loyalty/join` to save loyalty members
- `GET /api/dashboard` for quick totals and recent orders
- `GET /api/admin/dashboard` and `GET /api/admin/orders` for admin order history
- `POST /api/admin/orders/<reference>/delivery-status` to move orders between `new`, `on_delivery`, and `delivered`
- `GET /api/admin/events` for live admin dashboard updates

## Admin dashboard

After starting the backend, open `admin.html` directly or use the `Admin` link in the storefront footer. The admin dashboard is now a separate workspace from the customer UI.

Default admin login:

- Username: `admin`
- Password: `BlessingAdmin2026!`

You can override them before starting the backend with:

```powershell
$env:BLESSING_ADMIN_USERNAME="your-admin-name"
$env:BLESSING_ADMIN_PASSWORD="your-strong-password"
python backend/server.py
```

From there you can:

- add products to `data/products.json`
- view newsletter subscribers from `data/newsletter.json`
- watch recent orders and M-Pesa payment updates in real time
- move orders through `Orders`, `On Delivery`, and `Delivered` queues
- keep delivered orders out of the active queue while preserving their history

## Payments and email

The backend now uses SQLite at `data/blessing_enterprise.sqlite3` for order, payment, and email-delivery history.

Until real credentials are added, checkout runs in mock M-Pesa mode by default so the flow can still be tested locally.

By default, business email notifications target `vickyngvicky23@gmail.com`. You can override that with `BLESSING_ADMIN_EMAIL`.

Useful environment variables:

- `BLESSING_ADMIN_EMAIL`
- `BLESSING_SMTP_HOST`
- `BLESSING_SMTP_PORT`
- `BLESSING_SMTP_USERNAME`
- `BLESSING_SMTP_PASSWORD`
- `BLESSING_SMTP_FROM_EMAIL`
- `BLESSING_MPESA_CONSUMER_KEY`
- `BLESSING_MPESA_CONSUMER_SECRET`
- `BLESSING_MPESA_SHORTCODE`
- `BLESSING_MPESA_PASSKEY`
- `BLESSING_MPESA_CALLBACK_BASE_URL`
- `BLESSING_MPESA_MOCK_MODE`
- `BLESSING_MPESA_MOCK_RESULT`

## Stored data

The backend still writes these JSON files inside `data/` for compatibility:

- `products.json`
- `orders.json`
- `newsletter.json`
- `loyalty.json`

SQLite now stores the authoritative order, transaction, and email notification records.
