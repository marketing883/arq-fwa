"""Add TAO, CAPC, and ODA-RAG methodology tables

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-02-12 18:00:00.000000

11 new tables for patent-pending methodologies:
  TAO (6): lineage_node, lineage_edge, capability_token,
           agent_trust_profile, hitl_request, audit_receipt
  CAPC (2): compliance_ir_record, evidence_packet
  ODA-RAG (3): rag_signal, adaptation_event, rag_feedback
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── TAO: Lineage Graph ───────────────────────────────────────────────

    op.create_table(
        'lineage_node',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('node_id', sa.String(length=36), nullable=False),
        sa.Column('node_type', sa.String(length=30), nullable=False),
        sa.Column('agent_id', sa.String(length=100), nullable=False),
        sa.Column('action', sa.String(length=500), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('trust_score_at_action', sa.Float(), nullable=True),
        sa.Column('capability_token_id', sa.String(length=36), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('workspace_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_lineage_node_node_id', 'lineage_node', ['node_id'], unique=True)
    op.create_index('ix_lineage_node_node_type', 'lineage_node', ['node_type'])
    op.create_index('ix_lineage_node_agent_id', 'lineage_node', ['agent_id'])
    op.create_index('ix_lineage_node_workspace_id', 'lineage_node', ['workspace_id'])
    op.create_index('ix_lineage_node_created_at', 'lineage_node', ['created_at'])
    op.create_index('ix_lineage_node_agent_created', 'lineage_node', ['agent_id', 'created_at'])

    op.create_table(
        'lineage_edge',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_node_id', sa.String(length=36), nullable=False),
        sa.Column('target_node_id', sa.String(length=36), nullable=False),
        sa.Column('relationship', sa.String(length=30), nullable=False),
        sa.Column('data_hash', sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_lineage_edge_source', 'lineage_edge', ['source_node_id'])
    op.create_index('ix_lineage_edge_target', 'lineage_edge', ['target_node_id'])
    op.create_index('ix_lineage_edge_source_target', 'lineage_edge', ['source_node_id', 'target_node_id'])

    # ── TAO: Capability Tokens ───────────────────────────────────────────

    op.create_table(
        'capability_token',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token_id', sa.String(length=36), nullable=False),
        sa.Column('issuer', sa.String(length=100), nullable=False),
        sa.Column('subject_agent_id', sa.String(length=100), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_scope', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('constraints', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('issued_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('max_uses', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('uses_remaining', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('parent_token_id', sa.String(length=36), nullable=True),
        sa.Column('revoked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('signature', sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_capability_token_token_id', 'capability_token', ['token_id'], unique=True)
    op.create_index('ix_capability_token_agent', 'capability_token', ['subject_agent_id'])

    # ── TAO: Agent Trust Profiles ────────────────────────────────────────

    op.create_table(
        'agent_trust_profile',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.String(length=100), nullable=False),
        sa.Column('trust_score', sa.Float(), nullable=False, server_default='0.7'),
        sa.Column('initial_trust', sa.Float(), nullable=False, server_default='0.7'),
        sa.Column('decay_model', sa.String(length=20), nullable=False, server_default="'exponential'"),
        sa.Column('decay_rate', sa.Float(), nullable=False, server_default='0.01'),
        sa.Column('escalation_level', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('escalation_reason', sa.String(length=500), nullable=True),
        sa.Column('last_successful_action', sa.DateTime(), nullable=True),
        sa.Column('last_trust_update', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('trust_history', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agent_trust_profile_agent_id', 'agent_trust_profile', ['agent_id'], unique=True)

    # ── TAO: HITL Requests ───────────────────────────────────────────────

    op.create_table(
        'hitl_request',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.String(length=36), nullable=False),
        sa.Column('agent_id', sa.String(length=100), nullable=False),
        sa.Column('requested_action', sa.String(length=100), nullable=False),
        sa.Column('resource_scope', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('action_risk_score', sa.Float(), nullable=False),
        sa.Column('risk_tier', sa.String(length=20), nullable=False),
        sa.Column('agent_trust_score', sa.Float(), nullable=False),
        sa.Column('justification', sa.Text(), nullable=False),
        sa.Column('contributing_factors', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('context', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default="'pending'"),
        sa.Column('reviewer', sa.String(length=100), nullable=True),
        sa.Column('reviewer_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_hitl_request_request_id', 'hitl_request', ['request_id'], unique=True)
    op.create_index('ix_hitl_request_agent_id', 'hitl_request', ['agent_id'])
    op.create_index('ix_hitl_request_status', 'hitl_request', ['status'])

    # ── TAO: Audit Receipts ──────────────────────────────────────────────

    op.create_table(
        'audit_receipt',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('receipt_id', sa.String(length=36), nullable=False),
        sa.Column('lineage_node_id', sa.String(length=36), nullable=True),
        sa.Column('action_type', sa.String(length=100), nullable=False),
        sa.Column('agent_id', sa.String(length=100), nullable=False),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('input_data_hash', sa.String(length=64), nullable=True),
        sa.Column('output_data_hash', sa.String(length=64), nullable=True),
        sa.Column('output_summary', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('capability_token_id', sa.String(length=36), nullable=True),
        sa.Column('token_scope_snapshot', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('hitl_request_id', sa.String(length=36), nullable=True),
        sa.Column('action_risk_score', sa.Float(), nullable=True),
        sa.Column('agent_trust_score', sa.Float(), nullable=True),
        sa.Column('evidence', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('previous_receipt_hash', sa.String(length=64), nullable=True),
        sa.Column('receipt_hash', sa.String(length=64), nullable=False),
        sa.Column('signature', sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_audit_receipt_receipt_id', 'audit_receipt', ['receipt_id'], unique=True)
    op.create_index('ix_audit_receipt_lineage_node_id', 'audit_receipt', ['lineage_node_id'])
    op.create_index('ix_audit_receipt_agent_id', 'audit_receipt', ['agent_id'])

    # ── CAPC: Compliance IR Records ──────────────────────────────────────

    op.create_table(
        'compliance_ir_record',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ir_id', sa.String(length=36), nullable=False),
        sa.Column('original_request', sa.Text(), nullable=False),
        sa.Column('parsed_intents', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('parsed_entities', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('sensitivity_level', sa.String(length=30), nullable=False),
        sa.Column('opcodes', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('edges', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('validation_status', sa.String(length=20), nullable=False, server_default="'pending'"),
        sa.Column('validation_errors', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('runtime_checks_attached', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('agent_id', sa.String(length=100), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_compliance_ir_record_ir_id', 'compliance_ir_record', ['ir_id'], unique=True)
    op.create_index('ix_compliance_ir_record_agent_id', 'compliance_ir_record', ['agent_id'])

    # ── CAPC: Evidence Packets ───────────────────────────────────────────

    op.create_table(
        'evidence_packet',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('packet_id', sa.String(length=36), nullable=False),
        sa.Column('ir_id', sa.String(length=36), nullable=True),
        sa.Column('original_request', sa.Text(), nullable=False),
        sa.Column('compiled_ir', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('policy_decisions', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('preconditions', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('approvals', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('lineage_hashes', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('model_tool_versions', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('results', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('exception_action', sa.String(length=30), nullable=True),
        sa.Column('previous_packet_hash', sa.String(length=64), nullable=True),
        sa.Column('packet_hash', sa.String(length=64), nullable=False),
        sa.Column('signature', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_evidence_packet_packet_id', 'evidence_packet', ['packet_id'], unique=True)
    op.create_index('ix_evidence_packet_ir_id', 'evidence_packet', ['ir_id'])

    # ── ODA-RAG: RAG Signals ────────────────────────────────────────────

    op.create_table(
        'rag_signal',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('signal_id', sa.String(length=36), nullable=False),
        sa.Column('signal_type', sa.String(length=30), nullable=False),
        sa.Column('metric_name', sa.String(length=100), nullable=False),
        sa.Column('metric_value', sa.Float(), nullable=False),
        sa.Column('context', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('workspace_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_rag_signal_signal_id', 'rag_signal', ['signal_id'], unique=True)
    op.create_index('ix_rag_signal_signal_type', 'rag_signal', ['signal_type'])
    op.create_index('ix_rag_signal_metric_name', 'rag_signal', ['metric_name'])
    op.create_index('ix_rag_signal_workspace_id', 'rag_signal', ['workspace_id'])
    op.create_index('ix_rag_signal_created_at', 'rag_signal', ['created_at'])

    # ── ODA-RAG: Adaptation Events ──────────────────────────────────────

    op.create_table(
        'adaptation_event',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.String(length=36), nullable=False),
        sa.Column('trigger_signal_ids', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('drift_score', sa.Float(), nullable=True),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('parameters_before', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('parameters_after', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_adaptation_event_event_id', 'adaptation_event', ['event_id'], unique=True)
    op.create_index('ix_adaptation_event_action_type', 'adaptation_event', ['action_type'])

    # ── ODA-RAG: RAG Feedback ───────────────────────────────────────────

    op.create_table(
        'rag_feedback',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('feedback_id', sa.String(length=36), nullable=False),
        sa.Column('session_id', sa.String(length=50), nullable=True),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('response_quality', sa.Float(), nullable=False),
        sa.Column('relevance_score', sa.Float(), nullable=True),
        sa.Column('feedback_source', sa.String(length=30), nullable=False),
        sa.Column('context', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('workspace_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_rag_feedback_feedback_id', 'rag_feedback', ['feedback_id'], unique=True)
    op.create_index('ix_rag_feedback_session_id', 'rag_feedback', ['session_id'])


def downgrade() -> None:
    op.drop_table('rag_feedback')
    op.drop_table('adaptation_event')
    op.drop_table('rag_signal')
    op.drop_table('evidence_packet')
    op.drop_table('compliance_ir_record')
    op.drop_table('audit_receipt')
    op.drop_table('hitl_request')
    op.drop_table('agent_trust_profile')
    op.drop_table('capability_token')
    op.drop_table('lineage_edge')
    op.drop_table('lineage_node')
