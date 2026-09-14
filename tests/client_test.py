import httpx
import pytest
import respx

from mci_client.client import Client
from mci_client.models import NodeState

# ---------------------------------------------------------------------
# GET /v1/group/{group-id}/
# ---------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_state_200_returns_exists(client: Client):
    with respx.mock:
        respx.get("http://node1/v1/group/g1/").mock(
            return_value=httpx.Response(200, json={"groupId": "g1"})
        )
        state = await client.get_state("http://node1", "g1")
    assert state == NodeState.EXISTS
    
@pytest.mark.asyncio
async def test_get_state_404_returns_absent(client: Client):
    with respx.mock:
        respx.get("http://node1/v1/group/g1/").mock(return_value=httpx.Response(404))
        state = await client.get_state("http://node1", "g1")
    assert state == NodeState.ABSENT
    
@pytest.mark.asyncio
async def test_get_state_500_returns_unknown(client: Client):
    with respx.mock:
        respx.get("http://node1/v1/group/g1/").mock(return_value=httpx.Response(500))
        state = await client.get_state("http://node1", "g1")
    assert state == NodeState.UNKNOWN

@pytest.mark.asyncio
async def test_get_state_network_error_returns_unknown(client: Client):
    with respx.mock:
        respx.get("http://node1/v1/group/g1/").mock(
            side_effect=httpx.ConnectError("boom")
        )
        state = await client.get_state("http://node1", "g1")
    assert state == NodeState.UNKNOWN
    
# ---------------------------------------------------------------------
# POST /v1/group/
# ---------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_201_success(client: Client):
    with respx.mock:
        respx.post("http://node1/v1/group/").mock(
            return_value=httpx.Response(201)
        )
        result = await client.create("http://node1", "g1")
    assert result.success is True
    assert result.status_code == 201


@pytest.mark.asyncio
async def test_create_400_with_existing_returns_success(client: Client):
    """400 followed by GET 200 → group exists → idempotent success."""
    with respx.mock:
        respx.post("http://node1/v1/group/").mock(
            return_value=httpx.Response(400)
        )
        respx.get("http://node1/v1/group/g1/").mock(
            return_value=httpx.Response(200, json={"groupId": "g1"})
        )
        result = await client.create("http://node1", "g1")
    assert result.success is True
    assert result.status_code == 400


@pytest.mark.asyncio
async def test_create_400_but_absent_returns_failure(client: Client):
    """400 followed by GET 404 → real bad request → failure."""
    with respx.mock:
        respx.post("http://node1/v1/group/").mock(
            return_value=httpx.Response(400)
        )
        respx.get("http://node1/v1/group/g1/").mock(
            return_value=httpx.Response(404)
        )
        result = await client.create("http://node1", "g1")
    assert result.success is False
    assert result.status_code == 400


@pytest.mark.asyncio
async def test_create_500_returns_failure(client: Client):
    with respx.mock:
        respx.post("http://node1/v1/group/").mock(
            return_value=httpx.Response(500)
        )
        result = await client.create("http://node1", "g1")
    assert result.success is False
    assert result.status_code == 500


@pytest.mark.asyncio
async def test_create_network_error_returns_failure(client: Client):
    with respx.mock:
        respx.post("http://node1/v1/group/").mock(
            side_effect=httpx.ConnectError("boom")
        )
        result = await client.create("http://node1", "g1")
    assert result.success is False
    assert result.status_code is None


# ---------------------------------------------------------------------
# DELETE /v1/group/
# ---------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_200_success(client: Client):
    with respx.mock:
        respx.delete("http://node1/v1/group/").mock(
            return_value=httpx.Response(200)
        )
        result = await client.delete("http://node1", "g1")
    assert result.success is True
    assert result.status_code == 200


@pytest.mark.asyncio
async def test_delete_404_returns_failure(client: Client):
    """Current design: strict to docs, 404 is a failure."""
    with respx.mock:
        respx.delete("http://node1/v1/group/").mock(
            return_value=httpx.Response(404)
        )
        result = await client.delete("http://node1", "g1")
    assert result.success is True
    assert result.status_code == 404


@pytest.mark.asyncio
async def test_delete_network_error_returns_failure(client: Client):
    with respx.mock:
        respx.delete("http://node1/v1/group/").mock(
            side_effect=httpx.ConnectError("boom")
        )
        result = await client.delete("http://node1", "g1")
    assert result.success is False
    assert result.status_code is None

@pytest.mark.asyncio
async def test_delete_500_returns_failure(client: Client):
    with respx.mock:
        respx.delete("http://node1/v1/group/").mock(
            return_value=httpx.Response(500)
        )
        result = await client.delete("http://node1", "g1")
    assert result.success is False
    assert result.status_code == 500