import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.app.core.config import get_settings
from api.app.db.base import Base

engine = None
SessionLocal = None
engine_loop_id = None


def get_engine():
    global engine, SessionLocal, engine_loop_id

    current_loop_id = None
    try:
        current_loop_id = id(asyncio.get_running_loop())
    except RuntimeError:
        current_loop_id = None

    if engine is not None and engine_loop_id is not None and current_loop_id is not None and engine_loop_id != current_loop_id:
        try:
            engine.sync_engine.dispose()
        except Exception:
            pass
        engine = None
        SessionLocal = None
        engine_loop_id = None

    if engine is None:
        settings = get_settings()
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        engine_loop_id = current_loop_id

    return engine


def _iter_migration_statements(sql: str) -> list[str]:
    if "--;;" in sql:
        return [statement.strip() for statement in sql.split("--;;") if statement.strip()]

    statements: list[str] = []
    current: list[str] = []
    in_single_quote = False
    in_double_quote = False

    for char in sql:
        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote

        if char == ";" and not in_single_quote and not in_double_quote:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            continue

        current.append(char)

    tail = "".join(current).strip()
    if tail:
        statements.append(tail)

    return statements


async def _ensure_postgres_extensions(connection) -> None:
    if connection.dialect.name != "postgresql":
        return

    # pgvector must exist before ORM-managed tables with VECTOR columns are created.
    await connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector;")


async def _apply_sql_migrations(connection) -> None:
    if connection.dialect.name != "postgresql":
        return

    migration_dir = Path(__file__).resolve().parents[3] / "infra" / "sql"
    if not migration_dir.exists():
        return

    for sql_file in sorted(migration_dir.glob("*.sql")):
        content = sql_file.read_text(encoding="utf-8")
        for statement in _iter_migration_statements(content):
            await connection.exec_driver_sql(statement)


async def init_database() -> None:
    from api.app.models import entities  # noqa: F401

    current_engine = get_engine()
    async with current_engine.begin() as connection:
        await _ensure_postgres_extensions(connection)
        await connection.run_sync(Base.metadata.create_all)
        await _apply_sql_migrations(connection)


async def close_database() -> None:
    global engine, SessionLocal, engine_loop_id

    if engine is not None:
        await engine.dispose()
        engine = None
        SessionLocal = None
        engine_loop_id = None


async def get_db_session() -> AsyncIterator[AsyncSession]:
    if SessionLocal is None:
        get_engine()

    async with SessionLocal() as session:
        yield session
