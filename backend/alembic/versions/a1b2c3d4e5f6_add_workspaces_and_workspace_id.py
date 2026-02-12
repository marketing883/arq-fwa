"""Add workspaces table and workspace_id to all entity tables

Revision ID: a1b2c3d4e5f6
Revises: ffd44c2a326f
Create Date: 2026-02-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'ffd44c2a326f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create workspaces table
    op.create_table(
        'workspaces',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.String(length=32), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('client_name', sa.String(length=100), nullable=True),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('data_source', sa.String(length=20), nullable=False, server_default='upload'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('claim_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id'),
    )
    op.create_index('ix_workspaces_workspace_id', 'workspaces', ['workspace_id'], unique=True)

    # 2. Insert default workspace for existing synthetic data
    op.execute(
        "INSERT INTO workspaces (workspace_id, name, client_name, data_source, status) "
        "VALUES ('ws-default', 'Synthetic Demo', 'ArqAI', 'synthetic', 'active')"
    )

    # 3. Add workspace_id FK to all entity tables (nullable for backward compat)
    tables_with_workspace = [
        'providers', 'pharmacies', 'members',
        'medical_claims', 'pharmacy_claims',
        'risk_scores', 'rule_results', 'investigation_cases',
    ]
    for table in tables_with_workspace:
        op.add_column(table, sa.Column('workspace_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            f'fk_{table}_workspace_id',
            table, 'workspaces',
            ['workspace_id'], ['id'],
        )
        op.create_index(f'ix_{table}_workspace_id', table, ['workspace_id'])

    # 4. Backfill existing rows to default workspace
    for table in tables_with_workspace:
        op.execute(
            f"UPDATE {table} SET workspace_id = "
            f"(SELECT id FROM workspaces WHERE workspace_id = 'ws-default')"
        )


def downgrade() -> None:
    tables_with_workspace = [
        'providers', 'pharmacies', 'members',
        'medical_claims', 'pharmacy_claims',
        'risk_scores', 'rule_results', 'investigation_cases',
    ]
    for table in tables_with_workspace:
        op.drop_index(f'ix_{table}_workspace_id', table_name=table)
        op.drop_constraint(f'fk_{table}_workspace_id', table, type_='foreignkey')
        op.drop_column(table, 'workspace_id')

    op.drop_index('ix_workspaces_workspace_id', table_name='workspaces')
    op.drop_table('workspaces')
