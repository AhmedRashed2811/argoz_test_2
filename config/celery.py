"""Celery app entry point (docs §12). Tasks live in each app's tasks.py and
only call services."""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("argoz")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
