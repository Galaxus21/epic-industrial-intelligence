"""
Test configuration — seeds PostgreSQL from demo_data before any tests run.
All async tests share one session-scoped event loop to avoid asyncpg cross-loop errors.
"""
import asyncio
import pytest
import pytest_asyncio


@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop — all async tests share one loop."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def seed_test_db(event_loop):
    """Seed the DB with demo data once before all tests."""
    from app.services.seed import seed_db_from_demo
    await seed_db_from_demo()
