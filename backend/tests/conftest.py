"""Pytest test configuration and fixtures for ComplaintIQ backend."""
import asyncio
from typing import AsyncGenerator
import pytest
import pytest_asyncio
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from sqlalchemy import select, delete

from app.core.config import settings
from app.core import database
from app.models.complaint import Complaint

# Configure engine with NullPool to prevent connection reuse across async event loops in pytest
test_engine = create_async_engine(
    database._make_async_url(settings.database_url),
    poolclass=NullPool,
    echo=False,
)
database.engine = test_engine
database.AsyncSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

from app.main import app

async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with database.AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

app.dependency_overrides[database.get_db] = override_get_db


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provides an httpx AsyncClient connected directly to the FastAPI app via ASGITransport."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture
async def db_session():
    """Provides a transactional database session for testing."""
    async with database.AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def cleanup_test_complaint():
    """Fixture that yields a registration function to record complaint IDs to delete after testing."""
    created_ids = []

    def register(complaint_id: str):
        created_ids.append(complaint_id)
        return complaint_id

    yield register

    if created_ids:
        async with database.AsyncSessionLocal() as session:
            for cid in created_ids:
                try:
                    stmt = delete(Complaint).where(Complaint.id == cid)
                    await session.execute(stmt)
                except Exception:
                    pass
            await session.commit()

