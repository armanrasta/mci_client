from mci_client.config import ClusterConfig
from mci_client.logger import setup_logging


async def main():
    cfg = ClusterConfig()
    setup_logging(cfg.log_level)