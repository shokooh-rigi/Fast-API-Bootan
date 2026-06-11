from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, StrictInt, StrictStr


class QuoteInputs(BaseModel):
    distance_km: StrictInt = Field(..., gt=0)
    stop_count: StrictInt = Field(..., ge=1)
    cargo_type: StrictStr
    vehicle_type: StrictStr


class QuoteBreakdown(BaseModel):
    base_amount: StrictInt
    distance_amount: StrictInt
    stop_fee: StrictInt
    rate_per_km: StrictInt
    commission_rate_bps: StrictInt


class QuoteResponse(BaseModel):
    quote_id: StrictStr
    shipment_id: StrictStr
    quote_version: StrictInt
    inputs: dict[str, Any]
    gross_amount: StrictInt
    commission_amount: StrictInt
    driver_net_amount: StrictInt
    currency: StrictStr
    breakdown: QuoteBreakdown
    created_at: datetime


class SnapshotResponse(BaseModel):
    snapshot_id: StrictStr
    shipment_id: StrictStr
    quote_id: StrictStr
    quote_version: StrictInt
    gross_amount: StrictInt
    commission_amount: StrictInt
    driver_net_amount: StrictInt
    currency: StrictStr
    confirmed_at: datetime


class QuoteRequest(BaseModel):
    inputs: QuoteInputs
    force_recalculate: bool = False


class EventPayloadData(BaseModel):
    shipment_id: StrictStr
    price_snapshot_id: StrictStr
    quote_id: StrictStr
    gross_amount: StrictInt
    commission_amount: StrictInt
    driver_net_amount: StrictInt
    currency: StrictStr


class PriceSnapshotCreatedEvent(BaseModel):
    event_id: StrictStr
    event_type: Literal["price_snapshot.created"] = Field(default="price_snapshot.created")
    occurred_at: datetime
    correlation_id: StrictStr | None
    data: EventPayloadData


class ErrorResponse(BaseModel):
    error: dict[str, Any]
