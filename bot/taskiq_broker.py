"""TaskIQ broker and scheduler configuration."""

from taskiq import TaskiqScheduler
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
