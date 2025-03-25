from celery import shared_task
from django.utils import timezone
from .models import Campaign
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

@shared_task
def process_campaign(campaign_id: int):
    """
    Traite une campagne SMS en arrière-plan.
    
    Args:
        campaign_id (int): ID de la campagne à traiter
    """
    try:
        campaign = Campaign.objects.get(id=campaign_id)
        
        # Vérifier si la campagne peut être traitée
        if campaign.status not in [Campaign.Status.SCHEDULED, Campaign.Status.PAUSED]:
            return
            
        # Vérifier la date de début
        if campaign.scheduled_start_date > timezone.now():
            return
            
        # Vérifier la date de fin si elle existe
        if campaign.scheduled_end_date and campaign.scheduled_end_date < timezone.now():
            campaign.status = Campaign.Status.COMPLETED
            campaign.save()
            return
            
        # Mettre à jour le statut
        campaign.status = Campaign.Status.IN_PROGRESS
        campaign.save()
        
        # Calculer le nombre de messages à envoyer dans ce batch
        messages_per_hour = campaign.sending_speed
        batch_size = max(1, messages_per_hour // 6)  # Diviser par 6 pour avoir ~10 minutes entre les batchs
        
        # Récupérer les destinataires qui n'ont pas encore reçu le message
        sent_to = set()
        for msg_id in campaign.message_ids:
            sent_to.update(msg.get('mobileno') for msg in campaign.send_errors if msg.get('mobileno'))
            
        all_recipients = get_campaign_recipients(campaign)
        pending_recipients = [r for r in all_recipients if r not in sent_to]
        
        if not pending_recipients:
            campaign.status = Campaign.Status.COMPLETED
            campaign.save()
            return
            
        # Prendre le prochain batch
        current_batch = pending_recipients[:batch_size]
        
        # Envoyer le batch
        campaign.send_batch(current_batch)
        
        # Reprogrammer la tâche si nécessaire
        if len(pending_recipients) > batch_size:
            process_campaign.apply_async(
                args=[campaign_id],
                countdown=600  # 10 minutes
            )
            
    except Campaign.DoesNotExist:
        return
    except Exception as e:
        # Log l'erreur et mettre la campagne en pause
        campaign.status = Campaign.Status.PAUSED
        campaign.send_errors.append({
            "error_type": "system",
            "error_message": str(e),
            "timestamp": timezone.now().isoformat()
        })
        campaign.save()

def get_campaign_recipients(campaign: Campaign) -> List[str]:
    """
    Récupère la liste complète des destinataires pour une campagne.
    
    Args:
        campaign (Campaign): La campagne
        
    Returns:
        List[str]: Liste des numéros de téléphone
    """
    # TODO: Implémenter la logique pour récupérer les destinataires
    # depuis les groupes cibles et exclure les groupes d'exclusion
    return []

@shared_task
def schedule_pending_campaigns():
    """
    Vérifie et programme les campagnes en attente.
    Cette tâche doit être exécutée périodiquement.
    """
    campaigns = Campaign.objects.filter(
        status=Campaign.Status.SCHEDULED,
        scheduled_start_date__lte=timezone.now()
    )
    
    for campaign in campaigns:
        process_campaign.delay(campaign.id)

@shared_task
def process_scheduled_campaigns():
    """
    Traite les campagnes programmées dont la date d'envoi est arrivée.
    Cette tâche doit être exécutée périodiquement (idéalement toutes les minutes).
    """
    # Récupérer toutes les campagnes programmées dont la date d'envoi est passée
    scheduled_campaigns = Campaign.objects.filter(
        status='scheduled',
        scheduled_date__lte=timezone.now()
    )
    
    for campaign in scheduled_campaigns:
        try:
            # Appeler la méthode send() qui gère la transition des statuts
            campaign.send()
            logger.info(f"Campagne programmée {campaign.id} ({campaign.name}) envoyée avec succès")
        except Exception as e:
            # En cas d'erreur, logger le problème mais continuer avec les autres campagnes
            logger.error(f"Erreur lors de l'envoi de la campagne programmée {campaign.id} ({campaign.name}): {str(e)}")
            # Optionnel: marquer la campagne comme en erreur
            campaign.status = 'failed'
            campaign.save()

@shared_task
def cleanup_completed_campaigns():
    """
    Nettoie les anciennes campagnes terminées.
    Cette tâche doit être exécutée périodiquement.
    """
    # Marquer comme terminées les campagnes dépassant leur date de fin
    Campaign.objects.filter(
        status=Campaign.Status.IN_PROGRESS,
        scheduled_end_date__lt=timezone.now()
    ).update(status=Campaign.Status.COMPLETED)
    
    # TODO: Archivage des anciennes campagnes si nécessaire
