import json

import httpx
import pytest
import respx

from mci_client.client import Client
from mci_client.config import ClusterConfig
from mci_client.models import NodeState
from mci_client.reconciler import ReconciliationError, Reconciler


@pytest.mark.asyncio
async def test_rollback_on_partial_create_failure(config: ClusterConfig):
    
    state: dict[str, set[str]] = {h: set() for h in config.hosts}
    deleted: list[str] = []

    def make_get(host: str):
        def handler(request: httpx.Request) -> httpx.Response:
            group_id = request.url.path.strip("/").split("/")[-1]
            if group_id in state[host]:
                return httpx.Response(200, json={"groupId": group_id})
            return httpx.Response(404)
        return handler

    def make_post(host: str):
        def handler(request: httpx.Request) -> httpx.Response:
            if host == "http://node3":
                return httpx.Response(500)
            group_id = json.loads(request.content)["groupId"]
            state[host].add(group_id)
            return httpx.Response(201)
        return handler

    def make_delete(host: str):
        def handler(request: httpx.Request) -> httpx.Response:
            group_id = json.loads(request.content)["groupId"]
            if group_id in state[host]:
                state[host].discard(group_id)
                deleted.append(host)
                return httpx.Response(200)
            return httpx.Response(404)
        return handler

    client = Client(
        timeout=config.timeout,
        attempts=config.attempts,
        max_retry_time=config.max_retry_time,
    )
    reconciler = Reconciler(
        hosts=config.hosts,
        client=client,
        max_rounds=config.rounds,
        round_delay=config.delay,
    )

    with respx.mock:
        for host in config.hosts:
            respx.get(f"{host}/v1/group/g1/").mock(side_effect=make_get(host))
            respx.post(f"{host}/v1/group/").mock(side_effect=make_post(host))
            respx.delete(f"{host}/v1/group/").mock(side_effect=make_delete(host))

        with pytest.raises(ReconciliationError):
            await reconciler.reconcile("g1", NodeState.EXISTS)

    assert "http://node1" in deleted
    assert "http://node2" in deleted
    assert "http://node3" not in deleted
    assert state["http://node1"] == set()
    assert state["http://node2"] == set()