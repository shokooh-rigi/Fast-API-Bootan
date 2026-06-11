"""initial pricing schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-06-11 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = '0001_initial'
down_revision = None
branch_labels = None
de_pends_on = None

SCHEMA_NAME = 'pricing'


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME}")
    op.create_table(
        'rate_cards',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('cargo_type', sa.String(length=64), nullable=False),
        sa.Column('vehicle_type', sa.String(length=64), nullable=False),
        sa.Column('rate_per_km', sa.Integer(), nullable=False),
        sa.Column('stop_fee', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        schema=SCHEMA_NAME,
    )
    op.create_unique_constraint('uq_rate_cards_combo', 'rate_cards', ['cargo_type', 'vehicle_type'], schema=SCHEMA_NAME)

    op.create_table(
        'commission_rules',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('rate_bps', sa.Integer(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        schema=SCHEMA_NAME,
    )
    op.create_unique_constraint('uq_commission_rules_name', 'commission_rules', ['name'], schema=SCHEMA_NAME)

    op.create_table(
        'price_quotes',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('shipment_id', sa.String(length=128), nullable=False),
        sa.Column('quote_version', sa.Integer(), nullable=False),
        sa.Column('distance_km', sa.Integer(), nullable=False),
        sa.Column('stop_count', sa.Integer(), nullable=False),
        sa.Column('cargo_type', sa.String(length=64), nullable=False),
        sa.Column('vehicle_type', sa.String(length=64), nullable=False),
        sa.Column('gross_amount', sa.Integer(), nullable=False),
        sa.Column('commission_amount', sa.Integer(), nullable=False),
        sa.Column('driver_net_amount', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(length=8), nullable=False),
        sa.Column('rate_per_km', sa.Integer(), nullable=False),
        sa.Column('stop_fee', sa.Integer(), nullable=False),
        sa.Column('commission_rate_bps', sa.Integer(), nullable=False),
        sa.Column('breakdown', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        schema=SCHEMA_NAME,
    )
    op.create_unique_constraint('uq_price_quotes_shipment_version', 'price_quotes', ['shipment_id', 'quote_version'], schema=SCHEMA_NAME)

    op.create_table(
        'price_snapshots',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('shipment_id', sa.String(length=128), nullable=False),
        sa.Column('quote_id', sa.String(length=36), nullable=False),
        sa.Column('quote_version', sa.Integer(), nullable=False),
        sa.Column('gross_amount', sa.Integer(), nullable=False),
        sa.Column('commission_amount', sa.Integer(), nullable=False),
        sa.Column('driver_net_amount', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(length=8), nullable=False),
        sa.Column('confirmed_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        schema=SCHEMA_NAME,
    )
    op.create_unique_constraint('uq_price_snapshots_shipment_active', 'price_snapshots', ['shipment_id', 'is_active'], schema=SCHEMA_NAME)

    op.create_table(
        'idempotency_keys',
        sa.Column('key', sa.String(length=255), primary_key=True),
        sa.Column('shipment_id', sa.String(length=128), nullable=False),
        sa.Column('request_path', sa.String(length=512), nullable=False),
        sa.Column('request_method', sa.String(length=16), nullable=False),
        sa.Column('request_body', sa.JSON(), nullable=True),
        sa.Column('response_code', sa.Integer(), nullable=False),
        sa.Column('response_body', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        schema=SCHEMA_NAME,
    )

    op.create_table(
        'outbox_events',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('stream_name', sa.String(length=128), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('published', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_table('outbox_events', schema=SCHEMA_NAME)
    op.drop_table('idempotency_keys', schema=SCHEMA_NAME)
    op.drop_table('price_snapshots', schema=SCHEMA_NAME)
    op.drop_table('price_quotes', schema=SCHEMA_NAME)
    op.drop_table('commission_rules', schema=SCHEMA_NAME)
    op.drop_table('rate_cards', schema=SCHEMA_NAME)
