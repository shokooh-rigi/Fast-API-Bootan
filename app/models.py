import uuid
from sqlalchemy import Boolean, Column, ForeignKey, Integer, JSON, String, TIMESTAMP, UniqueConstraint, text
from sqlalchemy.orm import declarative_base
from .db import metadata

Base = declarative_base(metadata=metadata)


def generate_uuid() -> str:
    return str(uuid.uuid4())


class RateCard(Base):
    __tablename__ = "rate_cards"
    __table_args__ = (UniqueConstraint("cargo_type", "vehicle_type", name="uq_rate_cards_combo"),)

    id = Column(String(36), primary_key=True, default=generate_uuid)
    cargo_type = Column(String(64), nullable=False)
    vehicle_type = Column(String(64), nullable=False)
    rate_per_km = Column(Integer, nullable=False)
    stop_fee = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class CommissionRule(Base):
    __tablename__ = "commission_rules"
    __table_args__ = (UniqueConstraint("name", name="uq_commission_rules_name"),)

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(64), nullable=False)
    rate_bps = Column(Integer, nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class PriceQuote(Base):
    __tablename__ = "price_quotes"
    __table_args__ = (
        UniqueConstraint("shipment_id", "quote_version", name="uq_price_quotes_shipment_version"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    shipment_id = Column(String(128), nullable=False, index=True)
    quote_version = Column(Integer, nullable=False)
    distance_km = Column(Integer, nullable=False)
    stop_count = Column(Integer, nullable=False)
    cargo_type = Column(String(64), nullable=False)
    vehicle_type = Column(String(64), nullable=False)
    gross_amount = Column(Integer, nullable=False)
    commission_amount = Column(Integer, nullable=False)
    driver_net_amount = Column(Integer, nullable=False)
    currency = Column(String(8), nullable=False)
    rate_per_km = Column(Integer, nullable=False)
    stop_fee = Column(Integer, nullable=False)
    commission_rate_bps = Column(Integer, nullable=False)
    breakdown = Column(JSON, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"
    __table_args__ = (
        UniqueConstraint("shipment_id", "is_active", name="uq_price_snapshots_shipment_active"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    shipment_id = Column(String(128), nullable=False, index=True)
    quote_id = Column(String(36), ForeignKey("pricing.price_quotes.id"), nullable=False)
    quote_version = Column(Integer, nullable=False)
    gross_amount = Column(Integer, nullable=False)
    commission_amount = Column(Integer, nullable=False)
    driver_net_amount = Column(Integer, nullable=False)
    currency = Column(String(8), nullable=False)
    confirmed_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    is_active = Column(Boolean, nullable=False, default=True)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    key = Column(String(255), primary_key=True)
    shipment_id = Column(String(128), nullable=False)
    request_path = Column(String(512), nullable=False)
    request_method = Column(String(16), nullable=False)
    request_body = Column(JSON, nullable=True)
    response_code = Column(Integer, nullable=False)
    response_body = Column(JSON, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id = Column(String(36), primary_key=True)
    stream_name = Column(String(128), nullable=False)
    payload = Column(JSON, nullable=False)
    published = Column(Boolean, nullable=False, default=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
