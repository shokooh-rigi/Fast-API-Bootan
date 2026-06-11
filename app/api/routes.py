import json
from typing import Any

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import get_session
from ..exceptions import (
    ApiError,
    ConflictError,
    QuoteNotFoundError,
    UnknownRateCardError,
)
from ..middleware import get_correlation_id
from ..redis_client import RedisPublisher, RealRedisPublisher
from ..schemas import QuoteRequest, QuoteResponse, SnapshotResponse
from ..services import (
    RateCardNotFound,
    confirm_price_snapshot,
    create_quote,
    find_latest_quote,
    get_snapshot,
)

router = APIRouter(prefix="/api/v1/pricing")


def get_redis_publisher() -> RedisPublisher:
    return RealRedisPublisher(settings.redis_url)


def quote_to_response(quote: Any) -> dict[str, Any]:
    return {
        "quote_id": quote.id,
        "shipment_id": quote.shipment_id,
        "quote_version": quote.quote_version,
        "inputs": {
            "distance_km": quote.distance_km,
            "stop_count": quote.stop_count,
            "cargo_type": quote.cargo_type,
            "vehicle_type": quote.vehicle_type,
        },
        "gross_amount": quote.gross_amount,
        "commission_amount": quote.commission_amount,
        "driver_net_amount": quote.driver_net_amount,
        "currency": quote.currency,
        "breakdown": quote.breakdown,
        "created_at": quote.created_at,
    }


def snapshot_to_response(snapshot: Any) -> dict[str, Any]:
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


@router.post("/shipments/{shipment_id}/quote", response_model=QuoteResponse)
async def create_pricing_quote(
    shipment_id: str,
    request: QuoteRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        quote = await create_quote(session, shipment_id, request.inputs.model_dump(), request.force_recalculate)
        await session.commit()
        return quote_to_response(quote)
    except RateCardNotFound as exc:
        raise UnknownRateCardError(str(exc))
    except ApiError:
        raise


@router.get("/shipments/{shipment_id}/quotes/latest", response_model=QuoteResponse)
async def get_latest_quote(shipment_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    quote = await find_latest_quote(session, shipment_id)
    if quote is None:
        raise QuoteNotFoundError()
    return quote_to_response(quote)


@router.post("/shipments/{shipment_id}/confirm-snapshot", response_model=SnapshotResponse)
async def confirm_snapshot(
    shipment_id: str,
    request: Request,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
) -> Any:
    if idempotency_key is None:
        raise ConflictError("IDEMPOTENCY_CONFLICT", "Missing Idempotency-Key header")

    correlation_id = get_correlation_id(request)
    request_body = None
    request_path = request.url.path
    request_method = request.method
    redis_publisher = get_redis_publisher()

    try:
        response_body, event_payload, event_id, status_code = await confirm_price_snapshot(
            session,
            shipment_id,
            correlation_id,
            idempotency_key,
            request_path,
            request_method,
            request_body,
        )
        await session.commit()
        if event_payload is not None and event_id is not None:
            await redis_publisher.xadd("asanbar:events", {"payload": json.dumps(event_payload, ensure_ascii=False)})
        return JSONResponse(status_code=status_code, content=response_body)
    except ApiError:
        await session.rollback()
        raise


@router.get("/shipments/{shipment_id}/snapshot", response_model=SnapshotResponse)
async def get_snapshot_endpoint(shipment_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    snapshot = await get_snapshot(session, shipment_id)
    return snapshot_to_response(snapshot)


