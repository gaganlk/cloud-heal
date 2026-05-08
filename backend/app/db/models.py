"""
Production-grade SQLAlchemy models for the AIOps platform.
Changes from v1:
  - Added tenant_id to all user-owned tables (multi-tenancy Phase 9)
  - Added UniqueConstraint on (credential_id, resource_id) — prevents duplicate resources on rescan
  - Added role field to User — required by RBAC middleware
  - Added idempotency_key to HealingAction — prevents duplicate healing from Kafka redelivery
  - Added trace_id to EventLog — correlates with OpenTelemetry spans
  - MetricHistory: resource_id FK stays as integer for TimescaleDB compatibility
"""
from sqlalchemy import (
    Integer, String, Boolean, ForeignKey, DateTime, Text, Float, JSON,
    UniqueConstraint, Index, UUID,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from .database import Base
from typing import List, Optional
from datetime import datetime



class Tenant(Base):
    """
    Enterprise account/organization container.
    Users and resources belong to a specific tenant.
    """
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    subscription_tier: Mapped[str] = mapped_column(String(32), default="standard", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    users: Mapped[List["User"]] = relationship("User", back_populates="tenant")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # RBAC role — viewer | operator | admin
    role: Mapped[str] = mapped_column(String(20), default="operator", nullable=False)
    # OTP & Verification
    otp_code: Mapped[Optional[str]] = mapped_column(String(6), nullable=True)
    otp_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    credentials: Mapped[List["CloudCredential"]] = relationship(
        "CloudCredential", back_populates="user", cascade="all, delete-orphan"
    )
    healing_actions: Mapped[List["HealingAction"]] = relationship(
        "HealingAction", back_populates="user", cascade="all, delete-orphan", foreign_keys="[HealingAction.user_id]"
    )
    approved_actions: Mapped[List["HealingAction"]] = relationship(
        "HealingAction", back_populates="approver", foreign_keys="[HealingAction.approved_by_id]"
    )
    event_logs: Mapped[List["EventLog"]] = relationship(
        "EventLog", back_populates="user", cascade="all, delete-orphan"
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan"
    )
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(20), default="info", nullable=False)  # info|success|warning|error
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    link: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="notifications")

    __table_args__ = (
        Index("ix_notifications_user_unread", "user_id", "is_read"),
    )


class CloudCredential(Base):
    __tablename__ = "cloud_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)   # aws | gcp | azure
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # Fernet-encrypted JSON blob — never stored in plaintext
    encrypted_data: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_scan: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    scan_status: Mapped[str] = mapped_column(String(20), default="never", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="credentials")
    resources: Mapped[List["CloudResource"]] = relationship(
        "CloudResource", back_populates="credential", cascade="all, delete-orphan"
    )
    graph_edges: Mapped[List["GraphEdge"]] = relationship(
        "GraphEdge", back_populates="credential", cascade="all, delete-orphan"
    )


