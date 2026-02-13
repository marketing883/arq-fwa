"""Add pipeline_runs table

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-02-13 12:00:00.000000

Records every pipeline execution with config snapshot, stats,
and quality report.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'pipeline_runs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_id', sa.String(64), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=True),
        sa.Column('batch_id', sa.String(64), nullable=False),
        sa.Column('started_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='running'),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('config_snapshot', postgresql.JSONB(), nullable=True),
        sa.Column('stats', postgresql.JSONB(), nullable=True),
        sa.Column('quality_report', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_pipeline_runs_run_id', 'pipeline_runs', ['run_id'], unique=True)
    op.create_index('ix_pipeline_runs_batch_id', 'pipeline_runs', ['batch_id'])


def downgrade() -> None:
    op.drop_index('ix_pipeline_runs_batch_id', table_name='pipeline_runs')
    op.drop_index('ix_pipeline_runs_run_id', table_name='pipeline_runs')
    op.drop_table('pipeline_runs')
