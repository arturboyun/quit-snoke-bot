"""TaskIQ broker and scheduler configuration."""

from taskiq import TaskiqEvents, TaskiqScheduler, TaskiqState
from taskiq_redis import ListQueueBroker, ListRedisScheduleSource

from bot.config import settings

broker = ListQueueBroker(url=settings.redis_url)

schedule_source = ListRedisScheduleSource(
    url=settings.redis_url,
    prefix="quit_smoke:schedules",
)

scheduler = TaskiqScheduler(
    broker=broker,
    sources=[schedule_source],
)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _worker_startup(state: TaskiqState) -> None:
    await schedule_source.startup()


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _worker_shutdown(state: TaskiqState) -> None:
    await schedule_source.shutdown()
