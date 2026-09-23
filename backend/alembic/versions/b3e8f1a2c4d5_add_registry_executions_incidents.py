"""add registry executions incidents

Revision ID: b3e8f1a2c4d5
Revises: 6d9a46c7da96
Create Date: 2026-09-22
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "b3e8f1a2c4d5"
down_revision: Union[str, None] = "6d9a46c7da96"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("owner", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("allowed_tools", sa.JSON(), nullable=False),
        sa.Column("policy_id", sa.String(), nullable=True),
        sa.Column("limits", sa.JSON(), nullable=True),
        sa.Column("last_seen", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "tools",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("endpoint", sa.String(), nullable=False),
        sa.Column("protocol", sa.String(), nullable=False),
        sa.Column("risk_class", sa.String(), nullable=False),
        sa.Column("permission_scope", sa.String(), nullable=False),
        sa.Column("input_schema", sa.JSON(), nullable=False),
        sa.Column("output_schema", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "executions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("user_request", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("tool_call_count", sa.Integer(), nullable=False),
        sa.Column("tool_call_history", sa.JSON(), nullable=True),
        sa.Column("max_tool_calls", sa.Integer(), nullable=False),
        sa.Column("max_execution_seconds", sa.Integer(), nullable=False),
        sa.Column("max_same_tool_repeats", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.String(), nullable=False),
        sa.Column("completed_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_executions_agent_id", "executions", ["agent_id"])
    op.create_index("ix_executions_status", "executions", ["status"])
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("execution_id", sa.String(), nullable=True),
        sa.Column("action_id", sa.String(), nullable=True),
        sa.Column("incident_type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incidents_execution_id", "incidents", ["execution_id"])
    op.create_index("ix_incidents_action_id", "incidents", ["action_id"])
    op.create_index("ix_incidents_incident_type", "incidents", ["incident_type"])
    op.create_index("ix_incidents_created_at", "incidents", ["created_at"])
    with op.batch_alter_table("actions") as batch_op:
        batch_op.add_column(sa.Column("execution_id", sa.String(), nullable=True))
        batch_op.create_index("ix_actions_execution_id", ["execution_id"])
    with op.batch_alter_table("trace_spans") as batch_op:
        batch_op.add_column(sa.Column("execution_id", sa.String(), nullable=True))
        batch_op.alter_column("action_id", existing_type=sa.String(), nullable=True)
        batch_op.create_index("ix_trace_spans_execution_id", ["execution_id"])


def downgrade() -> None:
    with op.batch_alter_table("trace_spans") as batch_op:
        batch_op.drop_index("ix_trace_spans_execution_id")
        batch_op.drop_column("execution_id")
    with op.batch_alter_table("actions") as batch_op:
        batch_op.drop_index("ix_actions_execution_id")
        batch_op.drop_column("execution_id")
    op.drop_table("incidents")
    op.drop_table("executions")
    op.drop_table("tools")
    op.drop_table("agents")
