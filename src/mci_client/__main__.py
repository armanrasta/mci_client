import asyncio
import sys

import structlog

from mci_client.client import Client
from mci_client.config import ClusterConfig
from mci_client.logger import setup_logging
from mci_client.models import NodeState
from mci_client.reconciler import Reconciler

logger = structlog.get_logger(__name__)


async def run(command: str, group_id: str, cfg: ClusterConfig) -> None:
    client = Client(
        timeout=cfg.timeout,
        attempts=cfg.attempts,
        max_retry_time=cfg.max_retry_time,
    )
    reconciler = Reconciler(
        hosts=cfg.hosts,
        client=client,
        max_rounds=cfg.rounds,
        round_delay=cfg.delay,
    )

    target = NodeState.EXISTS if command == "create" else NodeState.ABSENT

    try:
        report = await reconciler.reconcile(group_id, target)
        logger.info(
            "done",
            group_id=group_id,
            action=command,
            used_rounds=report.used_rounds,
            converged=report.converged,
        )
    finally:
        await reconciler.close()


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in ("create", "delete"):
        print("usage: python -m mci_client <create|delete> <group_id>")
        return 1

    command, group_id = sys.argv[1], sys.argv[2]
    cfg = ClusterConfig() # type: ignore[call-arg]
    setup_logging(cfg.log_level)

    logger = structlog.get_logger(__name__)
    logger.info("cli_started", command=command, group_id=group_id)

    try:
        asyncio.run(run(command, group_id, cfg))
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.error("cli_failed", error=str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())