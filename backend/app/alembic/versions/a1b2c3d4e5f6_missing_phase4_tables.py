"""missing phase 4 tables

Revision ID: a1b2c3d4e5f6
Revises: 516e504ca564
Create Date: 2026-04-30 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '516e504ca564'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. drift_history
    op.create_table(
        'drift_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.String(length=256), nullable=False),
        sa.Column('field', sa.String(length=64), nullable=False),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_drift_history_id'), 'drift_history', ['id'], unique=False)
    op.create_index(op.f('ix_drift_history_resource_id'), 'drift_history', ['resource_id'], unique=False)

    # 2. cost_records
    op.create_table(
        'cost_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.String(length=256), nullable=False),
        sa.Column('service', sa.String(length=64), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False),
        sa.Column('original_currency', sa.String(length=10), nullable=True),
        sa.Column('exchange_rate', sa.Float(), nullable=False),
        sa.Column('normalized_usd', sa.Float(), nullable=False),
        sa.Column('date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('tags', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cost_records_id'), 'cost_records', ['id'], unique=False)
    op.create_index(op.f('ix_cost_records_tenant_id'), 'cost_records', ['tenant_id'], unique=False)
    op.create_index('ix_cost_records_resource_date', 'cost_records', ['resource_id', 'date'], unique=False)
    op.create_index('ix_cost_records_tenant_date', 'cost_records', ['tenant_id', 'date'], unique=False)

    # 3. budget_alerts
    op.create_table(
        'budget_alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('threshold', sa.Float(), nullable=False),
        sa.Column('current_spend', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('last_triggered', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_budget_alerts_id'), 'budget_alerts', ['id'], unique=False)
    op.create_index(op.f('ix_budget_alerts_tenant_id'), 'budget_alerts', ['tenant_id'], unique=False)

    # 4. cost_recommendations
    op.create_table(
        'cost_recommendations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.String(length=256), nullable=False),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('recommendation_type', sa.String(length=64), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('potential_savings', sa.Float(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('forecast_7d', sa.Float(), nullable=False),
        sa.Column('forecast_30d', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cost_recommendations_id'), 'cost_recommendations', ['id'], unique=False)
    op.create_index(op.f('ix_cost_recommendations_tenant_id'), 'cost_recommendations', ['tenant_id'], unique=False)

    # 5. security_findings
    op.create_table(
        'security_findings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.String(length=256), nullable=False),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('finding_type', sa.String(length=128), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('remediation', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('risk_score', sa.Float(), nullable=False),
        sa.Column('impact', sa.String(length=256), nullable=True),
        sa.Column('compliance_id', sa.String(length=64), nullable=True),
        sa.Column('iam_user', sa.String(length=128), nullable=True),
        sa.Column('policy_arn', sa.Text(), nullable=True),
        sa.Column('cross_cloud_correlation_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_security_findings_id'), 'security_findings', ['id'], unique=False)
    op.create_index(op.f('ix_security_findings_tenant_id'), 'security_findings', ['tenant_id'], unique=False)
    op.create_index('ix_security_findings_tenant_severity', 'security_findings', ['tenant_id', 'severity'], unique=False)
    op.create_index('ix_security_findings_provider', 'security_findings', ['tenant_id', 'finding_type'], unique=False)

    # 6. cost_anomalies
    op.create_table(
        'cost_anomalies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.String(length=256), nullable=False),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('service', sa.String(length=64), nullable=False),
        sa.Column('baseline_amount', sa.Float(), nullable=False),
        sa.Column('actual_amount', sa.Float(), nullable=False),
        sa.Column('deviation_pct', sa.Float(), nullable=False),
        sa.Column('anomaly_type', sa.String(length=32), nullable=False),
        sa.Column('risk_score', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cost_anomalies_id'), 'cost_anomalies', ['id'], unique=False)
    op.create_index(op.f('ix_cost_anomalies_tenant_id'), 'cost_anomalies', ['tenant_id'], unique=False)
    op.create_index('ix_cost_anomalies_tenant_status', 'cost_anomalies', ['tenant_id', 'status'], unique=False)
    op.create_index('ix_cost_anomalies_provider', 'cost_anomalies', ['tenant_id', 'provider'], unique=False)

    # 7. incidents
    op.create_table(
        'incidents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=256), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('source_types', sa.JSON(), nullable=False),
        sa.Column('correlated_event_ids', sa.JSON(), nullable=False),
        sa.Column('affected_resources', sa.JSON(), nullable=False),
        sa.Column('timeline', sa.JSON(), nullable=False),
        sa.Column('rule_matched', sa.String(length=128), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_incidents_id'), 'incidents', ['id'], unique=False)
    op.create_index(op.f('ix_incidents_tenant_id'), 'incidents', ['tenant_id'], unique=False)
    op.create_index('ix_incidents_tenant_status', 'incidents', ['tenant_id', 'status'], unique=False)
    op.create_index('ix_incidents_severity', 'incidents', ['tenant_id', 'severity'], unique=False)

    # 8. remediation_plans
    op.create_table(
        'remediation_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.String(length=256), nullable=False),
        sa.Column('action_type', sa.String(length=64), nullable=False),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('dry_run_result', sa.JSON(), nullable=False),
        sa.Column('actual_result', sa.JSON(), nullable=False),
        sa.Column('rollback_snapshot', sa.JSON(), nullable=False),
        sa.Column('blast_radius_analysis', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('idempotency_key', sa.String(length=64), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.Column('approved_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('idempotency_key', name='uq_remediation_idempotency')
    )
    op.create_index(op.f('ix_remediation_plans_id'), 'remediation_plans', ['id'], unique=False)
    op.create_index(op.f('ix_remediation_plans_tenant_id'), 'remediation_plans', ['tenant_id'], unique=False)
    op.create_index('ix_remediation_plans_tenant_status', 'remediation_plans', ['tenant_id', 'status'], unique=False)


def downgrade() -> None:
    op.drop_table('remediation_plans')
    op.drop_table('incidents')
    op.drop_table('cost_anomalies')
    op.drop_table('security_findings')
    op.drop_table('cost_recommendations')
    op.drop_table('budget_alerts')
    op.drop_table('cost_records')
    op.drop_table('drift_history')
