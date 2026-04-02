"""Shared test fixtures."""

import pytest
from httpx import ASGITransport, AsyncClient

from jsc.main import create_app


@pytest.fixture
def app():
    """Create a test FastAPI application."""
    return create_app()


@pytest.fixture
async def client(app):
    """Async HTTP test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
