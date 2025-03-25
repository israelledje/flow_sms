from django.apps import AppConfig


class CampaignsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'campaigns'
    
    def ready(self):
        # Importer les signaux
        import campaigns.signals
