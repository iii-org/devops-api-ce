from celery.schedules import crontab

# https://docs.celeryq.dev/en/v5.2.7/userguide/configuration.html#configuration
# https://github.com/miguelgrinberg/Flask-SocketIO/issues/361

"""
beat: celery -A apis.api.celery beat --loglevel=INFO --schedule=/tmp/celerybeat-schedule
worker: celery -A apis.api:celery worker -P eventlet --loglevel=INFO
"""


imports = ["apis.celerys.beat"]

accept_content = ["json", "yaml"]
# CELERY_TASK_SERIALIZER = "json"
result_serializer = "json"

beat_schedule = {
    "test-celery": {
        "task": "apis.celerys.beat.sync_redmine",
        # Every minute
        "schedule": crontab(minute="*"),
    }
}


celery_config = {
    "imports": ["apis.celerys.beat"],
    "accept_content": ["json", "yaml"],
    "result_serializer": "json",
    "beat_schedule": {
        "sync_redmine": {
            "task": "apis.celerys.beat.sync_redmine",
            # Every minute
            "schedule": crontab(minute="0"),
        }
    },
}
