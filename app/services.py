import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .exceptions import (
    ConflictError,
    IdempotencyConflictError,
    NotFoundError,
    QuoteNotFoundError,
    SnapshotAlreadyExistsError,
    UnknownRateCardError,
    ValidationError,
)
from .models import (
    CommissionRule,
    IdempotencyKey,
    OutboxEvent,
    PriceQuote,
    PriceSnapshot,
    RateCard,
)


class RateCardNotFound(Exception):
    pass


def calculate_commission(gross_amount: int, rate_bps: int) -> int:
    numerator = gross_amount * rate_bps
    commission = numerator // 10_000
    remainder = numerator % 10_000
    if remainder * 2 >= 10_000:
        commission += 1
    return commission


def build_quote_breakdown(inputs: dict[str, Any], rate_card: RateCard, commission_rate_bps: int) -> dict[str, int]:
    distance_amount = inputs["distance_km"] * rate_card.rate_per_km
    stop_fee = rate_card.stop_fee * max(0, inputs["stop_count"] - 1)
    base_amount = distance_amount + stop_fee
    return {
        "base_amount": base_amount,
        "distance_amount": distance_amount,
        "stop_fee": stop_fee,
        "rate_per_km": rate_card.rate_per_km,
        "commission_rate_bps": commission_rate_bps,
    }


async def get_active_commission_rate(session: AsyncSession) -> int:
    result = await session.execute(
        select(CommissionRule.rate_bps).where(CommissionRule.active.is_(True)).limit(1)
    )
    commission_rate = result.scalar_one_or_none()
    if commission_rate is None:
        raise NotFoundError("Active commission rule not found")
    return commission_rate


async def get_rate_card(session: AsyncSession, cargo_type: str, vehicle_type: str) -> RateCard:
    result = await session.execute(
        select(RateCard).where(
            and_(RateCard.cargo_type == cargo_type, RateCard.vehicle_type == vehicle_type)
        )
    )
    rate_card = result.scalar_one_or_none()
    if rate_card is None:
        raise RateCardNotFound(f"Unknown cargo/vehicle combo: {cargo_type}/{vehicle_type}")
    return rate_card


