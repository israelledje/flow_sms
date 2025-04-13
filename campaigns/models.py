from django.db import models
from django.utils import timezone
from django.conf import settings
from .services import SMSAPIService
from phonenumbers import parse, is_valid_number
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
import re
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

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
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Le numéro de téléphone doit être au format: '+999999999'. Jusqu'à 15 chiffres autorisés."
    )

    phone_number = models.CharField(validators=[phone_regex], max_length=17)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    groups = models.ManyToManyField(ContactGroup, related_name='contacts', blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['phone_number', 'user']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.phone_number})"

    def clean(self):
        if not self.first_name and not self.last_name:
            raise ValidationError(_("Le prénom ou le nom doit être fourni."))

class Campaign(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('scheduled', 'Programmée'),
        ('active', 'Active'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    message = models.TextField()
    sender_id = models.ForeignKey(SenderId, on_delete=models.SET_NULL, null=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def clean(self):
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError(_("La date de fin doit être postérieure à la date de début."))

    def save(self, *args, **kwargs):
        if self.status == 'active' and not self.start_date:
            self.start_date = timezone.now()
        super().save(*args, **kwargs)

    def send_sms(self, contacts):
        sms_service = SMSAPIService()
        phone_numbers = [contact.phone_number for contact in contacts]
        
        response = sms_service.send_bulk_sms(
            sender_id=self.sender_id.name,
            message=self.message,
            mobiles=phone_numbers,
            schedule_time=self.start_date if self.status == 'scheduled' else None
        )
        
        return sms_service.process_api_response(response, self)

class Message(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('sent', 'Envoyé'),
        ('delivered', 'Livré'),
        ('failed', 'Échoué'),
    ]

    message_id = models.CharField(max_length=100, unique=True)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='messages')
    phone_number = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_code = models.CharField(max_length=50, blank=True)
    error_description = models.TextField(blank=True)
    credits_used = models.IntegerField(default=0)
    sent_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f"Message {self.message_id} - {self.phone_number}"

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


"""





"""