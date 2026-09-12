import httpx
import pytest
import respx

from mci_client.client import Client
from mci_client.models import NodeState


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