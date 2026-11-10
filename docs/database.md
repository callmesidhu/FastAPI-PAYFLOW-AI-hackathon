# PAYFLOW AI — Database Persistence Architecture & Setup Guide

This document outlines the persistence layer, collection schemas, index strategy, and deployment configuration for MongoDB.

---

## 1. Driver Selection & Architecture Choice

**Driver**: [`motor`](https://motor.readthedocs.io/) (v3.5+), the official asynchronous Python driver for MongoDB maintained by the MongoDB team.

### Rationale
- **Simplicity & Performance**: Built directly on `asyncio` and `pymongo`, `motor` avoids the overhead, query translation bugs, and schema synchronization fragility common to heavy Object-Document Mappers (ODMs) like Beanie or ODMantic.
- **FastAPI Native**: Integrates cleanly with FastAPI's `lifespan` context manager for connection pooling and dependency injection (`Depends(get_db)`).
- **Direct Control Over Invariants**: Allows explicit enforcement of index idempotency, user ownership scoping (`user_id`), and atomic transactional operations without layer abstractions.

---

## 2. Collections & Index Strategy

All indexes are created idempotently on startup via [`create_indexes`](file:///c:/Users/sidha/OneDrive/Desktop/CodeDOT/FastAPI-PAYFLOW-AI-hackathon/backend/app/db/indexes.py).

| Collection | Key Fields | Primary Indexes | Invariant Enforced |
| :--- | :--- | :--- | :--- |
| **`users`** | `email`, `hashed_password`, `name` | `email` (unique), `created_at` | Unique accounts; fast auth lookups. |
| **`customers`** | `user_id`, `name`, `email`, `notes` | `user_id`, `(user_id, email)` (unique, sparse), `(user_id, name)` | Prevents duplicate customer entries per business owner. |
| **`invoices`** | `internal_id`, `user_id`, `invoice_number`, `status`, `due_date`, `total`, `paypal_invoice_id` | `internal_id` (unique), `user_id`, `(user_id, invoice_number)` (unique), `paypal_invoice_id` (sparse), `status`, `due_date`, `(user_id, status)` | Unique invoice numbering per user; quick status and overdue filtering. |
| **`approvals`** | `user_id`, `resource_id`, `payload_hash`, `status` | `user_id`, `resource_id`, `payload_hash`, `(user_id, status)` | Fast verification of human approval tokens and invalidation on payload changes. |
| **`reminders`** | `user_id`, `invoice_id`, `stage`, `status` | `user_id`, `invoice_id`, `(invoice_id, stage)` (unique) | Idempotent reminder drafting — prevents duplicate messages for the same overdue stage. |
| **`transactions`**| `user_id`, `invoice_id`, `paypal_capture_id`, `amount` | `user_id`, `invoice_id`, `paypal_capture_id` (sparse) | Immutable ledger of payments and settlements. |
| **`audit_logs`** | `user_id`, `resource_id`, `action`, `actor`, `metadata` | `user_id`, `resource_id`, `action`, `created_at` | Append-only security and operational audit trail. |
| **`webhook_events`** | `event_id`, `event_type`, `verified`, `payload` | `event_id` (unique), `created_at` | Webhook idempotency and replay protection. |

---

## 3. MongoDB Atlas Setup (Step-by-Step)

For production deployment and remote team development, follow these steps to set up MongoDB Atlas:

### Step 1: Create a Database Cluster
1. Log in to [MongoDB Atlas](https://cloud.mongodb.com/).
2. Click **Create** to deploy a free **M0 (Shared)** cluster (e.g. AWS `us-east-1` or `ap-south-1`).
3. Set cluster name to `payflow-cluster`.

### Step 2: Configure Database Access (User Credentials)
1. In the Atlas sidebar under **Security**, navigate to **Database Access**.
2. Click **Add New Database User**.
3. Authentication Method: **Password**.
4. Set Username: `payflow_app_user`.
5. Autogenerate a secure password (store securely; never commit).
6. Set Database User Privileges: **Read and write to any database** (or restrict to `payflow_ai`).
7. Click **Add User**.

### Step 3: Configure Network Access (IP Whitelisting)
1. In the Atlas sidebar under **Security**, navigate to **Network Access**.
2. Click **Add IP Address**.
3. For local development: Click **Add Current IP Address** to allow your workstation.
4. For cloud hosting (e.g., Render):
   - Click **Allow Access from Anywhere** (`0.0.0.0/0`).
   - *Note*: Render services use dynamic outbound IP addresses, so `0.0.0.0/0` with strong user password authentication is the standard practice on Render.
5. Click **Confirm**.

### Step 4: Retrieve Connection String
1. Return to **Database** in the sidebar.
2. Click **Connect** next to your cluster.
3. Choose **Drivers** $\rightarrow$ Python $\rightarrow$ version 3.12 or later.
4. Copy the connection string:
   ```
   mongodb+srv://payflow_app_user:<password>@payflow-cluster.xxxx.mongodb.net/?retryWrites=true&w=majority
   ```
5. Place this in your local `backend/.env` or Render environment settings under `MONGODB_URI`.

---

## 4. Connection Lifecycle & Health Monitoring

- **Asynchronous Lifespan**: MongoDB client connects asynchronously during FastAPI startup and disconnects cleanly during shutdown.
- **Liveliness Ping**: A lightweight `admin.command('ping')` verifies database availability.
- **Zero-Secret Diagnostic**: `/health` reports `"database": "connected"` or `"database": "disconnected"`. Credentials, usernames, and cluster URIs are never returned.
