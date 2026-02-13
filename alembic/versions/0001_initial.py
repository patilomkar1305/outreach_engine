"""
alembic/versions/0001_initial.py
────────────────────────────────
Initial migration: creates target_profiles, persona_records,
outreach_runs, draft_records + enables the pgvector extension.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid


revision  = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # NOTE: pgvector is NOT needed – vectors are stored in ChromaDB.

    # ── target_profiles ────────────────────────────────────────────────
    op.create_table(
        "target_profiles",
        sa.Column("id",           postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("target_hash",  sa.String(64),  unique=True, nullable=False, index=True),
        sa.Column("company",      sa.String(255), nullable=True),
        sa.Column("role",         sa.String(255), nullable=True),
        sa.Column("industry",     sa.String(255), nullable=True),
        sa.Column("links",        postgresql.JSON, nullable=True),
        sa.Column("created_at",   sa.DateTime,    server_default=sa.func.now()),
        sa.Column("updated_at",   sa.DateTime,    server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── persona_records ────────────────────────────────────────────────
    op.create_table(
        "persona_records",
        sa.Column("id",                   postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("target_id",            postgresql.UUID(as_uuid=True), sa.ForeignKey("target_profiles.id"), unique=True, nullable=False),
        sa.Column("formality_level",      sa.String(20),  nullable=True),
        sa.Column("communication_style",  sa.String(500), nullable=True),
        sa.Column("language_hints",       sa.Text,        nullable=True),
        sa.Column("interests",            postgresql.JSON, nullable=True),
        sa.Column("recent_activity",      sa.Text,        nullable=True),
        sa.Column("tone_json",            postgresql.JSON, nullable=True),
        sa.Column("created_at",           sa.DateTime,    server_default=sa.func.now()),
    )

    # ── outreach_runs ──────────────────────────────────────────────────
    op.create_table(
        "outreach_runs",
        sa.Column("id",            postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("target_id",     postgresql.UUID(as_uuid=True), sa.ForeignKey("target_profiles.id"), nullable=False),
        sa.Column("status",        sa.String(30),  server_default="pending"),
        sa.Column("error_message", sa.Text,        nullable=True),
        sa.Column("started_at",    sa.DateTime,    server_default=sa.func.now()),
        sa.Column("completed_at",  sa.DateTime,    nullable=True),
    )

    # ── draft_records ──────────────────────────────────────────────────
    op.create_table(
        "draft_records",
        sa.Column("id",         postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("target_id",  postgresql.UUID(as_uuid=True), sa.ForeignKey("target_profiles.id"),  nullable=False),
        sa.Column("run_id",     postgresql.UUID(as_uuid=True), sa.ForeignKey("outreach_runs.id"),    nullable=False),
        sa.Column("channel",    sa.String(30),  nullable=False),
        sa.Column("subject",    sa.String(255), nullable=True),
        sa.Column("body",       sa.Text,        nullable=False),
        sa.Column("score",      sa.Float,       nullable=True),
        sa.Column("approved",   sa.Boolean,     server_default=sa.text("false")),
        sa.Column("sent",       sa.Boolean,     server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime,    server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("draft_records")
    op.drop_table("outreach_runs")
    op.drop_table("persona_records")
    op.drop_table("target_profiles")
    op.execute("DROP EXTENSION IF EXISTS vector")
