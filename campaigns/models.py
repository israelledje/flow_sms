from django.db import models
from django.utils import timezone
from django.conf import settings
from .services import SMSAPIService
from phonenumbers import parse, is_valid_number
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
import re

class SenderId(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente de validation'),
        ('approved', 'Approuvé'),
        ('rejected', 'Rejeté')
    ]
    
    name = models.CharField(max_length=11)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Référence au modèle SenderID de l'application user
    user_sender_id = models.OneToOneField('user.SenderID', on_delete=models.SET_NULL, null=True, blank=True, related_name='campaign_sender_id')
    
    def __str__(self):
        return self.name
    
    def sync_with_user_sender_id(self):
        """Synchronise les données avec le SenderID de l'application user."""
        if self.user_sender_id:
            # Mapping des statuts entre les deux modèles
            status_mapping = {
                'EN_ATTENTE': 'pending',
                'APPROUVE': 'approved',
                'REJETE': 'rejected'
            }
            
            # Mise à jour des champs
            self.name = self.user_sender_id.name
            self.status = status_mapping.get(self.user_sender_id.status, 'pending')
            self.user = self.user_sender_id.user
            
            # Sauvegarder sans appeler sync_with_user_sender_id()
            self._skip_sync = True
            super().save()
            self._skip_sync = False
            
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Si lié à un SenderID de l'app user, synchroniser les données
        # Mais seulement si nous ne sommes pas déjà en train de synchroniser
        if hasattr(self, '_skip_sync') and self._skip_sync:
            # Si _skip_sync est True, nous sommes déjà en train de synchroniser,
            # donc on ne fait rien pour éviter la récursion infinie
            return
            
        if self.user_sender_id:
            self.sync_with_user_sender_id()

class ContactGroup(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']
        unique_together = ['name', 'user']

class Contact(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='contacts')
    phone_number = models.CharField(max_length=20)
    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    groups = models.ManyToManyField('ContactGroup', blank=True, related_name='contacts')
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'phone_number']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.phone_number})"

    @property
    def group_names(self):
        return ", ".join([group.name for group in self.groups.all()])

    def clean(self):
        try:
            # Vérification du format camerounais
            if not self.phone_number or not re.match(r'^237\d{8}$', self.phone_number):
                raise ValidationError({
                    'phone_number': 'Le numéro de téléphone doit être au format camerounais (237 suivi de 8 ou 9 chiffres)'
                })
        except Exception as e:
            raise ValidationError({
                'phone_number': str(e)
            })

class Campaign(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('scheduled', 'Programmé'),
        ('sending', 'En cours d\'envoi'),
        ('sent', 'Envoyé'),
        ('failed', 'Échoué'),
    ]

    name = models.CharField(max_length=200)
    message_content = models.TextField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    sender = models.ForeignKey(SenderId, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    scheduled_date = models.DateTimeField(null=True, blank=True)
    contacts = models.ManyToManyField(Contact, through='Message')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_rich_sms = models.BooleanField(default=False)
    rich_content = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.name

    def send(self):
        if not self.sender or self.sender.status != 'approved':
            raise ValueError("Un Sender ID approuvé est requis pour envoyer la campagne")

        # Préparer la liste des numéros
        phone_numbers = [contact.phone_number for contact in self.contacts.all()]

        # Initialisation du service SMS
        sms_service = SMSAPIService()
        
        # Envoi du SMS
        response = sms_service.send_bulk_sms(
            sender_id=self.sender.name,
            message=self.message_content,
            mobiles=phone_numbers,
            schedule_time=self.scheduled_date
        )
        
        # Traitement de la réponse
        processed_response = sms_service.process_api_response(response)
        
        self.status = 'sent' if processed_response['success'] else 'failed'
        self.save()        

class Message(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('sent', 'Envoyé'),
        ('delivered', 'Livré'),
        ('failed', 'Échoué'),
    ]

    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE)
    content = models.TextField()
    sender = models.ForeignKey(SenderId, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    is_rich_sms = models.BooleanField(default=False)
    rich_content = models.JSONField(null=True, blank=True)
    message_id = models.CharField(max_length=100, null=True, blank=True)
    error_description = models.TextField(null=True, blank=True)

    def send(self):
        try:
            # Vérification du Sender ID
            if not self.sender or self.sender.status != 'approved':
                raise ValueError("Un Sender ID approuvé est requis pour envoyer le message")
            
            # Initialisation du service SMS
            sms_service = SMSAPIService()
            
            # Envoi du SMS
            response = sms_service.send_bulk_sms(
                sender_id=self.sender.name,
                message=self.content,
                mobiles=[self.contact.phone_number],
                schedule_time=self.campaign.scheduled_date if self.campaign.status == 'scheduled' else None
            )
            
            # Traitement de la réponse
            processed_response = sms_service.process_api_response(response)
            
            if processed_response['success']:
                self.status = 'sent'
                self.sent_at = timezone.now()
                if processed_response['message_ids']:
                    self.message_id = processed_response['message_ids'][0]
            else:
                self.status = 'failed'
                self.error_description = processed_response['message']
            
            self.save()
            
        except Exception as e:
            self.status = 'failed'
            self.error_description = str(e)
            self.save()
            raise e

class SMSTemplate(models.Model):
    name = models.CharField(max_length=200)
    content = models.TextField()
    variables = models.JSONField(default=list, help_text="Liste des variables disponibles dans le template")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']