async def find_latest_quote(session: AsyncSession, shipment_id: str) -> PriceQuote | None:
    result = await session.execute(
        select(PriceQuote)
        .where(PriceQuote.shipment_id == shipment_id)
        .order_by(PriceQuote.quote_version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def find_matching_quote(session: AsyncSession, shipment_id: str, inputs: dict[str, Any]) -> PriceQuote | None:
    result = await session.execute(
        select(PriceQuote)
        .where(
            PriceQuote.shipment_id == shipment_id,
            PriceQuote.distance_km == inputs["distance_km"],
            PriceQuote.stop_count == inputs["stop_count"],
            PriceQuote.cargo_type == inputs["cargo_type"],
            PriceQuote.vehicle_type == inputs["vehicle_type"],
        )
        .order_by(PriceQuote.quote_version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_quote(session: AsyncSession, shipment_id: str, inputs: dict[str, Any], force_recalculate: bool) -> PriceQuote:
    rate_card = await get_rate_card(session, inputs["cargo_type"], inputs["vehicle_type"])
    commission_rate_bps = await get_active_commission_rate(session)
    breakdown = build_quote_breakdown(inputs, rate_card, commission_rate_bps)
    gross_amount = breakdown["base_amount"]
    commission_amount = calculate_commission(gross_amount, commission_rate_bps)
    driver_net_amount = gross_amount - commission_amount

    if driver_net_amount + commission_amount != gross_amount:
        raise ValidationError("MATH_INVARIANT_VIOLATION", "Commission math invariant violated")

    if not force_recalculate:
        existing = await find_matching_quote(session, shipment_id, inputs)
        if existing is not None:
            return existing

    latest = await find_latest_quote(session, shipment_id)
    quote_version = 1 if latest is None else latest.quote_version + 1
    quote = PriceQuote(
        shipment_id=shipment_id,
        quote_version=quote_version,
        distance_km=inputs["distance_km"],
        stop_count=inputs["stop_count"],
        cargo_type=inputs["cargo_type"],
        vehicle_type=inputs["vehicle_type"],
        gross_amount=gross_amount,
        commission_amount=commission_amount,
        driver_net_amount=driver_net_amount,
        currency=settings.currency,
        rate_per_km=rate_card.rate_per_km,
        stop_fee=rate_card.stop_fee,
        commission_rate_bps=commission_rate_bps,
        breakdown=breakdown,
    )
    session.add(quote)
    await session.flush()
    return quote


async def get_idempotency_record(session: AsyncSession, key: str) -> IdempotencyKey | None:
    result = await session.execute(select(IdempotencyKey).where(IdempotencyKey.key == key))
    return result.scalar_one_or_none()


async def save_idempotency_record(
    session: AsyncSession,
    key: str,
    shipment_id: str,
    request_path: str,
    request_method: str,
    request_body: dict[str, Any] | None,
    response_code: int,
    response_body: dict[str, Any],
) -> None:
    record = IdempotencyKey(
        key=key,
        shipment_id=shipment_id,
        request_path=request_path,
        request_method=request_method,
        request_body=request_body,
        response_code=response_code,
        response_body=response_body,
    )
    session.add(record)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise IdempotencyConflictError("Duplicate idempotency key") from exc


def build_snapshot_response(snapshot: PriceSnapshot) -> dict[str, Any]:
    return {
        "snapshot_id": snapshot.id,
        "shipment_id": snapshot.shipment_id,
        "quote_id": snapshot.quote_id,
        "quote_version": snapshot.quote_version,
        "gross_amount": snapshot.gross_amount,
        "commission_amount": snapshot.commission_amount,
        "driver_net_amount": snapshot.driver_net_amount,
        "currency": snapshot.currency,
        "confirmed_at": snapshot.confirmed_at,
    }


def build_event_payload(snapshot: PriceSnapshot, correlation_id: str) -> dict[str, Any]:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "price_snapshot.created",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        "data": {
            "shipment_id": snapshot.shipment_id,
            "price_snapshot_id": snapshot.id,
            "quote_id": snapshot.quote_id,
            "gross_amount": snapshot.gross_amount,
            "commission_amount": snapshot.commission_amount,
            "driver_net_amount": snapshot.driver_net_amount,
            "currency": snapshot.currency,
        },
    }


async def create_outbox_event(session: AsyncSession, event_payload: dict[str, Any]) -> None:
    event = OutboxEvent(
        id=event_payload["event_id"],
        stream_name="asanbar:events",
        payload=event_payload,
        published=False,
    )
    session.add(event)
    await session.flush()


async def mark_outbox_event_published(session: AsyncSession, event_id: str) -> None:
    await session.execute(
        update(OutboxEvent)
        .where(OutboxEvent.id == event_id)
        .values(published=True)
    )
    await session.flush()


async def confirm_price_snapshot(
    session: AsyncSession,
    shipment_id: str,
    correlation_id: str,
    idempotency_key: str,
    request_path: str,
    request_method: str,
    request_body: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any] | None, str | None, int]:
    existing = await get_idempotency_record(session, idempotency_key)
    if existing is not None:
        if (
            existing.shipment_id != shipment_id
            or existing.request_path != request_path
            or existing.request_method != request_method
            or existing.request_body != request_body
        ):
            raise IdempotencyConflictError("Idempotency key conflict")

        return existing.response_body, None, None, 200

    latest_quote = await find_latest_quote(session, shipment_id)
    if latest_quote is None:
        raise QuoteNotFoundError()

    snapshot_exists = await session.execute(
        select(PriceSnapshot).where(
            PriceSnapshot.shipment_id == shipment_id,
            PriceSnapshot.is_active.is_(True),
        )
    )
    if snapshot_exists.scalar_one_or_none() is not None:
        raise SnapshotAlreadyExistsError()

    snapshot = PriceSnapshot(
        shipment_id=shipment_id,
        quote_id=latest_quote.id,
        quote_version=latest_quote.quote_version,
        gross_amount=latest_quote.gross_amount,
        commission_amount=latest_quote.commission_amount,
        driver_net_amount=latest_quote.driver_net_amount,
        currency=latest_quote.currency,
    )
    session.add(snapshot)
    await session.flush()

    response_body = build_snapshot_response(snapshot)
    event_payload = build_event_payload(snapshot, correlation_id)
    await save_idempotency_record(
        session,
        idempotency_key,
        shipment_id,
        request_path,
        request_method,
        request_body,
        201,
        response_body,
    )
    await create_outbox_event(session, event_payload)

    return response_body, event_payload, event_payload["event_id"], 201


async def get_snapshot(session: AsyncSession, shipment_id: str) -> PriceSnapshot:
    result = await session.execute(
        select(PriceSnapshot).where(PriceSnapshot.shipment_id == shipment_id, PriceSnapshot.is_active.is_(True))
    )
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        raise SnapshotNotFoundError()
    return snapshot
