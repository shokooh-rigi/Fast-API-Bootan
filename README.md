# Fast-API-Bootan

Fast-API-Bootan is a Python 3.12 FastAPI pricing microservice built for Asanbar.
It provides quote generation, latest quote retrieval, snapshot confirmation, and snapshot retrieval with strict integer-based IRR pricing and idempotent confirmation.

## Key Features

- `/api/v1/pricing/shipments/{shipment_id}/quote` - create or reuse a quote
- `/api/v1/pricing/shipments/{shipment_id}/quotes/latest` - fetch the latest quote
- `/api/v1/pricing/shipments/{shipment_id}/confirm-snapshot` - confirm a snapshot with idempotency
- `/api/v1/pricing/shipments/{shipment_id}/snapshot` - retrieve the confirmed snapshot
- `/health` - service health check
- `/ready` - database readiness check

## Architecture

- FastAPI application with clearly separated router, services, models, and database setup
- PostgreSQL with a dedicated `pricing` schema
- Redis publishing via `asanbar:events` stream using a publisher abstraction
- Idempotency enforced using `idempotency_keys`
- Outbox-style event creation in the same DB transaction before publishing
- Strict integer arithmetic for IRR price values, no floats or Decimal

## Design Principles

- Separation of concerns: API routes delegate business logic to `app/services.py`
- Single responsibility: models, configuration, middleware, exceptions, and routes are separated
- Testable and scalable: Redis publisher is abstracted for `fakeredis` during tests
- Avoids hard-coded business logic in behaviors; configuration is loaded from environment variables

## Running locally

1. Start dependencies:

```bash
docker compose up -d
```

2. Set environment variables or copy `.env.example` to `.env`

3. Run the app:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

4. Run tests:

```bash
python -m pytest tests/test_pricing.py -q
```

## Commit and push status

The current repository contains the full implementation, database migration, Redis publisher abstraction, idempotency handling, and tests.
