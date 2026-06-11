import os
import uuid

import httpx
from httpx import ASGITransport
import pytest
from fastapi import status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import routes as pricing_routes
from app.main import app
from app.models import Base, RateCard, CommissionRule
from app.redis_client import FakeRedisPublisher


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://pricing_user:pricing_pass@localhost:5432/pricing")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def engine():
    engine = create_async_engine(DATABASE_URL, future=True)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS pricing CASCADE"))
        await conn.execute(text("CREATE SCHEMA pricing"))
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(engine):
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        await session.begin()
        yield session
        await session.rollback()


@pytest.fixture(scope="function")
async def seeded_db(db_session):
    await db_session.execute(
        text(
            "TRUNCATE TABLE pricing.rate_cards, pricing.commission_rules, pricing.price_quotes, pricing.price_snapshots, pricing.idempotency_keys, pricing.outbox_events RESTART IDENTITY CASCADE"
        )
    )
    rate_cards = [
        RateCard(cargo_type="general", vehicle_type="trailer", rate_per_km=12000, stop_fee=500000),
        RateCard(cargo_type="general", vehicle_type="single", rate_per_km=10000, stop_fee=400000),
        RateCard(cargo_type="refrigerated", vehicle_type="trailer", rate_per_km=15000, stop_fee=600000),
    ]
    commission = CommissionRule(name="default", rate_bps=1000, active=True)
    db_session.add_all(rate_cards + [commission])
    await db_session.flush()
    yield db_session


@pytest.fixture(scope="function")
def fake_redis():
    return FakeRedisPublisher()


@pytest.fixture(scope="function")
async def client(monkeypatch, db_session, fake_redis):
    async def override_get_session() -> AsyncSession:
        yield db_session

    app.dependency_overrides[pricing_routes.get_session] = override_get_session
    monkeypatch.setattr(pricing_routes, "get_redis_publisher", lambda: fake_redis)

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.pop(pricing_routes.get_session, None)


def test_commission_math_edge_case():
    from app.services import calculate_commission

    amount = 1234567
    commission = calculate_commission(amount, 1000)
    assert isinstance(commission, int)
    assert commission == (amount * 1000 + 5000) // 10000
    assert commission + (amount - commission) == amount


@pytest.mark.anyio
async def test_quote_unknown_rate_card(seeded_db, client):
    response = await client.post(
        "/api/v1/pricing/shipments/shipment1/quote",
        json={
            "inputs": {
                "distance_km": 100,
                "stop_count": 1,
                "cargo_type": "unknown",
                "vehicle_type": "single",
            },
            "force_recalculate": False,
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "UNKNOWN"


@pytest.mark.anyio
async def test_confirm_snapshot_idempotency(seeded_db, client):
    quote_response = await client.post(
        "/api/v1/pricing/shipments/shipment-123/quote",
        json={
            "inputs": {
                "distance_km": 10,
                "stop_count": 2,
                "cargo_type": "general",
                "vehicle_type": "trailer",
            },
            "force_recalculate": False,
        },
    )
    assert quote_response.status_code == status.HTTP_200_OK

    key = str(uuid.uuid4())
    response = await client.post(
        "/api/v1/pricing/shipments/shipment-123/confirm-snapshot",
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == status.HTTP_201_CREATED
    snapshot_id = response.json()["snapshot_id"]

    second = await client.post(
        "/api/v1/pricing/shipments/shipment-123/confirm-snapshot",
        headers={"Idempotency-Key": key},
    )
    assert second.status_code == status.HTTP_200_OK
    assert second.json()["snapshot_id"] == snapshot_id


@pytest.mark.anyio
async def test_confirm_snapshot_conflict_after_snapshot(seeded_db, client):
    quote_response = await client.post(
        "/api/v1/pricing/shipments/shipment-321/quote",
        json={
            "inputs": {
                "distance_km": 10,
                "stop_count": 1,
                "cargo_type": "general",
                "vehicle_type": "single",
            },
            "force_recalculate": False,
        },
    )
    assert quote_response.status_code == status.HTTP_200_OK

    first_key = str(uuid.uuid4())
    response = await client.post(
        "/api/v1/pricing/shipments/shipment-321/confirm-snapshot",
        headers={"Idempotency-Key": first_key},
    )
    assert response.status_code == status.HTTP_201_CREATED

    second_key = str(uuid.uuid4())
    conflict = await client.post(
        "/api/v1/pricing/shipments/shipment-321/confirm-snapshot",
        headers={"Idempotency-Key": second_key},
    )
    assert conflict.status_code == status.HTTP_409_CONFLICT
    assert conflict.json()["error"]["code"] == "SNAPSHOT_ALREADY_EXISTS"
