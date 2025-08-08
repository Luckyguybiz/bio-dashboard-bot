from .celery_app import celery_app


@celery_app.task
def poll_channels() -> str:
    return "ok"


@celery_app.task
def calc_signals() -> str:
    return "ok"


@celery_app.task
def send_alerts() -> str:
    return "ok"


@celery_app.task
def daily_brief() -> str:
    return "ok"
