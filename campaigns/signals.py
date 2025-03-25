from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.apps import apps
from .models import SenderId

@receiver(post_save, sender='user.SenderID')
def sync_user_sender_id_to_campaign(sender, instance, created, **kwargs):
    """
    Synchronise un SenderID de l'application user vers l'application campaigns.
    Crée ou met à jour un SenderId correspondant dans l'application campaigns.
    """
    # Récupérer ou créer un SenderId correspondant
    sender_id, created_sender = SenderId.objects.get_or_create(
        user_sender_id=instance,
        defaults={
            'name': instance.name,
            'user': instance.user,
            'status': 'pending'  # Valeur par défaut, sera mise à jour par sync_with_user_sender_id
        }
    )
    
    # Synchronisation des données
    if not created_sender:
        sender_id.sync_with_user_sender_id()

@receiver(post_delete, sender='user.SenderID')
def delete_campaign_sender_id(sender, instance, **kwargs):
    """
    Supprime le SenderId correspondant dans l'application campaigns
    lorsqu'un SenderID est supprimé dans l'application user.
    """
    try:
        # Recherche du SenderId lié
        sender_id = SenderId.objects.get(user_sender_id=instance)
        # Suppression
        sender_id.delete()
    except SenderId.DoesNotExist:
        pass
