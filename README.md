# Asanbar Pricing Service 🚀

`asanbar-pricing-service` is a high-performance, production-grade pricing microservice built with **Python 3.12** and **FastAPI** for the Asanbar freight marketplace. 

The service handles absolute, integer-based IRR currency quotes, enforces transactional idempotency across state-changing requests, and guarantees reliable event delivery to Redis via an Outbox Pattern.

---

## 🏗️ Architectural Deep Dive

This service is designed using a strict **Layered Architecture** paired with transactional enterprise integration patterns to ensure data consistency and high reliability under heavy concurrent loads.

```
+------------------------------------------------------------+
|                       FastAPI Layer                        |
|   (Routers, Domain Schemas, Correlation ID Middleware)    |
+------------------------------+-----------------------------+
|
v
+------------------------------------------------------------+
|                       Service Layer                        |
|      (Idempotency Validation, Financial Calculations)      |
+------------------------------+-----------------------------+
|
+---------+---------+
|  Database Transaction  |
v                   v
+----------------------------+   +---------------------------+
|      PostgreSQL Layer      |   |    Outbox Events Table    |
| (Quotes/Snapshots Schema)  |   | (Pending stream payloads) |
+----------------------------+   +-------------+-------------+
|
| (CDC / Publisher)
v
+---------------------------+
|       Redis Streams       |
|     (`asanbar:events`)    |
+---------------------------+

```
### Key Engineering Patterns Implemented:
* **Database-Backed Idempotency Engine:** Prevents duplicate financial operations (e.g., snapshot confirmation) by storing the context, path, and precise request body hash using atomic constraints. Any internal body mismatch immediately yields a `409 Conflict`.
* **Transactional Outbox Pattern:** To prevent partial failures (Dual-Write Problem), outbox event records are saved into the PostgreSQL `pricing.outbox_events` table inside the *exact same* database transaction that persists the snapshot. Events are then safely decoupled and published asynchronously to Redis Streams.
* **Exact Integer Arithmetic:** To eliminate IEEE 754 floating-point rounding drifts common in financial calculations, all values (Base Amount, Rates per KM, Stop Fees, Commissions, and Net Balances) are computed and stored as strict whole `Integer` units (Rials).
* **Isolated Database Schemas:** The entire service state is segregated within a dedicated, natively isolated PostgreSQL schema named `pricing`, keeping the default `public` catalog completely clean.

---

## 🛣️ API Specifications & Endpoints

### Core Endpoints
* `POST /api/v1/pricing/shipments/{shipment_id}/quote` - Generates a new dynamic price quote or safely reuses a valid unconfirmed version. Supports `force_recalculate=true`.
* `GET /api/v1/pricing/shipments/{shipment_id}/quotes/latest` - Retrieves the absolute latest price quote computed for a specific shipment.
* `POST /api/v1/pricing/shipments/{shipment_id}/confirm-snapshot` - Atomically locks a quote into an active snapshot. **Requires an `Idempotency-Key` header.**
* `GET /api/v1/pricing/shipments/{shipment_id}/snapshot` - Fetches the currently active confirmed snapshot details for the shipment.

### Platform Health
* `GET /health` - Liveness probe checking application runtime status.
* `GET /ready` - Readiness probe executing a raw dependency check (`SELECT 1`) against PostgreSQL.

---

## 🚦 Error Handling & Specification Compliance

All exceptions (including FastAPI framework input validation errors) are intercepted globally and wrapped in a strictly unified, structured JSON error envelope containing a unique, traceable request correlation ID:

```json
{
  "error": {
    "code": "UNKNOWN_RATE_CARD",
    "message": "The requested cargo_type and vehicle_type pair does not match any registered rate cards.",
    "correlation_id": "4e1b8b2a-5b6c-4d7e-8f9a-0b1c2d3e4f5g"
  }
}
```

## ⚙️ Local Infrastructure Setup

### 1. Spin up Core Dependencies
Bring up the isolated PostgreSQL 16 database and Redis 7 broker using Docker Compose:

Bash

```
docker compose up -d
```

### 2. Environment Configuration
The application automatically reads from system environment variables. You can easily export variables or create a `.env` file in the root directory:

Code snippet

```
DATABASE_URL=postgresql+asyncpg://pricing_user:pricing_pass@localhost:5432/pricing
REDIS_URL=redis://localhost:6379/0
```

### 3. Install Dependencies & Run Database Migrations
This repository leverages standard Python packaging configurations (`pyproject.toml`).

Bash

```
# Install the app along with development dependencies
pip install -e .[dev]

# Run native async schema migrations via Alembic
alembic upgrade head
```

### 4. Boot the Microservice
Start the production-ready Uvicorn ASGI server loop:

Bash

```
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 🧪 Comprehensive Test Suite
Testing is built around mock-free integration paradigms. It leverages an async testing loop backed by transient database schemas (automatically dropped/recreated per session) and an optimized concurrent mock implementation of Redis (`fakeredis`).

To run tests with full coverage analytics and missing-line tracing reports, execute:

Bash

```
pytest
```

