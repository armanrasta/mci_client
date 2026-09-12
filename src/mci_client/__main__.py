from mci_client.logger import setup_logging
from mci_client.config import ClusterConfig

async def main():
    cfg = ClusterConfig()
    setup_logging(cfg.log_level)