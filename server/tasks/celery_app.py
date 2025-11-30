# server/tasks/celery_app.py
from celery import Celery
from celery.schedules import crontab
import os

redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

celery = Celery(
    'parking_tasks',
    broker=redis_url,
    backend=redis_url
)

# Scheduled jobs
celery.conf.beat_schedule = {
    'daily-reminder': {
        'task': 'tasks.send_daily_reminder',
        'schedule': 60 * 60 * 24  # every 24 hours
    },
    'monthly-report': {
        'task': 'tasks.monthly_report_task',
        'schedule': crontab(minute=0, hour=5, day_of_month='1')
    }
}

celery.conf.timezone = 'UTC'
