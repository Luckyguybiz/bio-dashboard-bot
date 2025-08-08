from celery import Celery

from ..core.config import settings

celery_app = Celery("scc", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.timezone = settings.tz
