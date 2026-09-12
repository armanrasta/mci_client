import pytest

from mci_client.client import Client
from mci_client.config import ClusterConfig


@pytest.fixture
def hosts() -> list[str]:
    return [
        "http://node1",
        "http://node2",
        "http://node3",
    ]
    
@pytest.fixture
def config(hosts: list[str]) -> ClusterConfig:
    cfg = ClusterConfig(
        hosts=hosts,
        rounds=3,
        timeout=2.0,
        delay=0.01,
        attempts=2,
        max_retry_time=2.0,
        log_level="INFO",
    )
    return cfg

@pytest.fixture
async def client(config: ClusterConfig):
    c = Client(
        config.timeout,
        config.attempts, 
        max_retry_time=config.max_retry_time
    )
    yield c
    await c.close()
