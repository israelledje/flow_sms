from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from campaigns.models import SenderId, Contact, Campaign, Message
from .serializers import SenderIdSerializer, ContactSerializer, MessageSerializer, SMSSerializer
from campaigns.services import SMSAPIService
from django.utils import timezone
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404

class IsOwner(permissions.BasePermission):
    """
    Permission personnalisée pour n'autoriser que le propriétaire d'un objet à le voir/modifier.
    """
    def has_object_permission(self, request, view, obj):
        # Vérifie si l'utilisateur est le propriétaire de l'objet
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return False

class SenderIdViewSet(viewsets.ModelViewSet):
    """
    API endpoint pour gérer les Sender IDs.
    """
    serializer_class = SenderIdSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    
    def get_queryset(self):
        return SenderId.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user, status='pending')

class SMSAPIView(APIView):
    """
    API endpoint pour envoyer des SMS.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = SMSSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            data = serializer.validated_data
            sender_id_name = data['sender_id']
            message_content = data['message']
            phone_numbers = data['phone_numbers']
            schedule_time = data.get('schedule_time')
            
            # Récupération du sender_id
            sender_id = get_object_or_404(SenderId, name=sender_id_name, user=request.user)
            
            # Vérification du statut du sender_id
            if sender_id.status != 'approved':
                return Response(
                    {"error": f"Le Sender ID '{sender_id_name}' n'est pas approuvé. Statut actuel: {sender_id.get_status_display()}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Création d'une campagne
            campaign = Campaign.objects.create(
                name=f"API SMS - {timezone.now().strftime('%Y-%m-%d %H:%M')}",
                message_content=message_content,
                user=request.user,
                sender=sender_id,
                status='draft',
                scheduled_date=schedule_time
            )
            
            # Traitement des contacts et messages
            messages_data = []
            sms_service = SMSAPIService()
            failed_messages = []
            
            for phone_number in phone_numbers:
                # Création ou récupération du contact
                contact, created = Contact.objects.get_or_create(phone_number=phone_number)
                
                # Création du message
                message = Message.objects.create(
                    campaign=campaign,
                    contact=contact,
                    content=message_content,
                    sender=sender_id,
                    status='pending'
                )
                
                try:
                    # Envoi du SMS
                    response = sms_service.send_bulk_sms(
                        sender_id=sender_id.name,
                        message=message_content,
                        mobiles=[phone_number],
                        schedule_time=schedule_time
                    )
                    
                    # Traitement de la réponse
                    processed_response = sms_service.process_api_response(response)
                    
                    if processed_response['success']:
                        message.status = 'sent'
                        message.sent_at = timezone.now()
                        if processed_response['message_ids']:
                            message.message_id = processed_response['message_ids'][0]
                    else:
                        message.status = 'failed'
                        message.error_description = processed_response['message']
                        failed_messages.append({"phone": phone_number, "error": processed_response['message']})
                    
                    message.save()
                    messages_data.append(MessageSerializer(message).data)
                    
                except Exception as e:
                    message.status = 'failed'
                    message.error_description = str(e)
                    message.save()
                    failed_messages.append({"phone": phone_number, "error": str(e)})
            
            # Mise à jour du statut de la campagne
            if not failed_messages:
                campaign.status = 'sent' if not schedule_time or schedule_time <= timezone.now() else 'scheduled'
            else:
                campaign.status = 'failed'
            campaign.save()
            
            response_data = {
                "success": len(failed_messages) == 0,
                "campaign_id": campaign.id,
                "messages_sent": len(phone_numbers) - len(failed_messages),
                "messages_failed": len(failed_messages),
                "failed_messages": failed_messages,
                "messages": messages_data
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ContactViewSet(viewsets.ModelViewSet):
    """
    API endpoint pour gérer les contacts.
    """
    serializer_class = ContactSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Récupère les contacts associés aux campagnes de l'utilisateur
        user_campaigns = Campaign.objects.filter(user=self.request.user)
        contact_ids = Message.objects.filter(campaign__in=user_campaigns).values_list('contact_id', flat=True).distinct()
        return Contact.objects.filter(id__in=contact_ids)
