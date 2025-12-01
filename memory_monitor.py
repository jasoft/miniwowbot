import sys
import time
import threading
import tracemalloc
import resource

def _rss_mb() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF)
    rss = r.ru_maxrss
    if sys.platform == "darwin":
        return rss / (1024 * 1024)
    return rss / 1024 / 1024

def start_memory_monitor(logger, interval_sec: float = 10.0, enable_tracemalloc: bool = True):
    if enable_tracemalloc and not tracemalloc.is_tracing():
        tracemalloc.start()

    stop_event = threading.Event()

    def _loop():
        while not stop_event.is_set():
            rss_mb = _rss_mb()
            msg = f"内存RSS: {rss_mb:.1f} MB"
            if tracemalloc.is_tracing():
                current, peak = tracemalloc.get_traced_memory()
                msg += f" | Py内存: {current/1024/1024:.1f} MB, 峰值: {peak/1024/1024:.1f} MB"
            logger.info(msg)
            if stop_event.wait(interval_sec):
                break

    t = threading.Thread(target=_loop, name="MemoryMonitor", daemon=True)
    t.start()
    return stop_event
