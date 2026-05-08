import asyncio
import logging
from typing import Coroutine, Callable

logger = logging.getLogger(__name__)

async def supervise_task(task_name: str, task_func: Callable[[], Coroutine], restart_delay: int = 5):
    """
    Supervises a background task and restarts it if it crashes.
    """
    while True:
        logger.info(f"[Supervisor] Starting background task: {task_name}")
        try:
            await task_func()
        except asyncio.CancelledError:
            logger.info(f"[Supervisor] Task {task_name} cancelled. Stopping supervisor.")
            break
        except Exception as e:
            logger.error(f"[Supervisor] Task {task_name} crashed with error: {e}. Restarting in {restart_delay}s...")
            await asyncio.sleep(restart_delay)
        else:
            logger.warning(f"[Supervisor] Task {task_name} completed unexpectedly. Restarting in {restart_delay}s...")
            await asyncio.sleep(restart_delay)
