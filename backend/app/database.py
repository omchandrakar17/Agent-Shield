import os
from collections.abc import Generator
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.cloud.adapters import get_database_adapter

_db_adapter = get_database_adapter()
DATABASE_URL = os.getenv("AGENTSHIELD_DATABASE_URL") or _db_adapter.get_connection_url()

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=os.getenv("AGENTSHIELD_SQL_ECHO", "false").lower() == "true",
)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _apply_sqlite_patches():
    if not DATABASE_URL.startswith("sqlite"):
        return
    with engine.begin() as conn:
        def has_column(table: str, column: str) -> bool:
            rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            return any(row[1] == column for row in rows)

        def has_fk_on(table: str) -> bool:
            rows = conn.execute(text(f"PRAGMA foreign_key_list({table})")).fetchall()
            return len(rows) > 0

        if has_column("actions", "id") and not has_column("actions", "execution_id"):
            conn.execute(text("ALTER TABLE actions ADD COLUMN execution_id VARCHAR"))
        if has_column("audit_events", "id"):
            if not has_column("audit_events", "payload_hash"):
                conn.execute(text("ALTER TABLE audit_events ADD COLUMN payload_hash VARCHAR"))
            if not has_column("audit_events", "previous_event_hash"):
                conn.execute(text("ALTER TABLE audit_events ADD COLUMN previous_event_hash VARCHAR"))
            if not has_column("audit_events", "event_hash"):
                conn.execute(text("ALTER TABLE audit_events ADD COLUMN event_hash VARCHAR"))
        if has_column("trace_spans", "id"):
            if not has_column("trace_spans", "execution_id"):
                conn.execute(text("ALTER TABLE trace_spans ADD COLUMN execution_id VARCHAR"))
            if has_fk_on("trace_spans"):
                conn.execute(text("""
                    CREATE TABLE trace_spans_new (
                        id VARCHAR NOT NULL PRIMARY KEY,
                        action_id VARCHAR,
                        execution_id VARCHAR,
                        span_name VARCHAR NOT NULL,
                        start_time VARCHAR NOT NULL,
                        end_time VARCHAR NOT NULL,
                        duration_ms FLOAT NOT NULL,
                        status VARCHAR NOT NULL,
                        metadata_json JSON
                    )
                """))
                conn.execute(text("""
                    INSERT INTO trace_spans_new
                    SELECT id, action_id, execution_id, span_name, start_time, end_time, duration_ms, status, metadata_json
                    FROM trace_spans
                """))
                conn.execute(text("DROP TABLE trace_spans"))
                conn.execute(text("ALTER TABLE trace_spans_new RENAME TO trace_spans"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_trace_spans_action_id ON trace_spans (action_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_trace_spans_execution_id ON trace_spans (execution_id)"))

        tenant_columns = {
            "policies": "organization_id",
            "agents": "organization_id",
            "tools": "organization_id",
            "executions": "organization_id",
            "incidents": "organization_id",
            "actions": "organization_id",
            "approvals": "organization_id",
            "audit_events": "organization_id",
        }
        for table, column in tenant_columns.items():
            if has_column(table, "id") and not has_column(table, column):
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} VARCHAR DEFAULT 'org-default'"))

        agent_columns = {
            "description": "TEXT",
            "environment": "VARCHAR DEFAULT 'production'",
            "model_provider": "VARCHAR",
        }
        if has_column("agents", "id"):
            for column, col_type in agent_columns.items():
                if not has_column("agents", column):
                    conn.execute(text(f"ALTER TABLE agents ADD COLUMN {column} {col_type}"))

        tool_columns = {
            "description": "TEXT",
            "owner": "VARCHAR",
            "timeout_seconds": "INTEGER DEFAULT 30",
            "rate_limit_per_minute": "INTEGER",
            "requires_idempotency": "BOOLEAN DEFAULT 0",
            "organization_id": "VARCHAR DEFAULT 'org-default'",
        }
        if has_column("tools", "id"):
            for column, col_type in tool_columns.items():
                if not has_column("tools", column):
                    conn.execute(text(f"ALTER TABLE tools ADD COLUMN {column} {col_type}"))


def init_db():
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _apply_sqlite_patches()
