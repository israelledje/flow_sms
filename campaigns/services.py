import requests
import json
from django.conf import settings
from datetime import datetime
from typing import List, Dict, Any

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
    
    def process_api_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Traite la réponse de l'API pour extraire les informations importantes.
        
        Args:
            response (Dict[str, Any]): Réponse de l'API
            
        Returns:
            Dict[str, Any]: Informations traitées
        """
        if response.get("responsecode") != 1:
            return {
                "success": False,
                "message": response.get("responsemessage", "Erreur inconnue"),
                "sent_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "message_ids": [],
                "errors": [],
                "balance": 0
            }
            
        sent_messages = response.get("sms", [])
        success_count = sum(1 for msg in sent_messages if msg.get("status") == "success")
        
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
            "balance": sent_messages[0].get("balance", 0) if sent_messages else 0
        }
