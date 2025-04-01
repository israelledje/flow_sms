import requests
import json
from django.conf import settings
from datetime import datetime, timedelta
from typing import List, Dict, Any
from django.db.models import Count, Sum, F
from django.db.models.functions import TruncDate

class SMSAPIService:
    API_URL = "https://smsvas.com/bulk/public/index.php/api/v1/sendsms"
    
    def __init__(self):
        self.api_user = settings.SMS_API_USER
        self.api_password = settings.SMS_API_PASSWORD
    
    def send_bulk_sms(
        self,
        sender_id: str,
        message: str,
        mobiles: List[str],
        schedule_time: datetime = None
    ) -> Dict[str, Any]:
        """
        Envoie des SMS en masse via l'API SMSVAS.
        
        Args:
            sender_id (str): ID de l'expéditeur (max 11 caractères)
            message (str): Contenu du message
            mobiles (List[str]): Liste des numéros de téléphone
            schedule_time (datetime, optional): Date et heure d'envoi programmé
            
        Returns:
            Dict[str, Any]: Réponse de l'API
        """
        payload = {
            "user": self.api_user,
            "password": self.api_password,
            "senderid": sender_id,
            "sms": message,
            "mobiles": ",".join(mobiles)
        }
        
        if schedule_time:
            payload["scheduletime"] = schedule_time.strftime("%Y-%m-%d %H:%M")
            
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                self.API_URL,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            return {
                "responsecode": 0,
                "responsedescription": "error",
                "responsemessage": str(e),
                "sms": []
            }
    
    def process_api_response(self, response: Dict[str, Any], campaign=None) -> Dict[str, Any]:
        """
        Traite la réponse de l'API pour extraire les informations importantes et met à jour les statistiques.
        
        Args:
            response (Dict[str, Any]): Réponse de l'API
            campaign: Campagne associée aux messages
            
        Returns:
            Dict[str, Any]: Informations traitées
        """
        from .models import Message  # Import déplacé ici pour éviter l'importation circulaire
        
        if response.get("responsecode") != 1:
            return {
                "success": False,
                "message": response.get("responsemessage", "Erreur inconnue"),
                "sent_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "message_ids": [],
                "errors": [],
                "credits_used": 0
            }
            
        sent_messages = response.get("sms", [])
        success_count = sum(1 for msg in sent_messages if msg.get("status") == "success")
        
        # Calcul du total des crédits utilisés
        total_credits = sum(msg.get("total_sms_unit", 0) for msg in sent_messages)
        
        # Création des messages dans la base de données
        messages_to_create = []
        for msg in sent_messages:
            message = Message(
                message_id=msg.get("messageid"),
                campaign=campaign,
                phone_number=msg.get("mobileno"),
                status=msg.get("status", "error"),
                error_code=msg.get("errorcode"),
                error_description=msg.get("errordescription"),
                credits_used=msg.get("total_sms_unit", 0),
                sent_at=datetime.now()
            )
            messages_to_create.append(message)
        
        # Création en masse des messages
        Message.objects.bulk_create(messages_to_create)
        
        return {
            "success": True,
            "message": response.get("responsemessage"),
            "sent_count": len(sent_messages),
            "success_count": success_count,
            "failure_count": len(sent_messages) - success_count,
            "message_ids": [msg.get("messageid") for msg in sent_messages],
            "errors": [
                {
                    "mobile": msg.get("mobileno"),
                    "error": msg.get("errordescription")
                }
                for msg in sent_messages
                if msg.get("status") != "success"
            ],
            "credits_used": total_credits
        }

    def get_delivery_stats(self, days: int = 30) -> Dict[str, Any]:
        """
        Récupère les statistiques de livraison sur une période donnée.
        
        Args:
            days (int): Nombre de jours pour la période
            
        Returns:
            Dict[str, Any]: Statistiques de livraison
        """
        from .models import Message  # Import déplacé ici pour éviter l'importation circulaire
        
        start_date = datetime.now() - timedelta(days=days)
        
        # Statistiques globales
        total_messages = Message.objects.filter(sent_at__gte=start_date).count()
        delivered_messages = Message.objects.filter(
            sent_at__gte=start_date,
            status="success"
        ).count()
        
        # Statistiques par jour
        daily_stats = Message.objects.filter(
            sent_at__gte=start_date
        ).annotate(
            date=TruncDate('sent_at')
        ).values('date').annotate(
            total=Count('id'),
            delivered=Count('id', filter=F('status') == 'success')
        ).order_by('date')
        
        # Calcul du taux de livraison
        delivery_rate = (delivered_messages / total_messages * 100) if total_messages > 0 else 0
        
        return {
            "total_messages": total_messages,
            "delivered_messages": delivered_messages,
            "delivery_rate": round(delivery_rate, 2),
            "daily_stats": list(daily_stats),
            "period": {
                "start": start_date,
                "end": datetime.now()
            }
        }

    def get_campaign_stats(self, campaign_id: int) -> Dict[str, Any]:
        """
        Récupère les statistiques détaillées d'une campagne.
        
        Args:
            campaign_id (int): ID de la campagne
            
        Returns:
            Dict[str, Any]: Statistiques de la campagne
        """
        from .models import Message  # Import déplacé ici pour éviter l'importation circulaire
        
        messages = Message.objects.filter(campaign_id=campaign_id)
        
        total_messages = messages.count()
        delivered_messages = messages.filter(status="success").count()
        failed_messages = messages.filter(status="error").count()
        
        # Statistiques par jour
        daily_stats = messages.annotate(
            date=TruncDate('sent_at')
        ).values('date').annotate(
            total=Count('id'),
            delivered=Count('id', filter=F('status') == 'success'),
            failed=Count('id', filter=F('status') == 'error')
        ).order_by('date')
        
        # Calcul des taux
        delivery_rate = (delivered_messages / total_messages * 100) if total_messages > 0 else 0
        failure_rate = (failed_messages / total_messages * 100) if total_messages > 0 else 0
        
        return {
            "total_messages": total_messages,
            "delivered_messages": delivered_messages,
            "failed_messages": failed_messages,
            "delivery_rate": round(delivery_rate, 2),
            "failure_rate": round(failure_rate, 2),
            "daily_stats": list(daily_stats)
        }
