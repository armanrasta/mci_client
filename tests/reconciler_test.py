import json

import httpx
import pytest
import respx

from mci_client.client import Client
from mci_client.config import ClusterConfig
from mci_client.models import NodeState
from mci_client.reconciler import Reconciler, ReconciliationError


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
    

@pytest.mark.asyncio
async def test_sequential_reconciles_reuse_lock(config: ClusterConfig):
    
    with respx.mock:
        for host in config.hosts:
            respx.get(f"{host}/v1/group/g1/").mock(
                return_value=httpx.Response(status_code=200, json={"groupId": "g1"})
            )
        test_client = Client(
            timeout=config.timeout,
            attempts=config.attempts,
            max_retry_time=config.max_retry_time
        )
        test_reconciler = Reconciler(
            hosts=config.hosts,
            client=test_client,
            max_rounds=config.rounds,
            round_delay=config.delay,
        )
        report1 = await test_reconciler.reconcile("g1", NodeState.EXISTS)
        report2 = await test_reconciler.reconcile("g1", NodeState.EXISTS)
    
    assert report1.converged is True
    assert report2.converged is True
    assert test_reconciler._get_lock("g1") is test_reconciler._get_lock("g1")

@pytest.mark.asyncio
async def test_apply_drift_unknown_target_returns_empty(config: ClusterConfig):
    """_apply_drift should return empty list"""
    with respx.mock:
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
        result = await reconciler._apply_drift(
            drifted_nodes=["http://node1"],
            group_id="g1",
            target_state=NodeState.UNKNOWN,
        )

    assert result == []


@pytest.mark.asyncio
async def test_all_unknown_exhausts_rounds(config: ClusterConfig):

    with respx.mock:
        for host in config.hosts:
            respx.get(f"{host}/v1/group/g1/").mock(
                side_effect=httpx.ConnectError("boom")
            )
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
        with pytest.raises(ReconciliationError):
            await reconciler.reconcile("g1", NodeState.EXISTS)
 

@pytest.mark.asyncio
async def test_delete_failure_raises_without_rollback(config: ClusterConfig):
    
    with respx.mock:
        
        respx.get("http://node1/v1/group/g1/").mock(
            return_value=httpx.Response(200, json={"groupId": "g1"})
        )
        respx.delete("http://node1/v1/group/").mock(return_value=httpx.Response(500))
        respx.get("http://node2/v1/group/g1/").mock(return_value=httpx.Response(404))
        respx.get("http://node3/v1/group/g1/").mock(return_value=httpx.Response(404))
        
        def no_post(request):
            raise AssertionError("rollback POST must not run for delete failure")
        respx.post("http://node1/v1/group/").mock(side_effect=no_post)

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
        with pytest.raises(ReconciliationError):
            await reconciler.reconcile("g1", NodeState.ABSENT)
            

@pytest.mark.asyncio
async def test_reconcile_with_no_record_writer(config: ClusterConfig):

    with respx.mock:
        for host in config.hosts:
            respx.get(f"{host}/v1/group/g1/").mock(
                return_value=httpx.Response(200, json={"groupId": "g1"})
            )
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
            record_writer=None,
        )
        report = await reconciler.reconcile("g1", NodeState.EXISTS)

    assert report.converged is True


@pytest.mark.asyncio
async def test_reconcile_writes_record(config: ClusterConfig, tmp_path):

    from mci_client.recorder import RecordWriter

    path = tmp_path / "records.jsonl"

    with respx.mock:
        for host in config.hosts:
            respx.get(f"{host}/v1/group/g1/").mock(
                return_value=httpx.Response(200, json={"groupId": "g1"})
            )
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
            record_writer=RecordWriter(str(path)),
        )
        await reconciler.reconcile("g1", NodeState.EXISTS)

    lines = path.read_text().strip().splitlines()
    assert len(lines) == 1
    import json
    record = json.loads(lines[0])
    assert record["group_id"] == "g1"
    assert record["converged"] is True
    

@pytest.mark.asyncio
async def test_record_failure_does_not_crash_reconcile(config: ClusterConfig):
    """If the RecordWriter raises, reconcile still completes."""
    class ExplodingWriter:
        def write_record(self, report):
            raise OSError("disk full")

    with respx.mock:
        for host in config.hosts:
            respx.get(f"{host}/v1/group/g1/").mock(
                return_value=httpx.Response(200, json={"groupId": "g1"})
            )
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
            record_writer=ExplodingWriter().write_record, # type: ignore
        )
        report = await reconciler.reconcile("g1", NodeState.EXISTS)

    assert report.converged is True

