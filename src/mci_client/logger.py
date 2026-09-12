import logging

import structlog


def setup_logging(level: str) -> None:
    
    logging.basicConfig(format="{msg}s", level=getattr(logging, level.upper()))
    
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(
                fmt="iso",
                utc=False,
            ),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        cache_logger_on_first_use=True,
    )
    