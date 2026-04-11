# Blessing Enterprise Backend

This project now includes a lightweight Python backend that serves the storefront and exposes a small JSON API.

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
- `POST /api/orders` to save checkout orders
- `GET /api/newsletter` to view newsletter subscribers
- `POST /api/newsletter/subscribe` to save newsletter signups
- `POST /api/loyalty/join` to save loyalty members
- `GET /api/dashboard` for quick totals and recent orders

## Admin dashboard

After starting the backend, open the site and use the `Admin` link in the footer.

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

## Stored data

The backend writes JSON files inside `data/`:

- `products.json`
- `orders.json`
- `newsletter.json`
- `loyalty.json`
