from celery.schedules import crontab
import config

# https://docs.celeryq.dev/en/v5.2.7/userguide/configuration.html#configuration
# https://github.com/miguelgrinberg/Flask-SocketIO/issues/361


"""
beat: celery -A apis.api.celery beat -l INFO -s /tmp/celerybeat-schedule
worker: celery -A apis.api:celery worker -P eventlet -l INFO -c 10
"""

celery_config = {
    "broker_url": f"redis://{config.get('REDIS_BASE_URL')}",
    "result_backend": f"redis://{config.get('REDIS_BASE_URL')}",
    "imports": ["apis.celeries.beat"],
    "accept_content": ["json", "yaml"],
    "result_serializer": "json",
    "beat_schedule": {
        "sync_redmine": {
            "task": "sync_redmine",
            "schedule": crontab(minute="0"),
        },
        "sync_project_issue_calculation": {
            "task": "sync_project_issue_calculation",
            "schedule": crontab(minute="1"),
        },
        "sync_project_relation": {
            "task": "sync_project_relation",
            "schedule": crontab(minute="2"),
        },
    },
}
