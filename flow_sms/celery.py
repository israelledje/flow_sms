import os
from celery import Celery
from django.conf import settings

# Définir la variable d'environnement par défaut pour les paramètres Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flow_sms.settings')

# Créer l'instance Celery
app = Celery('flow_sms')

# Charger la configuration depuis l'objet settings de Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Configuration du beat schedule
app.conf.beat_schedule = {
    'check-pending-campaigns': {
        'task': 'campaigns.tasks.schedule_pending_campaigns',
        'schedule': 300.0,  # 5 minutes
    },
    'cleanup-campaigns': {
        'task': 'campaigns.tasks.cleanup_completed_campaigns',
        'schedule': 3600.0,  # 1 heure
    },
}

# Découverte automatique des tâches dans les applications Django
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
