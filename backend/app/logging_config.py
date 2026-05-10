import logging

from rich.logging import RichHandler


def setup_logging(level: int = logging.INFO) -> None:
    handler = RichHandler(
        level=level,
        show_time=True,
        show_level=True,
        show_path=False,
        markup=True,
        rich_tracebacks=True,
        tracebacks_show_locals=False,
    )
    handler.setFormatter(logging.Formatter("%(message)s", datefmt="[%H:%M:%S]"))

    logging.basicConfig(level=level, handlers=[handler], force=True)

    # Suppress noisy external loggers that add no value at INFO level
    for noisy in ("httpx", "httpcore", "asyncio", "uvicorn.access", "litellm"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