class CloudResource(Base):
    __tablename__ = "cloud_resources"
    __table_args__ = (
        # Prevents duplicate resources on repeated scans per tenant
        UniqueConstraint("tenant_id", "credential_id", "resource_id", name="uq_tenant_cred_resource"),
        Index("ix_cloud_resources_tenant_status", "tenant_id", "status"),
        Index("ix_cloud_resources_provider", "provider"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    credential_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cloud_credentials.id", ondelete="CASCADE"), nullable=False
    )
    resource_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    region: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    tags: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    extra_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # Metrics — latest values; historical data goes to MetricHistory
    cpu_usage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    memory_usage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    network_usage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    credential: Mapped["CloudCredential"] = relationship("CloudCredential", back_populates="resources")
    metric_history: Mapped[List["MetricHistory"]] = relationship(
        "MetricHistory", back_populates="resource", cascade="all, delete-orphan"
    )


class GraphEdge(Base):
    __tablename__ = "graph_edges"
    __table_args__ = (
        UniqueConstraint("credential_id", "source_id", "target_id", "edge_type", name="uq_graph_edge"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    credential_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cloud_credentials.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    edge_type: Mapped[str] = mapped_column(String(64), default="depends_on", nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    credential: Mapped["CloudCredential"] = relationship("CloudCredential", back_populates="graph_edges")


class HealingAction(Base):
    __tablename__ = "healing_actions"
    __table_args__ = (
        # Prevents duplicate healing from Kafka at-least-once redelivery
        UniqueConstraint("idempotency_key", name="uq_healing_idempotency"),
        Index("ix_healing_actions_tenant_status", "tenant_id", "status"),
        Index("ix_healing_actions_resource", "resource_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    resource_id: Mapped[str] = mapped_column(String(256), nullable=False)
    resource_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    auto_triggered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Phase 2: Human-in-the-Loop Approvals
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    
    # SHA256 of (resource_id + action_type + trigger_event_id) for idempotency
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Links back to OpenTelemetry trace for full request tracing
    trace_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="healing_actions", foreign_keys=[user_id])
    approver: Mapped[Optional["User"]] = relationship("User", back_populates="approved_actions", foreign_keys=[approved_by_id])


class EventLog(Base):
    __tablename__ = "event_logs"
    __table_args__ = (
        Index("ix_event_logs_tenant_severity", "tenant_id", "severity"),
        Index("ix_event_logs_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="info", nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, index=True)
    extra_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # OTel trace ID for correlation with distributed traces
    trace_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="event_logs")


class MetricHistory(Base):
    """
    Time-series table for resource metrics.
    In production: run  SELECT create_hypertable('metric_history', 'timestamp');
    after table creation to enable TimescaleDB automatic time-partitioning.
    """
    __tablename__ = "metric_history"
    __table_args__ = (
        Index("ix_metric_history_resource_ts", "resource_id", "timestamp"),
        Index("ix_metric_history_type_ts", "metric_type", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    resource_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cloud_resources.id", ondelete="CASCADE"), nullable=False
    )
    metric_type: Mapped[str] = mapped_column(String(32), nullable=False)  # cpu|memory|network|disk_io|latency
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="percent", nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    resource: Mapped["CloudResource"] = relationship("CloudResource", back_populates="metric_history")


class DesiredState(Base):
    """
    Drift detection baselines.
    Stores the 'known good' state of a resource.
    """
    __tablename__ = "desired_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    resource_id: Mapped[str] = mapped_column(String(256), nullable=False, unique=True, index=True)
    desired_state: Mapped[dict] = mapped_column(JSON, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DriftHistory(Base):
    """
    Historical log of configuration drift events.
    """
    __tablename__ = "drift_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    resource_id: Mapped[str] = mapped_column(String(256), index=True, nullable=False)
    field: Mapped[str] = mapped_column(String(64), nullable=False)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )



class CostRecord(Base):
    """
    Historical cost data for cloud resources.
    Aggregated from Cost Explorer / Billing APIs.
    """
    __tablename__ = "cost_records"
    __table_args__ = (
        Index("ix_cost_records_resource_date", "resource_id", "date"),
        Index("ix_cost_records_tenant_date", "tenant_id", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    resource_id: Mapped[str] = mapped_column(String(256), nullable=False)
    service: Mapped[str] = mapped_column(String(64), nullable=False) # ec2, s3, etc.
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    # Phase 4: currency normalisation
    original_currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    exchange_rate: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    normalized_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    tags: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BudgetAlert(Base):
    """
    Budget thresholds and alerts.
    """
    __tablename__ = "budget_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    current_spend: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_triggered: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CostRecommendation(Base):
    """
    Rightsizing and cost-saving recommendations.
    Phase 4: added provider, confidence_score, forecast fields.
    """
    __tablename__ = "cost_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    resource_id: Mapped[str] = mapped_column(String(256), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), default="aws", nullable=False)
    recommendation_type: Mapped[str] = mapped_column(String(64), nullable=False) # rightsize, idle, terminate
    description: Mapped[str] = mapped_column(Text, nullable=False)
    potential_savings: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)  # 0-1
    forecast_7d: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    forecast_30d: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False) # pending, applied, dismissed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SecurityFinding(Base):
    """
    Security misconfigurations and vulnerabilities.
    Phase 4: added IAM context and cross-cloud correlation.
    """
    __tablename__ = "security_findings"
    __table_args__ = (
        Index("ix_security_findings_tenant_severity", "tenant_id", "severity"),
        Index("ix_security_findings_provider", "tenant_id", "finding_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    resource_id: Mapped[str] = mapped_column(String(256), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), default="aws", nullable=False)
    finding_type: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False) # critical, high, medium, low
    description: Mapped[str] = mapped_column(Text, nullable=False)
    remediation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    # Compliance
    risk_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    impact: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    compliance_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # IAM / identity context
    iam_user: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    policy_arn: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Cross-cloud correlation
    cross_cloud_correlation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


# ── Phase 4 New Tables ─────────────────────────────────────────────────────────

class CostAnomaly(Base):
    """
    Detected cost anomalies: spikes, idle waste, sustained growth.
    Produced by FinOpsEngine.detect_cost_anomalies().
    """
    __tablename__ = "cost_anomalies"
    __table_args__ = (
        Index("ix_cost_anomalies_tenant_status", "tenant_id", "status"),
        Index("ix_cost_anomalies_provider", "tenant_id", "provider"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    resource_id: Mapped[str] = mapped_column(String(256), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    service: Mapped[str] = mapped_column(String(64), nullable=False)
    baseline_amount: Mapped[float] = mapped_column(Float, nullable=False)
    actual_amount: Mapped[float] = mapped_column(Float, nullable=False)
    deviation_pct: Mapped[float] = mapped_column(Float, nullable=False)   # e.g. 210.5 = 210.5% above baseline
    anomaly_type: Mapped[str] = mapped_column(String(32), nullable=False)  # spike | idle | sustained_growth
    risk_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Incident(Base):
    """
    Correlated security + cost + infra incidents.
    Produced by EventCorrelationEngine when multiple signals align.
    """
    __tablename__ = "incidents"
    __table_args__ = (
        Index("ix_incidents_tenant_status", "tenant_id", "status"),
        Index("ix_incidents_severity", "tenant_id", "severity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    source_types: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)   # ["cost_anomaly", "security_drift"]
    correlated_event_ids: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    affected_resources: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    timeline: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)       # [{ts, event_type, description}]
    rule_matched: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # correlation rule name
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class RemediationPlan(Base):
    """
    Safe auto-remediation execution record.
    Supports dry-run, rollback snapshot, and blast-radius analysis.
    """
    __tablename__ = "remediation_plans"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_remediation_idempotency"),
        Index("ix_remediation_plans_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    resource_id: Mapped[str] = mapped_column(String(256), nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    dry_run_result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    actual_result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    rollback_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    blast_radius_analysis: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # draft | dry_run_complete | approved | executing | complete | failed | rolled_back
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_by_id: Mapped[int] = mapped_column(Integer, nullable=False)
    approved_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
