"""Add users table with seeded demo accounts

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-02-13 14:00:00.000000

Creates the users table for JWT authentication and seeds
five demo accounts (one per role) with bcrypt-hashed passwords.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # Seed demo users — passwords hashed with bcrypt
    # These are generated offline to avoid runtime dependency on passlib during migration.
    # Default passwords: Admin123!, Compliance123!, Investigator123!, Analyst123!, Viewer123!
    from passlib.context import CryptContext
    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

    users = [
        ("admin@thearq.com", ctx.hash("Admin123!"), "Platform Admin", "admin"),
        ("compliance@thearq.com", ctx.hash("Compliance123!"), "Compliance Officer", "compliance"),
        ("investigator@thearq.com", ctx.hash("Investigator123!"), "SIU Investigator", "investigator"),
        ("analyst@thearq.com", ctx.hash("Analyst123!"), "Data Analyst", "analyst"),
        ("viewer@thearq.com", ctx.hash("Viewer123!"), "Executive Viewer", "viewer"),
    ]

    users_table = sa.table(
        "users",
        sa.column("email", sa.String),
        sa.column("password_hash", sa.String),
        sa.column("full_name", sa.String),
        sa.column("role", sa.String),
    )
    op.bulk_insert(users_table, [
        {"email": e, "password_hash": h, "full_name": n, "role": r}
        for e, h, n, r in users
    ])


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
