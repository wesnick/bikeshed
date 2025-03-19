import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_index(client: AsyncClient):
    """Test that the index page returns a 200 status code"""
    response = await client.get("/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_settings_component(client: AsyncClient):
    """Test that the settings component returns a 200 status code"""
    response = await client.get("/settings", headers={"HX-Request": "true"})
    assert response.status_code == 200

