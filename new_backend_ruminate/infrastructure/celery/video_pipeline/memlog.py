# memlog.py
import logging, os, psutil, tracemalloc, contextlib, time, asyncio

logger = logging.getLogger("mem")

_PROCESS = psutil.Process(os.getpid())

def rss_mb() -> float:
    """Current resident set size in MiB."""
    return _PROCESS.memory_info().rss / (1024 * 1024)

@contextlib.asynccontextmanager
async def stage(name: str):
    """Async context manager: log time + memory before/after a stage."""
    start_rss, start = rss_mb(), time.perf_counter()
    logger.info(f"[{name}] ▶ start  | RSS {start_rss:7.1f} MB")
    try:
        yield
    finally:
        end = time.perf_counter()
        end_rss = rss_mb()
        logger.info(
            f"[{name}] ■ done   | RSS {end_rss:7.1f} MB "
            f"(Δ {end_rss-start_rss:+.1f})  t={end-start:5.1f}s"
        )
