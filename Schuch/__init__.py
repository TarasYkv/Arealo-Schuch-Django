# Celery-App einbinden, damit .delay() aus Django-Views funktioniert.
# Ohne diesen Import würde @shared_task auf die Default-App (amqp://localhost//)
# statt unseren konfigurierten Redis-Broker (Schuch.celery) zeigen.
from .celery import app as celery_app

__all__ = ['celery_app']
