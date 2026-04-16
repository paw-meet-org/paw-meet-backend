import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paw_meet.settings')

app = Celery('paw_meet')
app.config_from_object('django.conf:settings', namespace = 'CELERY')
app.autodiscover_tasks()